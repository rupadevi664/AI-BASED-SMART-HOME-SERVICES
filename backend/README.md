# Backend — AI-BASED-SMART-HOME-SERVICES (Phase 1 + 2 + 3 + 4 + 5)

FastAPI backend for the intelligent home-service platform.

- **Phase 1 — foundation:** MySQL database, user/expert/service models, JWT
  authentication, role-based authorization, Swagger docs, automated tests.
- **Phase 2 — discovery:** service catalogue APIs, admin service management,
  expert profile management, expert–service relationships, admin verification
  workflow, and **nearby expert search** (Haversine over *static* profile
  coordinates).
- **Phase 3 — booking:** customers book verified experts for a service at a
  chosen date/time/address; experts accept / reject / complete; customers
  cancel; full status lifecycle with service name/price snapshots.
- **Phase 4 — real-time chat:** booking-scoped WebSocket text communication
  between the booking's customer and its assigned expert, with persisted
  messages and a REST history endpoint.

> **Phase 2 uses static expert coordinates. Live location tracking is NOT
> implemented** — experts manually enter latitude/longitude in their profile;
> nothing computes or streams GPS data.
>
> **Phase 4 implements REAL-TIME TEXT COMMUNICATION only.** It does NOT
> implement live location, GPS streaming, video/audio calls, payments, AI/RAG,
> or notifications. Phase 3 does NOT include payments, chat, WebSockets, live
> tracking, AI/RAG, reviews, or ratings.

## 1. Project overview

Customers register and discover verified home-service experts near them.
Experts register with a profile (skills, experience, location, static
coordinates, availability, offered services). Admins manage the service
catalogue and expert verification. Bookings get real-time chat and, once
ACCEPTED, live expert location tracking. Payments and AI features belong to
later phases.

## 2. Feature matrix

| Phase | Included |
|---|---|
| 1 | Auth (register/login/JWT), roles CUSTOMER/EXPERT/ADMIN, User + ExpertProfile + Service models, protected endpoints, Swagger, 31 tests |
| 2 | `GET /services`, `GET /services/{id}`, admin CRUD for services, expert profile GET/PUT, expert↔service M2M, admin verification, Haversine nearby search, 44 more tests |
| 3 | Booking model + lifecycle, `POST /bookings`, customer history/cancel, expert accept/reject/complete, admin booking views, snapshots, conflicts, 46 more tests |
| 4 | `WS /ws/bookings/{id}` chat, `GET /bookings/{id}/messages` history, Message model + table, booking-scoped ConnectionManager, JWT `?token=` auth, 30 more tests |
| 5 | Live location for ACCEPTED bookings: `WS /ws/bookings/{id}/location` (assigned expert sends, customer receives), `GET /bookings/{id}/location[/history]`, `live_locations` table, validation + throttling + retention, 55 more tests |

Not implemented (later phases): payments/Razorpay, LLM/RAG/ChromaDB,
notifications, reviews/ratings, frontend.

## 3. Technology stack

Python 3.10+ (developed on 3.13) · FastAPI 0.141 · Uvicorn 0.52 · SQLAlchemy 2.0
· PyMySQL (MySQL 8) · Pydantic v2 + pydantic-settings · PyJWT (HS256) · bcrypt ·
pytest + httpx. **No new dependencies were added for Phases 2–5.**

## 4. Folder structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app, lifespan (tables + migration + seeds)
│   ├── init_db.py         # CLI init: create_all + additive Phase 2 migration
│   ├── core/              # config.py, database.py, security.py
│   ├── auth/              # router, service, dependencies, schemas, security
│   ├── models/            # user.py, expert.py, service.py, associations.py
│   ├── schemas/           # user.py, expert.py, service.py (Pydantic)
│   ├── api/               # users.py, services.py, experts.py, admin.py
│   ├── services/          # expert_profile.py (Phase 2 business logic)
│   ├── utils/             # geo.py (Haversine)
│   └── scripts/           # run_live.py, live_acceptance.py  (as ../scripts)
├── tests/                 # conftest, test_auth, test_roles, test_services,
│                          # test_experts, test_nearby
├── requirements.txt · pytest.ini · pyproject.toml
├── .env.example           # template — copy to .env
└── .env                   # your local secrets (gitignored)
```

## 5–6. MySQL setup

```sql
CREATE DATABASE ai_home_services CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

