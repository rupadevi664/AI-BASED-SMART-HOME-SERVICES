"""Review business logic (Phase 6): eligibility, CRUD, average rating.

Rules enforced here (beyond Pydantic's 1-5 bound):
1.  Only authenticated CUSTOMERs create reviews.
2.  The customer must own the booking.
3.  The booking must be COMPLETED.
4.  expert_id is derived from the booking — reviewing an unrelated expert is
    impossible by construction.
5.  One review per booking (unique constraint + explicit check).
6.  Rating must be an integer 1-5 (Pydantic + DB CHECK).
7.  Nothing before completion — same as rule 3.
8.  EXPERT/ADMIN users hitting the customer endpoint are rejected by role.
"""
import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, Review
from app.services.booking_service import _fail

logger = logging.getLogger(__name__)


def _refresh_expert_rating(db: Session, expert_id: int) -> None:
    """Recompute the expert's rating_avg / rating_count from reviews.

    Called inside the caller's transaction so the aggregate can never drift
    from the reviews table.
    """
    from app.models import ExpertProfile

    # The app session uses autoflush=False — flush pending review writes so
    # the aggregate SELECT below sees them (avoids one-step-behind averages).
    db.flush()
    row = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.expert_id == expert_id
        )
    ).one()
    avg, count = row[0], row[1] or 0
    expert = db.get(ExpertProfile, expert_id)
    if expert is None:
        return
    # DECIMAL(3,2) holds 0.00-9.99; averages of 1-5 always fit.
    expert.rating_avg = Decimal(str(round(float(avg), 2))) if avg is not None else None
    expert.rating_count = int(count)


class ReviewService:
    # ------------------------------------------------------------------ create
    @staticmethod
    def create_review(db: Session, customer, payload) -> Review:
        if customer.role != "CUSTOMER":
            raise _fail("INVALID_ROLE", 403, "Only customers can submit reviews")

        booking = db.get(Booking, payload.booking_id)
        if booking is None:
            raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {payload.booking_id} not found")
        if booking.customer_id != customer.id:
            raise _fail("BOOKING_ACCESS_DENIED", 403, "You can only review your own bookings")
        if booking.status != BookingStatus.COMPLETED:
            raise _fail(
                "BOOKING_NOT_COMPLETED",
                400,
                "You can review a service only after it is completed",
            )

        existing = db.execute(
            select(Review).where(Review.booking_id == booking.id)
        ).scalar_one_or_none()
        if existing is not None:
            raise _fail(
                "REVIEW_ALREADY_EXISTS",
                409,
                "You have already reviewed this booking — edit your existing review instead",
            )

        review = Review(
            booking_id=booking.id,
            customer_id=customer.id,
            expert_id=booking.expert_id,  # derived — never from the body
            rating=payload.rating,
            comment=(payload.comment or "").strip() or None,
        )
        db.add(review)
        try:
            _refresh_expert_rating(db, booking.expert_id)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error creating review")
            raise _fail("REVIEW_DB_ERROR", 500, "Database error, please try again later") from exc
        db.refresh(review)
        return review

    # ------------------------------------------------------------------- read
    @staticmethod
    def list_for_expert(db: Session, expert_profile_id: int) -> dict:
        reviews = list(
            db.execute(
                select(Review)
                .where(Review.expert_id == expert_profile_id)
                .order_by(Review.created_at.desc(), Review.id.desc())
            ).scalars().all()
        )
        row = db.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.expert_id == expert_profile_id
            )
        ).one()
        avg = round(float(row[0]), 2) if row[0] is not None else None
        return {
            "expert_id": expert_profile_id,
            "average_rating": avg,
            "total_reviews": int(row[1] or 0),
            "reviews": reviews,
        }

    @staticmethod
    def get_for_booking(db: Session, user, booking_id: int) -> Review:
        booking = db.get(Booking, booking_id)
        if booking is None:
            raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
        is_owner = user.role == "CUSTOMER" and booking.customer_id == user.id
        is_expert = (
            user.role == "EXPERT"
            and user.expert_profile is not None
            and booking.expert_id == user.expert_profile.id
        )
        if not (is_owner or is_expert or user.role == "ADMIN"):
            raise _fail("REVIEW_ACCESS_DENIED", 403, "You do not have access to this booking")
        review = db.execute(
            select(Review).where(Review.booking_id == booking_id)
        ).scalar_one_or_none()
        if review is None:
            raise _fail("REVIEW_NOT_FOUND", 404, f"No review exists for booking {booking_id}")
        return review

    # ------------------------------------------------------------------ update
    @staticmethod
    def update_review(db: Session, customer, review_id: int, payload) -> Review:
        review = db.get(Review, review_id)
        if review is None:
            raise _fail("REVIEW_NOT_FOUND", 404, f"Review {review_id} not found")
        if customer.role != "CUSTOMER" or review.customer_id != customer.id:
            raise _fail("REVIEW_ACCESS_DENIED", 403, "You can only edit your own reviews")
        if payload.rating is not None:
            review.rating = payload.rating
        if payload.comment is not None:
            review.comment = payload.comment.strip() or None
        try:
            _refresh_expert_rating(db, review.expert_id)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error updating review")
            raise _fail("REVIEW_DB_ERROR", 500, "Database error, please try again later") from exc
        db.refresh(review)
        return review

    # ------------------------------------------------------------------ delete
    @staticmethod
    def delete_review(db: Session, user, review_id: int) -> None:
        review = db.get(Review, review_id)
        if review is None:
            raise _fail("REVIEW_NOT_FOUND", 404, f"Review {review_id} not found")
        is_owner = user.role == "CUSTOMER" and review.customer_id == user.id
        if not (is_owner or user.role == "ADMIN"):
            raise _fail("REVIEW_ACCESS_DENIED", 403, "You can only delete your own reviews")
        expert_id = review.expert_id
        try:
            db.delete(review)
            _refresh_expert_rating(db, expert_id)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error deleting review")
            raise _fail("REVIEW_DB_ERROR", 500, "Database error, please try again later") from exc
