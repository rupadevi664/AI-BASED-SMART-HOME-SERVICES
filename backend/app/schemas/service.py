"""Pydantic schemas for the service catalogue."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.service import ServiceStatus


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    # Serialized as a JSON number (spec example); inputs keep Decimal precision.
    base_price: float
    status: ServiceStatus
    created_at: datetime


class ServiceCreate(BaseModel):
    """ADMIN-only service creation."""

    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    base_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    status: ServiceStatus = ServiceStatus.ACTIVE


class ServiceUpdate(BaseModel):
    """ADMIN-only partial service update (id is never changeable)."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    base_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    status: ServiceStatus | None = None
