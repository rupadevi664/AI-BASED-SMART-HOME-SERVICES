"""Payment Pydantic schemas (Phase 6).

Amounts never travel from the client — the backend always charges the
booking's own `service_price` snapshot, so a tampered request body cannot
change what the customer pays.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus


class PaymentVerifyRequest(BaseModel):
    """Exactly what Razorpay Checkout hands back to the frontend on success.

    The signature is checked server-side against RAZORPAY_KEY_SECRET; a
    failing check marks the payment FAILED and never flips the booking.
    """

    razorpay_order_id: str = Field(min_length=3, max_length=100)
    razorpay_payment_id: str = Field(min_length=3, max_length=100)
    razorpay_signature: str = Field(min_length=3, max_length=256)


class PaymentOrderResponse(BaseModel):
    """Everything the React frontend needs to open Razorpay Checkout."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: int
    booking_id: int
    amount: float
    currency: str
    key_id: str
    razorpay_order_id: str
    # Pre-filled on the Checkout modal for a smoother UX.
    customer_name: str
    customer_email: str
    service_name: str
    expert_name: str | None = None
    prefill_contact: str | None = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    customer_id: int
    expert_id: int
    amount: float
    currency: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    # The signature is stored for audit but never echoed to clients.
    razorpay_signature_present: bool = False
    status: PaymentStatus
    payment_method: str | None = None
    created_at: datetime
    updated_at: datetime


class PaymentListResponse(BaseModel):
    payments: list[PaymentResponse]
    count: int
