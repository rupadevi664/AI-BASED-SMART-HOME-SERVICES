# AI-BASED-SMART-HOME-SERVICES

An intelligent home-service platform where customers can find and book **verified home-service experts** (electricians, plumbers, AC technicians, cleaners, and more).

> **Current status: Phase 1 (foundation) + Phase 2 (discovery) + Phase 3
> (booking) + Phase 4 (real-time chat) — complete.**

## What's implemented

**Phase 1** — FastAPI backend, MySQL via SQLAlchemy, User / ExpertProfile /
Service models, customer & expert registration, login, JWT authentication,
bcrypt password hashing, roles (`CUSTOMER`, `EXPERT`, `ADMIN`), role-protected
endpoints, Swagger docs, automated tests.

**Phase 2** — service catalogue APIs, admin service management, expert profile
management, expert↔service many-to-many relationships, admin verification
workflow (`PENDING / VERIFIED / REJECTED`), validated availability
(`AVAILABLE / UNAVAILABLE`), and **nearby expert search** using the Haversine
formula over *static* profile coordinates (experts manually enter
latitude/longitude — **no live GPS / location tracking**).

**Phase 3** — booking system: customers book verified experts
(`POST /bookings`) for a service at a date/time/address; experts manage
requests (`GET /experts/bookings`, accept / reject / complete); customers view
history (`GET /bookings/my`) and cancel; admins inspect all bookings. Full
lifecycle `PENDING → ACCEPTED → COMPLETED` (+ REJECTED/CANCELLED) with
server-validated transitions, service name/price **snapshots**, slot-conflict
detection (409), and `customer_id` always taken from the JWT.

Phase 3 does **NOT** include payments, chat, WebSockets, live tracking, AI/RAG,
reviews, or ratings.

**Phase 4** — real-time text communication: booking-scoped WebSocket chat
(`ws://host/ws/bookings/{booking_id}?token=<JWT>`) between the booking's
customer and its assigned expert, with JWT query-param authentication, a
booking-scoped connection manager, JSON message protocol (message / ping /
pong / join-leave events), persistence to a `messages` table, and a REST
history endpoint `GET /bookings/{booking_id}/messages`.

Phase 4 implements **text chat only** — no live location/GPS, video/audio
calls, payments, AI, or notifications.

Not yet (later phases): payments/Razorpay, live
location, LLM/RAG/ChromaDB, notifications, reviews/ratings, React frontend.

## Quick start

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # then edit DATABASE_URL with your MySQL password
python -m app.init_db           # create/update tables + seed the 8 services
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

## Testing

```bash
cd backend
.venv\Scripts\python -m pytest -v                 # 151 automated tests (no MySQL needed)
.venv\Scripts\python scripts\live_acceptance.py   # 77 live checks vs running server
.venv\Scripts\python scripts\setup_chat_booking.py        # chat fixtures + booking id
.venv\Scripts\python scripts\websocket_test.py [id]       # two-client chat flow
.venv\Scripts\python scripts\ws_security_test.py [id]     # intruders denied
```

## Structure

```
AI-BASED-SMART-HOME-SERVICES/
├── backend/            # FastAPI application (see backend/README.md)
├── .gitignore
└── README.md
```

Full documentation: **[backend/README.md](backend/README.md)**
