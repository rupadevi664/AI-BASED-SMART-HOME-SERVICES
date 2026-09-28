"""Booking model — a customer's service request to an expert (Phase 3).

The booking snapshots `service_name` and `service_price` at creation time so
later catalogue changes never rewrite history.
"""
import enum
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("expert_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # --- Snapshots (immutable history even if the catalogue changes) ---
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    service_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # --- Where the service should be performed (static, no GPS) ---
    service_address: Mapped[str] = mapped_column(String(500), nullable=False)
    service_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    service_longitude: Mapped[float | None] = mapped_column(Numeric(11, 7), nullable=True)

    # --- When ---
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)

    customer_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=BookingStatus.PENDING,
        index=True,
    )
    # Used for both customer cancellations and expert rejections.
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    customer: Mapped["User"] = relationship(foreign_keys=[customer_id])  # noqa: F821
    expert: Mapped["ExpertProfile"] = relationship(foreign_keys=[expert_id])  # noqa: F821
    service: Mapped["Service"] = relationship(foreign_keys=[service_id])  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Booking id={self.id} status={self.status.value} "
            f"customer={self.customer_id} expert={self.expert_id}>"
        )
