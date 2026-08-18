# Business Requirements Document
## Odysseus Cruise Booking System

---

## 1. Context & Purpose

Odysseus sells cruise holidays. This document captures what the system must do, the assumptions made in interpreting the brief, and the gaps or conflicts that were identified. It is the authoritative reference for what was built and why.

---

## 2. Functional Requirements

### 2.1 Cruise Discovery
- A customer **can browse all cruises** that are currently available to book.
- A cruise is available if: it is active, its departure date is in the future, and it has at least one passenger space remaining.
- Each cruise listing shows: name, destination, departure date, duration (nights), adult fare, and remaining capacity.

### 2.2 Passenger Specification
- A customer specifies:
  - How many **adults** are travelling
  - How many **children** are travelling and the **exact age of each child**
- Booking rules:
  - **At least 1 adult** is required.
  - **Maximum 6 passengers** per booking (adults + children combined).
  - A **child** is defined as aged **0–17**. Anyone aged 18 or over is treated as an adult.

### 2.3 Optional Services
The customer may add any combination of:
| Service | Pricing Basis |
|---|---|
| Travel Insurance | $80 per passenger |
| Wi-Fi Package | $15 per passenger per night of the cruise |
| Shore Excursion | $120 per passenger |

### 2.4 Pricing
Pricing is calculated in the following order:

1. **Base fares** (per passenger, by type/age band):

| Passenger | Fare |
|---|---|
| Adult | 100% of cruise adult fare |
| Child age 0–4 | Free (0%) |
| Child age 5–11 | 50% of adult fare |
| Child age 12–17 | 75% of adult fare |

2. **Group discount** applied to base fare subtotal:

| Total Passengers | Discount |
|---|---|
| 1–2 | 0% |
| 3–4 | 5% |
| 5–6 | 10% |

3. **Optional services** added (calculated on total passengers / nights).

4. **Promo code discount** applied to subtotal (fares after group discount + extras).

5. **Tax (12%)** applied to the net amount after promo discount.

### 2.5 Promo Codes
- A customer may optionally enter a promo code.
- A code has: code text, type (percentage or fixed amount), value, valid from/to dates, max total uses, max uses per customer, and a minimum spend threshold.
- **Validation order** (each failure produces a distinct rejection message):
  1. Code exists and is active
  2. Today's date is within valid_from – valid_to range
  3. Customer has not exceeded their personal usage limit
  4. The code has not been exhausted globally
  5. The booking subtotal meets the minimum spend requirement
- A code that fails any of these checks is **rejected with a clear reason** before the customer sees a final price.

### 2.6 Quotes & Price Lock
- Before confirming, the customer sees a **full itemised price breakdown**.
- The system issues a **quote token** (valid for 15 minutes).
- **The price shown in the quote is the price charged** — no recalculation occurs at confirmation.
- An expired quote token must be rejected; the customer must request a new quote.

### 2.7 Capacity Control
- A cruise **must never be sold beyond its stated capacity**, under any circumstances.
- Capacity is enforced:
  - As a pre-check when requesting a quote (early rejection).
  - **Definitively at confirmation time** (inside a locked database transaction), preventing race conditions between simultaneous bookings.

### 2.8 Booking Confirmation & Reference
- On confirmation, the customer receives a **unique booking reference** (format: `ODY-XXXXXXXX`).
- The reference can be quoted back to Odysseus to retrieve the booking.

### 2.9 Booking Record — Permanent & Reconstructable
- Every confirmed booking stores a **snapshot** of all pricing inputs at the time of booking:
  - Cruise name, departure, adult fare as charged
  - Each passenger with type, age, band applied, and individual fare
  - Group discount tier and percentage applied
  - Each optional service with unit price at time of booking and line total
  - Promo code details (if any) including type, value, and discount amount
  - Tax rate applied and tax amount
  - Final total charged
- **This snapshot never changes**, even if cruise fares, discount rules, tax rates, or promo codes are later modified or deleted.
- The amount charged for any booking is **fully reconstructable** from stored data alone, at any point in the future.

