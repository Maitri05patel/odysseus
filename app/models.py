"""
SQLAlchemy ORM models for Odysseus Cruise Booking System.

Design principles:
- All pricing configuration lives in DB tables (soft config) so changes
  never require a code redeploy.
- BookingSnapshot stores an immutable JSON record of every pricing input
  at confirmation time — so the charged amount is always reconstructable.
- booked_count on Cruise is incremented inside a transaction with a
  row-level lock to prevent overselling under concurrency.
"""

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
import uuid

from sqlalchemy import (
    String, Integer, Numeric, Boolean, DateTime, Date,
    ForeignKey, JSON, Enum as SAEnum, Text, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PromoType(str, enum.Enum):
    PCT = "PCT"        # percentage off
    FIXED = "FIXED"    # fixed amount off


class PriceType(str, enum.Enum):
    PER_PASSENGER = "PER_PASSENGER"
    PER_PASSENGER_PER_NIGHT = "PER_PASSENGER_PER_NIGHT"


class PassengerType(str, enum.Enum):
    ADULT = "ADULT"
    CHILD = "CHILD"


class BookingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Soft-Config Tables (change without code deploy)
# ---------------------------------------------------------------------------

class FareBand(Base):
    """
    Maps child age ranges to a fraction of the adult fare.
    E.g. age 0-4 → 0.00 (free), 5-11 → 0.50, 12-17 → 0.75
    These rows define who counts as a child (max_age 17 means 18+ = adult).
    """
    __tablename__ = "fare_bands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    min_age: Mapped[int] = mapped_column(Integer, nullable=False)
    max_age: Mapped[int] = mapped_column(Integer, nullable=False)
    fraction_of_adult: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "Infant", "Child", "Teen"

    def __repr__(self) -> str:
        return f"<FareBand age={self.min_age}-{self.max_age} fraction={self.fraction_of_adult}>"


class GroupDiscount(Base):
    """
    Tiered group discount applied to base fares based on total passenger count.
    1-2 pax → 0%, 3-4 pax → 5%, 5-6 pax → 10%
    """
    __tablename__ = "group_discounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    min_passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    max_passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # e.g. 0.0500

    def __repr__(self) -> str:
        return f"<GroupDiscount pax={self.min_passengers}-{self.max_passengers} pct={self.discount_pct}>"


class OptionalService(Base):
    """
    Optional services a customer can add to their booking.
    Price type determines how the unit price is multiplied.
    """
    __tablename__ = "optional_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_type: Mapped[PriceType] = mapped_column(SAEnum(PriceType), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<OptionalService {self.code} ${self.unit_price}>"


class TaxRate(Base):
    """
    Tax rate with effective date. The latest row where effective_from <= now() wins.
    This means new rates can be pre-loaded and automatically become active on schedule.
    """
    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # e.g. 0.1200 = 12%
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<TaxRate {self.rate_pct}% from {self.effective_from}>"


# ---------------------------------------------------------------------------
# Core Business Entities
# ---------------------------------------------------------------------------

class Cruise(Base):
    """
    A cruise available for booking.
    booked_count tracks total passengers booked. Must never exceed total_capacity.
    """
    __tablename__ = "cruises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_nights: Mapped[int] = mapped_column(Integer, nullable=False)
    adult_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    booked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="cruise")
    pending_quotes: Mapped[List["PendingQuote"]] = relationship("PendingQuote", back_populates="cruise")

    @property
    def available_capacity(self) -> int:
        return self.total_capacity - self.booked_count

    def __repr__(self) -> str:
        return f"<Cruise {self.name} departs={self.departure_date}>"


