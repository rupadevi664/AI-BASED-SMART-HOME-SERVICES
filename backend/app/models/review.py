"""Review model (Phase 6) — a customer's rating of a completed booking.

One review per booking (unique booking_id). Rating 1-5 is enforced by
Pydantic at the API layer; the DB column is an Integer with a CHECK for
defense in depth (MySQL enforces CHECK since 8.0.16).
"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        # Rule 5: exactly one review per booking.
        UniqueConstraint("booking_id", name="uq_reviews_booking_id"),
        # Fast expert-page lookups ordered by recency.
        Index("ix_reviews_expert_created", "expert_id", "created_at"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("expert_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    booking: Mapped["Booking"] = relationship(foreign_keys=[booking_id])  # noqa: F821
    customer: Mapped["User"] = relationship(foreign_keys=[customer_id])  # noqa: F821
    expert: Mapped["ExpertProfile"] = relationship(foreign_keys=[expert_id])  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Review id={self.id} booking={self.booking_id} rating={self.rating}>"
