# Technical Approach Document
## Odysseus Cruise Booking System

---

## 1. Stack Overview

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| Language | **Python** | 3.11+ | User preference; excellent ecosystem for web APIs |
| Web Framework | **FastAPI** | 0.111 | Async-ready, Pydantic-native, auto OpenAPI docs, production-quality |
| ORM | **SQLAlchemy** | 2.0 | Mature, supports any DB, clean migration path |
| Validation | **Pydantic v2** | 2.7 | Ships with FastAPI; strict type enforcement, fast |
| Database (dev) | **SQLite** | – | Zero setup; no server required for local development |
| Database (prod) | **PostgreSQL** | 14+ | Swap via `DATABASE_URL` env var; no code changes |
| Migrations | **Alembic** | 1.13 | Schema versioning without code deploys |
| Server | **Uvicorn** | 0.29 | ASGI server; fast, production-grade |
| Testing | **pytest + httpx** | 8.2 / 0.27 | Standard Python test stack; httpx for async-compatible HTTP |
| Frontend | **HTML + CSS + JS** | – | Vanilla stack; no build step; dark-ocean responsive SPA |

---

## 2. Data Model

### Entity Relationship Overview

```
Customer ──< PendingQuote >── Cruise
Customer ──< Booking >── Cruise
Booking ──< BookingPassenger
Booking ──< BookingExtra
Booking ──< PromoRedemption >── PromoCode
PendingQuote ──── Booking

FareBand           (soft config)
GroupDiscount      (soft config)
OptionalService    (soft config)
TaxRate            (soft config)
```

### Table-by-Table Rationale

#### `cruises`
Stores the bookable product. `adult_fare` is the price at the time a cruise is listed — it is the live price used to generate quotes. `booked_count` tracks cumulative passenger count (not booking count) to enforce capacity.

> **Why track `booked_count` on the cruise rather than counting bookings?**
> Capacity is in passengers, not in bookings. A booking of 6 passengers consumes 6 slots. Summing passengers across booking rows on every capacity check would be slow and harder to lock.

#### `fare_bands`
Maps child age ranges to a fraction of the adult fare. Three rows cover the spec (0-4, 5-11, 12-17). Adding a new age band (e.g. if under-2 policy changes) is a DB insert, not a code change.

#### `group_discounts`
Three rows covering the 1-2 / 3-4 / 5-6 passenger tiers. Adding a 7-passenger tier (if capacity rules change) is a DB insert.

#### `optional_services`
The `price_type` column distinguishes `PER_PASSENGER` from `PER_PASSENGER_PER_NIGHT` — the pricing engine uses this to calculate correctly without hardcoding service logic.

#### `tax_rates`
Uses `effective_from` (timestamp). The pricing engine always picks the latest rate where `effective_from ≤ now`. This allows future rate changes to be pre-loaded and they activate automatically on schedule.

#### `pending_quotes`
A critical table. When a customer requests a quote:
1. The system calculates the full price breakdown.
2. Stores it as JSON in `price_breakdown` along with the `total_amount`.
3. Returns a UUID token to the customer.

When the customer confirms, the system retrieves the token, reads the stored `total_amount`, and charges that — **no recalculation**. This is how "price shown = price charged" is guaranteed.

`expires_at` is checked at confirmation time. An expired quote is rejected; a new quote must be requested. This prevents price lock indefinitely.

#### `bookings`
The core transaction record. `snapshot_json` is a complete denormalised copy of everything that produced the price:
- Cruise details (name, fare, duration) as they were at booking time
- Every passenger with their age band and fare charged
- Group discount tier, percentage, and amount
- Every extra with unit price at booking time
- Promo code details and discount amount
- Tax rate and tax amount
- Final total

This snapshot is written once and never updated. Even if the cruise fare doubles tomorrow, this booking will always show the original fare.

#### `booking_passengers` and `booking_extras`
Normalised detail rows linked to the booking. These could be reconstructed from `snapshot_json`, but having them as rows enables SQL reporting (e.g. "how many children travelled on cruise X?") without parsing JSON.

#### `promo_redemptions`
An append-only audit table. One row per confirmed booking that used a promo. Used to:
- Count per-customer usage for `max_per_customer` enforcement
- Count total usage for `max_total_uses` enforcement