(The app also attempts this automatically on first run.)

## 7–9. Virtualenv, dependencies, environment

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
```

`.env`:

```
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/ai_home_services
JWT_SECRET_KEY=<at least 32 random characters>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
# optional, used by `python -m app.init_db --admin`
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<strong password>
ADMIN_NAME=Platform Admin
# Phase 6: Razorpay payments (get TEST keys: Razorpay Dashboard → Settings → API Keys)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_CURRENCY=INR

# Phase 7: Google Gemini AI assistant (key from https://aistudio.google.com/apikey)
# Backend-only secret; leave empty to run without the assistant (503 LLM_NOT_CONFIGURED)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT_SECONDS=20
GEMINI_MAX_HISTORY_TURNS=8

# Phase 5: live location
LOCATION_UPDATE_INTERVAL_SECONDS=1
LOCATION_HISTORY_RETENTION_DAYS=7
```

URL-encode special characters in the DB password (`@` → `%40`). Never commit `.env`.

## 10–11. Run & Swagger

```bash
python -m app.init_db             # create/update tables + seed services
python -m app.init_db --admin     # optional: also create the ADMIN account
uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

Open **http://127.0.0.1:8000/docs** → login via `POST /auth/login` (or the
Authorize button, which uses `/auth/login-form`) → copy `access_token` →
**Authorize** → paste `Bearer <access_token>`.

Startup is idempotent: `create_all` creates missing tables, an additive
migration adds `latitude`/`longitude` if absent, legacy values are normalized
(`Flexible`→`AVAILABLE`, `APPROVED`→`VERIFIED`), and the 8 services are seeded
exactly once. **No data is ever dropped.**

## 12. Testing

```bash
cd backend
.venv\Scripts\python -m pytest -v        # 269 tests, SQLite in-memory, no creds
.venv\Scripts\python scripts\live_acceptance.py   # 77 checks vs a running server
.venv\Scripts\python scripts\setup_chat_booking.py # mint customer/expert/booking for chat
.venv\Scripts\python scripts\websocket_test.py [booking_id]   # two-client chat flow
.venv\Scripts\python scripts\ws_security_test.py [booking_id] # intruders denied
.venv\Scripts\python scripts\location_test.py      # two-client live-location flow
```

## 13. Authentication flow (unchanged from Phase 1)

```
Register → bcrypt hash → DB (role forced server-side)
Login    → verify hash → JWT {sub: user_id, role, exp}
Requests → Authorization: Bearer <token> → get_current_user → role checks
```

## 14. Role-based authorization

| Endpoint | CUSTOMER | EXPERT | ADMIN |
|---|---|---|---|
| `GET /services`, `GET /services/{id}` | 200 | 200 | 200 |
| `GET /experts/nearby` | 200 | 200 | 200 |
| `GET/PUT /experts/profile` | 403 | 200 | 403 |
| `POST/PUT /admin/services` | 403 | 403 | 201/200 |
| `GET /admin/experts`, `PUT .../verification` | 403 | 403 | 200 |
| `GET /admin/dashboard` | 403 | 403 | 200 |
| `POST /bookings`, `GET /bookings/my`, `PUT .../cancel` | 200/201 | 403 | 403* |
| `GET /experts/bookings`, `PUT .../accept\|reject\|complete` | 403 | 200 | 403* |
| `GET /bookings/{id}` | own only | assigned only | any |
| `GET /admin/bookings` | 403 | 403 | 200 |

\* some customer/expert endpoints return 403 to admins by design (role-scoped
workflows); admins use the admin routes instead.

## Phase 3 — booking system

### Lifecycle

```
Customer creates           Expert decides            Either ends it
POST /bookings  ──►  PENDING ──►  ACCEPTED ──►  COMPLETED
                     │            │
                     ▼            ▼
                  REJECTED     CANCELLED (customer, PENDING/ACCEPTED only)
```

Invalid transitions are rejected with 400 (e.g. accept a REJECTED booking,
complete a PENDING booking, cancel a COMPLETED booking, cancel twice).

