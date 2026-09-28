"""ExpertProfile model — one-to-one extension of an EXPERT user."""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class AvailabilityStatus(str, enum.Enum):
    """Supported availability values — validated on the backend, never trusted
    from a client."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ExpertProfile(Base):
    __tablename__ = "expert_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    # Comma/space separated skill keywords, manually entered by the expert.
    skills: Mapped[str] = mapped_column(String(500), nullable=False)
    # Manually entered by the expert — never calculated automatically.
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False)
    # Free-text location label, e.g. "Indiranagar, Bengaluru".
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    # Static profile coordinates, manually provided by the expert.
    # Nullable: experts may register without coordinates and add them later.
    # Numeric(10, 7) covers ±90 with ~1cm precision at the equator.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    # Numeric(11, 7) covers ±180 with the same precision.
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 7), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    availability: Mapped[AvailabilityStatus] = mapped_column(
        Enum(
            AvailabilityStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=AvailabilityStatus.AVAILABLE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="expert_profile", uselist=False)
    # Many-to-many: services this expert offers.
    service_links: Mapped[list["ExpertService"]] = relationship(  # noqa: F821
        back_populates="expert", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def services(self) -> list["Service"]:  # noqa: F821
        """Service objects linked through expert_services."""
        return [link.service for link in self.service_links]

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ExpertProfile id={self.id} user_id={self.user_id}>"