Only confirmed bookings write a redemption row — an abandoned quote does not.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────┐
│                  HTTP Client                      │
│            (Browser / Postman / curl)             │
└───────────────────┬──────────────────────────────┘
                    │ HTTP/JSON
┌───────────────────▼──────────────────────────────┐
│              FastAPI Application                  │
│  app/api/routes.py  — request parsing,            │
│                       exception → HTTP mapping    │
│  app/api/schemas.py — Pydantic I/O models         │
└───────────────────┬──────────────────────────────┘
                    │ Python function calls
┌───────────────────▼──────────────────────────────┐
│            Booking Service (booking.py)           │
│  • DB queries & writes                            │
│  • Capacity locking (SELECT FOR UPDATE)           │
│  • Promo validation (ordered chain)               │
│  • Quote creation & confirmation                  │
└──────┬─────────────────────┬──────────────────────┘
       │ Pure fn calls        │ SQLAlchemy ORM
┌──────▼──────────┐   ┌──────▼──────────────────────┐
│  Pricing Engine │   │      Database               │
│  (pricing.py)   │   │  SQLite (dev)               │
│  Stateless pure │   │  PostgreSQL (prod)          │
│  functions      │   │                             │
└─────────────────┘   └─────────────────────────────┘
```

### Key Architecture Decisions

#### Decision 1: Stateless Pricing Engine
`pricing.py` contains pure functions — no DB calls, no global state. They take explicit parameters and return a `PriceBreakdown` dataclass.

**Why**: This makes pricing logic independently unit-testable (no DB fixtures, no mocking). The same functions produce the quote preview and the snapshot — no divergence possible.

#### Decision 2: Quote Token Pattern (Price Lock)
Rather than recalculating at confirm time, the quote stores the full breakdown and total in the DB. Confirmation reads the stored values.

**Why**: This is the only way to guarantee "price shown = price charged" across any gap in time between browsing and confirming, even if fares change in between. A recalculation at confirm time would be a latent bug waiting to happen.

#### Decision 3: Soft Config in DB Tables
Fare bands, group discounts, optional services, and tax rates are database rows, not Python constants.

**Why**: The brief explicitly requires that changing these must not require a code change or redeployment. Any approach that hardcodes them (even in config files) would require at minimum a restart.

#### Decision 4: Row-Level Lock at Confirm
When confirming a booking, `SELECT ... FOR UPDATE` is issued on the cruise row inside the same transaction as the capacity check and `INSERT`.

**Why**: Without this, two simultaneous confirmations for a nearly-full cruise could both pass the capacity check and both succeed, overselling the cruise. The lock serialises these operations.

> Note: SQLite does not support row-level locks (it uses file-level locking). The `with_for_update()` call is a no-op on SQLite but activates correctly on PostgreSQL. For production, PostgreSQL must be used to get the benefit.

#### Decision 5: Immutable Snapshot
`snapshot_json` stores a complete copy of every pricing input. It is never updated after creation.

**Why**: Relational joins across config tables would fail once config changes (e.g., an age band is updated). The snapshot is the only way to reconstruct the exact price that was charged, regardless of what changed afterwards.

#### Decision 6: Promo Validation in Ordered Chain
Promo validation is a sequence of explicit checks, each with a distinct error code.

**Why**: Each failure reason is distinct from a customer's perspective. "Expired" is different from "already used" is different from "minimum spend not met." Collapsing them into a single "invalid code" message would be a poor user experience and is explicitly prohibited by the requirements.

---

## 4. Pricing Logic (Detailed)

```
base_fare_total = Σ (adult_fare × band_fraction) for each passenger
group_discount_amount = base_fare_total × group_discount_pct
fare_after_group_discount = base_fare_total − group_discount_amount
extras_total = Σ line_total for each selected service
subtotal_before_promo = fare_after_group_discount + extras_total
promo_discount_amount = subtotal_before_promo × promo_pct   [if PCT]
                      = min(promo_fixed, subtotal_before_promo) [if FIXED]
