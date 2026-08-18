"""
FastAPI route handlers.

All business logic lives in booking.py / pricing.py.
Routes are responsible only for:
  - Parsing & validating HTTP input (Pydantic schemas)
  - Calling service functions
  - Translating exceptions to appropriate HTTP responses
  - Serialising ORM objects to response schemas
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import (
    CustomerCreate, CustomerOut,
    CruiseOut,
    QuoteRequest, QuoteOut,
    BookingConfirmRequest, BookingOut,
    ErrorOut,
)
from app import booking as svc
from app.booking import (
    BookingError, PromoValidationError, CapacityError, QuoteError
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Utility — exception → HTTPException
# ---------------------------------------------------------------------------

def _handle_booking_error(e: BookingError) -> HTTPException:
    status_map = {
        "CAPACITY_EXCEEDED": status.HTTP_409_CONFLICT,
        "CRUISE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "QUOTE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "QUOTE_EXPIRED": status.HTTP_410_GONE,
        "QUOTE_ALREADY_USED": status.HTTP_409_CONFLICT,
        "PROMO_NOT_FOUND": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "PROMO_NOT_YET_VALID": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "PROMO_EXPIRED": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "PROMO_CUSTOMER_LIMIT_REACHED": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "PROMO_EXHAUSTED": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "PROMO_MIN_SPEND_NOT_MET": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_SERVICE": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "CONFIG_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "CRUISE_DEPARTED": status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    http_status = status_map.get(e.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(
        status_code=http_status,
        detail={"code": e.code, "message": e.message},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/health", tags=["Health"])
def health():
    """Simple liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@router.post(
    "/customers",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Customers"],
    summary="Register or retrieve a customer",
)
def upsert_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    """
    Create a new customer or return the existing one if the email is already
    registered. This is an upsert so customers don't need to pre-register
    before requesting a quote.
    """
    customer = svc.get_or_create_customer(
        db, email=body.email, first_name=body.first_name, last_name=body.last_name
    )
    return customer


# ---------------------------------------------------------------------------
# Cruises
# ---------------------------------------------------------------------------

@router.get(
    "/cruises",
    response_model=list[CruiseOut],
    tags=["Cruises"],
    summary="List all available cruises",
)
def list_cruises(db: Session = Depends(get_db)):
    """
    Returns active cruises with remaining capacity that have not yet departed.
    Use this to show customers what they can book.
    """
    cruises = svc.get_available_cruises(db)
    return [
        CruiseOut(
            id=c.id,
            name=c.name,
            destination=c.destination,
            departure_date=c.departure_date,
            duration_nights=c.duration_nights,
            adult_fare=c.adult_fare,
            total_capacity=c.total_capacity,
            available_capacity=c.available_capacity,
            description=c.description,
        )
        for c in cruises
    ]


@router.get(
    "/cruises/{cruise_id}",
    response_model=CruiseOut,
    tags=["Cruises"],
    summary="Get details of a specific cruise",
)
def get_cruise(cruise_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.models import Cruise
    cruise = db.get(Cruise, cruise_id)
    if cruise is None:
        raise HTTPException(status_code=404, detail={"code": "CRUISE_NOT_FOUND", "message": "Cruise not found."})
    return CruiseOut(
        id=cruise.id,
        name=cruise.name,
        destination=cruise.destination,
        departure_date=cruise.departure_date,
        duration_nights=cruise.duration_nights,
        adult_fare=cruise.adult_fare,
        total_capacity=cruise.total_capacity,
        available_capacity=cruise.available_capacity,
        description=cruise.description,
    )


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

@router.post(
    "/quotes",
    response_model=QuoteOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Quotes"],
    summary="Request a price quote",
)
def create_quote(body: QuoteRequest, db: Session = Depends(get_db)):
    """
    Calculate the full itemised price for a booking and return a quote token.

    The token is valid for QUOTE_TTL_MINUTES (default 15 minutes). Submit it
    to POST /bookings to confirm the booking at exactly this price.

    Promo code validation happens here — if the code is invalid, the quote
    request is rejected with a clear reason before any payment is involved.
    """
    try:
        quote = svc.create_quote(
            db=db,
            customer_id=body.customer_id,
            cruise_id=body.cruise_id,
            num_adults=body.num_adults,
            child_ages=body.child_ages,
            service_codes=body.service_codes,
            promo_code_str=body.promo_code,
            request_payload=body.model_dump(),
        )
    except BookingError as e:
        raise _handle_booking_error(e)

    return QuoteOut(
        quote_token=quote.id,
        expires_at=quote.expires_at,
        total_amount=str(quote.total_amount),
        breakdown=quote.price_breakdown,
    )


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

@router.post(
    "/bookings",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Bookings"],
    summary="Confirm a booking using a quote token",
)
def confirm_booking(body: BookingConfirmRequest, db: Session = Depends(get_db)):
    """
    Confirm a booking. The customer must supply a valid, unexpired quote token.

    The amount charged is EXACTLY what was shown in the quote — no
    recalculation happens here. This guarantees price-shown == price-charged.

    On success, returns the booking with a unique reference the customer can
    quote back to Odysseus.
    """
    try:
        booking = svc.confirm_booking(db=db, quote_id=body.quote_token)
    except BookingError as e:
        raise _handle_booking_error(e)

    return BookingOut(
        reference=booking.reference,
        customer_id=booking.customer_id,
        cruise_id=booking.cruise_id,
        status=booking.status.value,
        total_charged=str(booking.total_charged),
        created_at=booking.created_at,
        passengers=[
            {"passenger_type": p.passenger_type.value, "age": p.age, "fare_charged": str(p.fare_charged)}
            for p in booking.passengers
        ],
        extras=[
            {
                "service_code": e.service_code,
                "service_name": e.service_name,
                "unit_price_at_booking": str(e.unit_price_at_booking),
                "quantity": e.quantity,
                "line_total": str(e.line_total),
            }
            for e in booking.extras
        ],
        snapshot=booking.snapshot_json,
    )


@router.get(
    "/bookings/{reference}",
    response_model=BookingOut,
    tags=["Bookings"],
    summary="Retrieve a booking by reference",
)
def get_booking(reference: str, db: Session = Depends(get_db)):
    """
    Retrieve a confirmed booking by its unique reference (e.g. ODY-A1B2C3D4).
    The snapshot field contains the complete immutable pricing record.
    """
    booking = svc.get_booking_by_reference(db, reference.upper())
    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BOOKING_NOT_FOUND", "message": f"Booking '{reference}' not found."},
        )
    return BookingOut(
        reference=booking.reference,
        customer_id=booking.customer_id,
        cruise_id=booking.cruise_id,
        status=booking.status.value,
        total_charged=str(booking.total_charged),
        created_at=booking.created_at,
        passengers=[
            {"passenger_type": p.passenger_type.value, "age": p.age, "fare_charged": str(p.fare_charged)}
            for p in booking.passengers
        ],
        extras=[
            {
                "service_code": e.service_code,
                "service_name": e.service_name,
                "unit_price_at_booking": str(e.unit_price_at_booking),
                "quantity": e.quantity,
                "line_total": str(e.line_total),
            }
            for e in booking.extras
        ],
        snapshot=booking.snapshot_json,
    )
