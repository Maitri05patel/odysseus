"""
Database seed script.

Populates the database with:
  - Soft-config: fare bands, group discounts, optional services, tax rate
  - Sample cruises (placeholder data — replace with real data when provided)
  - Sample promo codes
  - Sample customers

Run with:  python -m seed.seed
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.database import SessionLocal, engine
from app.models import (
    Base, FareBand, GroupDiscount, OptionalService, TaxRate,
    Cruise, Customer, PromoCode, PromoType, PriceType
)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ----------------------------------------------------------------
        # Guard — skip if already seeded
        # ----------------------------------------------------------------
        if db.query(Cruise).count() > 0:
            print("Database already seeded. Skipping.")
            return

        print("Seeding database...")

        # ----------------------------------------------------------------
        # Fare bands (child pricing — soft config)
        # ----------------------------------------------------------------
        fare_bands = [
            FareBand(min_age=0,  max_age=4,  fraction_of_adult=Decimal("0.0000"), label="Infant (0-4, Free)"),
            FareBand(min_age=5,  max_age=11, fraction_of_adult=Decimal("0.5000"), label="Child (5-11, 50%)"),
            FareBand(min_age=12, max_age=17, fraction_of_adult=Decimal("0.7500"), label="Teen (12-17, 75%)"),
        ]
        db.add_all(fare_bands)

        # ----------------------------------------------------------------
        # Group discounts (soft config)
        # ----------------------------------------------------------------
        group_discounts = [
            GroupDiscount(min_passengers=1, max_passengers=2, discount_pct=Decimal("0.0000")),
            GroupDiscount(min_passengers=3, max_passengers=4, discount_pct=Decimal("0.0500")),
            GroupDiscount(min_passengers=5, max_passengers=6, discount_pct=Decimal("0.1000")),
        ]
        db.add_all(group_discounts)

        # ----------------------------------------------------------------
        # Optional services (soft config)
        # ----------------------------------------------------------------
        services = [
            OptionalService(
                code="INSURANCE",
                name="Travel Insurance",
                price_type=PriceType.PER_PASSENGER,
                unit_price=Decimal("80.00"),
                is_active=True,
            ),
            OptionalService(
                code="WIFI",
                name="Wi-Fi Package",
                price_type=PriceType.PER_PASSENGER_PER_NIGHT,
                unit_price=Decimal("15.00"),
                is_active=True,
            ),
            OptionalService(
                code="SHORE_EXCURSION",
                name="Shore Excursion",
                price_type=PriceType.PER_PASSENGER,
                unit_price=Decimal("120.00"),
                is_active=True,
            ),
        ]
        db.add_all(services)

        # ----------------------------------------------------------------
        # Tax rate (soft config)
        # ----------------------------------------------------------------
        db.add(TaxRate(
            rate_pct=Decimal("0.1200"),   # 12%
            effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            label="Standard 12% Tax",
        ))

        # ----------------------------------------------------------------
        # Cruises  — real data provided by Odysseus
        #
        # "Capacity Left" from the brief = seats still available.
        # We model this as: total_capacity = capacity_left, booked_count = 0
        # EXCEPT for MSC Seascape which has 0 remaining → set as fully booked.
        # ----------------------------------------------------------------
        cruises = [
            Cruise(
                name="Wonder of the Sea",
                destination="Caribbean",
                departure_date=date(2026, 9, 15),
                duration_nights=7,
                adult_fare=Decimal("1200.00"),
                total_capacity=12,
                booked_count=0,
                is_active=True,
                description="Royal Caribbean — Wonder of the Sea sailing the Caribbean.",
            ),
            Cruise(
                name="Celebrity Beyond",
                destination="Mediterranean",
                departure_date=date(2026, 10, 1),
                duration_nights=10,
                adult_fare=Decimal("1850.00"),
                total_capacity=4,
                booked_count=0,
                is_active=True,
                description="Celebrity Cruises — Celebrity Beyond through the Mediterranean.",
            ),
            Cruise(
                name="Norwegian Prima",
                destination="Alaska",
                departure_date=date(2026, 8, 20),
                duration_nights=5,
                adult_fare=Decimal("950.00"),
                total_capacity=20,
                booked_count=0,
                is_active=True,
                description="Norwegian Cruise Line — Norwegian Prima exploring Alaska.",
            ),
            Cruise(
                name="Sky Princess",
                destination="Northern Europe",
                departure_date=date(2026, 11, 5),
                duration_nights=12,
                adult_fare=Decimal("2100.00"),
                total_capacity=2,
                booked_count=0,
                is_active=True,
                description="Princess Cruises — Sky Princess through Northern Europe.",
            ),
            Cruise(
                name="MSC Seascape",
                destination="Bahamas",
                departure_date=date(2026, 9, 1),
                duration_nights=4,
                adult_fare=Decimal("700.00"),
                total_capacity=100,
                booked_count=100,   # 0 capacity left — fully booked
                is_active=True,
                description="MSC Cruises — MSC Seascape to the Bahamas. SOLD OUT.",
            ),
        ]
        db.add_all(cruises)

        # ----------------------------------------------------------------
        # Customers  *** PLACEHOLDER — replace with your real customer data ***
        # ----------------------------------------------------------------
        customers = [
            Customer(email="alice@example.com",  first_name="Alice",  last_name="Johnson"),
            Customer(email="bob@example.com",    first_name="Bob",    last_name="Smith"),
            Customer(email="carol@example.com",  first_name="Carol",  last_name="Williams"),
        ]
        db.add_all(customers)

        # ----------------------------------------------------------------
        # Promo codes — real data provided by Odysseus
        #
        # SUMMER10 : 10% off, valid Jun-Aug 2026, max 100 uses, 1 per customer, min spend $1000
        # FIRST150 : $150 fixed off, valid 2026, max 500 uses, 1 per customer, min spend $2000
        # CREW25   : 25% off, valid 2026, max 3 uses total, 3 per customer, no min spend
        # WINTER5  : 5% off, expired Mar 2025 — left active for testing expired-code behaviour
        # ----------------------------------------------------------------
        promos = [
            PromoCode(
                code="SUMMER10",
                promo_type=PromoType.PCT,
                value=Decimal("10"),
                valid_from=date(2026, 6, 1),
                valid_to=date(2026, 8, 31),
                max_total_uses=100,
                max_per_customer=1,
                min_spend=Decimal("1000.00"),
                is_active=True,
                description="10% off bookings over $1000 — Summer 2026 promotion",
            ),
            PromoCode(
                code="FIRST150",
                promo_type=PromoType.FIXED,
                value=Decimal("150"),
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
                max_total_uses=500,
                max_per_customer=1,
                min_spend=Decimal("2000.00"),
                is_active=True,
                description="$150 off bookings over $2000",
            ),
            PromoCode(
                code="CREW25",
                promo_type=PromoType.PCT,
                value=Decimal("25"),
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
                max_total_uses=3,
                max_per_customer=3,
                min_spend=Decimal("0.00"),
                is_active=True,
                description="25% off — crew/staff discount (limited to 3 total redemptions)",
            ),
            PromoCode(
                code="WINTER5",
                promo_type=PromoType.PCT,
                value=Decimal("5"),
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 3, 31),   # EXPIRED — kept for testing
                max_total_uses=1000,
                max_per_customer=5,
                min_spend=Decimal("0.00"),
                is_active=True,
                description="5% Winter 2025 promotion — EXPIRED",
            ),
        ]
        db.add_all(promos)

        db.commit()
        print("[OK] Seed complete.")
        print("  Cruises:       ", len(cruises))
        print("  Customers:     ", len(customers))
        print("  Promo codes:   ", len(promos))
        print("  Fare bands:    ", len(fare_bands))
        print("  Group discounts:", len(group_discounts))
        print("  Services:      ", len(services))

    except Exception as e:
        db.rollback()
        print(f"[FAILED] Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
