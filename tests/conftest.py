"""
Shared pytest fixtures.

Uses a temporary file-based SQLite database so tests are:
  - Isolated (each test function gets a fresh DB file)
  - Thread-safe (file-based SQLite works with FastAPI's thread pool)
  - Dependency-injected (FastAPI's get_db is overridden)

NOTE: We cannot use SQLite :memory: here because FastAPI routes run in a
worker thread (anyio thread pool). An in-memory SQLite connection is NOT
shared across threads — each thread sees an empty DB. A temp file is shared.
"""

import os
import uuid
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models import (
    Base, FareBand, GroupDiscount, OptionalService, TaxRate,
    Cruise, Customer, PromoCode, PromoType, PriceType
)
from app.database import get_db
from main import app


# ---------------------------------------------------------------------------
# File-based test database (unique per test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_engine(tmp_path):
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db(db_engine) -> Session:
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def seed_config(db: Session):
    """Minimal soft-config needed for any pricing test."""
    db.add_all([
        FareBand(min_age=0,  max_age=4,  fraction_of_adult=Decimal("0.0000"), label="Infant"),
        FareBand(min_age=5,  max_age=11, fraction_of_adult=Decimal("0.5000"), label="Child"),
        FareBand(min_age=12, max_age=17, fraction_of_adult=Decimal("0.7500"), label="Teen"),
    ])
    db.add_all([
        GroupDiscount(min_passengers=1, max_passengers=2, discount_pct=Decimal("0.0000")),
        GroupDiscount(min_passengers=3, max_passengers=4, discount_pct=Decimal("0.0500")),
        GroupDiscount(min_passengers=5, max_passengers=6, discount_pct=Decimal("0.1000")),
    ])
    db.add_all([
        OptionalService(code="INSURANCE",      name="Travel Insurance", price_type=PriceType.PER_PASSENGER,          unit_price=Decimal("80.00")),
        OptionalService(code="WIFI",           name="Wi-Fi Package",    price_type=PriceType.PER_PASSENGER_PER_NIGHT, unit_price=Decimal("15.00")),
        OptionalService(code="SHORE_EXCURSION",name="Shore Excursion",  price_type=PriceType.PER_PASSENGER,          unit_price=Decimal("120.00")),
    ])
    db.add(TaxRate(
        rate_pct=Decimal("0.1200"),
        effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        label="12%",
    ))
    db.commit()


def make_cruise(db: Session, adult_fare=Decimal("1000.00"), capacity=50, booked=0,
                departure=None, nights=7) -> Cruise:
    c = Cruise(
        name="Test Cruise",
        destination="Somewhere",
        departure_date=departure or date(2027, 6, 1),
        duration_nights=nights,
        adult_fare=adult_fare,
        total_capacity=capacity,
        booked_count=booked,
        is_active=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def make_customer(db: Session, email="test@example.com") -> Customer:
    c = Customer(email=email, first_name="Test", last_name="User")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def make_promo(db: Session, **kwargs) -> PromoCode:
    defaults = dict(
        code="TEST10",
        promo_type=PromoType.PCT,
        value=Decimal("10"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2099, 12, 31),
        max_total_uses=None,
        max_per_customer=None,
        min_spend=Decimal("0.00"),
        is_active=True,
    )
    defaults.update(kwargs)
    p = PromoCode(**defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# FastAPI test client with DB override
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client(db) -> TestClient:
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
