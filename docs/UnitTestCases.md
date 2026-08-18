# Unit Test Case Document
## Odysseus Cruise Booking System

---

## Overview

Tests are structured in four files:

| File | Scope | Type | Tests |
|---|---|---|---|
| `test_pricing.py` | Pure pricing functions | Unit (no DB) | 40 |
| `test_promo.py` | Promo validation chain | Integration (DB, no HTTP) | 12 |
| `test_booking.py` | Quote & confirm service | Integration (DB, no HTTP) | 17 |
| `test_api.py` | HTTP endpoints | E2E (full stack, test client) | 30 |

All tests use a **file-based SQLite** database — one fresh database file per test function, isolated via `pytest` fixtures in `conftest.py`. No external services required.

Run all tests: `pytest tests/ -v`  (99 tests total, all passing)

---

## 1. Passenger Validation (`test_pricing.py::TestValidatePassengers`)

| ID | Category | Scenario | Expected |
|---|---|---|---|
| PV-01 | Positive | 1 adult, 0 children | Passes |
| PV-02 | Positive | 6 adults (max allowed) | Passes |
| PV-03 | Positive | 1 adult + infant age 0 | Passes |
| PV-04 | Positive | 1 adult + child age 17 (max child age) | Passes |
| PV-05 | Negative | 0 adults | Raises: "At least one adult" |
| PV-06 | Negative | 4 adults + 3 children (total 7) | Raises: "Maximum 6 passengers" |
| PV-07 | Negative | Child age 18 | Raises: "qualifies as an adult" |
| PV-08 | Negative | Child age -1 | Raises: "cannot be negative" |
| PV-09 | Boundary | Exactly 6 passengers | Passes |
| PV-10 | Boundary | Child age 0 | Passes (youngest valid) |
| PV-11 | Boundary | Child age 17 | Passes (oldest valid child) |

---

## 2. Child Fare Bands (`test_pricing.py::TestChildFareBands`)

| ID | Category | Scenario | Expected Fare |
|---|---|---|---|
| CB-01 | Positive | Child age 2 (band 0-4) | $0.00 (free) |
| CB-02 | Positive | Child age 8 (band 5-11) | $500.00 (50%) |
| CB-03 | Positive | Child age 15 (band 12-17) | $750.00 (75%) |
| CB-04 | Boundary | Age 4 (max of free band) | $0.00 |
| CB-05 | Boundary | Age 5 (min of 50% band) | $500.00 |
| CB-06 | Boundary | Age 11 (max of 50% band) | $500.00 |
| CB-07 | Boundary | Age 12 (min of 75% band) | $750.00 |
| CB-08 | Boundary | Age 17 (max child age) | $750.00 |
| CB-09 | Positive | Multiple children in different bands | Each priced independently |

---

## 3. Group Discounts (`test_pricing.py::TestGroupDiscounts`)

| ID | Category | Scenario | Expected Discount |
|---|---|---|---|
| GD-01 | Positive | 1 passenger | 0% |
| GD-02 | Positive | 2 passengers | 0% |
| GD-03 | Positive | 3 passengers | 5% |
| GD-04 | Positive | 4 passengers | 5% |
| GD-05 | Positive | 5 passengers | 10% |
| GD-06 | Positive | 6 passengers | 10% |
| GD-07 | Boundary | 2 adults + 1 child = 3 total | 5% (children count) |
| GD-08 | Boundary | Exactly 3 passengers (discount threshold) | 5% |
| GD-09 | Boundary | Exactly 5 passengers (higher discount threshold) | 10% |

---

## 4. Optional Services (`test_pricing.py::TestOptionalServices`)

| ID | Category | Scenario | Expected |
|---|---|---|---|
| OS-01 | Positive | Insurance, 2 adults | $160.00 (2 × $80) |
| OS-02 | Positive | Wi-Fi, 2 adults, 7 nights | $210.00 (2 × $15 × 7) |
| OS-03 | Positive | Shore excursion, 3 adults | $360.00 (3 × $120) |
| OS-04 | Positive | Insurance + shore excursion combined | $200.00 total extras |
| OS-05 | Positive | No services selected | $0.00 extras |
| OS-06 | Positive | Wi-Fi on 1-night cruise vs 7-night | Linear scaling per night |

---

## 5. Tax (`test_pricing.py::TestTax`)

