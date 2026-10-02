"""Phase 6 tests: Razorpay payments.

Runs without real Razorpay credentials:
- 503 paths hit the "not configured" branch directly.
- HMAC verification is exercised against a signature computed with a
  monkeypatched secret, mirroring Razorpay's documented algorithm
  (HMAC-SHA256 of `order_id|payment_id` keyed with KEY_SECRET).
"""
import hashlib
import hmac
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Payment, PaymentStatus
from tests.conftest import login, make_admin, register_customer, register_expert, token_headers

ADMIN_EMAIL = "admin.pay@example.com"
FUTURE_DATE = (date.today() + timedelta(days=7)).isoformat()


def _admin_token(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


def _verify_expert(client, admin_token, email):
    experts = client.get("/admin/experts", headers=token_headers(admin_token)).json()
    target = next(e for e in experts if e["email"] == email)
    response = client.put(
        f"/admin/experts/{target['id']}/verification",
        headers=token_headers(admin_token),
        params={"verification_status": "VERIFIED"},
    )
    assert response.status_code == 200
    return target["id"]


def _sign(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()


@pytest.fixture(scope="module")
def admin_token(client):
    return _admin_token(client)


@pytest.fixture(scope="module")
def world(client, admin_token, monkeypatch_module, fake_rzp):
    """Verified expert + customer with a COMPLETED booking ready for payment."""
    monkeypatch_module.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_fakekeyid")
    monkeypatch_module.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp_test_fakesecret")

    services = client.get("/services").json()
    electrician = next(s["id"] for s in services if s["name"] == "Electrician")

    register_expert(
        client, email="pay.expert@example.com",
        latitude=17.44, longitude=78.39, service_ids=[electrician],
    )
    expert_profile_id = _verify_expert(client, admin_token, "pay.expert@example.com")
    expert_token = login(client, "pay.expert@example.com")["access_token"]

    register_customer(client, email="pay.customer@example.com")
    customer_token = login(client, "pay.customer@example.com")["access_token"]
    register_customer(client, email="pay.other.customer@example.com")
    other_customer_token = login(client, "pay.other.customer@example.com")["access_token"]

    def _complete_booking(time_str):
        response = client.post(
            "/bookings",
            headers=token_headers(customer_token),
            json={
                "expert_id": expert_profile_id,
                "service_id": electrician,
                "service_address": "Madhapur, Hyderabad",
                "scheduled_date": FUTURE_DATE,
                "scheduled_time": time_str,
            },
        )
        assert response.status_code == 201, response.text
        booking = response.json()
        assert (
            client.put(
                f"/experts/bookings/{booking['id']}/accept",
                headers=token_headers(expert_token),
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"/experts/bookings/{booking['id']}/complete",
                headers=token_headers(expert_token),
            ).status_code
            == 200
        )
        return booking

    completed = _complete_booking("10:00:00")
    unpaid2 = _complete_booking("11:00:00")  # stays unpaid for edge tests

    return {
        "electrician": electrician,
        "customer_token": customer_token,
        "other_customer_token": other_customer_token,
        "completed_id": completed["id"],
        "completed_price": completed["service_price"],
        "unpaid2_id": unpaid2["id"],
    }


@pytest.fixture(scope="module")
def monkeypatch_module():
    from contextlib import contextmanager

    @contextmanager
    def _noop_cm(*args, **kwargs):
        yield

    # pytest's monkeypatch is function-scoped; a lightweight module-scope
    # shim lets the credentials + fake SDK live for the whole module.
    class _ModuleMonkeypatch:
        def __init__(self):
            self._undo = []

        def setattr(self, target, name, value):
            old = getattr(target, name)
            setattr(target, name, value)
            self._undo.append(lambda: setattr(target, name, old))

        def undo(self):
            while self._undo:
                self._undo.pop()()

    patch = _ModuleMonkeypatch()
    yield patch
    patch.undo()


class _FakeOrderResource:
    """Stands in for razorpay.Client().order — returns deterministic fake
    orders without touching the network."""

    def __init__(self, counter):
        self._counter = counter

    def create(self, data):
        self._counter[0] += 1
        return {
            "id": f"order_TEST{self._counter[0]:06d}",
            "amount": data["amount"],
            "currency": data["currency"],
            "receipt": data["receipt"],
            "status": "created",
        }


@pytest.fixture(scope="module")
def fake_rzp():
    """Swap payment_service._client for an offline fake (no real API calls)."""
    from app.services import payment_service

    counter = [1000]
    payment_service._client = (
        lambda: type("F", (), {"order": _FakeOrderResource(counter)})()
    )
    return counter
    """Swap payment_service._client for an offline fake (no real API calls)."""
    from app.services import payment_service

    counter = [1000]
    monkeypatch_module.setattr(
        payment_service, "_client", lambda: type("F", (), {"order": _FakeOrderResource(counter)})()
    )
    return counter


def _create_order(client, world, booking_id=None):
    return client.post(
        f"/payments/create-order/{booking_id or world['completed_id']}",
        headers=token_headers(world["customer_token"]),
    )


class TestCredentialsGate:
    def test_endpoints_503_without_credentials(self, client, world):
        # Credentials ARE set by the world fixture, so simulate absence.
        old_id, old_secret = settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET
        settings.RAZORPAY_KEY_ID = ""
        settings.RAZORPAY_KEY_SECRET = ""
        try:
            for method, url in (
                ("post", f"/payments/create-order/{world['completed_id']}"),
                ("post", "/payments/verify"),
            ):
                response = getattr(client, method)(
                    url,
                    headers=token_headers(world["customer_token"]),
                    json={"razorpay_order_id": "order_x", "razorpay_payment_id": "pay_x",
                          "razorpay_signature": "sig_x"},
                )
                assert response.status_code == 503, response.text
                assert response.json()["detail"]["error"]["code"] == "PAYMENTS_NOT_CONFIGURED"
        finally:
            settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET = old_id, old_secret


class TestCreateOrder:
    def test_requires_auth(self, client, world):
        assert client.post(f"/payments/create-order/{world['completed_id']}").status_code == 401

    def test_missing_booking_404(self, client, world):
        response = _create_order(client, world, booking_id=999999)
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "BOOKING_NOT_FOUND"

    def test_other_customer_403(self, client, world):
        response = client.post(
            f"/payments/create-order/{world['completed_id']}",
            headers=token_headers(world["other_customer_token"]),
        )
        assert response.status_code == 403

    def test_order_created_with_booking_amount(self, client, world):
        response = _create_order(client, world)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["booking_id"] == world["completed_id"]
        assert body["amount"] == float(world["completed_price"])
        assert body["currency"] == settings.RAZORPAY_CURRENCY
        assert body["key_id"] == "rzp_test_fakekeyid"
        assert body["razorpay_order_id"].startswith("order_")
        assert body["customer_email"] == "pay.customer@example.com"

        with SessionLocal() as db:
            payment = db.get(Payment, body["payment_id"])
            assert payment is not None
            assert payment.status == PaymentStatus.PENDING
            assert payment.razorpay_order_id == body["razorpay_order_id"]
            assert payment.razorpay_payment_id is None  # nothing captured yet

    def test_repeat_order_reuses_pending_payment(self, client, world):
        first = _create_order(client, world, world["unpaid2_id"]).json()
        second = _create_order(client, world, world["unpaid2_id"]).json()
        assert first["payment_id"] == second["payment_id"]
        assert first["razorpay_order_id"] == second["razorpay_order_id"]


class TestVerify:
    def _verify(self, client, world, order_id, payment_id, signature, token=None):
        return client.post(
            "/payments/verify",
            headers=token_headers(token or world["customer_token"]),
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            },
        )

    def test_happy_path_marks_paid(self, client, world):
        order = _create_order(client, world).json()
        secret = settings.RAZORPAY_KEY_SECRET
        sig = _sign(order["razorpay_order_id"], "pay_TESTok123", secret)
        response = self._verify(
            client, world, order["razorpay_order_id"], "pay_TESTok123", sig
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "SUCCESS"
        assert body["razorpay_payment_id"] == "pay_TESTok123"
        assert body["razorpay_signature_present"] is True

        # Booking flipped to PAID.
        booking = client.get(
            f"/bookings/{order['booking_id']}", headers=token_headers(world["customer_token"])
        ).json()
        assert booking["payment_status"] == "PAID"

    def test_bad_signature_marks_failed(self, client, world):
        order = _create_order(client, world, world["unpaid2_id"]).json()
        response = self._verify(
            client, world, order["razorpay_order_id"], "pay_TESTbad123", "0" * 64
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "INVALID_PAYMENT_SIGNATURE"

        # The payment row is FAILED and the booking stays UNPAID.
        with SessionLocal() as db:
            payment = db.get(Payment, order["payment_id"])
            assert payment.status == PaymentStatus.FAILED
        booking = client.get(
            f"/bookings/{world['unpaid2_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        assert booking["payment_status"] == "UNPAID"

    def test_unknown_order_404(self, client, world):
        response = self._verify(client, world, "order_unknown123", "pay_x", "sig_y")
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "PAYMENT_ORDER_NOT_FOUND"

    def test_other_customer_cannot_verify(self, client, world):
        order = _create_order(client, world, world["unpaid2_id"]).json()
        secret = settings.RAZORPAY_KEY_SECRET
        sig = _sign(order["razorpay_order_id"], "pay_TESTzz", secret)
        response = self._verify(
            client, world, order["razorpay_order_id"], "pay_TESTzz", sig,
            token=world["other_customer_token"],
        )
        assert response.status_code == 403

    def test_verify_is_idempotent_after_success(self, client, world):
        order = _create_order(client, world, world["unpaid2_id"]).json()
        secret = settings.RAZORPAY_KEY_SECRET
        sig = _sign(order["razorpay_order_id"], "pay_TESTidem", secret)
        first = self._verify(client, world, order["razorpay_order_id"], "pay_TESTidem", sig)
        assert first.status_code == 200
        second = self._verify(client, world, order["razorpay_order_id"], "pay_TESTidem", sig)
        assert second.status_code == 200
        assert second.json()["status"] == "SUCCESS"


class TestPaymentQueries:
    def test_my_payments_lists_history(self, client, world):
        response = client.get("/payments/my-payments", headers=token_headers(world["customer_token"]))
        assert response.status_code == 200
        payments = response.json()
        assert len(payments) >= 1
        assert all(p["customer_id"] for p in payments)

    def test_other_customer_has_no_payments(self, client, world):
        response = client.get(
            "/payments/my-payments", headers=token_headers(world["other_customer_token"])
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_booking_payments_owned_only(self, client, world):
        response = client.get(
            f"/payments/booking/{world['completed_id']}",
            headers=token_headers(world["other_customer_token"]),
        )
        assert response.status_code == 403

    def test_payment_detail(self, client, world):
        payments = client.get(
            "/payments/my-payments", headers=token_headers(world["customer_token"])
        ).json()
        payment_id = payments[0]["id"]
        response = client.get(f"/payments/{payment_id}", headers=token_headers(world["customer_token"]))
        assert response.status_code == 200
        assert response.json()["id"] == payment_id
        # Signature value is never echoed — only a boolean presence flag.
        assert "razorpay_signature" not in response.json()

    def test_admin_can_view_any_payment(self, client, world, admin_token):
        payments = client.get(
            "/payments/my-payments", headers=token_headers(world["customer_token"])
        ).json()
        response = client.get(f"/payments/{payments[0]['id']}", headers=token_headers(admin_token))
        assert response.status_code == 200
