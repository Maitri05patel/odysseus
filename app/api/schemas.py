"""
Pydantic v2 schemas for request / response validation.

All monetary values are returned as strings (e.g. "1234.56") to avoid
floating-point precision issues in JSON. Clients should parse as Decimal.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class CustomerOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Cruise
# ---------------------------------------------------------------------------

class CruiseOut(BaseModel):
    id: int
    name: str
    destination: str
    departure_date: date
    duration_nights: int
    adult_fare: Decimal
    total_capacity: int
    available_capacity: int
    description: Optional[str]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Quote request / response
# ---------------------------------------------------------------------------

class QuoteRequest(BaseModel):
    customer_id: int = Field(..., description="ID of the customer requesting the quote")
    cruise_id: int = Field(..., description="ID of the cruise to book")
    num_adults: int = Field(..., ge=1, description="Number of adults (≥1)")
    child_ages: List[int] = Field(default_factory=list, description="Age of each child (0–17)")
    service_codes: List[str] = Field(default_factory=list, description="Optional service codes e.g. ['INSURANCE','WIFI']")
    promo_code: Optional[str] = Field(None, description="Promotional code to apply")

    @field_validator("child_ages", mode="before")
    @classmethod
    def validate_child_ages(cls, v):
        return v or []

    @field_validator("service_codes", mode="before")
    @classmethod
    def validate_service_codes(cls, v):
        return v or []


class PassengerFareOut(BaseModel):
    passenger_type: str
    age: Optional[int]
    band_label: str
    fraction_of_adult: str
    fare: str


class ExtraLineOut(BaseModel):
    service_code: str
    service_name: str
    price_type: str
    unit_price: str
    quantity: int
    duration_nights: int
    line_total: str


class PriceBreakdownOut(BaseModel):
    cruise_id: int
    cruise_name: str
    adult_fare: str
    duration_nights: int
    passenger_fares: List[PassengerFareOut]
    base_fare_total: str
    total_passengers: int
    group_discount_pct: str
    group_discount_amount: str
    fare_after_group_discount: str
    extras: List[ExtraLineOut]
    extras_total: str
    subtotal_before_promo: str
    promo_code: Optional[str]
    promo_type: Optional[str]
    promo_value: Optional[str]
    promo_discount_amount: str
    tax_rate_pct: str
    taxable_amount: str
    tax_amount: str
    total: str


class QuoteOut(BaseModel):
    quote_token: str = Field(..., description="Token to submit with confirm request")
    expires_at: datetime
    total_amount: str
    breakdown: Any  # full dict from price_breakdown JSON column

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Booking confirm / response
# ---------------------------------------------------------------------------

class BookingConfirmRequest(BaseModel):
    quote_token: str = Field(..., description="Token returned by the quote endpoint")


class PassengerOut(BaseModel):
    passenger_type: str
    age: Optional[int]
    fare_charged: str

    model_config = {"from_attributes": True}


class ExtraOut(BaseModel):
    service_code: str
    service_name: str
    unit_price_at_booking: str
    quantity: int
    line_total: str

    model_config = {"from_attributes": True}


class BookingOut(BaseModel):
    reference: str
    customer_id: int
    cruise_id: int
    status: str
    total_charged: str
    created_at: datetime
    passengers: List[PassengerOut]
    extras: List[ExtraOut]
    snapshot: Any  # full immutable pricing record

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------

class ErrorOut(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None
