"""
Pure pricing engine for Odysseus cruise bookings.

ALL functions here are stateless — they take explicit data parameters and
return structured results. No database access happens here.

This separation means:
  - Pricing logic is trivially unit-testable (no DB fixtures needed).
  - The booking service calls these functions with data it fetches from DB.
  - The same functions produce both the quote preview and the snapshot stored
    at confirmation, ensuring price-shown == price-charged.

Tax application decision:
  We apply tax to the FINAL net amount after group discount and promo code.
  Rationale: tax is owed on what the customer actually pays, not on a
  pre-discount amount. This matches standard VAT/sales-tax practice.
"""

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List


# ---------------------------------------------------------------------------
# Input data classes (plain Python — no ORM dependency)
# ---------------------------------------------------------------------------

@dataclass
class FareBandData:
    min_age: int
    max_age: int
    fraction_of_adult: Decimal
    label: str


@dataclass
class GroupDiscountData:
    min_passengers: int
    max_passengers: int
    discount_pct: Decimal


@dataclass
class ServiceData:
    code: str
    name: str
    price_type: str          # "PER_PASSENGER" | "PER_PASSENGER_PER_NIGHT"
    unit_price: Decimal


@dataclass
class PromoData:
    code: str
    promo_type: str          # "PCT" | "FIXED"
    value: Decimal
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Output / breakdown data classes
# ---------------------------------------------------------------------------

@dataclass
class PassengerFare:
    passenger_type: str      # "ADULT" | "CHILD"
    age: Optional[int]
    band_label: str
    fraction_of_adult: Decimal
    fare: Decimal


@dataclass
class ExtraLine:
    service_code: str
    service_name: str
    price_type: str
    unit_price: Decimal
    quantity: int            # total passengers
    duration_nights: int
    line_total: Decimal


