"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.api.admin import router as admin_router
from app.api.bookings import router as bookings_router
from app.api.experts import router as experts_router
from app.api.messages import router as messages_router
from app.api.services import router as services_router
from app.api.users import router as users_router
from app.auth.router import router as auth_router
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
        "**Auth flow:** `POST /auth/login` (or Authorize button) → copy the "
        "`access_token` → click Authorize → paste "
        "`Bearer <access_token>`."
    ),
    version="4.0.0-phase4",
    lifespan=lifespan,
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
app.include_router(admin_router)


@app.get("/", tags=["Health"], summary="Health check")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "AI-BASED-SMART-HOME-SERVICES",
        "phases": [1, 2, 3, 4],
    }
