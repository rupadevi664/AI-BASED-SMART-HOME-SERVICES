"""Review Pydantic schemas (Phase 6).

Rating is strictly bounded to 1-5 integers at the API boundary; the DB adds
a CHECK constraint as defense in depth.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    """`expert_id` and `customer_id` are derived server-side from the booking
    and JWT — a client cannot review an unrelated expert."""

    booking_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    customer_id: int
    expert_id: int
    rating: int
    comment: str | None = None
    customer: ReviewerSummary | None = None
    created_at: datetime
    updated_at: datetime


class ExpertRatingSummary(BaseModel):
    """Aggregates exposed alongside expert data."""

    expert_id: int
    average_rating: float | None
    total_reviews: int


class ReviewListResponse(BaseModel):
    expert_id: int
    average_rating: float | None
    total_reviews: int
    reviews: list[ReviewResponse]
