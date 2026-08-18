"""
API (HTTP) integration tests.
Tests the full request/response cycle through FastAPI routes.
"""

import pytest
from decimal import Decimal

from tests.conftest import seed_config, make_cruise, make_customer, make_promo
from app.models import PromoType


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestCustomerEndpoints:

    def test_create_customer(self, client):
        r = client.post("/api/v1/customers", json={
            "email": "jane@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "jane@example.com"
        assert "id" in data

    def test_create_customer_returns_existing_on_duplicate_email(self, client):
        payload = {"email": "jane@example.com", "first_name": "Jane", "last_name": "Doe"}
        r1 = client.post("/api/v1/customers", json=payload)
        r2 = client.post("/api/v1/customers", json=payload)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]

    def test_invalid_email_rejected(self, client):
        r = client.post("/api/v1/customers", json={
            "email": "not-an-email",
            "first_name": "Jane",
            "last_name": "Doe",
        })
        assert r.status_code == 422


class TestCruiseEndpoints:

    def test_list_cruises_returns_array(self, client, db):
        seed_config(db)
        make_cruise(db, adult_fare=Decimal("1000.00"))
        r = client.get("/api/v1/cruises")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_cruise_has_required_fields(self, client, db):
        seed_config(db)
        make_cruise(db)
        r = client.get("/api/v1/cruises")
        cruise = r.json()[0]
        assert "id" in cruise
        assert "name" in cruise
        assert "adult_fare" in cruise
        assert "available_capacity" in cruise
        assert "departure_date" in cruise

    def test_full_cruise_excluded_from_list(self, client, db):
        seed_config(db)
        make_cruise(db, capacity=5, booked=5)  # full
        r = client.get("/api/v1/cruises")
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_get_cruise_by_id(self, client, db):
        seed_config(db)
        cruise = make_cruise(db)
        r = client.get(f"/api/v1/cruises/{cruise.id}")
        assert r.status_code == 200
        assert r.json()["id"] == cruise.id

    def test_get_nonexistent_cruise_404(self, client, db):
        seed_config(db)
        r = client.get("/api/v1/cruises/99999")
        assert r.status_code == 404


class TestQuoteEndpoints:

    def _setup(self, db):
        seed_config(db)
        cruise = make_cruise(db, adult_fare=Decimal("1000.00"))
        customer_r = make_customer(db)
        return cruise, customer_r

    def test_create_quote_returns_token(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id,
            "cruise_id": cruise.id,
            "num_adults": 2,
            "child_ages": [],
            "service_codes": [],
            "promo_code": None,
        })
        assert r.status_code == 201
        data = r.json()
        assert "quote_token" in data
        assert "total_amount" in data
        assert "breakdown" in data
        assert "expires_at" in data

    def test_quote_breakdown_contains_all_fields(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 1, "child_ages": [], "service_codes": [], "promo_code": None,
        })
        bd = r.json()["breakdown"]
        required_fields = [
            "adult_fare", "base_fare_total", "group_discount_pct",
            "group_discount_amount", "extras_total", "subtotal_before_promo",
            "promo_discount_amount", "tax_rate_pct", "tax_amount", "total"
        ]
        for field in required_fields:
            assert field in bd, f"Missing field: {field}"

    def test_quote_with_promo_reduces_total(self, client, db):
        cruise, customer = self._setup(db)
        make_promo(db, code="SAVE10")

        r_no_promo = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 1, "child_ages": [], "service_codes": [], "promo_code": None,
        })
        r_with_promo = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 1, "child_ages": [], "service_codes": [], "promo_code": "SAVE10",
        })
        assert Decimal(r_with_promo.json()["total_amount"]) < Decimal(r_no_promo.json()["total_amount"])

    def test_quote_with_invalid_promo_returns_422(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 1, "child_ages": [], "service_codes": [], "promo_code": "BADCODE",
        })
        assert r.status_code == 422
        assert "PROMO_NOT_FOUND" in str(r.json())

    def test_quote_with_services(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 2, "child_ages": [], "service_codes": ["INSURANCE", "WIFI"],
            "promo_code": None,
        })
        assert r.status_code == 201
        extras = r.json()["breakdown"]["extras"]
        codes = [e["service_code"] for e in extras]
        assert "INSURANCE" in codes
        assert "WIFI" in codes

    def test_quote_with_children_of_different_bands(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 1, "child_ages": [2, 8, 15], "service_codes": [], "promo_code": None,
        })
        assert r.status_code == 201
        fares = r.json()["breakdown"]["passenger_fares"]
        child_fares = [p["fare"] for p in fares if p["passenger_type"] == "CHILD"]
        assert "0.00" in child_fares  # infant

    def test_quote_full_cruise_returns_409(self, client, db):
        seed_config(db)
        cruise = make_cruise(db, capacity=1, booked=1)
        customer = make_customer(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 1, "child_ages": [], "service_codes": [], "promo_code": None,
        })
        assert r.status_code == 409

    def test_quote_zero_adults_returns_422(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 0, "child_ages": [], "service_codes": [], "promo_code": None,
        })
        assert r.status_code == 422

    def test_quote_too_many_passengers_returns_422(self, client, db):
        cruise, customer = self._setup(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": 4, "child_ages": [5, 8, 12], "service_codes": [], "promo_code": None,
        })
        assert r.status_code == 422  # 7 passengers > max 6


