# Prompt Log — Odysseus Cruise Booking System

This document records every prompt given to the AI assistant during this project.

---

## Prompt 1 — Initial Brief (2026-08-18)

> i want to create a project : brief: odysseus sells cruise holidays. we need a booking system. a customer should be able to find a cruise, tell us who is travelling, and which extras they want, see what it will cost, apply a promo code if they have one, and confirm booking, afterwards we ned to know exactly what we sold, to whomand for how much- permanently , and long after our prices have changed. please use stack around python... as i know pythin.
>
> i want to build businessrequirements.md-understanding of what being asked, every assumptions you made and every gap or conflict you found in brief, i also want technical approach.md-data model,the reasoning behind it. architecture, and the imp decision you made, and explain what would have done differently with more time, as we have 110 mins only,, i want unittestcase.md- the test scenarios you consider imp,covering positive,neagavtive,boundary and failure cases. sutomated tests are welcomed but written scenarios matter more.
>
> Functional req:
> a customer can find the cruise that are availabale to book.
> a customer spacify who is traveling- how many adults,how many childern, and the age of each child=and which optional services they want
> a cutomer may apply promotional code. a code that is invalid or expired or exhausted or not applicable to this booking must be rejected with clear reason.
> a cruise must never be sold to more passengers than its capacity,under any circuimstancec.
> a promo code must not be reedems more than its limit allow-neither in total, not by a single customer.
> a confirmed booking is stored and the customer recieves a unique reference they can quote back to us later.
> the amount charged for nay booking must be fully recontructable from stored data at any point in the future, after fares. discount rules, and promo code have all changed.
> the price shown to customers before they confirm is the price they are charged, it must not be possibele for these to differ.
> fares, child age bands, discount tires, tax rates, and prommo codes all change regularly, changing any of them must not require a code change or a redeplyment.
>
> PRICING RULES:
> adults pay full base fare of the selected cruise.
> fare of child of age 0-4 are free of charge.
> 5-11 aged child's fare will be 50% of the adult's fare
> and 12-17 aged child's fare will be 75% of the adult's fare.
> booking limits:
> at least one adult is required per booking.
> maximum 6 passengers per booking.
> a child is aged 0-17. anyone aged 18 or over 18 is adult.
> GROUP DISCOUNT:
> 1-2 PASSENGERS: 0% DISCOUNT
> 3-4 PASSENGERS:5% DISCOUNT
> 5-6 PASSENGERS:10% DISCOUNT
>
> OPTIONAL SERVICES:
> insurance:80$ per passenger
> wi-fi:$15 per passenger per night of the cruise
> shore excursion: $120 per passenger
>
> PROMO CODES:
> code:the text customer tyoes in
> type:either percentage reduction or a fixed amount off
> value:the percentage or fixed amount
> valid from/to: outside the date range the code must be rejected
> max total uses: how many times the code may be redeemed across all customers
> max use per customer: how many times one customer may redeem it
> max spend: the code is only vaalid on bookings at or above this value
> TAX:
> a tax of 12% applies. determining the correct point at which to apply it is part of the exercise.
>
> DATA:
> what we need to store:
> cruises that are available to book
> customers
> orders
> promo codes
> redemption of promo codes
> whatever else our design requires
>
> I also want one promp.md where all prompt i give is stored.. and also i'll give you the data to seed into the db

---

## Prompt 2 — Proceed with Implementation (2026-08-18)

> i'll provide you the data later first proceed with implementation

---

## Prompt 3 — User Approved Implementation Plan (2026-08-18)

> [User approved the implementation_plan.md artifact and confirmed to proceed]

---

## Prompt 4 — Seed Data (2026-08-18)

> seed this data
>
> and also tell me where db is located..

*(User provided the cruise and promo code seed data at this point. The seed script was updated to use the provided data and the database location was confirmed as `odysseus/odysseus.db` in the project root.)*

---

## Prompt 5 — README (2026-08-18)

> make readme file
> where all info abt project and how to run project and all instructions are there

*(A full `README.md` was created covering features, tech stack, project structure, quick start, environment variables, database, seeding, running the API, API reference, running tests, pricing rules, promo code rules, and documentation links.)*

---

## Prompt 6 — Build Attractive UI (2026-08-18)

> we have time left, so lets build attractive ui

*(A full browser-based SPA was built in `frontend/` using HTML, CSS, and vanilla JavaScript. Design: dark ocean theme, glassmorphism cards, animated hero section, floating orbs, wave animations, Outfit + Playfair Display fonts. The UI is a 4-step booking wizard covering cruise browsing, passenger selection, extras + promo, and review & confirm.)*

---

## Prompt 7 — Continue UI (2026-08-18)

> continue from where was left

*(The `frontend/app.js` state machine was completed — `selectCruise` was refactored to use array indices to avoid JSON-in-HTML attribute parsing issues. The `main.py` was updated to serve the frontend via `StaticFiles`. A live estimated fare box was added to Step 2.)*

---

## Prompt 8 — Update All Docs (2026-08-18)

> update the docs
> update the readme and all docs
> update all the docs as the project
> update docs including readme and add how to run the programme

*(All documentation was updated to reflect the completed full-stack project:)*
- *`README.md` — updated with two-server setup (backend `:8001`, frontend `:5500`), booking flow, troubleshooting section, and development workflow.*
- *`docs/TechnicalApproach.md` — added Frontend row to stack table, updated "What Would Be Done Differently" row, added `frontend/` to file map, added new §7 Frontend Architecture section.*
- *`docs/BusinessRequirements.md` — updated context paragraph and Assumption A6 to reflect the delivered SPA.*
- *`docs/UnitTestCases.md` — corrected SQLite type (file-based, not in-memory), added per-file test counts, confirmed 99 total passing tests.*

---

## Prompt 9 — Bug Fix: Duplicate Code in app.js (2026-08-18)

> *(Automatic — spotted during doc update)*

*(Removed orphaned duplicate code block at module scope in `frontend/app.js` left from manual editing — variable declarations outside any function that would cause a `ReferenceError`. Fixed missing closing brace on `updateFrontendPrice()`. Added missing `.live-price-box` CSS styles to `style.css`. Node.js syntax check confirmed clean.)*

---

## Prompt 10 — Add Relevant Prompts to Prompts.md (2026-08-18)

> please add relevant prompts to prompts.md file

*(This update — all prompts from the session were backfilled into this document.)*
