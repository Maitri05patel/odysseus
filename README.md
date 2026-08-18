# Odysseus Cruise Booking System

A fully featured cruise holiday booking API built for Odysseus Travel.
Customers can discover cruises, build a price quote, apply promo codes, and confirm a booking — all via a clean REST API.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Database](#database)
- [Seeding Data](#seeding-data)
- [Running the API](#running-the-api)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)
- [Pricing Rules](#pricing-rules)
- [Promo Code Rules](#promo-code-rules)
- [Documentation](#documentation)

---

## Features

- **Browse cruises** — list all available cruises with live capacity
- **Build a quote** — specify passengers (adults + children by age), optional services, and promo code; get a locked price back
- **Price lock guarantee** — the price shown is always the price charged, even if fares change before confirmation
- **Confirm a booking** — convert a quote to a permanent booking with a unique reference (`ODY-XXXXXXXX`)
- **Immutable booking records** — every booking stores a full price snapshot; the exact amount charged is reconstructable forever, long after fares change
- **Capacity enforcement** — a cruise can never be oversold under any circumstances
- **Promo code validation** — codes are checked for expiry, per-customer limits, total-use limits, and minimum spend — each failure returns a specific reason
- **Soft configuration** — fares, age bands, group discounts, tax rates, and promo codes are all stored in the database; changing them requires no code change or redeployment

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Web Framework | FastAPI 0.111 |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL (swap via `DATABASE_URL`) |
| Migrations | Alembic |
| Server | Uvicorn |
| Testing | pytest + httpx |

---

## Project Structure

```
odysseus/
├── main.py                    # FastAPI app entry point
├── requirements.txt           # Python dependencies
├── .env                       # Local environment config (not committed)
├── .env.example               # Template for .env
├── odysseus.db                # SQLite database (created on first run)
│
├── app/
│   ├── config.py              # Settings loaded from environment
│   ├── database.py            # SQLAlchemy engine + session factory
│   ├── models.py              # All ORM models (11 tables)
│   ├── pricing.py             # Stateless pricing engine (pure functions)
│   ├── booking.py             # Business logic + DB orchestration
│   └── api/
│       ├── schemas.py         # Pydantic request/response schemas
│       └── routes.py          # FastAPI route handlers
│
├── seed/
│   └── seed.py                # Database seed script
│
├── tests/
│   ├── conftest.py            # Shared fixtures (test DB, client)
│   ├── test_pricing.py        # Pure pricing logic unit tests
│   ├── test_promo.py          # Promo validation chain tests
│   ├── test_booking.py        # Booking service integration tests
│   └── test_api.py            # Full HTTP API tests
│
└── docs/
    ├── businessrequirements.md
    ├── technical_approach.md
    ├── unittestcase.md
    └── prompt.md
```

---

## Quick Start

### 1. Clone / navigate to the project

```powershell
cd c:\Users\Kishan\Desktop\PLACEMENT\odysseus
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment

Copy the example env file and edit if needed:

```powershell
copy .env.example .env
```

The defaults work out of the box for local SQLite development — no changes required.

### 4. Seed the database

```powershell
python -m seed.seed
```

This creates `odysseus.db` in the project root and populates it with:
- 5 cruises (including one sold-out cruise)
- 4 promo codes (including one expired code for testing)
- Fare bands, group discounts, optional services, tax rate

### 5. Start the server

```powershell
python -m uvicorn main:app --reload
```

The API is now running at **http://127.0.0.1:8000**

### 6. Open the interactive docs

Navigate to **http://127.0.0.1:8000/docs** in your browser to see the full Swagger UI — you can make live requests from there.

---

## Environment Variables

All settings live in `.env`. See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./odysseus.db` | Database connection string |
| `QUOTE_TTL_MINUTES` | `15` | How long a price quote stays valid |
| `DEBUG` | `true` | Enable SQL query logging |

**To use PostgreSQL in production**, change `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:password@host:5432/odysseus
```

No other changes needed — the application is database-agnostic.

---

## Database

### Location (development)

```
c:\Users\Kishan\Desktop\PLACEMENT\odysseus\odysseus.db
```

This is a standard SQLite file. You can inspect it with:
- [DB Browser for SQLite](https://sqlitebrowser.org/) (GUI)
- Any SQLite CLI: `sqlite3 odysseus.db`

### Schema overview

| Table | Purpose |
|---|---|
| `cruises` | Bookable cruise products |
| `customers` | Customer records |
| `fare_bands` | Child age bands → price fraction (soft config) |
| `group_discounts` | Passenger count → discount tier (soft config) |
| `optional_services` | Insurance, Wi-Fi, shore excursion (soft config) |
| `tax_rates` | Tax rate history with effective-from date (soft config) |
| `promo_codes` | Promotional codes with all rules |
| `pending_quotes` | Price-locked quotes (15-min TTL) |
| `bookings` | Confirmed bookings with immutable snapshot |
| `booking_passengers` | Per-passenger fare breakdown rows |
| `booking_extras` | Per-service line items |
| `promo_redemptions` | Audit trail of promo code usage |

---

## Seeding Data

To wipe the database and start fresh:

```powershell
# Delete existing DB
Remove-Item -Force odysseus.db -ErrorAction SilentlyContinue

# Re-seed
python -m seed.seed
```

### Seeded cruises

| Ship | Destination | Nights | Fare | Capacity Left |
|---|---|---|---|---|
| Wonder of the Sea | Caribbean | 7 | $1,200 | 12 |
| Celebrity Beyond | Mediterranean | 10 | $1,850 | 4 |
| Norwegian Prima | Alaska | 5 | $950 | 20 |
| Sky Princess | Northern Europe | 12 | $2,100 | 2 |
| MSC Seascape | Bahamas | 4 | $700 | 0 (Sold Out) |

### Seeded promo codes

| Code | Type | Value | Valid Period | Notes |
|---|---|---|---|---|
| `SUMMER10` | Percentage | 10% | Jun–Aug 2026 | Min spend $1,000 |
| `FIRST150` | Fixed | $150 off | Jan–Dec 2026 | Min spend $2,000 |
| `CREW25` | Percentage | 25% | Jan–Dec 2026 | Max 3 uses total |
| `WINTER5` | Percentage | 5% | Jan–Mar 2025 | **Expired** |

---

## Running the API

```powershell
# Development (auto-reload on file save)
python -m uvicorn main:app --reload

# Production
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

| URL | Description |
|---|---|
| http://127.0.0.1:8000/docs | Swagger UI (interactive) |
| http://127.0.0.1:8000/redoc | ReDoc documentation |
| http://127.0.0.1:8000/api/v1/health | Health check |

---

## API Reference

All endpoints are prefixed with `/api/v1`.

### Health

```
GET  /api/v1/health
```

### Customers

```
POST /api/v1/customers
```
Creates a customer or returns an existing one (upsert by email).

**Request body:**
```json
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Doe"
}
```

### Cruises

```
GET  /api/v1/cruises             — List all available (non-full, non-departed) cruises
GET  /api/v1/cruises/{id}        — Get a single cruise by ID
```

### Quotes

```
POST /api/v1/quotes
```
Calculates the full price and stores a 15-minute price-locked quote. Returns a token.

**Request body:**
```json
{
  "customer_id": 1,
  "cruise_id": 1,
  "num_adults": 2,
  "child_ages": [4, 9],
  "service_codes": ["INSURANCE", "WIFI"],
  "promo_code": "SUMMER10"
}
```

**Response includes:**
- `quote_token` — UUID to use at confirmation
- `total_amount` — exactly what will be charged
- `price_breakdown` — full itemised breakdown
- `expires_at` — quote expiry timestamp

### Bookings

```
POST /api/v1/bookings                      — Confirm a booking from a quote token
GET  /api/v1/bookings/{reference}          — Retrieve a booking by reference (e.g. ODY-A1B2C3D4)
```

**Confirm request body:**
```json
{
  "quote_token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Response includes:**
- `reference` — unique booking reference (`ODY-XXXXXXXX`)
- `total_charged` — amount charged (matches the quote exactly)
- `snapshot` — complete price breakdown frozen at booking time
- `passengers` — per-passenger fare breakdown
- `extras` — per-service line items

### Optional Services

```
GET  /api/v1/services            — List all available optional services and prices
```

---

## Running Tests

```powershell
# Run all 99 tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_pricing.py -v
python -m pytest tests/test_promo.py -v
python -m pytest tests/test_booking.py -v
python -m pytest tests/test_api.py -v

# Run with short error output
python -m pytest tests/ --tb=short
```

Tests use an isolated file-based SQLite database per test function — no shared state, no cleanup needed.

**Test breakdown (99 total):**

| File | Tests | Coverage |
|---|---|---|
| `test_pricing.py` | 40 | Passenger validation, child bands, group discounts, services, tax, full scenario |
| `test_promo.py` | 12 | All 5 promo validation failure reasons + positive cases |
| `test_booking.py` | 17 | Quote creation, booking confirmation, capacity, snapshots |
| `test_api.py` | 30 | Full HTTP request/response cycle for all endpoints |

---

## Pricing Rules

Prices are calculated in this exact order:

```
1.  Adult fare  = cruise.adult_fare × 1.00  (per adult)
2.  Child fare  = cruise.adult_fare × band_fraction  (by age band)
                  Age 0–4:   FREE  (0%)
                  Age 5–11:  50% of adult fare
                  Age 12–17: 75% of adult fare

3.  Base total  = sum of all passenger fares

4.  Group discount applied to base total:
                  1–2 passengers:  0%
                  3–4 passengers:  5%
                  5–6 passengers: 10%

5.  Extras added:
                  Insurance:        $80.00 per passenger
                  Wi-Fi:            $15.00 per passenger per night
                  Shore Excursion: $120.00 per passenger

6.  Subtotal    = (base total − group discount) + extras

7.  Promo discount applied to subtotal (if code provided)

8.  Tax (12%)   applied to (subtotal − promo discount)

9.  Total       = taxable amount + tax
```

**Booking limits:** Minimum 1 adult. Maximum 6 passengers total. Children must be aged 0–17.

---

## Promo Code Rules

A promo code is validated in this order. Each failure returns a distinct error code:

| Check | Error Code |
|---|---|
| Code does not exist or is inactive | `PROMO_NOT_FOUND` |
| Today is before `valid_from` | `PROMO_NOT_YET_VALID` |
| Today is after `valid_to` | `PROMO_EXPIRED` |
| Customer has already used it `max_per_customer` times | `PROMO_CUSTOMER_LIMIT_REACHED` |
| Code has been redeemed `max_total_uses` times globally | `PROMO_EXHAUSTED` |
| Booking subtotal is below `min_spend` | `PROMO_MIN_SPEND_NOT_MET` |

---

## Documentation

All documentation is in the `docs/` folder:

| File | Contents |
|---|---|
| [businessrequirements.md](docs/businessrequirements.md) | Full functional requirements, assumptions made, gaps and conflicts found in the original brief |
| [technical_approach.md](docs/technical_approach.md) | Data model rationale, architecture diagram, key design decisions, and what would be done differently with more time |
| [unittestcase.md](docs/unittestcase.md) | 100+ written test scenarios covering positive, negative, boundary, and failure cases |
| [prompt.md](docs/prompt.md) | Log of all prompts given during this project |

---

## Example Booking Flow

```
# 1. Create / retrieve a customer
POST /api/v1/customers
{ "email": "jane@example.com", "first_name": "Jane", "last_name": "Doe" }
→ { "id": 1, "email": "jane@example.com", ... }

# 2. Browse available cruises
GET /api/v1/cruises
→ [ { "id": 1, "name": "Wonder of the Sea", "adult_fare": "1200.00", ... }, ... ]

# 3. Request a price quote
POST /api/v1/quotes
{ "customer_id": 1, "cruise_id": 1, "num_adults": 2, "child_ages": [9],
  "service_codes": ["INSURANCE"], "promo_code": "SUMMER10" }
→ { "quote_token": "abc-123...", "total_amount": "2956.80",
    "price_breakdown": { ... }, "expires_at": "2026-08-18T19:00:00" }

# 4. Confirm the booking
POST /api/v1/bookings
{ "quote_token": "abc-123..." }
→ { "reference": "ODY-X7K2P9QR", "total_charged": "2956.80",
    "status": "CONFIRMED", "snapshot": { ... } }

# 5. Retrieve booking later (even after prices have changed)
GET /api/v1/bookings/ODY-X7K2P9QR
→ { "reference": "ODY-X7K2P9QR", "total_charged": "2956.80",
    "snapshot": { "adult_fare": "1200.00", "tax_rate": "0.12", ... } }
```