class Customer(Base):
    """
    A customer who can make bookings.
    Email is the natural identifier / login key.
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="customer")
    pending_quotes: Mapped[List["PendingQuote"]] = relationship("PendingQuote", back_populates="customer")
    promo_redemptions: Mapped[List["PromoRedemption"]] = relationship("PromoRedemption", back_populates="customer")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Customer {self.email}>"


class PromoCode(Base):
    """
    Promotional discount codes.
    Validation order: active → date range → per-customer limit → total limit → min_spend.
    type=PCT: value is a percentage (e.g. 10 = 10% off).
    type=FIXED: value is a fixed monetary amount off.
    min_spend=0 means no minimum.
    max_total_uses=None means unlimited.
    max_per_customer=None means unlimited per customer.
    """
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    promo_type: Mapped[PromoType] = mapped_column(SAEnum(PromoType), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    max_total_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_per_customer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    redemptions: Mapped[List["PromoRedemption"]] = relationship("PromoRedemption", back_populates="promo_code")

    def __repr__(self) -> str:
        return f"<PromoCode {self.code} type={self.promo_type} value={self.value}>"


# ---------------------------------------------------------------------------
# Transactional / Booking Tables
# ---------------------------------------------------------------------------

class PendingQuote(Base):
    """
    Stores a price quote before the customer confirms.

    The quote token (UUID) is returned to the customer. When they confirm,
    they submit the token and we use the STORED price — not a recalculation.
    This guarantees: price shown = price charged.

    expires_at enforces a TTL (default 15 min) so stale quotes don't block capacity.
    is_used=True once a booking is created from this quote.
    """
    __tablename__ = "pending_quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    cruise_id: Mapped[int] = mapped_column(Integer, ForeignKey("cruises.id"), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)   # raw input
    price_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)   # full itemised breakdown
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="pending_quotes")
    cruise: Mapped["Cruise"] = relationship("Cruise", back_populates="pending_quotes")
    booking: Mapped[Optional["Booking"]] = relationship("Booking", back_populates="quote")

    def __repr__(self) -> str:
        return f"<PendingQuote {self.id} amount={self.total_amount} expires={self.expires_at}>"


class Booking(Base):
    """
    A confirmed booking.

    snapshot_json is the IMMUTABLE record of everything that went into the price:
    cruise details at time of booking, fare bands, group discount tier, extras,
    promo code (if any), tax rate. This data never changes even if config tables do.

    reference is a human-friendly code the customer can quote (e.g. ODY-A1B2C3D4).
    """
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    cruise_id: Mapped[int] = mapped_column(Integer, ForeignKey("cruises.id"), nullable=False)
    quote_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("pending_quotes.id"), nullable=True)
    status: Mapped[BookingStatus] = mapped_column(SAEnum(BookingStatus), default=BookingStatus.CONFIRMED, nullable=False)
    total_charged: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # immutable pricing record
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="bookings")
    cruise: Mapped["Cruise"] = relationship("Cruise", back_populates="bookings")
    quote: Mapped[Optional["PendingQuote"]] = relationship("PendingQuote", back_populates="booking")
    passengers: Mapped[List["BookingPassenger"]] = relationship("BookingPassenger", back_populates="booking", cascade="all, delete-orphan")
    extras: Mapped[List["BookingExtra"]] = relationship("BookingExtra", back_populates="booking", cascade="all, delete-orphan")
    promo_redemption: Mapped[Optional["PromoRedemption"]] = relationship("PromoRedemption", back_populates="booking", uselist=False)

    def __repr__(self) -> str:
        return f"<Booking {self.reference} charged={self.total_charged}>"


class BookingPassenger(Base):
    """
    One row per passenger on a booking.
    Adults have age=None (age is irrelevant for pricing once they're ≥18).
    fare_charged is the actual amount charged for this passenger (after band fraction applied).
    """
    __tablename__ = "booking_passengers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False)
    passenger_type: Mapped[PassengerType] = mapped_column(SAEnum(PassengerType), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None for adults
    fare_charged: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="passengers")

    def __repr__(self) -> str:
        return f"<BookingPassenger type={self.passenger_type} age={self.age} fare={self.fare_charged}>"


class BookingExtra(Base):
    """
    One row per optional service added to a booking.
    Stores the unit price at the time of booking (not a FK to OptionalService)
    so future price changes don't alter historical records.
    """
    __tablename__ = "booking_extras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False)
    service_code: Mapped[str] = mapped_column(String(50), nullable=False)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_type: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price_at_booking: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="extras")

    def __repr__(self) -> str:
        return f"<BookingExtra {self.service_code} total={self.line_total}>"


class PromoRedemption(Base):
    """
    Audit trail of every promo code redemption.
    Used to enforce max_total_uses and max_per_customer limits.
    Each confirmed booking that used a promo creates exactly one row here.
    """
    __tablename__ = "promo_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_code_id: Mapped[int] = mapped_column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    promo_code: Mapped["PromoCode"] = relationship("PromoCode", back_populates="redemptions")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="promo_redemptions")
    booking: Mapped["Booking"] = relationship("Booking", back_populates="promo_redemption")

    def __repr__(self) -> str:
        return f"<PromoRedemption promo={self.promo_code_id} customer={self.customer_id} booking={self.booking_id}>"
