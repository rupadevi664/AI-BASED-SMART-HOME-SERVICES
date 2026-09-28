"""Booking business logic (Phase 3): creation, lifecycle, listings.

All writes happen inside one session transaction; any failure rolls back so no
partial booking rows can exist.
"""
import logging
from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, ExpertProfile, Service, User
from app.models.expert import AvailabilityStatus, VerificationStatus
from app.models.service import ServiceStatus
from app.schemas.booking import BookingCreate, _floor_to_slot

logger = logging.getLogger(__name__)


def _fail(code: str, http_status: int, message: str) -> HTTPException:
    """Machine-readable booking error: `{"error": {"code": ..., "message": ...}}`."""
    return HTTPException(
        status_code=http_status,
        detail={"error": {"code": code, "message": message}},
    )


class BookingService:
    # ------------------------------------------------------------------ create
    @staticmethod
    def create_booking(db: Session, customer: User, payload: BookingCreate) -> Booking:
        """Validate everything, then create a PENDING booking in one transaction.

        customer_id always comes from the authenticated user (JWT) — never the
        request body.
        """
        if customer.role != "CUSTOMER":
            raise _fail("INVALID_ROLE", 403, "Only customers can create bookings")

        # --- Validate date/time (before touching other tables) ---
        BookingService._validate_schedule(payload.scheduled_date, payload.scheduled_time)

        # --- Expert checks ---
        expert = db.get(ExpertProfile, payload.expert_id)
        if expert is None:
            raise _fail("EXPERT_NOT_FOUND", 404, f"Expert {payload.expert_id} not found")
        expert_user = expert.user
        if expert_user is None or not expert_user.is_active:
            raise _fail("EXPERT_INACTIVE", 400, "Expert account is not active")
        if expert.verification_status != VerificationStatus.VERIFIED:
            raise _fail("EXPERT_NOT_VERIFIED", 400, "Expert is not verified yet")
        if expert.availability != AvailabilityStatus.AVAILABLE:
            raise _fail("EXPERT_UNAVAILABLE", 400, "Expert is currently unavailable")

        # --- Service checks ---
        service = db.get(Service, payload.service_id)
        if service is None:
            raise _fail("SERVICE_NOT_FOUND", 404, f"Service {payload.service_id} not found")
        if service.status != ServiceStatus.ACTIVE:
            raise _fail("SERVICE_INACTIVE", 400, "Service is not active")

        # --- Relationship check: expert must provide this service ---
        provides = any(link.service_id == payload.service_id for link in expert.service_links)
        if not provides:
            raise _fail(
                "SERVICE_NOT_OFFERED",
                400,
                "Expert does not provide the selected service",
            )

        # --- Conflict check: same expert, same 5-minute slot, active booking ---
        BookingService._ensure_no_conflict(
            db, expert_id=expert.id,
            scheduled_date=payload.scheduled_date,
            scheduled_time=payload.scheduled_time,
        )

        booking = Booking(
            customer_id=customer.id,          # from JWT, never from the body
            expert_id=expert.id,
            service_id=service.id,
            service_name=service.name,        # snapshot
            service_price=service.base_price,  # snapshot
            service_address=payload.service_address.strip(),
            service_latitude=payload.service_latitude,
            service_longitude=payload.service_longitude,
            scheduled_date=payload.scheduled_date,
            scheduled_time=payload.scheduled_time,
            customer_notes=payload.customer_notes,
            status=BookingStatus.PENDING,
        )
        db.add(booking)
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error creating booking")
            raise _fail("BOOKING_DB_ERROR", 500, "Database error, please try again later") from exc
        db.refresh(booking)
        return booking

    # ------------------------------------------------------------- validations
    @staticmethod
    def _validate_schedule(scheduled_date: date, scheduled_time: time) -> None:
        # Naive system-local comparison keeps this portable (no tzdata needed).
        combined = datetime.combine(scheduled_date, scheduled_time)
        if combined < datetime.now():
            raise _fail("PAST_SCHEDULE", 400, "Scheduled date/time is in the past")

    @staticmethod
    def _ensure_no_conflict(
        db: Session, *, expert_id: int, scheduled_date: date, scheduled_time: time
    ) -> None:
        slot = _floor_to_slot(scheduled_time)
        # Load the expert's active bookings for that day and compare slots in
        # Python (portable across MySQL and SQLite).
        rows = db.execute(
            select(Booking.scheduled_time)
            .where(
                Booking.expert_id == expert_id,
                Booking.scheduled_date == scheduled_date,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.ACCEPTED]),
            )
        ).scalars().all()
        for existing_time in rows:
            if _floor_to_slot(existing_time) == slot:
                raise _fail(
                    "BOOKING_CONFLICT",
                    409,
                    f"Expert already has a booking at {slot.strftime('%H:%M')} on {scheduled_date}",
                )

    # ------------------------------------------------------------- transitions
    @staticmethod
    def transition(
        db: Session,
        booking: Booking,
        new_status: BookingStatus,
        reason: str | None = None,
    ) -> Booking:
        """Apply a validated status transition and commit."""
        allowed: dict[BookingStatus, set[BookingStatus]] = {
            BookingStatus.PENDING: {BookingStatus.ACCEPTED, BookingStatus.REJECTED, BookingStatus.CANCELLED},
            BookingStatus.ACCEPTED: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
            BookingStatus.REJECTED: set(),
            BookingStatus.CANCELLED: set(),
            BookingStatus.COMPLETED: set(),
        }
        if new_status not in allowed.get(booking.status, set()):
            raise _fail(
                "INVALID_TRANSITION",
                400,
                f"Cannot move booking from {booking.status.value} to {new_status.value}",
            )
        booking.status = new_status
        if reason is not None:
            booking.cancellation_reason = reason
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during booking transition")
            raise _fail("BOOKING_DB_ERROR", 500, "Database error, please try again later") from exc
        db.refresh(booking)
        return booking

    # ---------------------------------------------------------------- listings
    @staticmethod
    def list_for_customer(
        db: Session, customer_id: int, status_filter: BookingStatus | None
    ) -> list[Booking]:
        query = (
            select(Booking)
            .where(Booking.customer_id == customer_id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
        )
        if status_filter is not None:
            query = query.where(Booking.status == status_filter)
        return list(db.execute(query).scalars().all())

    @staticmethod
    def list_for_expert(
        db: Session, expert_profile_id: int, status_filter: BookingStatus | None
    ) -> list[Booking]:
        query = (
            select(Booking)
            .where(Booking.expert_id == expert_profile_id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
        )
        if status_filter is not None:
            query = query.where(Booking.status == status_filter)
        return list(db.execute(query).scalars().all())

    @staticmethod
    def list_for_admin(
        db: Session,
        *,
        status_filter: BookingStatus | None,
        service_id: int | None,
        expert_id: int | None,
        customer_id: int | None,
    ) -> list[Booking]:
        query = select(Booking).order_by(Booking.created_at.desc(), Booking.id.desc())
        if status_filter is not None:
            query = query.where(Booking.status == status_filter)
        if service_id is not None:
            query = query.where(Booking.service_id == service_id)
        if expert_id is not None:
            query = query.where(Booking.expert_id == expert_id)
        if customer_id is not None:
            query = query.where(Booking.customer_id == customer_id)
        return list(db.execute(query).scalars().all())