### Booking table

`bookings`: id, customer_id →users, expert_id →expert_profiles, service_id →services,
**service_name / service_price (snapshots)**, service_address, service_latitude,
service_longitude (where the work happens — static, not GPS), scheduled_date,
scheduled_time, customer_notes, status, cancellation_reason, created_at, updated_at.

### Customer workflow

```jsonc
// POST /bookings   (CUSTOMER; customer_id always comes from the JWT)
{
  "expert_id": 5, "service_id": 1,
  "service_address": "Madhapur, Hyderabad",
  "service_latitude": 17.4483, "service_longitude": 78.3915,
  "scheduled_date": "2026-10-05", "scheduled_time": "10:30:00",
  "customer_notes": "Need electrical wiring repair"
}
// → 201 { "id": 1, "status": "PENDING", "service_name": "Electrician",
//          "service_price": 299.0, ... }
```

Creation validates (in order): date not in the past → expert exists (404) →
active (400) → VERIFIED (400) → AVAILABLE (400) → service exists (404) →
service ACTIVE (400) → expert offers the service (400) → no slot conflict for
that expert (409) → insert + commit. Any failure rolls everything back.

Other customer endpoints: `GET /bookings/my?status=` (history),
`GET /bookings/{id}` (own only), `PUT /bookings/{id}/cancel {"reason": ...}`
(PENDING/ACCEPTED → CANCELLED).

### Expert workflow

| Endpoint | Transition | Notes |
|---|---|---|
| `GET /experts/bookings?status=` | — | own bookings only |
| `PUT /experts/bookings/{id}/accept` | PENDING → ACCEPTED | requires active + VERIFIED + AVAILABLE |
| `PUT /experts/bookings/{id}/reject` | PENDING → REJECTED | body `{"reason": ...}` stored in cancellation_reason |
| `PUT /experts/bookings/{id}/complete` | ACCEPTED → COMPLETED | |

Experts only ever see/touch bookings assigned to them (403 otherwise).

### Admin workflow

`GET /admin/bookings?status=&service_id=&expert_id=&customer_id=` — inspect all
bookings (no analytics). ADMIN can also view any booking via `GET /bookings/{id}`.

### Snapshot guarantee

`service_name` / `service_price` are copied into the booking at creation and
never re-read from the catalogue: if an admin later renames the service or
changes its price, every historical booking still shows the original values
(verified by tests and the live acceptance script).

### Conflict rule

An expert cannot have two active (PENDING/ACCEPTED) bookings in the same
5-minute slot of the same day → `409 BOOKING_CONFLICT`. No advanced scheduling.

## Phase 4 — real-time communication (WebSocket chat)

Each booking has its own chat room (`booking_{id}`). Only the booking's
**customer** and its **assigned expert** may join — admins are deliberately
not admitted to private chats.

### WebSocket URL & authentication

```
ws://127.0.0.1:8000/ws/bookings/{booking_id}?token=<JWT>
```

The JWT is passed via the `?token=` query parameter (the natural browser
option, since browsers cannot set headers on WebSocket handshakes). The token
is validated with the **same** `decode_access_token` used by the REST API —
no duplicated JWT logic. Missing/invalid/expired tokens are rejected before
the socket is accepted (close codes `4401`), as are missing bookings (`4404`),
non-participants (`4403`), and REJECTED/CANCELLED bookings (`4409`).

Chat is allowed for `PENDING`, `ACCEPTED`, and `COMPLETED` bookings (completed
stays readable so participants can recap the job); REJECTED/CANCELLED rooms
refuse connections.

### Message protocol (JSON)

```jsonc
// client → server
{"type": "message", "message": "Hello, when will you arrive?"}   // 1–2000 chars, trimmed
{"type": "ping"}                                                  // → {"type": "pong"}

// server → all room members
{"type": "message", "booking_id": 101, "sender_id": 10,
 "sender_role": "CUSTOMER", "message": "Hello, ...",
 "timestamp": "2026-09-28T18:30:00Z"}

// connection events (not persisted as messages)
{"type": "user_joined", "user_id": 10}   {"type": "user_left", "user_id": 10}

// errors go only to the sender
{"type": "error", "message": "Message must contain 1-2000 characters."}
```

