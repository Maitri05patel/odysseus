"""
Tests for promo code validation (service layer).
Tests the ordered validation chain: active → dates → per-customer → total → min_spend.
"""

import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from app.booking import _validate_promo, PromoValidationError
from app.models import PromoCode, PromoRedemption, PromoType, Booking, BookingStatus
from tests.conftest import seed_config, make_customer, make_cruise


class TestPromoValidation:

    # --- Positive ---
    def test_valid_pct_promo_accepted(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        promo = make_promo(db, code="VALID10", promo_type=PromoType.PCT, value=Decimal("10"),
                           valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))
        promo_row, promo_data = _validate_promo(db, "VALID10", customer.id, Decimal("1000.00"))
        assert promo_data.code == "VALID10"
        assert promo_data.promo_type == "PCT"
        assert promo_data.value == Decimal("10")

    def test_valid_fixed_promo_accepted(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        make_promo(db, code="FLAT50", promo_type=PromoType.FIXED, value=Decimal("50"),
                   valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))
        promo_row, promo_data = _validate_promo(db, "FLAT50", customer.id, Decimal("100.00"))
        assert promo_data.promo_type == "FIXED"

    # --- Code does not exist ---
    def test_nonexistent_code_rejected(self, db):
        seed_config(db)
        customer = make_customer(db)
        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "DOESNOTEXIST", customer.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_NOT_FOUND"

    def test_inactive_code_rejected(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        make_promo(db, code="OFF", is_active=False)
        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "OFF", customer.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_NOT_FOUND"

    # --- Date range ---
    def test_expired_code_rejected(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        make_promo(db, code="EXP", valid_from=date(2020, 1, 1), valid_to=date(2020, 12, 31))
        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "EXP", customer.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_EXPIRED"

    def test_not_yet_valid_code_rejected(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        make_promo(db, code="FUTURE", valid_from=date(2099, 1, 1), valid_to=date(2099, 12, 31))
        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "FUTURE", customer.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_NOT_YET_VALID"

    # --- Per-customer limit ---
    def test_per_customer_limit_enforced(self, db):
        seed_config(db)
        customer = make_customer(db)
        cruise = make_cruise(db)
        from tests.conftest import make_promo

        promo = make_promo(db, code="ONCE", max_per_customer=1,
                           valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))

        # Simulate one existing redemption for this customer
        booking = Booking(
            reference="ODY-TESTREF1",
            customer_id=customer.id,
            cruise_id=cruise.id,
            status=BookingStatus.CONFIRMED,
            total_charged=Decimal("100.00"),
            snapshot_json={},
        )
        db.add(booking)
        db.flush()
        db.add(PromoRedemption(promo_code_id=promo.id, customer_id=customer.id, booking_id=booking.id))
        db.commit()

        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "ONCE", customer.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_CUSTOMER_LIMIT_REACHED"

    def test_different_customer_can_still_use_code(self, db):
        """Per-customer limit doesn't block a different customer."""
        seed_config(db)
        customer1 = make_customer(db, email="c1@test.com")
        customer2 = make_customer(db, email="c2@test.com")
        cruise = make_cruise(db)
        from tests.conftest import make_promo

        promo = make_promo(db, code="ONCE2", max_per_customer=1,
                           valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))

        # customer1 has used it
        booking = Booking(reference="ODY-TESTREF2", customer_id=customer1.id,
                          cruise_id=cruise.id, status=BookingStatus.CONFIRMED,
                          total_charged=Decimal("100.00"), snapshot_json={})
        db.add(booking)
        db.flush()
        db.add(PromoRedemption(promo_code_id=promo.id, customer_id=customer1.id, booking_id=booking.id))
        db.commit()

        # customer2 should still be able to use it
        promo_row, promo_data = _validate_promo(db, "ONCE2", customer2.id, Decimal("500.00"))
        assert promo_data.code == "ONCE2"

    # --- Total usage limit ---
    def test_exhausted_code_rejected(self, db):
        seed_config(db)
        customer = make_customer(db)
        cruise = make_cruise(db)
        from tests.conftest import make_promo

        promo = make_promo(db, code="EXHAUST", max_total_uses=1,
                           valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))

        # Use up the one allowed redemption
        booking = Booking(reference="ODY-TESTREF3", customer_id=customer.id,
                          cruise_id=cruise.id, status=BookingStatus.CONFIRMED,
                          total_charged=Decimal("100.00"), snapshot_json={})
        db.add(booking)
        db.flush()
        db.add(PromoRedemption(promo_code_id=promo.id, customer_id=customer.id, booking_id=booking.id))
        db.commit()

        customer2 = make_customer(db, email="c2@test.com")
        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "EXHAUST", customer2.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_EXHAUSTED"

    # --- Minimum spend ---
    def test_min_spend_not_met_rejected(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        make_promo(db, code="HIGHSPEND", min_spend=Decimal("1000.00"),
                   valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))
        with pytest.raises(PromoValidationError) as exc_info:
            _validate_promo(db, "HIGHSPEND", customer.id, Decimal("500.00"))
        assert exc_info.value.reason_code == "PROMO_MIN_SPEND_NOT_MET"

    def test_exactly_min_spend_accepted(self, db):
        seed_config(db)
        customer = make_customer(db)
        from tests.conftest import make_promo
        make_promo(db, code="EXACT", min_spend=Decimal("500.00"),
                   valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))
        # Exactly at min spend should pass
        promo_row, promo_data = _validate_promo(db, "EXACT", customer.id, Decimal("500.00"))
        assert promo_data.code == "EXACT"

    def test_unlimited_code_no_cap(self, db):
        """max_total_uses=None means unlimited — should always pass."""
        seed_config(db)
        customer = make_customer(db)
        cruise = make_cruise(db)
        from tests.conftest import make_promo

        promo = make_promo(db, code="UNLIMITED", max_total_uses=None, max_per_customer=None,
                           valid_from=date(2026, 1, 1), valid_to=date(2099, 12, 31))

        # Add many redemptions
        for i in range(10):
            c = make_customer(db, email=f"c{i}@test.com")
            b = Booking(reference=f"ODY-TEST{i:04d}", customer_id=c.id,
                        cruise_id=cruise.id, status=BookingStatus.CONFIRMED,
                        total_charged=Decimal("100.00"), snapshot_json={})
            db.add(b)
            db.flush()
            db.add(PromoRedemption(promo_code_id=promo.id, customer_id=c.id, booking_id=b.id))
        db.commit()

        # Should still work for a new customer
        new_c = make_customer(db, email="new@test.com")
        promo_row, promo_data = _validate_promo(db, "UNLIMITED", new_c.id, Decimal("100.00"))
        assert promo_data.code == "UNLIMITED"