taxable_amount = subtotal_before_promo − promo_discount_amount
tax_amount = taxable_amount × 0.12
total = taxable_amount + tax_amount
```

**Tax application point rationale**: Tax is applied to what the customer actually pays (after all discounts). This matches standard VAT/sales-tax practice in most jurisdictions — you do not charge tax on a discount.

---

## 5. What Would Be Done Differently With More Time

| Area | What Was Done | What Would Be Improved |
|---|---|---|
| **Authentication** | Email-only customer identification | JWT / OAuth2 authentication so a customer can only see and confirm their own quotes |
| **Concurrency** | SQLite (file-level locking), FOR UPDATE on PostgreSQL | Full PostgreSQL in CI with concurrent booking tests to validate the lock under load |
| **Alembic migrations** | Table creation via `Base.metadata.create_all` at startup | Full Alembic migration history from day one, so schema changes are tracked and reversible |
| **API versioning** | `/api/v1` prefix | Proper versioning strategy with deprecation headers |
| **Error handling** | Basic exception-to-HTTP mapping | RFC 7807 Problem Details format for all errors |
| **Observability** | `echo=DEBUG` SQL logging only | Structured logging (structlog), request IDs, distributed tracing |
| **Rate limiting** | None | Per-IP and per-customer rate limits on quote endpoint to prevent pricing scraping |
| **Async DB** | Synchronous SQLAlchemy | `asyncpg` + async SQLAlchemy for true async performance under load |
| **Admin interface** | None | Simple admin API / Django-admin-style UI for managing cruises, promos, and config |
| **Cancellation flow** | `status` field exists but not implemented | Full cancellation with capacity release and refund calculation |
| **Email notifications** | None | Booking confirmation email with PDF receipt containing the full price snapshot |
| **Containerisation** | None | Docker + docker-compose for zero-friction local setup |
| **Frontend** | Browser-based SPA (HTML/CSS/JS) with 4-step booking wizard, live fare estimate, quote + confirm flow, and booking lookup. Served separately via `python -m http.server 5500`. | Production: bundle with Vite/Next.js, serve via CDN or same origin with a reverse proxy. |

---

## 6. Project File Map

```
odysseus/
├── main.py                    # FastAPI app entry point
├── requirements.txt
├── .env / .env.example
├── odysseus.db                # SQLite dev database
├── app/
│   ├── config.py              # Settings from env vars
│   ├── database.py            # Engine + session factory
│   ├── models.py              # All SQLAlchemy ORM models
│   ├── pricing.py             # Pure pricing functions (no DB)
│   ├── booking.py             # Business logic + DB orchestration
│   └── api/
│       ├── schemas.py         # Pydantic request/response models
│       └── routes.py          # FastAPI route handlers
├── frontend/
│   ├── index.html             # SPA shell — nav, hero, wizard, lookup
│   ├── style.css              # Dark-ocean design system + all component styles
│   └── app.js                 # All JS: state machine, API calls, DOM rendering
├── seed/
│   └── seed.py                # DB seed script
├── tests/
│   ├── conftest.py            # Fixtures (file-based SQLite per test, test client)
│   ├── test_pricing.py        # Pure pricing logic tests
│   ├── test_promo.py          # Promo validation chain tests
│   ├── test_booking.py        # Booking service integration tests
│   └── test_api.py            # Full HTTP API tests
└── docs/
    ├── BusinessRequirements.md
    ├── TechnicalApproach.md    (this document)
    ├── UnitTestCases.md
    └── Prompts.md
```

## 7. Frontend Architecture

The UI is a single-page application (SPA) with no build step — pure HTML, CSS, and vanilla JavaScript.

```
Browser (http://localhost:5500)
         │
         │  fetch() calls to http://127.0.0.1:8001/api/v1
         │
    FastAPI backend
         │
    SQLite (odysseus.db)
```

### State machine

`app.js` holds a single `state` object:

```js
{
  cruises: [],        // loaded from /api/v1/cruises
  cruise: null,       // selected cruise object
  adults: 2,
  children: 0,
  childAges: [],
  selectedExtras: [],
  promoCode: '',
  promoApplied: false,
  customer: null,     // returned by POST /api/v1/customers
  quote: null,        // returned by POST /api/v1/quotes
  quoteTimer: null,   // setInterval handle for 15-min countdown
}
```

### Wizard steps

| Step | Description | API call |
|---|---|---|
| 1 | Select adults, children, child ages | none (local) |
| 2 | Choose extras, enter promo code | none (local) |
| 3 | Enter name and email; click "Get My Quote" | `POST /customers` then `POST /quotes` |
| 4 | Review locked quote; click "Confirm & Book" | `POST /bookings` |

A live estimated fare updates on Step 2 as extras are toggled. The authoritative price comes from the backend quote.
