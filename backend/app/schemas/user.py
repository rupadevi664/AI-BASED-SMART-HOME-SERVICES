"""Pydantic schemas for users — responses never expose password_hash."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class UserResponse(BaseModel):
    """Safe public representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
