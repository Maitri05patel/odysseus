"""
Unit tests for app/pricing.py

Pure function tests — no database, no HTTP. These are the fastest tests
and cover the core business logic in exhaustive detail.
"""

import pytest
from decimal import Decimal

from app.pricing import (
    FareBandData, GroupDiscountData, ServiceData, PromoData,
    calculate_price, validate_passengers, PricingValidationError,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

FARE_BANDS = [
    FareBandData(min_age=0,  max_age=4,  fraction_of_adult=Decimal("0.0000"), label="Infant"),
    FareBandData(min_age=5,  max_age=11, fraction_of_adult=Decimal("0.5000"), label="Child"),
    FareBandData(min_age=12, max_age=17, fraction_of_adult=Decimal("0.7500"), label="Teen"),
]

GROUP_DISCOUNTS = [
    GroupDiscountData(min_passengers=1, max_passengers=2, discount_pct=Decimal("0.0000")),
    GroupDiscountData(min_passengers=3, max_passengers=4, discount_pct=Decimal("0.0500")),
    GroupDiscountData(min_passengers=5, max_passengers=6, discount_pct=Decimal("0.1000")),
]

TAX = Decimal("0.1200")   # 12%
ADULT_FARE = Decimal("1000.00")


def _calc(**kwargs):
    """Helper: call calculate_price with defaults overrideable by kwargs."""
    defaults = dict(
        cruise_id=1,
        cruise_name="Test Cruise",
        adult_fare=ADULT_FARE,
        duration_nights=7,
        num_adults=1,
        child_ages=[],
        fare_bands=FARE_BANDS,
        group_discount_tiers=GROUP_DISCOUNTS,
        selected_services=[],
        tax_rate_pct=TAX,
        promo=None,
    )
    defaults.update(kwargs)
    return calculate_price(**defaults)


# ===========================================================================
# validate_passengers
# ===========================================================================

class TestValidatePassengers:

    # --- Positive ---
    def test_one_adult_is_valid(self):
        validate_passengers(1, [])  # should not raise

    def test_max_six_passengers_valid(self):
        validate_passengers(3, [5, 8, 12])  # 3+3=6, valid

    def test_adult_with_infant(self):
        validate_passengers(1, [0])  # infant OK

    def test_adult_with_oldest_child(self):
        validate_passengers(1, [17])  # 17 = max child age

    # --- Negative ---
    def test_zero_adults_rejected(self):
        with pytest.raises(PricingValidationError, match="At least one adult"):
            validate_passengers(0, [])

    def test_seven_passengers_rejected(self):
        with pytest.raises(PricingValidationError, match="Maximum 6"):
            validate_passengers(4, [5, 8, 12])  # 4+3=7

    def test_child_age_18_rejected(self):
        with pytest.raises(PricingValidationError, match="qualifies as an adult"):
            validate_passengers(1, [18])

    def test_negative_child_age_rejected(self):
        with pytest.raises(PricingValidationError, match="cannot be negative"):
            validate_passengers(1, [-1])

    # --- Boundary ---
    def test_exactly_six_passengers(self):
        validate_passengers(6, [])          # 6 adults, 0 children — valid

    def test_child_age_zero_valid(self):
        validate_passengers(1, [0])

    def test_child_age_17_valid(self):
        validate_passengers(1, [17])


# ===========================================================================
# Adult fare pricing
# ===========================================================================

class TestAdultFares:

    def test_single_adult_base_fare(self):
        bd = _calc(num_adults=1)
        assert bd.base_fare_total == Decimal("1000.00")
        assert bd.group_discount_pct == Decimal("0.0000")
        assert bd.group_discount_amount == Decimal("0.00")

    def test_two_adults_no_discount(self):
        bd = _calc(num_adults=2)
        assert bd.base_fare_total == Decimal("2000.00")
        assert bd.group_discount_pct == Decimal("0.0000")
        assert bd.fare_after_group_discount == Decimal("2000.00")

    def test_fare_math_is_correct_with_tax(self):
        # 1 adult, $1000 fare, 12% tax, no extras
        # expected: 1000 * 1.12 = 1120.00
        bd = _calc(num_adults=1)
        assert bd.taxable_amount == Decimal("1000.00")
        assert bd.tax_amount == Decimal("120.00")
        assert bd.total == Decimal("1120.00")


# ===========================================================================
# Child fare bands
# ===========================================================================

class TestChildFareBands:

    def test_infant_is_free(self):
        bd = _calc(num_adults=1, child_ages=[2])   # age 2 = infant
        infant_fare = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert infant_fare.fare == Decimal("0.00")

    def test_child_5_11_is_50_pct(self):
        bd = _calc(num_adults=1, child_ages=[8])   # age 8 = 50%
        child_fare = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert child_fare.fare == Decimal("500.00")

    def test_teen_12_17_is_75_pct(self):
        bd = _calc(num_adults=1, child_ages=[15])  # age 15 = 75%
        teen_fare = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert teen_fare.fare == Decimal("750.00")

    def test_boundary_age_4_is_free(self):
        bd = _calc(num_adults=1, child_ages=[4])
        child = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert child.fare == Decimal("0.00")

    def test_boundary_age_5_is_50_pct(self):
        bd = _calc(num_adults=1, child_ages=[5])
        child = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert child.fare == Decimal("500.00")

    def test_boundary_age_11_is_50_pct(self):
        bd = _calc(num_adults=1, child_ages=[11])
        child = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert child.fare == Decimal("500.00")

    def test_boundary_age_12_is_75_pct(self):
        bd = _calc(num_adults=1, child_ages=[12])
        child = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert child.fare == Decimal("750.00")

    def test_boundary_age_17_is_75_pct(self):
        bd = _calc(num_adults=1, child_ages=[17])
        child = next(p for p in bd.passenger_fares if p.passenger_type == "CHILD")
        assert child.fare == Decimal("750.00")

    def test_multiple_children_different_bands(self):
        # adult + infant(2) + child(8) + teen(15)
        bd = _calc(num_adults=1, child_ages=[2, 8, 15])
        fares = {p.age: p.fare for p in bd.passenger_fares if p.passenger_type == "CHILD"}
        assert fares[2] == Decimal("0.00")
        assert fares[8] == Decimal("500.00")
        assert fares[15] == Decimal("750.00")


# ===========================================================================
# Group discounts
# ===========================================================================

class TestGroupDiscounts:

    def test_1_passenger_no_discount(self):
        bd = _calc(num_adults=1)
        assert bd.group_discount_pct == Decimal("0.0000")
        assert bd.group_discount_amount == Decimal("0.00")

    def test_2_passengers_no_discount(self):
        bd = _calc(num_adults=2)
        assert bd.group_discount_pct == Decimal("0.0000")

    def test_3_passengers_5_pct_discount(self):
        bd = _calc(num_adults=3)
        # 3 * 1000 = 3000, 5% = 150 off
        assert bd.group_discount_pct == Decimal("0.0500")
        assert bd.group_discount_amount == Decimal("150.00")
        assert bd.fare_after_group_discount == Decimal("2850.00")

    def test_4_passengers_5_pct_discount(self):
        bd = _calc(num_adults=4)
        assert bd.group_discount_pct == Decimal("0.0500")

    def test_5_passengers_10_pct_discount(self):
        bd = _calc(num_adults=5)
        assert bd.group_discount_pct == Decimal("0.1000")
        # 5000 * 10% = 500 off
        assert bd.group_discount_amount == Decimal("500.00")

    def test_6_passengers_10_pct_discount(self):
        bd = _calc(num_adults=6)
        assert bd.group_discount_pct == Decimal("0.1000")

    def test_boundary_3_gets_group_discount(self):
        # 2 adults + 1 child — total 3 → 5% discount
        bd = _calc(num_adults=2, child_ages=[10])
        assert bd.group_discount_pct == Decimal("0.0500")


# ===========================================================================
# Optional services
# ===========================================================================

class TestOptionalServices:

    INSURANCE = ServiceData(code="INSURANCE", name="Travel Insurance",
                            price_type="PER_PASSENGER", unit_price=Decimal("80.00"))
    WIFI = ServiceData(code="WIFI", name="Wi-Fi",
                       price_type="PER_PASSENGER_PER_NIGHT", unit_price=Decimal("15.00"))
    SHORE = ServiceData(code="SHORE_EXCURSION", name="Shore Excursion",
                        price_type="PER_PASSENGER", unit_price=Decimal("120.00"))

    def test_insurance_per_passenger(self):
        # 2 adults, insurance = 2 * 80 = 160
        bd = _calc(num_adults=2, selected_services=[self.INSURANCE])
        ins = next(e for e in bd.extras if e.service_code == "INSURANCE")
        assert ins.line_total == Decimal("160.00")

    def test_wifi_per_passenger_per_night(self):
        # 2 adults, 7 nights, wifi = 2 * 15 * 7 = 210
        bd = _calc(num_adults=2, duration_nights=7, selected_services=[self.WIFI])
        wifi = next(e for e in bd.extras if e.service_code == "WIFI")
        assert wifi.line_total == Decimal("210.00")

    def test_shore_excursion(self):
        # 3 adults, shore = 3 * 120 = 360
        bd = _calc(num_adults=3, selected_services=[self.SHORE])
        shore = next(e for e in bd.extras if e.service_code == "SHORE_EXCURSION")
        assert shore.line_total == Decimal("360.00")

    def test_multiple_services_totalled(self):
        # 1 adult, insurance (80) + shore (120) = 200 extras
        bd = _calc(num_adults=1, selected_services=[self.INSURANCE, self.SHORE])
        assert bd.extras_total == Decimal("200.00")

    def test_no_services(self):
        bd = _calc(num_adults=1, selected_services=[])
        assert bd.extras_total == Decimal("0.00")


# ===========================================================================
# Promo codes (pricing calculation — validation tested in test_promo.py)
# ===========================================================================

class TestPromoPricing:

    def test_percentage_promo(self):
        # 1 adult $1000, 10% promo → subtotal=1000, discount=100 → taxable=900 → tax=108 → total=1008
        promo = PromoData(code="SAVE10", promo_type="PCT", value=Decimal("10"))
        bd = _calc(num_adults=1, promo=promo)
        assert bd.promo_discount_amount == Decimal("100.00")
        assert bd.taxable_amount == Decimal("900.00")
        assert bd.tax_amount == Decimal("108.00")
        assert bd.total == Decimal("1008.00")

    def test_fixed_promo(self):
        # 1 adult $1000, $50 fixed off → subtotal=1000, discount=50 → taxable=950 → tax=114 → total=1064
        promo = PromoData(code="FLAT50", promo_type="FIXED", value=Decimal("50"))
        bd = _calc(num_adults=1, promo=promo)
        assert bd.promo_discount_amount == Decimal("50.00")
        assert bd.taxable_amount == Decimal("950.00")
        assert bd.total == Decimal("1064.00")

    def test_fixed_promo_cannot_exceed_subtotal(self):
        # Tiny fare, massive promo → discount capped at subtotal
        bd = _calc(
            num_adults=1,
            adult_fare=Decimal("30.00"),
            promo=PromoData(code="BIG", promo_type="FIXED", value=Decimal("9999")),
        )
        assert bd.promo_discount_amount == bd.subtotal_before_promo
        assert bd.taxable_amount == Decimal("0.00")
        assert bd.total == Decimal("0.00")

    def test_no_promo(self):
        bd = _calc(num_adults=1, promo=None)
        assert bd.promo_discount_amount == Decimal("0.00")
        assert bd.promo_code is None


# ===========================================================================
# Tax
# ===========================================================================

class TestTax:

    def test_tax_applied_after_promo(self):
        # Tax is on the post-promo amount, not pre-promo
        promo = PromoData(code="X", promo_type="PCT", value=Decimal("50"))
        bd = _calc(num_adults=1, promo=promo)
        # subtotal=1000, 50% off = 500 taxable, 12% tax = 60, total = 560
        assert bd.taxable_amount == Decimal("500.00")
        assert bd.tax_amount == Decimal("60.00")
        assert bd.total == Decimal("560.00")

    def test_zero_tax_rate(self):
        bd = _calc(num_adults=1, tax_rate_pct=Decimal("0.00"))
        assert bd.tax_amount == Decimal("0.00")
        assert bd.total == bd.taxable_amount


# ===========================================================================
# Full end-to-end pricing scenario
# ===========================================================================

class TestFullScenario:

    def test_family_booking_with_all_features(self):
        """
        2 adults + 1 infant(2) + 1 child(8) + 1 teen(15) = 5 passengers
        Adult fare: $1000
        Group discount: 10% (5 pax)
        Insurance + Wi-Fi (7 nights)
        Promo: 10% off
        Tax: 12%
        """
        promo = PromoData(code="SAVE10", promo_type="PCT", value=Decimal("10"))
        services = [
            ServiceData("INSURANCE", "Travel Insurance", "PER_PASSENGER", Decimal("80.00")),
            ServiceData("WIFI", "Wi-Fi", "PER_PASSENGER_PER_NIGHT", Decimal("15.00")),
        ]
        bd = _calc(
            num_adults=2,
            child_ages=[2, 8, 15],
            duration_nights=7,
            selected_services=services,
            promo=promo,
        )
        # Adults: 2 * 1000 = 2000
        # Infant(2): 0
        # Child(8): 500
        # Teen(15): 750
        # Base total: 3250
        # Group discount 10%: 325 → 2925
        # Insurance: 5 * 80 = 400
        # WiFi: 5 * 15 * 7 = 525
        # Subtotal before promo: 2925 + 400 + 525 = 3850
        # Promo 10%: 385
        # Taxable: 3465
        # Tax 12%: 415.80
        # Total: 3880.80
        assert bd.base_fare_total == Decimal("3250.00")
        assert bd.group_discount_pct == Decimal("0.1000")
        assert bd.group_discount_amount == Decimal("325.00")
        assert bd.fare_after_group_discount == Decimal("2925.00")
        assert bd.extras_total == Decimal("925.00")
        assert bd.subtotal_before_promo == Decimal("3850.00")
        assert bd.promo_discount_amount == Decimal("385.00")
        assert bd.taxable_amount == Decimal("3465.00")
        assert bd.tax_amount == Decimal("415.80")
        assert bd.total == Decimal("3880.80")
