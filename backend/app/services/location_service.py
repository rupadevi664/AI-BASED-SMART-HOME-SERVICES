"""Live-location business logic (Phase 5).

Persistence is transactional and ordered: validate → insert → commit →
broadcast. A location that failed to commit is never broadcast, and a failed
commit always rolls back.

Throttling keeps one accepted update per booking per
`LOCATION_UPDATE_INTERVAL_SECONDS` (per process — sufficient for the single
uvicorn worker this phase targets).

Retention: rows are never silently auto-deleted. Instead, this module exposes
`purge_expired_locations`, an explicit, opt-in maintenance function.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LiveLocation

logger = logging.getLogger(__name__)


def save_location(
    db: Session,
    *,
    booking_id: int,
    expert_id: int,
    latitude: float,
    longitude: float,
    accuracy: float | None,
    heading: float | None,
    speed: float | None,
    timestamp: datetime | None,
) -> LiveLocation:
    """Insert one GPS fix and commit.

    Raises the original SQLAlchemyError (after rollback) so the caller can
    distinguish a database failure from a validation rejection.
    """
    row = LiveLocation(
        booking_id=booking_id,
        expert_id=expert_id,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        heading=heading,
        speed=speed,
        timestamp=timestamp or datetime.now(),
        # Set explicitly in Python (not just server_default) so the throttle
        # comparison in should_accept_update uses the same clock basis on
        # both SQLite (CURRENT_TIMESTAMP is UTC) and MySQL (NOW() is local).
        created_at=datetime.now(),
    )
    db.add(row)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist location for booking %s", booking_id)
        raise
    db.refresh(row)
    return row


def latest_location(db: Session, booking_id: int) -> LiveLocation | None:
    """The most recent stored fix for the booking (timestamp DESC, id tiebreak)."""
    return db.execute(
        select(LiveLocation)
        .where(LiveLocation.booking_id == booking_id)
        .order_by(LiveLocation.timestamp.desc(), LiveLocation.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def location_history(db: Session, booking_id: int, limit: int) -> list[LiveLocation]:
    """Up to `limit` fixes, oldest → newest (timestamp ASC, id tiebreak)."""
    # Inner query: newest `limit` rows (DESC); outer query re-sorts ASC.
    newest = (
        select(LiveLocation)
        .where(LiveLocation.booking_id == booking_id)
        .order_by(LiveLocation.timestamp.desc(), LiveLocation.id.desc())
        .limit(limit)
    ).subquery()
    aliased = select(LiveLocation).join(
        newest, LiveLocation.id == newest.c.id
    ).order_by(LiveLocation.timestamp.asc(), LiveLocation.id.asc())
    return list(db.execute(aliased).scalars().all())


def should_accept_update(db: Session, booking_id: int, *, interval: float | None = None) -> bool:
    """True when enough time has passed since the booking's last stored fix.

    One accepted update per booking per interval (default: settings value).
    Anchored on `created_at` (server-side accept time) — never the client's
    `timestamp` — so a skewed/faked client clock cannot buy extra throughput.
    """
    effective = settings.LOCATION_UPDATE_INTERVAL_SECONDS if interval is None else interval
    last = latest_location(db, booking_id)
    if last is None:
        return True
    delta = (datetime.now() - last.created_at).total_seconds()
    if delta < 0:
        # Clock skew or an inserted future row: treat as "just now" so a bad
        # clock can never grant an extra pass.
        delta = 0.0
    return delta >= effective


def purge_expired_locations(db: Session, *, days: int | None = None) -> int:
    """Delete fixes older than the retention window (explicit maintenance).

    NOT called automatically anywhere — run it deliberately, e.g.:

        python -c "from app.core.database import SessionLocal; \
from app.services.location_service import purge_expired_locations; \
print(purge_expired_locations(SessionLocal()))"

    Returns the number of deleted rows.
    """
    effective_days = settings.LOCATION_HISTORY_RETENTION_DAYS if days is None else days
    if effective_days <= 0:
        logger.info("Location retention disabled (days=%s); nothing purged.", effective_days)
        return 0
    cutoff = datetime.now() - timedelta(days=effective_days)
    result = db.execute(delete(LiveLocation).where(LiveLocation.timestamp < cutoff))
    db.commit()
    deleted = int(result.rowcount or 0)
    logger.info("Purged %d live_location row(s) older than %s.", deleted, cutoff.isoformat())
    return deleted
