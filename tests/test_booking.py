"""
Integration tests for the booking service layer (create_quote, confirm_booking).
Tests capacity enforcement, quote expiry, and full booking flow.
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.booking import create_quote, confirm_booking, CapacityError, BookingError, QuoteError
from app.models import BookingStatus
from tests.conftest import seed_config, make_cruise, make_customer, make_promo


class TestCreateQuote:

    def test_basic_quote_created(self, db):
        seed_config(db)
        cruise = make_cruise(db, adult_fare=Decimal("1000.00"))
        customer = make_customer(db)

        quote = create_quote(
            db=db,
            customer_id=customer.id,
            cruise_id=cruise.id,
            num_adults=1,
            child_ages=[],
            service_codes=[],
            promo_code_str=None,
            request_payload={},
        )
        assert quote.id is not None
        assert quote.total_amount > Decimal("0.00")
        assert not quote.is_used

    def test_quote_includes_promo_discount(self, db):
        seed_config(db)
        cruise = make_cruise(db, adult_fare=Decimal("1000.00"))
        customer = make_customer(db)
        make_promo(db, code="P10", value=Decimal("10"))

        quote_no_promo = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=1, child_ages=[], service_codes=[],
            promo_code_str=None, request_payload={},
        )
        quote_with_promo = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=1, child_ages=[], service_codes=[],
            promo_code_str="P10", request_payload={},
        )
        assert quote_with_promo.total_amount < quote_no_promo.total_amount

    def test_quote_with_services(self, db):
        seed_config(db)
        cruise = make_cruise(db)
        customer = make_customer(db)

        quote = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=2, child_ages=[], service_codes=["INSURANCE"],
            promo_code_str=None, request_payload={},
        )
        bd = quote.price_breakdown
        assert any(e["service_code"] == "INSURANCE" for e in bd["extras"])

    def test_quote_rejects_invalid_promo(self, db):
        seed_config(db)
        cruise = make_cruise(db)
        customer = make_customer(db)

        with pytest.raises(BookingError) as exc_info:
            create_quote(
                db=db, customer_id=customer.id, cruise_id=cruise.id,
                num_adults=1, child_ages=[], service_codes=[],
                promo_code_str="FAKECODE", request_payload={},
            )
        assert exc_info.value.code == "PROMO_NOT_FOUND"

    def test_quote_capacity_pre_check(self, db):
        """Pre-check rejects when even approximate capacity is exceeded."""
        seed_config(db)
        cruise = make_cruise(db, capacity=2, booked=2)  # full
        customer = make_customer(db)

        with pytest.raises(CapacityError):
            create_quote(
                db=db, customer_id=customer.id, cruise_id=cruise.id,
                num_adults=1, child_ages=[], service_codes=[],
                promo_code_str=None, request_payload={},
            )

    def test_quote_rejected_for_unknown_service(self, db):
        seed_config(db)
        cruise = make_cruise(db)
        customer = make_customer(db)

        with pytest.raises(BookingError) as exc_info:
            create_quote(
                db=db, customer_id=customer.id, cruise_id=cruise.id,
                num_adults=1, child_ages=[], service_codes=["UNKNOWN_SVC"],
                promo_code_str=None, request_payload={},
            )
        assert exc_info.value.code == "INVALID_SERVICE"

    def test_zero_adults_rejected_in_quote(self, db):
        seed_config(db)
        cruise = make_cruise(db)
        customer = make_customer(db)

        with pytest.raises(BookingError) as exc_info:
            create_quote(
                db=db, customer_id=customer.id, cruise_id=cruise.id,
                num_adults=0, child_ages=[], service_codes=[],
                promo_code_str=None, request_payload={},
            )
        assert exc_info.value.code == "VALIDATION_ERROR"


class TestConfirmBooking:

    def _make_quote(self, db, **kwargs):
        seed_config(db)
        cruise = make_cruise(db, **kwargs)
        customer = make_customer(db)
        quote = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=2, child_ages=[5], service_codes=[],
            promo_code_str=None, request_payload={},
        )
        return quote, cruise, customer

    def test_confirm_returns_booking_with_reference(self, db):
        quote, _, _ = self._make_quote(db)
        booking = confirm_booking(db, quote.id)
        assert booking.reference.startswith("ODY-")
        assert booking.status == BookingStatus.CONFIRMED

    def test_confirm_charges_exact_quote_amount(self, db):
        quote, _, _ = self._make_quote(db)
        booking = confirm_booking(db, quote.id)
        assert booking.total_charged == quote.total_amount

    def test_confirm_increments_cruise_booked_count(self, db):
        quote, cruise, _ = self._make_quote(db)
        initial_count = cruise.booked_count
        confirm_booking(db, quote.id)
        db.refresh(cruise)
        assert cruise.booked_count == initial_count + 3  # 2 adults + 1 child (age 5)

    def test_confirm_marks_quote_used(self, db):
        quote, _, _ = self._make_quote(db)
        confirm_booking(db, quote.id)
        db.refresh(quote)
        assert quote.is_used is True

    def test_quote_cannot_be_used_twice(self, db):
        quote, _, _ = self._make_quote(db)
        confirm_booking(db, quote.id)
        with pytest.raises(QuoteError) as exc_info:
            confirm_booking(db, quote.id)
        assert exc_info.value.code == "QUOTE_ALREADY_USED"

    def test_expired_quote_rejected(self, db):
        seed_config(db)
        cruise = make_cruise(db)
        customer = make_customer(db)
        quote = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=1, child_ages=[], service_codes=[],
            promo_code_str=None, request_payload={},
        )
        # Manually expire the quote (use naive datetime to match SQLite storage)
        quote.expires_at = datetime(2020, 1, 1)  # naive, far in the past
        db.commit()

        with pytest.raises(QuoteError) as exc_info:
            confirm_booking(db, quote.id)
        assert exc_info.value.code == "QUOTE_EXPIRED"

    def test_invalid_quote_id_rejected(self, db):
        seed_config(db)
        with pytest.raises(QuoteError) as exc_info:
            confirm_booking(db, "00000000-0000-0000-0000-000000000000")
        assert exc_info.value.code == "QUOTE_NOT_FOUND"

    def test_snapshot_stored_on_booking(self, db):
        quote, _, _ = self._make_quote(db)
        booking = confirm_booking(db, quote.id)
        snap = booking.snapshot_json
        assert "adult_fare" in snap
        assert "tax_rate_pct" in snap
        assert "total" in snap
        assert "passenger_fares" in snap
        assert "confirmed_at" in snap

    def test_capacity_enforced_at_confirm(self, db):
        """Quote was created when capacity existed, but capacity filled before confirm."""
        seed_config(db)
        cruise = make_cruise(db, capacity=2, booked=0)
        customer = make_customer(db)

        quote = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=2, child_ages=[], service_codes=[],
            promo_code_str=None, request_payload={},
        )
        # Simulate another booking filling the cruise
        cruise.booked_count = 2
        db.commit()

        with pytest.raises(CapacityError):
            confirm_booking(db, quote.id)

    def test_booking_has_passenger_rows(self, db):
        quote, _, _ = self._make_quote(db)
        booking = confirm_booking(db, quote.id)
        assert len(booking.passengers) == 3  # 2 adults + 1 child

    def test_booking_has_extra_rows_when_services_selected(self, db):
        seed_config(db)
        cruise = make_cruise(db)
        customer = make_customer(db)
        quote = create_quote(
            db=db, customer_id=customer.id, cruise_id=cruise.id,
            num_adults=1, child_ages=[], service_codes=["INSURANCE"],
            promo_code_str=None, request_payload={},
        )
        booking = confirm_booking(db, quote.id)
        assert len(booking.extras) == 1
        assert booking.extras[0].service_code == "INSURANCE"
