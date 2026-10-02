"""Live-location endpoints (Phase 5): WebSocket stream + REST latest/history.

Authorization model (enforced on the backend, never trusted from the client):

- Identity comes from the `?token=<JWT>` (WebSocket) or the Authorization
  header (REST) — `user_role`/ids in any client payload are ignored.
- Only the booking's CUSTOMER and its ASSIGNED EXPERT may access location;
  admins are deliberately NOT auto-admitted (private data, not oversight).
- Only the ASSIGNED EXPERT may send `location_update` frames; the customer
  (and the expert, as an observer) may only receive.
- Live tracking exists only while the booking is ACCEPTED.
- Updates are throttled to one accepted update per booking per
  `LOCATION_UPDATE_INTERVAL_SECONDS`.
"""

import json
import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.messages import _authenticate_query_token, _participant_or_none
from app.api.messages import ws_error as _ws_error
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.models import Booking, BookingStatus, User
from app.schemas.location import (
    LocationHistoryResponse,
    LocationResponse,
    LocationUpdate,
    LocationWebSocketMessage,
)
from app.services.booking_service import _fail
from app.services.chat_manager import CHANNEL_LOCATION, manager
from app.services.location_service import (
    latest_location,
    location_history,
    save_location,
    should_accept_update,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Location"])

# Live tracking is only for an active job — exactly the ACCEPTED status.
LOCATION_ALLOWED_STATUSES = {BookingStatus.ACCEPTED}


def _get_booking_or_404(db: Session, booking_id: int, user: User) -> Booking:
    """Shared REST guard: booking exists, caller is a participant."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
    if not _participant_or_none(booking, user):
        raise _fail(
            "LOCATION_ACCESS_DENIED", 403, "You do not have access to this booking's location"
        )
    return booking


# --- REST: current + historical location -------------------------------------


@router.get(
    "/bookings/{booking_id}/location",
    response_model=LocationResponse,
    summary="Latest expert location for a booking (customer or assigned expert)",
)
def get_current_location(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationResponse:
    """Most recent stored fix, or 404 when nothing has been tracked yet."""
    _get_booking_or_404(db, booking_id, current_user)
    row = latest_location(db, booking_id)
    if row is None:
        raise _fail(
            "NO_LOCATION_AVAILABLE", 404, "No location has been tracked for this booking yet"
        )
    return LocationResponse.model_validate(row)


@router.get(
    "/bookings/{booking_id}/location/history",
    response_model=LocationHistoryResponse,
    summary="Expert location history for a booking, oldest → newest (max 500)",
)
def get_location_history(
    booking_id: int,
    limit: int = Query(default=100, gt=0, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationHistoryResponse:
    _get_booking_or_404(db, booking_id, current_user)
    points = location_history(db, booking_id, limit)
    return LocationHistoryResponse(
        booking_id=booking_id,
        count=len(points),
        points=[LocationResponse.model_validate(p) for p in points],
    )


# --- WebSocket: live location stream -----------------------------------------


@router.websocket("/ws/bookings/{booking_id}/location")
async def booking_location_ws(
    websocket: WebSocket,
    booking_id: int,
    token: str = Query(...),
) -> None:
    """Dedicated location channel, separate from the chat WebSocket.

    - Auth before accept (close codes 4401/4404/4403/4409 — same convention
      as the chat socket).
    - Only the assigned expert's `location_update` frames are accepted; they
      are validated, persisted (commit → broadcast), then fanned out to every
      subscriber on this booking's location channel.
    """
    db = SessionLocal()
    try:
        user = _authenticate_query_token(db, token)
        if user is None:
            await websocket.close(code=4401, reason="Invalid authentication token.")
            return

        booking = db.get(Booking, booking_id)
        if booking is None:
            await websocket.close(code=4404, reason="Booking not found.")
            return
        if not _participant_or_none(booking, user):
            await websocket.close(code=4403, reason="You are not authorized to access this booking.")
            return
        if booking.status not in LOCATION_ALLOWED_STATUSES:
            await websocket.close(
                code=4409,
                reason="Live location is available only for accepted bookings.",
            )
            return

        # May THIS connection produce updates? Assigned expert only, decided
        # from the JWT user — never from any client-sent role field.
        is_expert = booking.expert_id == getattr(
            getattr(user, "expert_profile", None), "id", None
        )

        await manager.connect(booking_id, websocket, channel=CHANNEL_LOCATION)
        try:
            await websocket.send_json(
                {
                    "type": "connected",
                    "booking_id": booking_id,
                    "role": "expert" if is_expert else "customer",
                    "can_send": is_expert,
                    "message": "Live location stream connected.",
                }
            )
            while True:
                raw = await websocket.receive_text()
                reply = await _handle_location_frame(db, booking, user, is_expert, raw)
                if reply is not None:
                    # Errors and pong keepalives go to the sender only;
                    # successful updates return None (already broadcast).
                    await websocket.send_json(reply)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Unexpected error in booking %s location stream", booking_id)
        finally:
            manager.disconnect(booking_id, websocket, channel=CHANNEL_LOCATION)
    finally:
        db.close()


async def _handle_location_frame(
    db: Session,
    booking: Booking,
    user: User,
    is_expert: bool,
    raw: str,
) -> dict | None:
    """Validate → persist → broadcast one frame.

    Returns an error dict for the sender, or None when the frame was a
    successful update (already broadcast) or a throttled no-op.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _ws_error("Invalid JSON.")
    if not isinstance(data, dict):
        return _ws_error("Invalid JSON.")

    if data.get("type") == "ping":
        return {"type": "pong"}

    if not is_expert:
        return _ws_error("Only the assigned expert can send location updates.")

    try:
        update = LocationUpdate.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(loc) for loc in first.get("loc", []))
        return _ws_error(f"Invalid location data: {field or 'payload'} — {first.get('msg')}")

    # Throttle BEFORE writing anything to the database.
    interval = settings.LOCATION_UPDATE_INTERVAL_SECONDS
    if not should_accept_update(db, booking.id, interval=interval):
        return _ws_error(
            "Location updates are being sent too frequently. "
            f"Limit is one update every {interval:g} second(s)."
        )

    try:
        row = save_location(
            db,
            booking_id=booking.id,
            expert_id=user.id,
            latitude=update.latitude,
            longitude=update.longitude,
            accuracy=update.accuracy,
            heading=update.heading,
            speed=update.speed,
            timestamp=update.timestamp,
        )
    except SQLAlchemyError:
        # Rolled back inside save_location; nothing was persisted or broadcast.
        return _ws_error("Could not save the location. Please try again.")

    payload = LocationWebSocketMessage(
        booking_id=booking.id,
        expert_id=user.id,
        latitude=row.latitude,
        longitude=row.longitude,
        accuracy=row.accuracy,
        heading=row.heading,
        speed=row.speed,
        timestamp=row.timestamp,
    )
    await manager.broadcast_to_booking(
        booking.id, payload.broadcast_dict(), channel=CHANNEL_LOCATION
    )
    return None
