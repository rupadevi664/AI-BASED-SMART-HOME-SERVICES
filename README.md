# AI-BASED-SMART-HOME-SERVICES

An intelligent home-service platform where customers can find and book **verified home-service experts** (electricians, plumbers, AC technicians, cleaners, and more).

> **Current status: Phase 1 (foundation) + Phase 2 (discovery) + Phase 3
> (booking) + Phase 4 (real-time chat) + Phase 5 (live location tracking) +
> Phase 6 (Razorpay payments + reviews/ratings) + Phase 7 (Gemini AI
> assistant) + React frontend — complete.**

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

**Phase 5** — live expert location tracking for **ACCEPTED** bookings only:
a dedicated WebSocket (`ws://host/ws/bookings/{booking_id}/location?token=<JWT>`) where the assigned expert sends `location_update` frames and the
booking's customer receives them in real time; `live_locations` table
(booking/user FKs, indexed); latest + history REST endpoints
(`GET /bookings/{booking_id}/location[/history]`, max 500 points); server-side
coordinate validation; throttling (`LOCATION_UPDATE_INTERVAL_SECONDS=1`);
booking-scoped privacy (never public, never cross-booking, admins excluded);
configurable retention (`LOCATION_HISTORY_RETENTION_DAYS=7`, explicit
opt-in cleanup — nothing deletes automatically). Browser demo page at
**`http://127.0.0.1:8000/location-demo`**.

**Phase 6** — **Razorpay payments + reviews/ratings** for COMPLETED bookings:
`POST /payments/create-order/{booking_id}` creates a Razorpay order (amount
always from the booking's price snapshot, never the client), the React app
opens Razorpay Checkout, and `POST /payments/verify` validates the
HMAC-SHA256 signature server-side (`order_id|payment_id` keyed with
`RAZORPAY_KEY_SECRET`) before flipping `payments.status = SUCCESS` and
`bookings.payment_status = PAID` — the frontend claim alone is never trusted.
A full review system (1-5 stars + comment, one per booking, edit/delete by
its author) recalculates each expert's `rating_avg` / `rating_count` on every
change; `GET /reviews/expert/{id}` is public for profile pages.

**Phase 7** — **Gemini LLM assistant**: `POST /llm/chat` (JWT; CUSTOMER and
EXPERT) sends the customer's question — plus an optional short client-side
history and context — to **Google Gemini** (`gemini-2.0-flash` REST via
httpx) under a controlled "Smart Home Service Assistant" system prompt. The
backend returns a single clean `response` string (never the raw provider
payload) and maps every failure to a controlled error code (503
`LLM_NOT_CONFIGURED` without a key, 502 rejected-key/upstream/empty, 429 rate
limit, 504 timeout). The key lives only in `backend/.env`; the assistant can
only *suggest* service categories — it has no tool access and can never
create bookings/payments or invent prices/availability. The React app adds
an **AI Assistant** page (chat bubbles, Thinking… state, friendly errors).
No database changes — conversation stays in React state.

**Frontend (React + Vite)** — a `frontend/` SPA connected to this backend:
JWT auth with role-guarded routes (CUSTOMER/EXPERT/ADMIN), service catalogue,
Haversine nearby-expert search (browser GPS or manual coordinates), booking
creation with status lifecycle, booking-scoped **WebSocket chat**, and
**live expert tracking** on a Leaflet/OpenStreetMap map — the assigned expert
streams `navigator.geolocation` positions over the Phase 5 WebSocket and the
customer's marker moves in real time. See `frontend/.env.example` and the
backend README for run instructions.

Not yet (later phases): RAG/embeddings/ChromaDB (Phase 8 — will reuse the
Phase 7 `gemini_service` as the generation step), notifications, deployment.

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
.venv\Scripts\python -m pytest -v                 # 269 automated tests (no MySQL needed)
.venv\Scripts\python scripts\live_acceptance.py   # 77 live checks vs running server
.venv\Scripts\python scripts\setup_chat_booking.py        # chat fixtures + booking id
.venv\Scripts\python scripts\websocket_test.py [id]       # two-client chat flow
.venv\Scripts\python scripts\ws_security_test.py [id]     # intruders denied
.venv\Scripts\python scripts\location_test.py             # two-client live-location flow
```

## Quick start (full stack)

```bash
# Terminal 1 — backend
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload          # http://127.0.0.1:8000/docs

# Terminal 2 — frontend
cd frontend
npm install                            # first time only
npm run dev                            # http://localhost:5173
```

## Structure

```
AI-BASED-SMART-HOME-SERVICES/
├── backend/            # FastAPI application (see backend/README.md)
├── frontend/           # React + Vite SPA (see frontend/README.md)
├── .gitignore
└── README.md
```

Full documentation: **[backend/README.md](backend/README.md)**
