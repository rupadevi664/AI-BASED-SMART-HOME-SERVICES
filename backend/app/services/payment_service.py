"""Payment business logic (Phase 6): Razorpay orders + server-side verification.

Security invariants:
- The charged amount ALWAYS comes from the booking's `service_price` snapshot,
  never from the request body.
- Payment success is decided ONLY by the HMAC-SHA256 signature check
  (`order_id|payment_id` signed with RAZORPAY_KEY_SECRET) computed here on the
  backend — the frontend's claim is never trusted.
- The Razorpay secret never leaves the backend; only `key_id` is exposed to
  the frontend (needed to open Checkout).
- Sensitive card data is never stored — only Razorpay identifiers.
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Booking, BookingPaymentStatus, Payment, PaymentStatus, User
from app.services.booking_service import _fail

logger = logging.getLogger(__name__)


def _fail_503() -> HTTPException:
    return _fail(
        "PAYMENTS_NOT_CONFIGURED",
        503,
        "Payments are not configured on this server (RAZORPAY_KEY_ID / "
        "RAZORPAY_KEY_SECRET missing). Add them to backend/.env and restart.",
    )


def _credentials_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID) and bool(settings.RAZORPAY_KEY_SECRET)


def _client():
    """Lazily construct a Razorpay SDK client (never at import time so tests
    run without credentials and without network access)."""
    import razorpay

    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def compute_expected_signature(order_id: str, payment_id: str) -> str:
    """Razorpay's documented check: HMAC-SHA256 of `order_id|payment_id` keyed
    with the KEY_SECRET, hex-encoded. Used by verify() and by the tests."""
    message = f"{order_id}|{payment_id}".encode()
    return hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()


class PaymentService:
    # ------------------------------------------------------------------ order
    @staticmethod
    def create_order(db: Session, customer: User, booking_id: int) -> Payment:
        """Create a Razorpay order for an eligible COMPLETED booking.

        The Payment row is created transactionally with the Razorpay order;
        on any SDK failure the DB rolls back so no PENDING orphan remains.
        """
        if not _credentials_configured():
            raise _fail_503()

        booking = db.get(Booking, booking_id)
        if booking is None:
            raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
        if customer.role != "CUSTOMER" or booking.customer_id != customer.id:
            raise _fail("BOOKING_ACCESS_DENIED", 403, "You can only pay for your own bookings")

        # --- Eligibility gates ---
        if booking.status != "COMPLETED":
            raise _fail(
                "BOOKING_NOT_COMPLETED",
                400,
                "Only completed bookings can be paid for",
            )
        if booking.payment_status == BookingPaymentStatus.PAID:
            raise _fail("PAYMENT_ALREADY_COMPLETED", 409, "This booking is already paid")
        if booking.service_price is None or Decimal(str(booking.service_price)) <= 0:
            raise _fail("INVALID_AMOUNT", 400, "Booking amount is invalid")

        # A previous attempt exists — reuse it so one order maps to one row.
        existing = db.execute(
            select(Payment)
            .where(Payment.booking_id == booking.id)
            .order_by(Payment.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None and existing.status == PaymentStatus.PENDING:
            return existing

        amount_decimal = Decimal(str(booking.service_price))
        amount_paise = int((amount_decimal * 100).to_integral_value())

        try:
            rzp_order = _client().order.create(
                {
                    "amount": amount_paise,  # Razorpay expects paise
                    "currency": settings.RAZORPAY_CURRENCY,
                    "receipt": f"booking-{booking.id}",
                    "notes": {"booking_id": str(booking.id)},
                }
            )
        except Exception as exc:  # SDK/network errors — fail closed, nothing stored
            logger.exception("Razorpay order creation failed for booking %s", booking.id)
            raise _fail(
                "RAZORPAY_ORDER_ERROR",
                502,
                "Could not create the payment order with Razorpay. Please try again.",
            ) from exc

        payment = Payment(
            booking_id=booking.id,
            customer_id=booking.customer_id,
            expert_id=booking.expert_id,
            amount=amount_decimal,
            currency=settings.RAZORPAY_CURRENCY,
            razorpay_order_id=rzp_order["id"],
            status=PaymentStatus.PENDING,
            payment_method="razorpay",
        )
        db.add(payment)
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error saving payment order")
            raise _fail("PAYMENT_DB_ERROR", 500, "Database error, please try again later") from exc
        db.refresh(payment)
        return payment

    # ----------------------------------------------------------------- verify
    @staticmethod
    def verify(db: Session, customer: User, payload) -> Payment:
        """Verify the Checkout response and (only then) mark everything paid.

        - Unknown order_id → 404
        - Not the booking's customer → 403
        - Bad HMAC signature → payment marked FAILED, 400 returned
        - A payment already SUCCESS (or booking already PAID) → idempotent 200
        """
        if not _credentials_configured():
            raise _fail_503()

        payment = db.execute(
            select(Payment).where(Payment.razorpay_order_id == payload.razorpay_order_id)
        ).scalar_one_or_none()
        if payment is None:
            raise _fail("PAYMENT_ORDER_NOT_FOUND", 404, "Unknown razorpay_order_id")
        if payment.customer_id != customer.id:
            raise _fail("PAYMENT_ACCESS_DENIED", 403, "You can only verify your own payments")
        if payment.booking is None or payment.booking.payment_status == BookingPaymentStatus.PAID:
            # Already verified earlier (e.g. double-clicked) — idempotent OK.
            return payment
        if payment.status == PaymentStatus.SUCCESS:
            return payment

        expected = compute_expected_signature(
            payload.razorpay_order_id, payload.razorpay_payment_id
        )
        if not hmac.compare_digest(expected, payload.razorpay_signature):
            logger.warning(
                "Invalid Razorpay signature for order %s (payment %s)",
                payload.razorpay_order_id,
                payload.razorpay_payment_id,
            )
            payment.status = PaymentStatus.FAILED
            payment.razorpay_payment_id = payload.razorpay_payment_id
            payment.razorpay_signature = payload.razorpay_signature
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Database error saving failed payment")
            raise _fail(
                "INVALID_PAYMENT_SIGNATURE",
                400,
                "Payment verification failed: signature mismatch",
            )

        # --- Signature valid: capture the payment atomically ---
        payment.razorpay_payment_id = payload.razorpay_payment_id
        payment.razorpay_signature = payload.razorpay_signature
        payment.status = PaymentStatus.SUCCESS
        payment.booking.payment_status = BookingPaymentStatus.PAID
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error finalizing payment")
            raise _fail("PAYMENT_DB_ERROR", 500, "Database error, please try again later") from exc
        db.refresh(payment)
        return payment

    # ---------------------------------------------------------------- queries
    @staticmethod
    def get_payment(db: Session, user: User, payment_id: int) -> Payment:
        payment = db.get(Payment, payment_id)
        if payment is None:
            raise _fail("PAYMENT_NOT_FOUND", 404, f"Payment {payment_id} not found")
        if user.role == "ADMIN":
            return payment
        if payment.customer_id != user.id:
            raise _fail("PAYMENT_ACCESS_DENIED", 403, "You do not have access to this payment")
        return payment

    @staticmethod
    def get_for_booking(db: Session, user: User, booking_id: int) -> list[Payment]:
        booking = db.get(Booking, booking_id)
        if booking is None:
            raise _fail("BOOKING_NOT_FOUND", 404, f"Booking {booking_id} not found")
        if user.role == "ADMIN":
            return list(booking.payments)
        if booking.customer_id != user.id:
            raise _fail("BOOKING_ACCESS_DENIED", 403, "You can only view your own payments")
        return list(booking.payments)

    @staticmethod
    def list_for_customer(db: Session, user: User) -> list[Payment]:
        if user.role != "CUSTOMER":
            raise _fail("INVALID_ROLE", 403, "Only customers have payment history")
        return list(
            db.execute(
                select(Payment)
                .where(Payment.customer_id == user.id)
                .order_by(Payment.created_at.desc(), Payment.id.desc())
            ).scalars().all()
        )
