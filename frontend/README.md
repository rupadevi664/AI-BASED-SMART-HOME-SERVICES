# Frontend — SmartHome Services (React + Vite)

React SPA for the AI-BASED-SMART-HOME-SERVICES backend (Phases 1–6). It uses
only the existing REST endpoints and WebSocket protocols — no mock data.

## Stack

React 18 · Vite 5 · React Router 6 · Axios · Context API (auth) ·
Leaflet + OpenStreetMap (live map) · WebSocket API · Browser Geolocation API ·
plain CSS (custom theme, responsive).

## Run

```bash
cd frontend
npm install            # first time
npm run dev            # http://localhost:5173  (backend must be running)
npm run build          # production build → dist/
```

Backend (separate terminal, from `backend/`): `uvicorn app.main:app --reload`.
The backend's CORS default already allows `http://localhost:5173`
(override with `CORS_ORIGINS` in `backend/.env`).

## Environment

Copy `.env.example` → `.env` (already done for local dev):

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

Only `VITE_*` vars are exposed to the browser bundle — never put backend
secrets here. JWT lives in `localStorage` and is attached by an Axios
interceptor; a 401 anywhere clears the session and redirects to `/login`.

## Structure

```
frontend/src/
├── components/   Navbar, ProtectedRoute(routes/), ServiceCard, ExpertCard,
│                 BookingCard, ChatBox, LiveMap, Badges, Loading
├── pages/        Login, Register, CustomerDashboard, Services, NearbyExperts,
│                 ExpertProfile, CreateBooking, MyBookings, ExpertDashboard,
│                 ExpertBookings, ExpertProfileEditor, Chat, LiveTracking,
│                 AdminDashboard
├── services/     api.js (Axios + JWT + errors), authService, serviceService,
│                 expertService, bookingService, messageService,
│                 websocketService (BookingSocket: reconnect + heartbeat)
├── context/      AuthContext (token + user + role helpers)
├── hooks/        useGeolocation (getCurrentPosition + watchPosition)
└── routes/       AppRoutes (ProtectedRoute with allowedRoles)
```

## Route map (role-protected)

| Route | Role |
|---|---|
| `/login`, `/register` | public |
| `/customer/dashboard` `/customer/services` `/customer/experts` `/customer/experts/:id` `/customer/book/new` `/customer/bookings` `/customer/bookings/:id/chat` `/customer/bookings/:id/tracking` | CUSTOMER |
| `/expert/dashboard` `/expert/bookings` `/expert/profile` `/expert/bookings/:id/chat` `/expert/bookings/:id/tracking` | EXPERT |
| `/admin/dashboard` (stats · expert verification · services · bookings) | ADMIN |

Wrong-role access redirects to the user's own dashboard; missing/expired JWT
redirects to `/login`.

## Backend integration map

| UI | Backend call |
|---|---|
| Login / Register | `POST /auth/login`, `POST /auth/register`, `POST /auth/register-expert`, `GET /auth/me` |
| Services | `GET /services` |
| Nearby experts | `GET /experts/nearby?latitude&longitude&radius_km[&service_id]` |
| Expert profile | data from the nearby response (backend has no public `GET /experts/{id}`) + `GET /reviews/expert/{id}` (public ratings) |
| Create booking | `POST /bookings` (BookingCreate schema) |
| My bookings / cancel | `GET /bookings/my`, `PUT /bookings/{id}/cancel` |
| Pay Now (COMPLETED) | `POST /payments/create-order/{id}` → Razorpay Checkout (`checkout.js`) → `POST /payments/verify` (server-side signature check) |
| Rate your expert (COMPLETED) | `GET/POST /reviews`, `PUT/DELETE /reviews/{id}` |
| Expert requests | `GET /experts/bookings`, `PUT /experts/bookings/{id}/accept|reject|complete` |
| Expert profile editor | `GET/PUT /experts/profile` |
| Chat history | `GET /bookings/{id}/messages` |
| Admin | `GET /admin/dashboard`, `GET /admin/experts`, `PUT /admin/experts/{id}/verification`, `POST/PUT /admin/services`, `GET /admin/bookings` |

**WebSockets** (JWT via `?token=`, same as Swagger-era Phase 4/5 contracts):

- Chat: `ws://host/ws/bookings/{id}?token=<JWT>` — frames
  `message`/`user_joined`/`user_left`/`error`/`pong`.
- Location: `ws://host/ws/bookings/{id}/location?token=<JWT>` — server sends
  `connected` then `location_update`; the assigned expert sends
  `location_update` frames (server validates + throttles).

## Payments + reviews (Phase 6)

- COMPLETED bookings in **My Bookings** show a **Pay ₹…** button. It loads
  `https://checkout.razorpay.com/v1/checkout.js`, creates the order via the
  backend, opens Razorpay Checkout, and verifies the result via the backend
  (`POST /payments/verify`) before showing the success receipt (payment id,
  amount, booking id). Cancelled/failed checkouts show a readable error and
  the booking stays UNPAID. Requires `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`
  in `backend/.env` (otherwise the backend returns a clear 503 message).
- The same cards show a **Rate your expert** star widget (1–5 + comment) with
  edit/delete of an existing review.
- **Expert profile** pages show the public average rating, review count and
  the review list from `GET /reviews/expert/{id}`.

## Live tracking flow

- **Expert** (`LiveTracking`): Start Location Sharing →
  `navigator.geolocation.watchPosition` → `location_update` frames at most
  ~1/s (server throttle is 1/s). Stop Sharing ends the stream.
- **Customer** (`LiveTracking`): opens the same booking's location channel;
  the map seeds from `GET /bookings/{id}/location[/history]` and the 🛠️
  marker moves on every `location_update` — no refresh.

## AI Assistant (Phase 7)

- **AI Assistant** appears in the customer navbar (`/customer/assistant`,
  CUSTOMER-only route). Chat bubbles in a card (reusing the Phase 4 chat
  styles), suggestion chips for common questions, and a **Thinking…** pending
  bubble while the request runs — the Send button is disabled while busy so
  duplicates are impossible.
- The conversation lives in React state (max 8 turns sent as `history`);
  a **Clear conversation** button resets it. Nothing is persisted.
- Calls `POST /llm/chat` through the shared `api` client (JWT attached
  automatically) via `src/services/llmService.js` — no duplicate axios
  config, and the Gemini key is backend-only (never in frontend code or
  responses).
- Errors surface as a friendly alert line above the input (e.g. the backend's
  503 `LLM_NOT_CONFIGURED` message when no `GEMINI_API_KEY` is set); a failed
  turn keeps the user's question and drops the pending bubble.

## Demo script (2 browsers or normal + incognito)

1. Register a customer (Customer tab) and an expert (Expert tab).
2. Admin verifies the expert (Swagger `PUT /admin/experts/{id}/verification`
   or the Admin Dashboard → EXPERTS → Verify).
3. Customer: Services → Electrician → set radius/location → E2E Expert →
   Book Now → create booking.
4. Expert: Dashboard → Accept.
5. Customer: My Bookings → 💬 Chat → send a message; Expert: Chat → reply.
6. Expert: 📍 Share location → Start Location Sharing (allow GPS).
   Customer: 🗺 Track expert → watch the marker move live.
7. Refresh any page — the session persists (TEST 8 passed).

## Known limitations (honest list)

- Expert identity in booking cards shows "Expert #id" — the backend exposes
  no public expert-by-id endpoint for customers (identified gap, not worked
  around with an invented API).
- In the automated test browser, `watchPosition` cannot supply real GPS
  (headless limitation); manual testing in a normal browser streams fine.
