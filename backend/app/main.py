"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.api.admin import router as admin_router
from app.api.bookings import router as bookings_router
from app.api.experts import router as experts_router
from app.api.llm import router as llm_router
from app.api.location import router as location_router
from app.api.messages import router as messages_router
from app.api.payments import router as payments_router
from app.api.reviews import router as reviews_router
from app.api.services import router as services_router
from app.api.users import router as users_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.init_db import INITIAL_SERVICES, _migrate_phase2
from app.models import Service
from app.models.service import ServiceStatus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed the initial services on startup (idempotent)."""
    logger.info("Running database initialization (tables + migration + seeds)...")
    Base.metadata.create_all(bind=engine)
    _migrate_phase2()
    db = SessionLocal()
    try:
        existing_names = set(
            db.execute(select(Service.name)).scalars().all()
        )
        for name, description, base_price in INITIAL_SERVICES:
            if name not in existing_names:
                db.add(
                    Service(
                        name=name,
                        description=description,
                        base_price=base_price,
                        status=ServiceStatus.ACTIVE,
                    )
                )
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="AI-BASED-SMART-HOME-SERVICES API",
    description=(
        "Intelligent home-service platform API.\n\n"
        "**Phase 1:** authentication, users, experts, services, role-based authorization.\n\n"
        "**Phase 2:** service catalogue APIs, admin service management, expert profile "
        "management, expert-service relationships, verification workflow, and nearby "
        "expert search (Haversine over *static* profile coordinates — no live GPS).\n\n"
        "**Phase 3:** booking system — customers book verified experts, experts "
        "accept/reject/complete, customers cancel; status lifecycle "
        "PENDING → ACCEPTED → COMPLETED (plus REJECTED/CANCELLED); service "
        "name/price snapshots. No payments, chat, or live tracking.\n\n"
        "**Phase 4:** real-time text chat per booking via WebSocket — "
        "`ws://host/ws/bookings/{booking_id}?token=<JWT>` — only the booking's "
        "customer and assigned expert; messages persisted and available via "
        "`GET /bookings/{booking_id}/messages`.\n\n"
        "**Phase 5:** live expert location tracking per ACCEPTED booking via a "
        "dedicated WebSocket — `ws://host/ws/bookings/{booking_id}/location?token=<JWT>` "
        "— only the assigned expert sends `location_update` frames; customer and "
        "expert receive them; latest + history REST endpoints "
        "(`GET /bookings/{booking_id}/location[/history]`); throttled and "
        "validated server-side.\n\n"
        "**Phase 6:** Razorpay payments for COMPLETED bookings — "
        "`POST /payments/create-order/{booking_id}` → Razorpay Checkout → "
        "`POST /payments/verify` (server-side HMAC-SHA256 signature check; the "
        "frontend claim is never trusted) → `payments` row + "
        "`bookings.payment_status = PAID`. Plus a 1-5 review system: one review "
        "per completed booking, editable/deletable by its author, with the "
        "expert's average rating recalculated on every change.\n\n"
        "**Phase 7:** Google Gemini AI assistant — `POST /llm/chat` (JWT, "
        "CUSTOMER/EXPERT) returns clean guidance text for home-service "
        "questions and suggests a service category; it never books, pays, or "
        "invents prices/availability. The Gemini key stays on the backend; "
        "without it the endpoint answers 503 `LLM_NOT_CONFIGURED`.\n\n"
        "**Auth flow:** `POST /auth/login` (or Authorize button) → copy the "
        "`access_token` → click Authorize → paste "
        "`Bearer <access_token>`."
    ),
    version="7.0.0-phase7",
    lifespan=lifespan,
)


# --- CORS (for the React frontend) -------------------------------------------

# Frontend origins — configurable via env (.env: CORS_ORIGINS) so deployments
# stay explicit. Never widen to "*" in production: unsafe with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global exception handlers ---------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 with a clean list of what failed validation."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": [
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", []) if loc != "body"),
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
                for err in exc.errors()
            ]
        },
    )


@app.exception_handler(DBAPIError)
async def dbapi_error_handler(request: Request, exc: DBAPIError):
    logger.exception("Database error")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error, please try again later"},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("SQLAlchemy error")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error, please try again later"},
    )


@app.exception_handler(OperationalError)
async def operational_error_handler(request: Request, exc: OperationalError):
    logger.exception("Database connection error")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database unavailable, please try again later"},
    )


# --- Routers ----------------------------------------------------------------

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(services_router)
app.include_router(experts_router)
app.include_router(bookings_router)
app.include_router(messages_router)
app.include_router(location_router)
app.include_router(payments_router)
app.include_router(reviews_router)
app.include_router(llm_router)
app.include_router(admin_router)


@app.get("/", tags=["Health"], summary="Health check")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "AI-BASED-SMART-HOME-SERVICES",
        "phases": [1, 2, 3, 4, 5, 6, 7],
    }


# --- Phase 5 demo page -------------------------------------------------------

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/location-demo", include_in_schema=False, summary="Phase 5 live location demo page")
def location_demo_page() -> FileResponse:
    """Browser demo for the location WebSocket (dev/testing aid — the page
    itself is harmless without a valid JWT)."""
    return FileResponse(_STATIC_DIR / "location_demo.html", media_type="text/html")


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