@dataclass
class PriceBreakdown:
    # Inputs (snapshot of what was used to calculate)
    cruise_id: int
    cruise_name: str
    adult_fare: Decimal
    duration_nights: int

    # Passenger fares
    passenger_fares: List[PassengerFare]
    base_fare_total: Decimal

    # Group discount
    total_passengers: int
    group_discount_pct: Decimal
    group_discount_amount: Decimal
    fare_after_group_discount: Decimal

    # Extras
    extras: List[ExtraLine]
    extras_total: Decimal

    # Subtotal before promo + tax
    subtotal_before_promo: Decimal

    # Promo
    promo_code: Optional[str]
    promo_type: Optional[str]
    promo_value: Optional[Decimal]
    promo_discount_amount: Decimal

    # Tax
    tax_rate_pct: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal

    # Final
    total: Decimal

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON storage in snapshot_json."""
        def _convert(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, list):
                return [_convert(i) for i in obj]
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _convert(v) for k, v in asdict(obj).items()}
            return obj

        return {k: _convert(v) for k, v in asdict(self).items()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CENT = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _find_fare_band(age: int, bands: List[FareBandData]) -> Optional[FareBandData]:
    for band in bands:
        if band.min_age <= age <= band.max_age:
            return band
    return None


def _find_group_discount(total_passengers: int, tiers: List[GroupDiscountData]) -> GroupDiscountData:
    for tier in sorted(tiers, key=lambda t: t.min_passengers):
        if tier.min_passengers <= total_passengers <= tier.max_passengers:
            return tier
    # Default: no discount
    return GroupDiscountData(min_passengers=total_passengers, max_passengers=total_passengers, discount_pct=Decimal("0"))


# ---------------------------------------------------------------------------
# Validation helpers (used by booking service before calling calculate_price)
# ---------------------------------------------------------------------------

class PricingValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def validate_passengers(num_adults: int, child_ages: List[int]) -> None:
    """
    Enforce booking-level passenger rules:
    - At least one adult
    - Max 6 passengers total
    - Child ages must be 0-17 (18+ must be an adult)
    """
    if num_adults < 1:
        raise PricingValidationError("At least one adult is required per booking.")

    total = num_adults + len(child_ages)
    if total > 6:
        raise PricingValidationError(
            f"Maximum 6 passengers per booking. You requested {total}."
        )

    for age in child_ages:
        if age < 0:
            raise PricingValidationError(f"Child age cannot be negative (got {age}).")
        if age > 17:
            raise PricingValidationError(
                f"A child must be aged 0–17. Age {age} qualifies as an adult — "
                "please move this passenger to the adults count."
            )


# ---------------------------------------------------------------------------
# Core pricing function
# ---------------------------------------------------------------------------

def calculate_price(
    *,
    cruise_id: int,
    cruise_name: str,
    adult_fare: Decimal,
    duration_nights: int,
    num_adults: int,
    child_ages: List[int],
    fare_bands: List[FareBandData],
    group_discount_tiers: List[GroupDiscountData],
    selected_services: List[ServiceData],
    tax_rate_pct: Decimal,
    promo: Optional[PromoData] = None,
) -> PriceBreakdown:
    """
    Calculate the full price breakdown for a cruise booking.

    Pricing order (matters for correctness):
      1. Individual passenger fares (adults full, children per band fraction)
      2. Sum base fare total
      3. Apply group discount % to base fare total
      4. Add optional extras (each calculated on total passengers / nights)
      5. Sum subtotal (discounted fares + extras)
      6. Apply promo code discount to subtotal
      7. Apply tax to net amount (subtotal after promo)
      8. Round final total to 2 d.p.

    All inputs are explicit — no DB calls here.
    """
    # ---- 1. Passenger fares ------------------------------------------------
    passenger_fares: List[PassengerFare] = []

    for _ in range(num_adults):
        passenger_fares.append(PassengerFare(
            passenger_type="ADULT",
            age=None,
            band_label="Adult",
            fraction_of_adult=Decimal("1.0000"),
            fare=_round(adult_fare),
        ))

    for age in child_ages:
        band = _find_fare_band(age, fare_bands)
        if band is None:
            # Shouldn't happen if validate_passengers passed, but defensive
            raise PricingValidationError(f"No fare band found for child age {age}.")
        child_fare = _round(adult_fare * band.fraction_of_adult)
        passenger_fares.append(PassengerFare(
            passenger_type="CHILD",
            age=age,
            band_label=band.label,
            fraction_of_adult=band.fraction_of_adult,
            fare=child_fare,
        ))

    # ---- 2. Base fare total ------------------------------------------------
    base_fare_total = sum(p.fare for p in passenger_fares)

    # ---- 3. Group discount --------------------------------------------------
    total_passengers = len(passenger_fares)
    discount_tier = _find_group_discount(total_passengers, group_discount_tiers)
    group_discount_pct = discount_tier.discount_pct
    group_discount_amount = _round(base_fare_total * group_discount_pct)
    fare_after_group_discount = _round(base_fare_total - group_discount_amount)

    # ---- 4. Optional extras -------------------------------------------------
    extras: List[ExtraLine] = []
    for svc in selected_services:
        if svc.price_type == "PER_PASSENGER":
            line_total = _round(svc.unit_price * total_passengers)
        else:  # PER_PASSENGER_PER_NIGHT
            line_total = _round(svc.unit_price * total_passengers * duration_nights)

        extras.append(ExtraLine(
            service_code=svc.code,
            service_name=svc.name,
            price_type=svc.price_type,
            unit_price=svc.unit_price,
            quantity=total_passengers,
            duration_nights=duration_nights,
            line_total=line_total,
        ))
    extras_total = sum(e.line_total for e in extras)

    # ---- 5. Subtotal before promo ------------------------------------------
    subtotal_before_promo = _round(fare_after_group_discount + extras_total)

    # ---- 6. Promo discount --------------------------------------------------
    promo_discount_amount = Decimal("0.00")
    if promo:
        if promo.promo_type == "PCT":
            promo_discount_amount = _round(subtotal_before_promo * (promo.value / Decimal("100")))
        else:  # FIXED
            promo_discount_amount = min(_round(promo.value), subtotal_before_promo)

    taxable_amount = _round(subtotal_before_promo - promo_discount_amount)

    # ---- 7. Tax (applied to net amount after promo) ------------------------
    tax_amount = _round(taxable_amount * tax_rate_pct)

    # ---- 8. Final total ----------------------------------------------------
    total = _round(taxable_amount + tax_amount)

    return PriceBreakdown(
        cruise_id=cruise_id,
        cruise_name=cruise_name,
        adult_fare=adult_fare,
        duration_nights=duration_nights,
        passenger_fares=passenger_fares,
        base_fare_total=base_fare_total,
        total_passengers=total_passengers,
        group_discount_pct=group_discount_pct,
        group_discount_amount=group_discount_amount,
        fare_after_group_discount=fare_after_group_discount,
        extras=extras,
        extras_total=extras_total,
        subtotal_before_promo=subtotal_before_promo,
        promo_code=promo.code if promo else None,
        promo_type=promo.promo_type if promo else None,
        promo_value=promo.value if promo else None,
        promo_discount_amount=promo_discount_amount,
        tax_rate_pct=tax_rate_pct,
        taxable_amount=taxable_amount,
        tax_amount=tax_amount,
        total=total,
    )
