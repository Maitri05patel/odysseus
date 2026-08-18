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
