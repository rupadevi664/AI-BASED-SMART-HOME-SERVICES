# Frequently Asked Questions (FAQ)

## About the platform

Question: What is AI-BASED-SMART-HOME-SERVICES?
Answer: A home-service platform where customers browse service categories, find VERIFIED experts nearby, book them for a time slot, chat with the assigned expert, track them live on the map during the visit, pay securely through Razorpay after completion, and rate the service with a review.

Question: Which service categories are available?
Answer: Electrician, Plumber, AC Repair, Cleaning, Appliance Repair, Carpenter, Painter and Pest Control are seeded in the service catalogue. Customers pick a category, then choose a verified expert who offers it.

Question: How do I find experts near me?
Answer: Open the Experts page, allow location access (or type coordinates manually), set a radius in kilometres, and search. Nearby search lists only VERIFIED experts with saved coordinates, sorted by distance.

## Bookings

Question: How do I book an expert?
Answer: Choose a service and expert, pick a date and a 5-minute time slot that does not clash with the expert's other bookings, and confirm the address. The booking starts as PENDING.

Question: What do booking statuses mean?
Answer: PENDING — waiting for the expert to respond. ACCEPTED — the expert confirmed; chat and live tracking become available. COMPLETED — the work is done; you can pay and review. REJECTED — the expert declined. CANCELLED — cancelled before completion.

Question: Can I cancel a booking?
Answer: Yes, customers can cancel a PENDING or ACCEPTED booking before it is completed. Experts can accept, reject or complete; every transition is validated on the server.

Question: Why is there a booking conflict error?
Answer: The expert already has a PENDING or ACCEPTED booking in the same 5-minute slot. Pick a different time or another expert.

## Payments

Question: When do I pay?
Answer: After the booking is COMPLETED. Open My Bookings and use Pay Now on the completed card. The amount always comes from the booking's own price snapshot.

Question: Is payment secure?
Answer: Payments run through Razorpay Checkout. The backend verifies an HMAC-SHA256 signature server-side before marking anything PAID — the app never trusts the browser's claim, and no card data is stored.

Question: What if payment fails?
Answer: The payment row is marked FAILED, the booking stays UNPAID, and you can retry Pay Now. Nothing is charged without a verified signature.

## Reviews

Question: Can I review an expert?
Answer: Yes — once per completed booking, 1–5 stars plus an optional comment. You can edit or delete your review; the expert's average rating updates automatically.

## Accounts and access

Question: Who can use the AI assistant?
Answer: Signed-in customers and experts. The assistant gives general guidance and suggests a service category — it never books anything by itself and does not invent prices or availability.

Question: What do the roles mean?
Answer: CUSTOMER books services. EXPERT offers services after admin verification. ADMIN manages the catalogue, verification and can inspect all data.