### Persistence & history

Messages are saved to the `messages` table **before** broadcast (a failed save
returns an error to the sender instead of faking success). History lives in
REST: `GET /bookings/{booking_id}/messages?limit=200` — booking customer or
assigned expert only (other customers/experts/admin → 403, missing booking →
404), ordered `created_at ASC`.

### Connection manager

`app/services/chat_manager.py::ConnectionManager` keeps
`booking_id → [sockets]` (a `defaultdict(list)`); `connect`, `disconnect`,
`get_booking_connections`, and `broadcast_to_booking` operate per booking.
Multiple simultaneous connections per user are supported; dead sockets are
removed individually without touching other participants.

### Try it live

```bash
.venv\Scripts\python scripts\setup_chat_booking.py        # mints booking + prints emails/id
.venv\Scripts\python scripts\websocket_test.py 9          # two-client chat flow
.venv\Scripts\python scripts\ws_security_test.py 9        # intruders denied
```

Swagger documents the REST history endpoint; WebSocket endpoints are not
executable in Swagger UI — use the scripts above or any WS client with the
URL pattern shown here.

## Phase 5 — live location tracking (ACCEPTED bookings only)

**Phase 5 provides live location tracking only for an ACCEPTED booking. Only
the assigned expert can send location. Only the booking's customer and its
assigned expert can access that location. This is NOT public location
sharing.** PENDING/REJECTED/CANCELLED/COMPLETED bookings refuse the location
socket (`4409`); admins are deliberately not admitted; unrelated users get
`4403`; REST without access returns 403 (401 unauthenticated, 404 missing
booking/no location yet).

### Purpose & architecture

While an expert is on an accepted job, they stream GPS fixes that the customer
sees in real time. Location traffic runs over a **dedicated WebSocket,
separate from chat**: `ConnectionManager` keys sockets by `(booking_id,
channel)` with channels `"chat"` (Phase 4) and `"location"` (Phase 5) — the
two streams never mix, and nothing ever crosses bookings.

### WebSocket URL, authentication & authorization

```
ws://127.0.0.1:8000/ws/bookings/{booking_id}/location?token=<JWT>
```

Same JWT machinery as chat: `?token=` is validated with the existing
`decode_access_token` before the socket is accepted (missing/invalid/expired
→ `4401`, missing booking → `4404`, non-participant → `4403`, non-ACCEPTED
status → `4409`). Identity and send-permission come from the JWT user only —
any `user_role` in a client payload is ignored. On connect the server sends
`{"type":"connected","booking_id":…,"role":"expert"|"customer","can_send":bool}`.

### Location message protocol (JSON)

```jsonc
// assigned expert → server (latitude/longitude required, rest optional)
{"type":"location_update","latitude":17.3850,"longitude":78.4867,
 "accuracy":5.0,"heading":90.0,"speed":8.0,"timestamp":"2026-09-29T10:30:00Z"}

// server → every location-channel subscriber of that booking
// (the expert's own socket receives the broadcast echo too)
{"type":"location_update","booking_id":101,"expert_id":20,
 "latitude":17.3850,"longitude":78.4867,"accuracy":5.0,"heading":90.0,
 "speed":8.0,"timestamp":"..."}

{"type":"ping"}   // → {"type":"pong"}
{"type":"error","message":"..."}   // validation/rule errors: sender only
```

Validation (server-side, before anything touches the DB): latitude −90…90,
longitude −180…180, accuracy ≥ 0, heading 0…360, speed ≥ 0, finite numbers,
client `timestamp` must not be > 5 min in the future. Customers and any other
sender get `error: "Only the assigned expert can send location updates."`.

### Update flow & throttling

authenticate → load booking → participant check → ACCEPTED check → parse →
validate → **throttle gate → insert → commit → broadcast**. A frame that fails
any step is never broadcast; a failed commit rolls back and errors to the
sender only. Throttle: at most **one accepted update per booking per
`LOCATION_UPDATE_INTERVAL_SECONDS`** (default `1`, env-configurable; not a GPS
sampling rate) — measured on server-side accept time, so client clocks cannot
buy extra throughput. Too-fast frames are rejected with a clear error and are
not persisted.

