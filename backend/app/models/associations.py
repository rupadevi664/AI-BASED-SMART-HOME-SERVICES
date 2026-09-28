"""Association model: many-to-many ExpertProfile ↔ Service."""
from sqlalchemy import ForeignKey, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExpertService(Base):
    """One row per (expert, service) pair the expert offers.

    Composite primary key prevents duplicate associations at the database
    level; CASCADE deletes keep rows consistent when experts/services go away.
    """

    __tablename__ = "expert_services"
    __table_args__ = (PrimaryKeyConstraint("expert_id", "service_id"),)

    expert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("expert_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )

    expert: Mapped["ExpertProfile"] = relationship(  # noqa: F821
        back_populates="service_links"
    )
    service: Mapped["Service"] = relationship(back_populates="expert_links")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ExpertService expert_id={self.expert_id} service_id={self.service_id}>"
