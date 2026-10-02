"""LiveLocation model — one GPS fix from the assigned expert (Phase 5).

Rows are streamed over the location WebSocket and persisted before broadcast.
Only the booking's assigned expert creates rows; the customer reads them.
Retention: rows are historical by design — see
`app.services.location_service.purge_expired_locations` (explicit, opt-in).
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LiveLocation(Base):
    __tablename__ = "live_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The expert's USER id (users.id), not the expert_profiles.id — matches
    # the JWT subject so identity is never trusted from the client.
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Float per Phase 5 spec: approximate streamed fixes, not surveyed points.
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)

    # GPS fix time (client-supplied if valid, else server accept time).
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    booking: Mapped["Booking"] = relationship(foreign_keys=[booking_id])  # noqa: F821
    expert: Mapped["User"] = relationship(foreign_keys=[expert_id])  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<LiveLocation id={self.id} booking={self.booking_id} expert={self.expert_id} "
            f"lat={self.latitude} lon={self.longitude}>"
        )
