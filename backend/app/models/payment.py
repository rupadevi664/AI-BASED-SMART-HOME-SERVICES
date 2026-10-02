"""Payment model (Phase 6) — one row per Razorpay order attempt.

No sensitive card data is ever stored — only Razorpay identifiers, the
amount, and the verification status. Order attempts are kept even when a
checkout is abandoned, so a repeated "Pay Now" creates a new PENDING order
and the previous row remains as history.
"""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # Razorpay's own identifiers: unique when present, NULL allowed while
        # the order is still PENDING (checkout not completed yet).
        UniqueConstraint("razorpay_order_id", name="uq_payments_razorpay_order_id"),
        UniqueConstraint("razorpay_payment_id", name="uq_payments_razorpay_payment_id"),
        Index("ix_payments_booking_status", "booking_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Snapshots of the booking's participants — kept for audit even if a
    # booking/expert is ever removed. Explicit FKs with RESTRICT so an
    # account cannot silently disappear under a financial record.
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("expert_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")

    # --- Razorpay identifiers (no card data, ever) ---
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    razorpay_signature: Mapped[str | None] = mapped_column(String(256), nullable=True)

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    # "razorpay" for orders created through Checkout; informational only —
    # the source of truth is the signature verification.
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    booking: Mapped["Booking"] = relationship(  # noqa: F821
        foreign_keys=[booking_id], back_populates="payments"
    )
    customer: Mapped["User"] = relationship(foreign_keys=[customer_id])  # noqa: F821
    expert: Mapped["ExpertProfile"] = relationship(foreign_keys=[expert_id])  # noqa: F821

    @property
    def razorpay_signature_present(self) -> bool:
        """APIs expose a boolean, never the signature value itself."""
        return self.razorpay_signature is not None

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Payment id={self.id} booking={self.booking_id} "
            f"status={self.status.value} amount={self.amount}>"
        )