| ID | Category | Scenario | Expected |
|---|---|---|---|
| TX-01 | Positive | 12% tax on $1000 base | $120.00 tax |
| TX-02 | Positive | Tax applied AFTER promo discount | Tax on (1000 − 50% = 500) = $60 |
| TX-03 | Boundary | 0% tax rate | No tax, total = subtotal |

> **Critical**: TX-02 verifies that tax is not calculated on the pre-promo amount. This is the correct commercial behaviour.

---

## 6. Promo Code Pricing (`test_pricing.py::TestPromoPricing`)

| ID | Category | Scenario | Expected |
|---|---|---|---|
| PP-01 | Positive | 10% PCT promo on $1000 | Discount $100, taxable $900 |
| PP-02 | Positive | $50 FIXED promo on $1000 | Discount $50, taxable $950 |
| PP-03 | Boundary | FIXED promo exceeds subtotal | Discount = subtotal, taxable = $0, total = $0 |
| PP-04 | Positive | No promo | Discount = $0, total unchanged |

---

## 7. Promo Code Validation (`test_promo.py::TestPromoValidation`)

| ID | Category | Scenario | Expected Error Code |
|---|---|---|---|
| PCV-01 | Positive | Valid PCT code | Accepted — returns PromoData |
| PCV-02 | Positive | Valid FIXED code | Accepted |
| PCV-03 | Negative | Code does not exist | `PROMO_NOT_FOUND` |
| PCV-04 | Negative | Code is inactive | `PROMO_NOT_FOUND` |
| PCV-05 | Negative | Code expired | `PROMO_EXPIRED` |
| PCV-06 | Negative | Code not yet valid | `PROMO_NOT_YET_VALID` |
| PCV-07 | Negative | Customer has reached per-customer limit | `PROMO_CUSTOMER_LIMIT_REACHED` |
| PCV-08 | Positive | Different customer can still use same code | Accepted |
| PCV-09 | Negative | Code exhausted globally | `PROMO_EXHAUSTED` |
| PCV-10 | Negative | Booking below min_spend | `PROMO_MIN_SPEND_NOT_MET` |
| PCV-11 | Boundary | Booking exactly at min_spend | Accepted |
| PCV-12 | Positive | Unlimited code (no caps) — many uses | Always accepted |

> **PCV-07 + PCV-08 together** verify that the per-customer limit is correctly scoped to the individual, not the code globally.

---

## 8. Quote Creation (`test_booking.py::TestCreateQuote`)

| ID | Category | Scenario | Expected |
|---|---|---|---|
| QC-01 | Positive | Basic quote, 1 adult | Quote token returned, total > 0 |
| QC-02 | Positive | Quote with valid promo | Total less than quote without promo |
| QC-03 | Positive | Quote with optional services | Services appear in breakdown |
| QC-04 | Negative | Invalid promo code | Raises PROMO_NOT_FOUND |
| QC-05 | Negative | Cruise at full capacity | Raises CapacityError |
| QC-06 | Negative | Unknown service code | Raises INVALID_SERVICE |
| QC-07 | Negative | 0 adults | Raises VALIDATION_ERROR |

---

## 9. Booking Confirmation (`test_booking.py::TestConfirmBooking`)

| ID | Category | Scenario | Expected |
|---|---|---|---|
| BC-01 | Positive | Valid quote → confirmed booking | Reference starting "ODY-", status CONFIRMED |
| BC-02 | Positive | Total charged = quote total | Exact match (no recalculation) |
| BC-03 | Positive | Cruise booked_count incremented correctly | +N (total passengers) |
| BC-04 | Positive | Quote marked as used | `is_used = True` |
| BC-05 | Negative | Reuse same quote token | Raises QUOTE_ALREADY_USED |
| BC-06 | Negative | Expired quote token | Raises QUOTE_EXPIRED |
| BC-07 | Negative | Non-existent quote token | Raises QUOTE_NOT_FOUND |
| BC-08 | Positive | Snapshot stored on booking | Contains adult_fare, tax_rate, confirmed_at |
| BC-09 | Failure | Capacity filled between quote and confirm | Raises CapacityError |
| BC-10 | Positive | Passenger rows created per passenger | N rows in booking_passengers |
| BC-11 | Positive | Extra rows created for each service | N rows in booking_extras |

> **BC-09** is the most critical test — it simulates a race condition and verifies the system correctly rejects the late booking.
> **BC-02** is the price-lock guarantee test — no recalculation at confirm time.

---

## 10. HTTP API Tests (`test_api.py`)

### Customers

