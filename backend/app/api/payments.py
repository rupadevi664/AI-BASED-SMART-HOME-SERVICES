"""Payment endpoints (Phase 6).

Auth model (unchanged from the rest of the app): `get_current_user` resolves
the JWT; ownership/role checks happen in the service layer.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models import User
from app.schemas.payment import (
    PaymentOrderResponse,
    PaymentResponse,
    PaymentVerifyRequest,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


def _order_response(db: Session, payment) -> dict:
    """Build the Checkout payload — the only place key_id is exposed."""
    booking = payment.booking
    expert_user = booking.expert.user if booking.expert is not None else None
    return PaymentOrderResponse(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        amount=float(payment.amount),
        currency=payment.currency,
        key_id=settings.RAZORPAY_KEY_ID,
        razorpay_order_id=payment.razorpay_order_id,
        customer_name=booking.customer.name,
        customer_email=booking.customer.email,
        service_name=booking.service_name,
        expert_name=expert_user.name if expert_user else None,
        prefill_contact=booking.customer.phone,
    )


@router.post(
    "/create-order/{booking_id}",
    response_model=PaymentOrderResponse,
    status_code=201,
    summary="Create a Razorpay order for a COMPLETED booking (CUSTOMER who owns it)",
)
def create_order(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Amount is taken from the booking's price snapshot — never from the
    client. Returns everything Checkout needs, including the public key_id."""
    payment = PaymentService.create_order(db, current_user, booking_id)
    return _order_response(db, payment)


@router.post(
    "/verify",
    response_model=PaymentResponse,
    summary="Verify the Razorpay Checkout response (server-side signature check)",
)
def verify_payment(
    payload: PaymentVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Only a valid HMAC-SHA256 signature flips the payment to SUCCESS and the
    booking to PAID. A bad signature marks the payment FAILED (400)."""
    return PaymentService.verify(db, current_user, payload)


@router.get(
    "/my-payments",
    response_model=list[PaymentResponse],
    summary="Customer's payment history",
)
def my_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PaymentService.list_for_customer(db, current_user)


@router.get(
    "/booking/{booking_id}",
    response_model=list[PaymentResponse],
    summary="Payment attempts for one booking (owner customer or ADMIN)",
)
def payments_for_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PaymentService.get_for_booking(db, current_user, booking_id)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Payment detail (owner customer or ADMIN)",
)
def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return PaymentService.get_payment(db, current_user, payment_id)
