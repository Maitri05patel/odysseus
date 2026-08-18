"""
Booking service — orchestrates DB queries, validation, and pricing.

This module is the only place that touches both the database and the pricing
engine. It enforces all business rules that require DB state (capacity,
promo limits, quote expiry) while keeping pricing logic in pricing.py.

Key design choices:
  - Capacity is enforced with a row-level SELECT ... FOR UPDATE inside
    the same transaction as the INSERT, preventing overselling under load.
  - Promo validation is ordered: active → dates → per-customer → total → min_spend.
    Each failure returns a distinct reason so the UI can show a clear message.
  - Quotes expire after QUOTE_TTL_MINUTES (default 15). Confirming an expired
    quote is rejected; the customer must request a fresh quote.
  - A confirmed booking stores snapshot_json: a complete copy of every pricing
    input. This makes the charged amount reconstructable forever.
  - JSON columns require a custom serializer because Python's json module cannot
    handle Decimal or datetime objects natively.
"""

import json
import uuid
import random
from decimal import Decimal
import string
from datetime import date
from datetime import datetime, timezone

from typing import Optional, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models import (
    Cruise, Customer, PromoCode, PromoRedemption,
    FareBand, GroupDiscount, OptionalService, TaxRate,
    PendingQuote, Booking, BookingPassenger, BookingExtra,
    BookingStatus, PassengerType,
)
from app.pricing import (
    FareBandData, GroupDiscountData, ServiceData, PromoData,
    PriceBreakdown, calculate_price, validate_passengers, PricingValidationError,
)
from app.config import settings


# ---------------------------------------------------------------------------
# Custom exceptions (translated to HTTP errors in routes.py)
# ---------------------------------------------------------------------------