### Database model (`live_locations`)

`id` PK · `booking_id` FK→`bookings.id` (CASCADE, indexed) · `expert_id`
FK→`users.id` — the expert's **user** id, matching the JWT subject (indexed) ·
`latitude`/`longitude` Float NOT NULL · `accuracy`/`heading`/`speed` Float
NULL · `timestamp` DateTime NOT NULL (client fix time or server accept time,
indexed) · `created_at` DateTime NOT NULL. Created by `create_all` — additive
only, no existing table or row is ever touched.

### Current + history APIs

- `GET /bookings/{booking_id}/location` — latest fix (`LocationResponse`),
  404 `NO_LOCATION_AVAILABLE` when nothing has been tracked yet.
- `GET /bookings/{booking_id}/location/history?limit=100` —
  `{"booking_id":…,"count":…,"points":[…]}` ordered `timestamp ASC`;
  `limit` is clamped to 1…500 (422 outside).

### Privacy & retention

Location is booking-scoped and access-controlled on the backend; it is never
exposed publicly, never broadcast across bookings, and no JWTs/credentials are
ever stored in location rows. Exact coordinates are not logged. Retention is
configurable via `LOCATION_HISTORY_RETENTION_DAYS=7`, but **nothing deletes
automatically** — run the explicit maintenance helper when you choose:

```bash
.venv\Scripts\python -c "from app.core.database import SessionLocal; from app.services.location_service import purge_expired_locations; print(purge_expired_locations(SessionLocal()))"
```

### Try it live

```bash
.venv\Scripts\python scripts\location_test.py   # full two-client acceptance flow (10 checks)
```

