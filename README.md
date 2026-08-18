# Odysseus Cruise Booking System

A full-stack cruise holiday booking system built for **Odysseus
Travel**.

Odysseus allows customers to discover available cruises, select
passengers and optional extras, generate a price-locked quote, apply
promo codes, and confirm a booking through a REST API and browser-based
frontend.

## Table of Contents

-   [Features](#features)
-   [Tech Stack](#tech-stack)
-   [Project Structure](#project-structure)
-   [Quick Start](#quick-start)
-   [Environment Variables](#environment-variables)
-   [Database](#database)
-   [Seeding Data](#seeding-data)
-   [Running the Backend API](#running-the-backend-api)
-   [Running the Frontend](#running-the-frontend)
-   [API Reference](#api-reference)
-   [Booking Flow](#booking-flow)
-   [Pricing Rules](#pricing-rules)
-   [Promo Code Rules](#promo-code-rules)
-   [Running Tests](#running-tests)
-   [Troubleshooting](#troubleshooting)
-   [Documentation](#documentation)

## Features

### Customer-facing booking flow

-   **Browse cruises** --- view available cruises with destination,
    duration, departure date, fare, and capacity.
-   **Select passengers** --- choose adults and children and enter child
    ages.
-   **Optional extras** --- Travel Insurance (\$80/passenger), Wi-Fi
    (\$15/passenger/night), and Shore Excursion (\$120/passenger).
-   **Live estimated fare** --- the frontend updates the estimated
    pre-tax fare as extras are selected.
-   **Promo codes** --- apply eligible promotional codes before
    requesting a quote.
-   **Get My Quote** --- sends the booking details to the FastAPI
    backend and displays the backend-calculated final quote.
-   **Price lock** --- quotes remain locked for 15 minutes.
-   **Review and pay** --- review the final itemised quote before
    confirmation.
-   **Booking confirmation** --- confirmed bookings receive a unique
    reference such as `ODY-A1B2C3D4`.

### Backend capabilities

-   Browse available cruises
-   Customer creation/upsert by email
-   Full passenger fare calculation
-   Child age-band pricing
-   Group discounts
-   Optional service pricing
-   Promo-code validation
-   Tax calculation
-   15-minute quote locking
-   Capacity enforcement
-   Immutable booking price snapshots
-   Booking retrieval by reference
-   REST API with Swagger/OpenAPI documentation

## Tech Stack

  Layer                    Technology
  ------------------------ -----------------------
  Language                 Python 3.11+
  Web Framework            FastAPI
  ORM                      SQLAlchemy 2.0
  Validation               Pydantic v2
  Database (development)   SQLite
  Database (production)    PostgreSQL
  Migrations               Alembic
  API Server               Uvicorn
  Testing                  pytest + httpx
  Frontend                 HTML, CSS, JavaScript
  Frontend Dev Server      Python `http.server`

## Project Structure

``` text
odysseus/
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── odysseus.db
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── pricing.py
│   ├── booking.py
│   └── api/
│       ├── __init__.py
│       ├── schemas.py
│       └── routes.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── seed/
│   ├── __init__.py
│   └── seed.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_booking.py
│   ├── test_pricing.py
│   └── test_promo.py
└── docs/
    ├── BusinessRequirements.md
    ├── TechnicalApproach.md
    └── UnitTestCases.md
```

## Quick Start

### 1. Navigate to the project

``` powershell
cd "C:\Users\Kishan\Desktop\PLACEMENT\odysseus"
```

### 2. Activate the virtual environment

``` powershell
.venv\Scripts\Activate.ps1
```

If it does not exist:

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

``` powershell
pip install -r requirements.txt
```

### 4. Configure environment

``` powershell
copy .env.example .env
```

The default local configuration uses SQLite.

## Database

The development database is:

``` text
odysseus.db
```

Default:

``` env
DATABASE_URL=sqlite:///./odysseus.db
```

### Main tables

  Table                  Purpose
  ---------------------- -------------------------------------
  `cruises`              Bookable cruise products
  `customers`            Customer records
  `fare_bands`           Child age bands and price fractions
  `group_discounts`      Passenger-count discount tiers
  `optional_services`    Insurance, Wi-Fi, excursions
  `tax_rates`            Tax rate history
  `promo_codes`          Promotional codes and rules
  `pending_quotes`       Price-locked quotes
  `bookings`             Confirmed bookings
  `booking_passengers`   Passenger fare snapshots
  `booking_extras`       Extra/service line items
  `promo_redemptions`    Promo-code usage audit trail

## Seeding Data

Create/populate the database:

``` powershell
python -m seed.seed
```

Reset the database:

``` powershell
Remove-Item -Force odysseus.db -ErrorAction SilentlyContinue
python -m seed.seed
```

### Seeded cruises

  Ship                Destination         Nights      Fare   Capacity Left
  ------------------- ----------------- -------- --------- ---------------
  Wonder of the Sea   Caribbean                7   \$1,200              12
  Celebrity Beyond    Mediterranean           10   \$1,850               4
  Norwegian Prima     Alaska                   5     \$950              20
  Sky Princess        Northern Europe         12   \$2,100               2
  MSC Seascape        Bahamas                  4     \$700    0 (Sold Out)

### Seeded promo codes

  Code         Type               Value Valid Period    Notes
  ------------ ------------ ----------- --------------- -----------------------
  `SUMMER10`   Percentage           10% Jun--Aug 2026   Minimum spend \$1,000
  `FIRST150`   Fixed          \$150 off Jan--Dec 2026   Minimum spend \$2,000
  `CREW25`     Percentage           25% Jan--Dec 2026   Maximum 3 uses total
  `WINTER5`    Percentage            5% Jan--Mar 2025   Expired

## Running the Backend API

From the project root:

``` powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

The backend is available at:

``` text
http://127.0.0.1:8001
```

The included frontend is configured to call:

``` text
http://127.0.0.1:8001/api/v1
```

### Useful backend URLs

  URL                                      Description
  ---------------------------------------- ----------------
  `http://127.0.0.1:8001/`                 API root
  `http://127.0.0.1:8001/docs`             Swagger UI
  `http://127.0.0.1:8001/redoc`            ReDoc
  `http://127.0.0.1:8001/api/v1/health`    Health check
  `http://127.0.0.1:8001/api/v1/cruises`   Cruise listing

## Running the Frontend

Open a **second terminal**:

``` powershell
cd "C:\Users\Kishan\Desktop\PLACEMENT\odysseus\frontend"
python -m http.server 5500
```

Then open:

``` text
http://localhost:5500
```

Keep both servers running:

**Terminal 1 --- Backend**

``` powershell
cd "C:\Users\Kishan\Desktop\PLACEMENT\odysseus"
.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

**Terminal 2 --- Frontend**

``` powershell
cd "C:\Users\Kishan\Desktop\PLACEMENT\odysseus\frontend"
python -m http.server 5500
```

### Application architecture

``` text
Browser
   │
   │ http://localhost:5500
   ▼
Frontend
   │
   │ HTTP API requests
   ▼
FastAPI
http://127.0.0.1:8001
   │
   ▼
SQLite
odysseus.db
```

## API Reference

All API endpoints use the `/api/v1` prefix.

### Health

``` http
GET /api/v1/health
```

### Customers

``` http
POST /api/v1/customers
```

Request:

``` json
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Doe"
}
```

### Cruises

``` http
GET /api/v1/cruises
GET /api/v1/cruises/{id}
```

### Optional Services

``` http
GET /api/v1/services
```

### Quotes

``` http
POST /api/v1/quotes
```

Request:

``` json
{
  "customer_id": 1,
  "cruise_id": 1,
  "num_adults": 2,
  "child_ages": [4, 9],
  "service_codes": ["INSURANCE", "WIFI"],
  "promo_code": "SUMMER10"
}
```

Response includes:

-   `quote_token`
-   `total_amount`
-   `price_breakdown`
-   `expires_at`

### Bookings

Confirm:

``` http
POST /api/v1/bookings
```

Request:

``` json
{
  "quote_token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Retrieve:

``` http
GET /api/v1/bookings/{reference}
```

Response includes the booking reference, charged amount, status, price
snapshot, passengers, and extras.

## Booking Flow

The frontend uses four steps:

``` text
1. Passengers
      ↓
2. Extras
      ↓
3. Your Details
      ↓
4. Review & Pay
```

### Step 1 --- Passengers

The customer selects:

-   Adults
-   Children
-   Child ages

### Step 2 --- Extras

The customer can select optional services and enter a promo code.

The frontend shows a live **estimated pre-tax fare** as extras are
selected.

### Step 3 --- Your Details

The customer enters first name, last name, and email.

The frontend creates/retrieves the customer using:

``` http
POST /api/v1/customers
```

### Step 4 --- Review & Pay

**Get My Quote** sends the complete booking request to:

``` http
POST /api/v1/quotes
```

The backend performs the authoritative pricing calculation and returns
the locked quote.

The final screen displays:

-   Passenger fares
-   Group discount
-   Extras
-   Promo discount
-   Tax
-   Final total
-   Quote expiry

## Pricing Rules

Prices are calculated in this order:

``` text
1. Adult fare
   = cruise.adult_fare × 1.00

2. Child fare
   Age 0–4   = 0% of adult fare
   Age 5–11  = 50% of adult fare
   Age 12–17 = 75% of adult fare

3. Base total
   = sum of passenger fares

4. Group discount
   1–2 passengers → 0%
   3–4 passengers → 5%
   5–6 passengers → 10%

5. Extras
   Insurance        = $80 × passengers
   Wi-Fi             = $15 × passengers × cruise nights
   Shore Excursion   = $120 × passengers

6. Subtotal
   = (base total − group discount) + extras

7. Promo discount
   = applied to eligible subtotal

8. Tax
   = 12% of taxable amount

9. Final total
   = taxable amount + tax
```

Passenger limits:

-   Minimum 1 adult
-   Maximum 6 total passengers
-   Children must be aged 0--17

## Promo Code Rules

Promo codes are validated in this order:

  Check                                Error Code
  ------------------------------------ --------------------------------
  Code does not exist or is inactive   `PROMO_NOT_FOUND`
  Today is before `valid_from`         `PROMO_NOT_YET_VALID`
  Today is after `valid_to`            `PROMO_EXPIRED`
  Customer limit reached               `PROMO_CUSTOMER_LIMIT_REACHED`
  Global usage limit reached           `PROMO_EXHAUSTED`
  Minimum spend not reached            `PROMO_MIN_SPEND_NOT_MET`

## Price Lock

Quotes are stored in `pending_quotes` and remain valid for:

``` text
15 minutes
```

The quote stores a complete pricing snapshot. Booking confirmation uses
the quote token so the locked price is preserved even if underlying
fares change.

## Running Tests

Run all tests:

``` powershell
python -m pytest tests/ -v
```

Individual suites:

``` powershell
python -m pytest tests/test_pricing.py -v
python -m pytest tests/test_promo.py -v
python -m pytest tests/test_booking.py -v
python -m pytest tests/test_api.py -v
```

Short error output:

``` powershell
python -m pytest tests/ --tb=short
```

The test suite covers:

  -----------------------------------------------------------------------
  Test File                           Coverage
  ----------------------------------- -----------------------------------
  `test_pricing.py`                   Passenger validation, child bands,
                                      group discounts, services, tax,
                                      pricing scenarios

  `test_promo.py`                     Promo validation and failure
                                      conditions

  `test_booking.py`                   Quote creation, booking
                                      confirmation, capacity, snapshots

  `test_api.py`                       HTTP API request/response behaviour
  -----------------------------------------------------------------------

> The exact number of tests may change as the project evolves. Run
> `pytest` to see the current count.

## Troubleshooting

### Backend does not start

If you see:

``` text
WinError 10013
An attempt was made to access a socket in a way forbidden by its access permissions
```

start Uvicorn explicitly on port 8001:

``` powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

If port 8001 is occupied:

``` powershell
netstat -ano | findstr :8001
```

### Frontend says "Unable to connect"

First verify:

``` text
http://127.0.0.1:8001/
```

Then:

``` text
http://127.0.0.1:8001/api/v1/cruises
```

If cruise JSON is returned, verify `frontend/app.js` contains:

``` javascript
const API = 'http://127.0.0.1:8001/api/v1';
```

Then check the browser Console (`F12`) for CORS or JavaScript errors.

### Cruise cards are stuck loading

Check that:

1.  Backend is running on port `8001`.
2.  `/api/v1/cruises` returns JSON.
3.  Frontend is running on port `5500`.
4.  `app.js` points to `http://127.0.0.1:8001/api/v1`.
5.  Browser Developer Tools show no JavaScript/CORS error.

### Get My Quote does not move to Review & Pay

If the backend shows:

``` text
POST /api/v1/quotes ... 201 Created
```

the quote was successfully created.

If the UI does not advance, check the browser Console for frontend
errors and verify the wizard is allowed to transition from Step 3 to
Step 4.

## Example Booking Flow

### 1. Create/retrieve customer

``` http
POST /api/v1/customers
```

``` json
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Doe"
}
```

### 2. Browse cruises

``` http
GET /api/v1/cruises
```

### 3. Request a quote

``` http
POST /api/v1/quotes
```

``` json
{
  "customer_id": 1,
  "cruise_id": 1,
  "num_adults": 2,
  "child_ages": [9],
  "service_codes": ["INSURANCE"],
  "promo_code": "SUMMER10"
}
```

Example response:

``` json
{
  "quote_token": "abc-123...",
  "total_amount": "2956.80",
  "price_breakdown": {},
  "expires_at": "2026-08-18T19:00:00"
}
```

### 4. Confirm booking

``` http
POST /api/v1/bookings
```

``` json
{
  "quote_token": "abc-123..."
}
```

Example response:

``` json
{
  "reference": "ODY-X7K2P9QR",
  "total_charged": "2956.80",
  "status": "CONFIRMED"
}
```

### 5. Retrieve booking

``` http
GET /api/v1/bookings/ODY-X7K2P9QR
```

The response contains the booking reference, charged amount, passengers,
extras, and immutable pricing snapshot.

## Development Workflow

For normal local development, use two terminals.

### Terminal 1 --- Backend

``` powershell
cd "C:\Users\Kishan\Desktop\PLACEMENT\odysseus"
.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

### Terminal 2 --- Frontend

``` powershell
cd "C:\Users\Kishan\Desktop\PLACEMENT\odysseus\frontend"
python -m http.server 5500
```

Open:

``` text
http://localhost:5500
```

API documentation:

``` text
http://127.0.0.1:8001/docs
```

## Documentation

Additional project documentation is available in `docs/`:

  -----------------------------------------------------------------------
  File                                Contents
  ----------------------------------- -----------------------------------
  `BusinessRequirements.md`           Functional requirements,
                                      assumptions, gaps, and conflicts

  `TechnicalApproach.md`              Architecture, data model, design
                                      decisions, and implementation
                                      approach

  `UnitTestCases.md`                  Test scenarios and expected
                                      behaviour
  -----------------------------------------------------------------------

## Project Status

The project currently includes:

-   FastAPI backend
-   SQLAlchemy database layer
-   SQLite development database
-   Seeded cruise/pricing data
-   REST API
-   Swagger/OpenAPI documentation
-   Browser-based frontend
-   Passenger selection
-   Optional extras
-   Live frontend fare estimate
-   Promo-code flow
-   Backend quote calculation
-   15-minute price-locked quotes
-   Booking confirmation flow
-   Automated tests
