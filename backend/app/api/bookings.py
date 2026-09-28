"""Booking endpoints (Phase 3): create, history, detail, cancel."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models import Booking, BookingStatus, User
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCreate,
    BookingResponse,
)
from app.services.booking_service import BookingService, _fail

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking (CUSTOMER only)",
)
def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    """customer_id comes from the JWT; the body value (if any) is ignored.
    Snapshots service name/price; status starts at PENDING."""
    return BookingService.create_booking(db, current_user, payload)


@router.get(
    "/my",
    response_model=list[BookingResponse],
    summary="Customer's own booking history",
)
def my_bookings(
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Booking]:
    if current_user.role != "CUSTOMER":
        raise _fail("INVALID_ROLE", 403, "Only customers have a booking history here")
    return BookingService.list_for_customer(db, current_user.id, status_filter)


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Booking details (owner customer, assigned expert, or ADMIN)",
)
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")

    role = current_user.role
    if role == "ADMIN":
        return booking
    if role == "CUSTOMER" and booking.customer_id == current_user.id:
        return booking
    if role == "EXPERT" and current_user.expert_profile is not None \
            and booking.expert_id == current_user.expert_profile.id:
        return booking
    raise _fail("BOOKING_ACCESS_DENIED", 403, "You do not have access to this booking")


@router.put(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking (CUSTOMER who owns it)",
)
def cancel_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Booking:
    """Allowed: PENDING → CANCELLED, ACCEPTED → CANCELLED."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
    if current_user.role != "CUSTOMER" or booking.customer_id != current_user.id:
        raise _fail("BOOKING_ACCESS_DENIED", 403, "You can only cancel your own bookings")
    return BookingService.transition(
        db, booking, BookingStatus.CANCELLED, reason=payload.reason
    )