| ID | Category | Scenario | HTTP |
|---|---|---|---|
| AC-01 | Positive | Create new customer | 201 + id |
| AC-02 | Positive | Same email returns same customer | 201 + same id |
| AC-03 | Negative | Invalid email format | 422 |

### Cruises

| ID | Category | Scenario | HTTP |
|---|---|---|---|
| CR-01 | Positive | List available cruises | 200 + array |
| CR-02 | Positive | Response has required fields | 200 + all fields present |
| CR-03 | Positive | Full cruise not in list | 200 + empty array |
| CR-04 | Positive | Get cruise by ID | 200 + cruise object |
| CR-05 | Negative | Get non-existent cruise | 404 |

### Quotes

| ID | Category | Scenario | HTTP |
|---|---|---|---|
| AQ-01 | Positive | Request a quote | 201 + token |
| AQ-02 | Positive | Response breakdown has all fields | 201 + all fields |
| AQ-03 | Positive | Promo reduces total | 201 + lower total |
| AQ-04 | Negative | Invalid promo code | 422 |
| AQ-05 | Positive | Quote with services | 201 + extras in breakdown |
| AQ-06 | Positive | Quote with mixed-age children | 201 + correct infant fare |
| AQ-07 | Negative | Full cruise | 409 |
| AQ-08 | Negative | 0 adults | 422 |
| AQ-09 | Negative | 7 passengers | 422 |

### Bookings

| ID | Category | Scenario | HTTP |
|---|---|---|---|
| AB-01 | Positive | Confirm booking | 201 + reference |
| AB-02 | Positive | Charged = quote total | 201 + matching amount |
| AB-03 | Positive | Snapshot in response | 201 + snapshot fields |
| AB-04 | Negative | Reuse quote token | 409 |
| AB-05 | Negative | Invalid token | 404 |
| AB-06 | Positive | Retrieve by reference | 200 + booking |
| AB-07 | Negative | Retrieve non-existent reference | 404 |
| AB-08 | Positive | Passengers in response | 201 + passenger array |
| AB-09 | Positive | Extras in response | 201 + extras array |

---

## 11. Full End-to-End Scenario (`test_pricing.py::TestFullScenario`)

| ID | Category | Scenario |
|---|---|---|
| E2E-01 | Positive | 2 adults + infant(2) + child(8) + teen(15), 7 nights, insurance + wifi, 10% promo, 12% tax → verified total $3,880.80 |

This test verifies the entire pricing pipeline end-to-end with known inputs and manually calculated expected outputs.

---

## 12. Scenarios Not Automated (Written Scenarios)

These scenarios matter but require either production PostgreSQL (for concurrency) or external integrations not in scope:

| ID | Category | Scenario | Why Manual |
|---|---|---|---|
| M-01 | Failure | Two simultaneous confirms for last 1 seat — only one succeeds | Requires real PostgreSQL + concurrent threads |
| M-02 | Failure | Tax rate changes between quote and confirm — charged amount uses stored quote, not new rate | Verify by: create quote, update TaxRate, confirm — check snapshot has original rate |
| M-03 | Failure | Adult fare changes between quote and confirm — charged amount unchanged | Same as M-02 but update cruise fare |
| M-04 | Boundary | Promo with exactly 0 max_total_uses is immediately rejected | Already covered in seed data |
| M-05 | Failure | Database write fails mid-confirm (e.g. network drop) | Verify transaction rollback — no partial booking, no capacity change |
| M-06 | Boundary | Quote token submitted 1 second before expiry | Should succeed |
| M-07 | Boundary | Quote token submitted 1 second after expiry | Should fail |

---

## 13. Test Coverage Summary

| Area | Positive | Negative | Boundary | Failure |
|---|---|---|---|---|
| Passenger validation | ✓ | ✓ | ✓ | – |
| Child fare bands | ✓ | – | ✓ (all band edges) | – |
| Group discounts | ✓ | – | ✓ (tier boundaries) | – |
| Optional services | ✓ | – | ✓ | – |
| Tax | ✓ | – | ✓ (0% rate) | – |
| Promo pricing | ✓ | ✓ (cap at subtotal) | ✓ | – |
| Promo validation | ✓ | ✓ (all 5 reasons) | ✓ (min_spend edge) | – |
| Quote creation | ✓ | ✓ | ✓ | – |
| Booking confirm | ✓ | ✓ | ✓ | ✓ (race condition) |
| HTTP API | ✓ | ✓ | ✓ | – |
| Concurrency | – | – | – | Manual only |

**Total automated tests: 99** (all passing as of last run).