class BookingError(Exception):
    """Base booking error."""
    def __init__(self, message: str, code: str = "BOOKING_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class PromoValidationError(BookingError):
    """Raised when a promo code fails any validation check."""
    def __init__(self, message: str, reason_code: str):
        super().__init__(message, code=reason_code)
        self.reason_code = reason_code


class CapacityError(BookingError):
    """Raised when a cruise has insufficient capacity."""
    def __init__(self, available: int, requested: int):
        super().__init__(
            f"Cruise has only {available} space(s) remaining; requested {requested}.",
            code="CAPACITY_EXCEEDED",
        )
        self.available = available
        self.requested = requested


class QuoteError(BookingError):
    """Raised for invalid / expired / already-used quote tokens."""


# ---------------------------------------------------------------------------
# Reference generation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------

class _DecimalEncoder(json.JSONEncoder):
    """Extend the stdlib encoder to handle Decimal, date, and datetime."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _to_json_safe(obj) -> dict:
    """Round-trip through JSON to make all values JSON-serialisable."""
    return json.loads(json.dumps(obj, cls=_DecimalEncoder))


def _utcnow() -> datetime:
    """
    Return the current UTC time as a NAIVE datetime (no tzinfo).
    SQLite stores datetimes without timezone, so comparisons against DB values
    must use naive datetimes to avoid 'can't compare offset-naive and offset-aware'
    errors. For PostgreSQL, timezone-aware datetimes work correctly.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _generate_reference() -> str:
    """Generate a unique human-readable booking reference like ODY-A1B2C3D4."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=8))
    return f"ODY-{suffix}"


# ---------------------------------------------------------------------------
# DB helpers — fetch soft-config tables
# ---------------------------------------------------------------------------

def _get_fare_bands(db: Session) -> List[FareBandData]:
    rows = db.execute(select(FareBand).order_by(FareBand.min_age)).scalars().all()
    return [
        FareBandData(
            min_age=r.min_age,
            max_age=r.max_age,
            fraction_of_adult=r.fraction_of_adult,
            label=r.label,
        )
        for r in rows
    ]


def _get_group_discounts(db: Session) -> List[GroupDiscountData]:
    rows = db.execute(select(GroupDiscount)).scalars().all()
    return [
        GroupDiscountData(
            min_passengers=r.min_passengers,
            max_passengers=r.max_passengers,
            discount_pct=r.discount_pct,
        )
        for r in rows
    ]


def _get_current_tax_rate(db: Session) -> Decimal:
    """Return the tax rate for the most recent TaxRate row effective now."""
    now = _utcnow()  # naive UTC so SQLite comparison works
    row = (
        db.execute(
            select(TaxRate)
            .where(TaxRate.effective_from <= now)
            .order_by(TaxRate.effective_from.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    if row is None:
        raise BookingError("No tax rate is currently configured.", code="CONFIG_ERROR")
    return row.rate_pct


def _get_services(db: Session, codes: List[str]) -> List[ServiceData]:
    """Fetch active optional services by code list."""
    rows = db.execute(
        select(OptionalService)
        .where(OptionalService.code.in_(codes), OptionalService.is_active == True)
    ).scalars().all()
    found_codes = {r.code for r in rows}
    missing = set(codes) - found_codes
    if missing:
        raise BookingError(f"Unknown or inactive service codes: {', '.join(missing)}", code="INVALID_SERVICE")
    return [
        ServiceData(
            code=r.code,
            name=r.name,
            price_type=r.price_type.value,
            unit_price=r.unit_price,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Promo validation
# ---------------------------------------------------------------------------

def _validate_promo(
    db: Session,
    code_str: str,
    customer_id: int,
    subtotal_before_promo: Decimal,
) -> Tuple[PromoCode, PromoData]:
    """
    Validate a promo code against all rules. Returns (ORM row, PromoData) on
    success. Raises PromoValidationError with a specific reason_code on any failure.

    Validation order:
      1. Code exists and is_active
      2. Within valid date range
      3. Per-customer usage limit
      4. Total usage limit
      5. Minimum spend
    """
    today = datetime.now(timezone.utc).date()

    promo = db.execute(
        select(PromoCode).where(PromoCode.code == code_str)
    ).scalar_one_or_none()

    if promo is None or not promo.is_active:
        raise PromoValidationError(
            f"Promo code '{code_str}' does not exist or is no longer active.",
            reason_code="PROMO_NOT_FOUND",
        )

    if today < promo.valid_from:
        raise PromoValidationError(
            f"Promo code '{code_str}' is not yet valid (valid from {promo.valid_from}).",
            reason_code="PROMO_NOT_YET_VALID",
        )

    if today > promo.valid_to:
        raise PromoValidationError(
            f"Promo code '{code_str}' expired on {promo.valid_to}.",
            reason_code="PROMO_EXPIRED",
        )

    # Per-customer usage
    if promo.max_per_customer is not None:
        customer_uses = db.execute(
            select(func.count()).where(
                PromoRedemption.promo_code_id == promo.id,
                PromoRedemption.customer_id == customer_id,
            )
        ).scalar_one()
        if customer_uses >= promo.max_per_customer:
            raise PromoValidationError(
                f"You have already used promo code '{code_str}' the maximum number of times.",
                reason_code="PROMO_CUSTOMER_LIMIT_REACHED",
            )

    # Total usage
    if promo.max_total_uses is not None:
        total_uses = db.execute(
            select(func.count()).where(PromoRedemption.promo_code_id == promo.id)
        ).scalar_one()
        if total_uses >= promo.max_total_uses:
            raise PromoValidationError(
                f"Promo code '{code_str}' has been fully redeemed and is no longer available.",
                reason_code="PROMO_EXHAUSTED",
            )

    # Minimum spend
    if subtotal_before_promo < promo.min_spend:
        raise PromoValidationError(
            f"Promo code '{code_str}' requires a minimum booking value of ${promo.min_spend:.2f}. "
            f"Your subtotal is ${subtotal_before_promo:.2f}.",
            reason_code="PROMO_MIN_SPEND_NOT_MET",
        )

    promo_data = PromoData(
        code=promo.code,
        promo_type=promo.promo_type.value,
        value=promo.value,
        description=promo.description,
    )
    return promo, promo_data


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def get_available_cruises(db: Session) -> List[Cruise]:
    """Return all active cruises that still have capacity and haven't departed."""
    today = datetime.now(timezone.utc).date()
    return db.execute(
        select(Cruise)
        .where(
            Cruise.is_active == True,
            Cruise.departure_date >= today,
            Cruise.booked_count < Cruise.total_capacity,
        )
        .order_by(Cruise.departure_date)
    ).scalars().all()


def get_or_create_customer(
    db: Session, email: str, first_name: str, last_name: str
) -> Customer:
    """Upsert a customer by email. Returns existing if found, else creates new."""
    customer = db.execute(
        select(Customer).where(Customer.email == email)
    ).scalar_one_or_none()
    if customer is None:
        customer = Customer(email=email, first_name=first_name, last_name=last_name)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    return customer


def create_quote(
    db: Session,
    customer_id: int,
    cruise_id: int,
    num_adults: int,
    child_ages: List[int],
    service_codes: List[str],
    promo_code_str: Optional[str],
    request_payload: dict,
) -> PendingQuote:
    """
    Validate inputs, calculate price, and store a PendingQuote.
    Returns the quote (with token) so the API can return it to the customer.
    Does NOT confirm a booking or touch capacity.
    """
    # Validate passengers
    try:
        validate_passengers(num_adults, child_ages)
    except PricingValidationError as e:
        raise BookingError(e.message, code="VALIDATION_ERROR")

    # Fetch cruise
    cruise = db.get(Cruise, cruise_id)
    if cruise is None or not cruise.is_active:
        raise BookingError(f"Cruise {cruise_id} not found.", code="CRUISE_NOT_FOUND")
    if cruise.departure_date < datetime.now(timezone.utc).date():
        raise BookingError("Cannot book a cruise that has already departed.", code="CRUISE_DEPARTED")

    # Capacity pre-check (not locked — final check is at confirm time)
    total_passengers = num_adults + len(child_ages)
    if total_passengers > cruise.available_capacity:
        raise CapacityError(cruise.available_capacity, total_passengers)

    # Fetch soft config
    fare_bands = _get_fare_bands(db)
    group_discounts = _get_group_discounts(db)
    tax_rate = _get_current_tax_rate(db)
    services = _get_services(db, service_codes) if service_codes else []

    # Initial price calc (without promo) to get subtotal for promo min_spend check
    breakdown_no_promo = calculate_price(
        cruise_id=cruise_id,
        cruise_name=cruise.name,
        adult_fare=cruise.adult_fare,
        duration_nights=cruise.duration_nights,
        num_adults=num_adults,
        child_ages=child_ages,
        fare_bands=fare_bands,
        group_discount_tiers=group_discounts,
        selected_services=services,
        tax_rate_pct=tax_rate,
        promo=None,
    )

    # Promo validation (uses subtotal_before_promo as the spend threshold)
    promo_data: Optional[PromoData] = None
    if promo_code_str:
        _, promo_data = _validate_promo(
            db, promo_code_str, customer_id,
            breakdown_no_promo.subtotal_before_promo,
        )

    # Final price with promo
    breakdown = calculate_price(
        cruise_id=cruise_id,
        cruise_name=cruise.name,
        adult_fare=cruise.adult_fare,
        duration_nights=cruise.duration_nights,
        num_adults=num_adults,
        child_ages=child_ages,
        fare_bands=fare_bands,
        group_discount_tiers=group_discounts,
        selected_services=services,
        tax_rate_pct=tax_rate,
        promo=promo_data,
    )

    now = _utcnow()
    expires_at = datetime.utcfromtimestamp(
        datetime.now(timezone.utc).timestamp() + settings.QUOTE_TTL_MINUTES * 60
    )

    quote = PendingQuote(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        cruise_id=cruise_id,
        request_payload=_to_json_safe(request_payload),
        price_breakdown=_to_json_safe(breakdown.to_dict()),
        total_amount=breakdown.total,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def confirm_booking(db: Session, quote_id: str) -> Booking:
    """
    Confirm a booking from a valid, unexpired, unused quote token.

    Steps (all inside one transaction):
      1. Load and validate the quote.
      2. SELECT cruise FOR UPDATE (row-level lock).
      3. Re-check capacity with locked row.
      4. Create Booking, BookingPassenger, BookingExtra rows.
      5. Create PromoRedemption if applicable.
      6. Increment cruise.booked_count.
      7. Mark quote as used.
      8. Commit.
    """
    now = datetime.now(timezone.utc)

    # 1. Validate quote
    quote = db.get(PendingQuote, quote_id)
    if quote is None:
        raise QuoteError("Quote not found. Please request a new quote.", code="QUOTE_NOT_FOUND")
    if quote.is_used:
        raise QuoteError("This quote has already been used.", code="QUOTE_ALREADY_USED")
    # expires_at from SQLite is naive; compare against naive UTC now
    expires_naive = quote.expires_at if quote.expires_at.tzinfo is None else quote.expires_at.replace(tzinfo=None)
    if expires_naive < _utcnow():
        raise QuoteError(
            f"This quote expired at {quote.expires_at.isoformat()}. Please request a new quote.",
            code="QUOTE_EXPIRED",
        )

    # 2. Lock cruise row (FOR UPDATE not supported in SQLite; we use
    #    with_for_update() which is a no-op on SQLite but works on PostgreSQL)
    cruise = db.execute(
        select(Cruise).where(Cruise.id == quote.cruise_id).with_for_update()
    ).scalar_one()

    # 3. Re-check capacity (definitive check under lock)
    breakdown = quote.price_breakdown
    total_passengers = breakdown["total_passengers"]
    if cruise.booked_count + total_passengers > cruise.total_capacity:
        raise CapacityError(cruise.available_capacity, total_passengers)

    # 4. Create Booking
    reference = _generate_reference()
    # Ensure uniqueness (collision astronomically unlikely but handle it)
    while db.execute(select(Booking).where(Booking.reference == reference)).scalar_one_or_none():
        reference = _generate_reference()

    # Build snapshot (quote breakdown + customer + cruise metadata)
    # breakdown is already JSON-safe (came from the JSON column), but
    # _to_json_safe ensures any stray Decimal/datetime values are handled.
    snapshot = _to_json_safe({
        **breakdown,
        "customer_id": quote.customer_id,
        "quote_id": quote_id,
        "confirmed_at": now.isoformat(),
    })

    booking = Booking(
        reference=reference,
        customer_id=quote.customer_id,
        cruise_id=quote.cruise_id,
        quote_id=quote_id,
        status=BookingStatus.CONFIRMED,
        total_charged=quote.total_amount,
        snapshot_json=snapshot,
    )
    db.add(booking)
    db.flush()  # get booking.id

    # 4a. BookingPassenger rows
    for pax in breakdown["passenger_fares"]:
        db.add(BookingPassenger(
            booking_id=booking.id,
            passenger_type=PassengerType(pax["passenger_type"]),
            age=pax["age"],
            fare_charged=Decimal(pax["fare"]),
        ))

    # 4b. BookingExtra rows
    for extra in breakdown["extras"]:
        db.add(BookingExtra(
            booking_id=booking.id,
            service_code=extra["service_code"],
            service_name=extra["service_name"],
            price_type=extra["price_type"],
            unit_price_at_booking=Decimal(extra["unit_price"]),
            quantity=extra["quantity"],
            line_total=Decimal(extra["line_total"]),
        ))

    # 5. PromoRedemption
    if breakdown.get("promo_code"):
        promo = db.execute(
            select(PromoCode).where(PromoCode.code == breakdown["promo_code"])
        ).scalar_one_or_none()
        if promo:
            db.add(PromoRedemption(
                promo_code_id=promo.id,
                customer_id=quote.customer_id,
                booking_id=booking.id,
            ))

    # 6. Increment capacity counter
    cruise.booked_count += total_passengers

    # 7. Mark quote used
    quote.is_used = True

    # 8. Commit everything atomically
    db.commit()
    db.refresh(booking)
    return booking


def get_booking_by_reference(db: Session, reference: str) -> Optional[Booking]:
    return db.execute(
        select(Booking)
        .where(Booking.reference == reference)
    ).scalar_one_or_none()
