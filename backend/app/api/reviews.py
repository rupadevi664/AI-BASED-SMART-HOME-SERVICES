"""Review endpoints (Phase 6).

Public expert reviews (`GET /reviews/expert/{expert_id}`) are intentionally
unauthenticated so nearby-search / profile pages can show ratings without a
token; everything that mutates data is JWT-protected.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.review import ReviewCreate, ReviewListResponse, ReviewResponse, ReviewUpdate
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=201,
    summary="Create a review for a COMPLETED booking (CUSTOMER who owns it)",
)
def create_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """expert_id comes from the booking, customer_id from the JWT — neither is
    accepted from the body."""
    return ReviewService.create_review(db, current_user, payload)


@router.get(
    "/expert/{expert_id}",
    response_model=ReviewListResponse,
    summary="Public: an expert's reviews + average rating + count",
)
def expert_reviews(
    expert_id: int,
    db: Session = Depends(get_db),
):
    return ReviewService.list_for_expert(db, expert_id)


@router.get(
    "/booking/{booking_id}",
    response_model=ReviewResponse,
    summary="The review for one booking (owner customer, assigned expert, or ADMIN)",
)
def booking_review(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ReviewService.get_for_booking(db, current_user, booking_id)


@router.put(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Edit your review (rating and/or comment)",
)
def update_review(
    review_id: int,
    payload: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ReviewService.update_review(db, current_user, review_id, payload)


@router.delete(
    "/{review_id}",
    status_code=204,
    summary="Delete your review (owner customer or ADMIN)",
)
def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ReviewService.delete_review(db, current_user, review_id)
