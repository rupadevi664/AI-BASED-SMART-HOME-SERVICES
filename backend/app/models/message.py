"""Message model — persisted chat text for a booking (Phase 4)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Plain text only — never HTML/JS; validated (1..2000 chars) before insert.
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    booking: Mapped["Booking"] = relationship(foreign_keys=[booking_id])  # noqa: F821
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Message id={self.id} booking={self.booking_id} sender={self.sender_id}>"