class TestBookingEndpoints:

    def _get_quote_token(self, client, db, num_adults=2, child_ages=None, service_codes=None):
        seed_config(db)
        cruise = make_cruise(db, adult_fare=Decimal("1000.00"))
        customer = make_customer(db)
        r = client.post("/api/v1/quotes", json={
            "customer_id": customer.id, "cruise_id": cruise.id,
            "num_adults": num_adults, "child_ages": child_ages or [],
            "service_codes": service_codes or [], "promo_code": None,
        })
        assert r.status_code == 201
        return r.json()["quote_token"], customer, cruise

    def test_confirm_booking_returns_reference(self, client, db):
        token, _, _ = self._get_quote_token(client, db)
        r = client.post("/api/v1/bookings", json={"quote_token": token})
        assert r.status_code == 201
        data = r.json()
        assert data["reference"].startswith("ODY-")
        assert data["status"] == "CONFIRMED"

    def test_confirm_booking_total_matches_quote(self, client, db):
        token, _, _ = self._get_quote_token(client, db)
        # Get quote amount first
        from app.models import PendingQuote
        from sqlalchemy import select
        quote = db.execute(select(PendingQuote).where(PendingQuote.id == token)).scalar_one()
        quote_amount = str(quote.total_amount)

        r = client.post("/api/v1/bookings", json={"quote_token": token})
        assert r.status_code == 201
        assert r.json()["total_charged"] == quote_amount

    def test_confirm_booking_snapshot_present(self, client, db):
        token, _, _ = self._get_quote_token(client, db)
        r = client.post("/api/v1/bookings", json={"quote_token": token})
        assert "snapshot" in r.json()
        snap = r.json()["snapshot"]
        assert "adult_fare" in snap
        assert "confirmed_at" in snap

    def test_reusing_same_token_returns_409(self, client, db):
        token, _, _ = self._get_quote_token(client, db)
        r1 = client.post("/api/v1/bookings", json={"quote_token": token})
        r2 = client.post("/api/v1/bookings", json={"quote_token": token})
        assert r1.status_code == 201
        assert r2.status_code == 409

    def test_invalid_token_returns_404(self, client, db):
        seed_config(db)
        r = client.post("/api/v1/bookings", json={"quote_token": "00000000-0000-0000-0000-000000000000"})
        assert r.status_code == 404

    def test_get_booking_by_reference(self, client, db):
        token, _, _ = self._get_quote_token(client, db)
        confirm_r = client.post("/api/v1/bookings", json={"quote_token": token})
        reference = confirm_r.json()["reference"]

        r = client.get(f"/api/v1/bookings/{reference}")
        assert r.status_code == 200
        assert r.json()["reference"] == reference

    def test_get_nonexistent_booking_returns_404(self, client, db):
        seed_config(db)
        r = client.get("/api/v1/bookings/ODY-NOTREAL")
        assert r.status_code == 404

    def test_booking_passengers_included(self, client, db):
        token, _, _ = self._get_quote_token(client, db, num_adults=2, child_ages=[5])
        r = client.post("/api/v1/bookings", json={"quote_token": token})
        passengers = r.json()["passengers"]
        assert len(passengers) == 3  # 2 adults + 1 child

    def test_booking_extras_included(self, client, db):
        token, _, _ = self._get_quote_token(client, db, num_adults=1, service_codes=["INSURANCE"])
        r = client.post("/api/v1/bookings", json={"quote_token": token})
        extras = r.json()["extras"]
        assert len(extras) == 1
        assert extras[0]["service_code"] == "INSURANCE"