### 2.10 Configuration Without Redeployment
The following can be changed at any time by updating database records, with no code change or redeployment required:
- Cruise adult fares
- Child age bands and their fare fractions
- Group discount tiers and percentages
- Optional service types and unit prices
- Tax rate (new rates take effect from a scheduled date)
- Promo codes (create, modify, deactivate)

---

## 3. Data to Store

| Entity | Purpose |
|---|---|
| Cruises | Available voyages with pricing and capacity |
| Fare Bands | Child age → fare fraction mapping (soft config) |
| Group Discounts | Passenger count → discount tier (soft config) |
| Optional Services | Extras the customer can add (soft config) |
| Tax Rates | Effective-dated tax rates (soft config) |
| Customers | Registered customers |
| Promo Codes | Promotional discount codes |
| Promo Redemptions | Audit trail of which customer used which code on which booking |
| Pending Quotes | Price quotes awaiting confirmation (expires after TTL) |
| Bookings | Confirmed bookings with immutable snapshot |
| Booking Passengers | Per-passenger record with fare charged |
| Booking Extras | Per-service record with unit price at time of booking |

---

## 4. Assumptions Made

| # | Assumption | Rationale |
|---|---|---|
| A1 | Tax applies to the amount after group discount and promo. | Tax is on what the customer actually pays — standard commercial/VAT practice. |
| A2 | Group discount applies to the base fare subtotal only, not to extras. | Extras are add-on services; group discount is a reward for travelling together, not for spending more on services. |
| A3 | Promo discount applies to the full subtotal (discounted fares + extras). | Brief says "amount off the booking" — interpreted as the full basket after group discount. |
| A4 | A child's age band is determined by the age provided at booking time. | No mechanism for age verification is in scope. |
| A5 | Quotes expire after 15 minutes by default (configurable). | Prevents capacity being held indefinitely by abandoned sessions. |
| A6 | The system is an API (no HTML frontend). | Brief describes a booking system without specifying UI; API is the correct backend foundation. |
| A7 | Email is the customer's unique identifier. | Industry standard; no authentication system is in scope. |
| A8 | "Infant (0–4)" children count toward the total passenger count for group discount and capacity. | They occupy a seat/berth. |
| A9 | SQLite is used for development; PostgreSQL for production. | Zero-setup for the time-boxed build; production path documented. |
| A10 | Promo code `min_spend` is compared against the subtotal *before* the promo discount. | If it were compared after, a code could validate based on a lower number — circular logic. |
| A11 | Optional services are priced on total passengers (adults + children). | Every passenger consumes the service (insurance, wifi, excursion). |

---

## 5. Gaps & Conflicts Identified in the Brief

| # | Gap / Conflict | How Handled |
|---|---|---|
| G1 | **Tax application point not specified.** Brief says "determining the correct point is part of the exercise." | Applied after group discount and promo, on the actual amount paid. See A1. |
| G2 | **Group discount basis not specified** — does it apply to base fares only, or to the whole basket including extras? | Applied to base fares only. See A2. |
| G3 | **Promo discount basis not specified** — before or after group discount? Before or after extras? | Applied to (group-discounted fares + extras), i.e., the full post-group-discount basket. See A3. |
| G4 | **No authentication mechanism described.** Customer is identified by email only. | Upsert by email — no passwords or sessions in scope. |
| G5 | **No cancellation / amendment workflow described.** | Bookings are confirmed-only (status field exists for future extension). Out of scope. |
| G6 | **Payment processing not mentioned.** | Out of scope. The API calculates and records the amount; payment integration is external. |
| G7 | **No specification on whether a cruise can be booked after departure.** | Rejected — booking a departed cruise is nonsensical. |
| G8 | **No specification on what happens if a child turns 18 between quote and travel.** | Age is fixed at booking time. See A4. |
| G9 | **Max-per-customer promo limit: does it count quotes or confirmed bookings?** | Only confirmed bookings count — a quote that was never confirmed should not consume a usage. |
| G10 | **No multi-currency mentioned.** | USD assumed throughout. |
