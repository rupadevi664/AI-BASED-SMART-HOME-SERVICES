# Backend — AI-BASED-SMART-HOME-SERVICES (Phase 1 + 2 + 3 + 4)

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
catalogue and expert verification. Booking, chat, payments and AI features
belong to later phases.

## 2. Feature matrix

| Phase | Included |
|---|---|
| 1 | Auth (register/login/JWT), roles CUSTOMER/EXPERT/ADMIN, User + ExpertProfile + Service models, protected endpoints, Swagger, 31 tests |
| 2 | `GET /services`, `GET /services/{id}`, admin CRUD for services, expert profile GET/PUT, expert↔service M2M, admin verification, Haversine nearby search, 44 more tests |
| 3 | Booking model + lifecycle, `POST /bookings`, customer history/cancel, expert accept/reject/complete, admin booking views, snapshots, conflicts, 46 more tests |
| 4 | `WS /ws/bookings/{id}` chat, `GET /bookings/{id}/messages` history, Message model + table, booking-scoped ConnectionManager, JWT `?token=` auth, 30 more tests |

Not implemented (later phases): booking, payments/Razorpay, chat/WebSockets,
live location, LLM/RAG/ChromaDB, notifications, reviews/ratings, frontend.

## 3. Technology stack

Python 3.10+ (developed on 3.13) · FastAPI 0.141 · Uvicorn 0.52 · SQLAlchemy 2.0
· PyMySQL (MySQL 8) · Pydantic v2 + pydantic-settings · PyJWT (HS256) · bcrypt ·
pytest + httpx. **No new dependencies were added for Phase 2.**

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
.venv\Scripts\python -m pytest -v        # 151 tests, SQLite in-memory, no creds
.venv\Scripts\python scripts\live_acceptance.py   # 77 checks vs a running server
.venv\Scripts\python scripts\setup_chat_booking.py # mint customer/expert/booking for chat
.venv\Scripts\python scripts\websocket_test.py [booking_id]   # two-client chat flow
.venv\Scripts\python scripts\ws_security_test.py [booking_id] # intruders denied
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
