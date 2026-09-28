"""Service model — the catalogue of home services offered."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ServiceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[ServiceStatus] = mapped_column(
        Enum(
            ServiceStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ServiceStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Many-to-many back reference: experts offering this service.
    expert_links: Mapped[list["ExpertService"]] = relationship(  # noqa: F821
        back_populates="service", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def experts(self) -> list["ExpertProfile"]:  # noqa: F821
        return [link.expert for link in self.expert_links]

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Service id={self.id} name={self.name!r}>"
