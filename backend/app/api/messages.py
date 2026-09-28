"""Chat endpoints (Phase 4): WebSocket real-time messaging + REST history."""
import json
import logging
from datetime import timezone

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import SessionLocal, get_db
from app.models import Booking, BookingStatus, Message, User
from app.schemas.message import MAX_MESSAGE_LENGTH, MessageResponse, OutgoingChatMessage
from app.services.booking_service import _fail
from app.services.chat_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

# Bookings in these statuses allow chat. COMPLETED stays readable so
# participants can recap the job afterwards; REJECTED/CANCELLED do not.
CHAT_ALLOWED_STATUSES = {BookingStatus.PENDING, BookingStatus.ACCEPTED, BookingStatus.COMPLETED}


def ws_error(message: str) -> dict:
    """Consistent WebSocket error payload."""
    return {"type": "error", "message": message}


def _get_booking_or_none(db: Session, booking_id: int) -> Booking | None:
    return db.get(Booking, booking_id)


def _participant_or_none(booking: Booking, user: User) -> bool:
    """Only the booking's customer or its assigned expert may participate.
    Admins are NOT auto-admitted to private chats."""
    if user.id == booking.customer_id:
        return True
    expert_profile = user.expert_profile
    return expert_profile is not None and booking.expert_id == expert_profile.id


# --- REST: message history ----------------------------------------------------


def _booking_for_history(db: Session, booking_id: int, user: User) -> Booking:
    booking = _get_booking_or_none(db, booking_id)
    if booking is None:
        raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
    if not _participant_or_none(booking, user):
        raise _fail("CHAT_ACCESS_DENIED", 403, "You do not have access to this chat")
    return booking


@router.get(
    "/bookings/{booking_id}/messages",
    response_model=list[MessageResponse],
    summary="Chat history for a booking (customer or assigned expert)",
)
def message_history(
    booking_id: int,
    limit: int = Query(default=200, gt=0, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    """Messages ordered oldest → newest (created_at ASC)."""
    _booking_for_history(db, booking_id, current_user)
    return list(db.execute(select_messages(booking_id, limit)).scalars().all())


def select_messages(booking_id: int, limit: int):
    from sqlalchemy import select

    return (
        select(Message)
        .where(Message.booking_id == booking_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .limit(limit)
    )


# --- WebSocket: real-time chat -------------------------------------------------


@router.websocket("/ws/bookings/{booking_id}")
async def booking_chat(
    websocket: WebSocket,
    booking_id: int,
    token: str = Query(...),
) -> None:
    """Booking room: only the booking's customer and assigned expert, JWT via
    `?token=<JWT>`. Messages are validated, persisted, then broadcast."""
    # --- Authenticate BEFORE accepting the socket (clean HTTP 401/403 path) ---
    db = SessionLocal()
    try:
        user = _authenticate_query_token(db, token)
        if user is None:
            await websocket.close(code=4401, reason="Invalid authentication token.")
            return

        booking = _get_booking_or_none(db, booking_id)
        if booking is None:
            await websocket.close(code=4404, reason="Booking not found.")
            return
        if not _participant_or_none(booking, user):
            await websocket.close(code=4403, reason="You are not authorized to access this booking.")
            return
        if booking.status not in CHAT_ALLOWED_STATUSES:
            await websocket.close(
                code=4409,
                reason=f"Chat is not available for {booking.status.value} bookings.",
            )
            return

        await manager.connect(booking_id, websocket)
        # Optional join event — never persisted as a chat message.
        await manager.broadcast_to_booking(
            booking_id, {"type": "user_joined", "user_id": user.id}
        )

        try:
            while True:
                raw = await websocket.receive_text()
                reply = await _handle_client_payload(db, booking, user, raw)
                if reply is not None:
                    if reply.get("type") == "error":
                        # Errors go only to the sender.
                        await websocket.send_json(reply)
                    else:
                        await manager.broadcast_to_booking(booking_id, reply)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Unexpected error in booking %s chat", booking_id)
        finally:
            manager.disconnect(booking_id, websocket)
            await manager.broadcast_to_booking(
                booking_id, {"type": "user_left", "user_id": user.id}
            )
    finally:
        db.close()


def _authenticate_query_token(db: Session, token: str) -> User | None:
    """Validate the query-param JWT with the existing core implementation."""
    import jwt as pyjwt

    from app.core.security import decode_access_token

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (pyjwt.InvalidTokenError, TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


async def _handle_client_payload(
    db: Session, booking: Booking, user: User, raw: str
) -> dict | None:
    """Validate + persist + build the broadcast payload for one client frame.

    Returns an error dict (sent to the sender only) or the broadcast payload.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ws_error("Invalid JSON.")
    if not isinstance(data, dict):
        return ws_error("Invalid JSON.")

    msg_type = data.get("type", "message")

    if msg_type == "ping":
        return {"type": "pong"}

    if msg_type != "message":
        return ws_error(f"Unsupported message type: {msg_type}")

    text = data.get("message")
    if not isinstance(text, str):
        return ws_error("Message must contain 1-2000 characters.")
    text = text.strip()
    if not (1 <= len(text) <= MAX_MESSAGE_LENGTH):
        return ws_error("Message must contain 1-2000 characters.")

    # --- Persist first: a failed save must never be broadcast as success ---
    message = Message(booking_id=booking.id, sender_id=user.id, message=text)
    db.add(message)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist chat message for booking %s", booking.id)
        return ws_error("Could not save the message. Please try again.")
    db.refresh(message)

    payload = OutgoingChatMessage(
        booking_id=booking.id,
        sender_id=user.id,
        sender_role=user.role.value if hasattr(user.role, "value") else str(user.role),
        message=text,
        timestamp=message.created_at.replace(tzinfo=timezone.utc),
    )
    return json.loads(payload.model_dump_json())