Browser demo: open **`http://127.0.0.1:8000/location-demo`**, paste a booking id
and JWT (both prefillable via `?booking_id=…&token=…`), and watch `location_update`
frames arrive in real time — latest fix panel + live event log, keepalive ping,
reconnect on demand. Connected as the **expert**, the page also shows a send
panel (manual frame, simulated movement, or the device's real GPS); as the
customer it is receive-only, mirroring the server's rules.

WebSocket endpoints cannot be executed from Swagger UI — use the script above
or any WS client with the URL pattern shown here. Swagger documents
`GET /bookings/{id}/location` and `GET /bookings/{id}/location/history`.

## Phase 6 — Razorpay payments + reviews (COMPLETED bookings only)

**Payments.** A customer pays for a COMPLETED booking:

1. `POST /payments/create-order/{booking_id}` (owner CUSTOMER) — validates
   eligibility (COMPLETED, not already PAID, amount > 0), creates a Razorpay
   order via the SDK, and stores a `payments` row (PENDING). The charged
   amount ALWAYS comes from the booking's `service_price` snapshot — never
   the request body. Repeat calls reuse the pending order. Returns the
   Checkout payload including the PUBLIC `key_id` (the secret never leaves
   the backend).
2. React opens Razorpay Checkout (`checkout.js`), customer pays.
3. `POST /payments/verify` — the backend recomputes
   `HMAC-SHA256(order_id|payment_id, KEY_SECRET)` and compares (constant-time)
   with the sent `razorpay_signature`. Valid → `payments.status=SUCCESS` +
   `bookings.payment_status=PAID` (idempotent). Invalid → the payment row is
   marked FAILED and 400 `INVALID_PAYMENT_SIGNATURE` is returned.

Read endpoints: `GET /payments/{id}` (owner/ADMIN),
`GET /payments/booking/{id}` (owner/ADMIN), `GET /payments/my-payments`
(CUSTOMER). No card data is ever stored — only Razorpay ids/signature.
Without `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` in `.env`, payment endpoints
return `503 PAYMENTS_NOT_CONFIGURED` (tests run fully offline via a faked SDK
client + real HMAC verification).

Error codes: `BOOKING_NOT_FOUND` 404, `BOOKING_ACCESS_DENIED` 403,
`BOOKING_NOT_COMPLETED` 400, `PAYMENT_ALREADY_COMPLETED` 409, `INVALID_AMOUNT`
400, `PAYMENT_ORDER_NOT_FOUND` 404, `PAYMENT_ACCESS_DENIED` 403,
`INVALID_PAYMENT_SIGNATURE` 400, `RAZORPAY_ORDER_ERROR` 502,
`PAYMENTS_NOT_CONFIGURED` 503.

**Reviews.** After completion the customer reviews the expert:

- `POST /reviews` `{booking_id, rating 1-5, comment?}` — CUSTOMER who owns a
  COMPLETED booking; one review per booking (409 `REVIEW_ALREADY_EXISTS`);
  `expert_id` is derived from the booking, never accepted from the body.
- `GET /reviews/expert/{expert_id}` — **public**; returns
  `{average_rating, total_reviews, reviews[]}` (newest first, reviewer name).
- `GET /reviews/booking/{booking_id}` — participants/admin.
- `PUT /reviews/{id}` / `DELETE /reviews/{id}` — author (or ADMIN); the
  expert's `rating_avg`/`rating_count` are recalculated on every change.

Rating bounds (1-5) are enforced by Pydantic (422) plus a DB CHECK constraint.

## Phase 6 database changes

Additive and idempotent (no data is ever dropped) — applied automatically at
startup via `create_all` + `_migrate_phase2`:

- **New table `payments`** — `id, booking_id FK→bookings (CASCADE),
  customer_id FK→users (RESTRICT), expert_id FK→expert_profiles (RESTRICT),
  amount DECIMAL(10,2), currency VARCHAR(8), razorpay_order_id VARCHAR(100)
  UNIQUE, razorpay_payment_id VARCHAR(100) UNIQUE, razorpay_signature
  VARCHAR(256), status ENUM(PENDING/SUCCESS/FAILED/REFUNDED), payment_method,
  created_at, updated_at`; index `(booking_id, status)`.
- **New table `reviews`** — `id, booking_id FK→bookings (CASCADE) UNIQUE,
  customer_id FK→users (CASCADE), expert_id FK→expert_profiles (CASCADE),
  rating INT CHECK (1-5), comment VARCHAR(1000), created_at, updated_at`;
  index `(expert_id, created_at)`.
- **`bookings` + `payment_status`** — `VARCHAR(20) NOT NULL DEFAULT 'UNPAID'`
  (legacy rows backfilled to UNPAID; flips to PAID only after verification).
- **`expert_profiles` + `rating_avg DECIMAL(3,2) NULL`,
  `rating_count INT NOT NULL DEFAULT 0`** — denormalized from `reviews`, kept
  consistent by `review_service` inside the same transaction.

## Phase 7 — Gemini LLM assistant (POST /llm/chat)

A JWT-protected AI assistant (CUSTOMER and EXPERT roles; ADMIN → 403) backed
by **Google Gemini** over its REST API (`generativelanguage.googleapis.com
/v1beta/models/{GEMINI_MODEL}:generateContent`, called with httpx — no extra
SDK).

- `POST /llm/chat` `{message, service_context?, history?}` →
  `{"response": "<clean text>"}` — the raw Gemini payload is never forwarded;
  only the single clean text is.
- `message` is required, 1–2000 chars, whitespace-only rejected (422).
- `history` is optional recent conversation from the client
  (`[{role: "user"|"assistant", text}]`, max 8 turns, each ≤ 1000 chars) —
  mapped to Gemini roles (`assistant` → `model`) and truncated server-side to
  `GEMINI_MAX_HISTORY_TURNS`. **No chat persistence** — Phase 7 adds no tables;
  the frontend keeps the conversation in React state.
- The key is read from `GEMINI_API_KEY` (pydantic Settings) and sent only in
  the upstream URL — never returned to clients, never logged.
- System prompt ("Smart Home Service Assistant"): general guidance only,
  explains possible causes, suggests a service category, recommends booking an
  expert; never claims physical diagnosis, never invents
  prices/availability/bookings, never claims actions were performed.
- Error mapping (project `{"error": {code, message}}` idiom):
  `LLM_NOT_CONFIGURED` 503 (no key), `LLM_AUTH_ERROR` 502 (key rejected —
  provider detail never leaks), `LLM_RATE_LIMITED` 429, `LLM_UPSTREAM_ERROR`
  502, `LLM_REQUEST_ERROR` 502, `LLM_UNREACHABLE` 502 (network),
  `LLM_TIMEOUT` 504, `LLM_EMPTY_RESPONSE` 502.
- Offline testability: the network boundary `gemini_service._post` is a
  one-line wrapper that tests replace with a fake (same spirit as the
  payments suite's fake Razorpay client) — no key, no network.

## Phase 8 connection note

Phase 8 (RAG) will slot in *in front of* this service without changing the
endpoint contract: question → embedding → ChromaDB search → retrieved context
→ merged into the Gemini request (`system_instruction`/`contents`) → grounded
response. `GeminiService.generate_reply` and `/llm/chat` are the seams.

## Phase 2 database changes

- `expert_profiles.latitude  NUMERIC(10,7) NULL`
- `expert_profiles.longitude NUMERIC(11,7) NULL`
- `expert_profiles.availability` → enum `AVAILABLE | UNAVAILABLE` (validated server-side)
- `expert_profiles.verification_status` → `PENDING | VERIFIED | REJECTED`
- **New table** `expert_services (expert_id FK→expert_profiles, service_id FK→services)`,
  composite PK — duplicate associations are impossible at the DB level.
- **Phase 4:** new `messages` table — `id, booking_id FK→bookings (CASCADE),
  sender_id FK→users (CASCADE), message VARCHAR(2000), created_at` — indexed on
  `booking_id`, `sender_id`, `created_at`.
- Relationship: `ExpertProfile.service_links ↔ ExpertService.service ↔ Service.expert_links`

## Phase 2 API endpoints & examples

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/services` | public | active services only |
| GET | `/services/{service_id}` | public | 404 if missing |
| POST | `/admin/services` | ADMIN | 409 on duplicate name |
| PUT | `/admin/services/{service_id}` | ADMIN | id immutable |
| GET | `/experts/profile` | EXPERT | full profile + services |
| PUT | `/experts/profile` | EXPERT | partial; `service_ids` replaces set atomically |
| GET | `/experts/nearby` | any signed-in user | see below |
| GET | `/admin/experts` | ADMIN | optional `?verification_status=` filter |
| PUT | `/admin/experts/{expert_id}/verification` | ADMIN | `?verification_status=VERIFIED` |

**Expert registration** (`POST /auth/register-expert`) now also accepts
`latitude`, `longitude`, `availability` (`AVAILABLE|UNAVAILABLE`) and
`service_ids`; User + ExpertProfile + service links are created in ONE
transaction (unknown service id → 404, nothing persisted).

```json
{
  "name": "Ravi Kumar", "email": "ravi@example.com", "phone": "9999999999",
  "password": "password123", "skills": "Electrical wiring",
  "experience_years": 5, "location": "Hyderabad",
  "latitude": 17.3850, "longitude": 78.4867,
  "availability": "AVAILABLE", "service_ids": [1]
}
```

**Nearby search** — `GET /experts/nearby?latitude=17.3850&longitude=78.4867&radius_km=10&service_id=1`:

```json
[
  {
    "expert_id": 5, "user_id": 10, "name": "Ravi Kumar",
    "skills": "Electrical wiring", "experience_years": 5,
    "location": "Hyderabad", "latitude": 17.3850, "longitude": 78.4867,
    "availability": "AVAILABLE", "verification_status": "VERIFIED",
    "distance_km": 3.33,
    "services": [{ "id": 1, "name": "Electrician" }]
  }
]
```

Rules: latitude ∈ [-90, 90], longitude ∈ [-180, 180], radius ∈ (0, 100] km —
violations → 422. Unknown `service_id` → 404. Only VERIFIED + ACTIVE experts
with coordinates are considered; sorted nearest-first; no matches → `200 []`.

## Haversine distance

`app/utils/geo.py::calculate_distance(lat1, lon1, lat2, lon2)` — great-circle
distance in km with Earth radius ≈ 6371:

```
a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlon/2)
c = 2·atan2(√a, √(1−a)) ; distance = 6371 · c
```

## Troubleshooting

- **`Access denied for user 'root'`** — wrong password in `DATABASE_URL`.
- **`Unknown database`** — run `python -m app.init_db` (auto-creates) or create manually.
- **`InsecureKeyLengthWarning`** — use a 32+ character JWT secret.
