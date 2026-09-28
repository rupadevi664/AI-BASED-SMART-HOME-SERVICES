"""Phase 3 tests: booking system (creation, lifecycle, authz, snapshots)."""
import itertools
from datetime import date, datetime, timedelta

import pytest

from tests.conftest import (
    login,
    make_admin,
    register_customer,
    register_expert,
    token_headers,
)

ADMIN_EMAIL = "admin.bookings@example.com"

FUTURE_DATE = date.today() + timedelta(days=3)
MORNING = "10:30:00"
AFTERNOON = "15:00:00"


def _admin(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


def _verify_expert(client, admin_token, email: str) -> int:
    """Verify the expert through the admin API; return their expert_id."""
    experts = client.get("/admin/experts", headers=token_headers(admin_token)).json()
    target = next(e for e in experts if e["email"] == email)
    response = client.put(
        f"/admin/experts/{target['id']}/verification",
        headers=token_headers(admin_token),
        params={"verification_status": "VERIFIED"},
    )
    assert response.status_code == 200
    return target["id"]


def _service_id(client, name: str) -> int:
    return next(s["id"] for s in client.get("/services").json() if s["name"] == name)


_slot_counter = itertools.count()


def _next_time() -> str:
    """Unique 5-minute slot per booking (06:00 onward, next day when exhausted)
    so tests never collide on the expert-conflict rule."""
    minutes_of_day = 6 * 60 + 5 * next(_slot_counter)
    day_offset = 0
    while minutes_of_day > 23 * 60 + 55:
        minutes_of_day -= 24 * 60
        day_offset += 1
    slot_date = FUTURE_DATE + timedelta(days=day_offset)
    payload_date = slot_date.isoformat()
    _next_time.current_date = payload_date
    hh, mm = divmod(minutes_of_day, 60)
    return f"{hh:02d}:{mm:02d}:00"


def _booking_payload(expert_id: int, service_id: int, **overrides) -> dict:
    if "scheduled_time" not in overrides:
        overrides["scheduled_time"] = _next_time()
        if "scheduled_date" not in overrides:
            overrides["scheduled_date"] = _next_time.current_date
    payload = {
        "expert_id": expert_id,
        "service_id": service_id,
        "service_address": "Madhapur, Hyderabad",
        "service_latitude": 17.4483,
        "service_longitude": 78.3915,
        "scheduled_date": FUTURE_DATE.isoformat(),
        "scheduled_time": MORNING,
        "customer_notes": "Need electrical wiring repair",
    }
    payload.update(overrides)
    return payload


def _create_booking(client, customer_token, expert_id, service_id, **overrides):
    return client.post(
        "/bookings",
        headers=token_headers(customer_token),
        json=_booking_payload(expert_id, service_id, **overrides),
    )


@pytest.fixture(scope="module")
def admin_token(client):
    return _admin(client)


@pytest.fixture(scope="module")
def world(client, admin_token):
    """Verified electrician + verified plumber + two customers."""
    electrician = _service_id(client, "Electrician")
    plumber = _service_id(client, "Plumber")

    register_expert(
        client, email="book.electrician@example.com",
        latitude=17.44, longitude=78.39, service_ids=[electrician],
    )
    expert_id = _verify_expert(client, admin_token, "book.electrician@example.com")

    register_expert(
        client, email="book.plumber@example.com",
        latitude=17.44, longitude=78.39, service_ids=[plumber],
    )
    plumber_expert_id = _verify_expert(client, admin_token, "book.plumber@example.com")

    register_customer(client, email="book.customer1@example.com")
    customer1 = login(client, "book.customer1@example.com")["access_token"]
    register_customer(client, email="book.customer2@example.com")
    customer2 = login(client, "book.customer2@example.com")["access_token"]

    return {
        "electrician": electrician,
        "plumber": plumber,
        "expert_id": expert_id,
        "plumber_expert_id": plumber_expert_id,
        "customer1": customer1,
        "customer2": customer2,
    }


class TestBookingCreation:
    def test_customer_creates_booking_starts_pending(self, client, world):
        response = _create_booking(client, world["customer1"], world["expert_id"], world["electrician"])
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "PENDING"
        assert body["customer_id"] > 0
        assert body["service_name"] == "Electrician"
        assert float(body["service_price"]) == 299.00  # seeded base price
        assert body["scheduled_date"] == FUTURE_DATE.isoformat()
        assert body["scheduled_time"] == "06:00:00"  # first slot from the helper
        assert body["cancellation_reason"] is None

    def test_customer_id_comes_from_jwt_not_body(self, client, world):
        """A second customer cannot create a booking on customer1's behalf."""
        response = client.post(
            "/bookings",
            headers=token_headers(world["customer2"]),
            json=_booking_payload(
                world["expert_id"], world["electrician"], extra_customer_id=99999
            ),
        )
        assert response.status_code == 201
        body = response.json()
        customers = {c["customer_id"] for c in client.get(
            "/bookings/my", headers=token_headers(world["customer2"])
        ).json()}
        assert body["customer_id"] in customers
        assert body["customer_id"] != 99999

    def test_unauthenticated_cannot_create_401(self, client, world):
        response = client.post(
            "/bookings", json=_booking_payload(world["expert_id"], world["electrician"])
        )
        assert response.status_code == 401

    def test_invalid_jwt_401(self, client, world):
        response = client.post(
            "/bookings",
            headers={"Authorization": "Bearer bad.token.value"},
            json=_booking_payload(world["expert_id"], world["electrician"]),
        )
        assert response.status_code == 401

    def test_invalid_expert_404(self, client, world):
        response = _create_booking(client, world["customer1"], 999999, world["electrician"])
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "EXPERT_NOT_FOUND"

    def test_invalid_service_404(self, client, world):
        response = _create_booking(client, world["customer1"], world["expert_id"], 999999)
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "SERVICE_NOT_FOUND"

    def test_unverified_expert_cannot_receive_booking(self, client, world, admin_token):
        register_expert(
            client, email="book.unverified@example.com",
            service_ids=[world["electrician"]],
        )
        # deliberately NOT verified
        unverified_id = _expert_id_unverified(
            client, admin_token, "book.unverified@example.com"
        )
        response = _create_booking(
            client, world["customer1"], unverified_id, world["electrician"],
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "EXPERT_NOT_VERIFIED"

    def test_expert_not_providing_service_400(self, client, world):
        # Electrician expert, but the customer books the plumber service.
        response = _create_booking(client, world["customer1"], world["expert_id"], world["plumber"])
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "SERVICE_NOT_OFFERED"

    def test_expert_unavailable_400(self, client, world, admin_token):
        register_expert(
            client, email="book.busy@example.com",
            service_ids=[world["electrician"]],
        )
        busy_id = _verify_expert(client, admin_token, "book.busy@example.com")
        token = login(client, "book.busy@example.com")["access_token"]
        response = client.put(
            "/experts/profile", headers=token_headers(token), json={"availability": "UNAVAILABLE"}
        )
        assert response.status_code == 200
        response = _create_booking(client, world["customer1"], busy_id, world["electrician"])
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "EXPERT_UNAVAILABLE"

    def test_inactive_service_400(self, client, world, admin_token):
        created = client.post(
            "/admin/services", headers=token_headers(admin_token),
            json={"name": "Inactive Book Svc", "description": "", "base_price": 50},
        ).json()
        client.put(
            f"/admin/services/{created['id']}", headers=token_headers(admin_token),
            json={"status": "INACTIVE"},
        )
        # Link the electrician to it so the relationship check passes.
        token = login(client, "book.electrician@example.com")["access_token"]
        client.put(
            "/experts/profile", headers=token_headers(token),
            json={"service_ids": [world["electrician"], created["id"]]},
        )
        response = _create_booking(client, world["customer1"], world["expert_id"], created["id"])
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "SERVICE_INACTIVE"

    def test_past_date_400(self, client, world):
        past = (date.today() - timedelta(days=1)).isoformat()
        response = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_date=past,
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "PAST_SCHEDULE"

    def test_invalid_date_format_422(self, client, world):
        response = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_date="2026-13-45",
        )
        assert response.status_code == 422

    def test_invalid_time_format_422(self, client, world):
        response = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="25:99:00",
        )
        assert response.status_code == 422

    def test_invalid_latitude_422(self, client, world):
        response = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            service_latitude=95.0,
        )
        assert response.status_code == 422

    def test_invalid_longitude_422(self, client, world):
        response = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            service_longitude=-181.0,
        )
        assert response.status_code == 422

    def test_expert_cannot_create_booking_403(self, client, world):
        token = login(client, "book.electrician@example.com")["access_token"]
        response = client.post(
            "/bookings",
            headers=token_headers(token),
            json=_booking_payload(world["expert_id"], world["electrician"]),
        )
        assert response.status_code == 403


def _expert_id_unverified(client, admin_token, email: str) -> int:
    experts = client.get("/admin/experts", headers=token_headers(admin_token)).json()
    return next(e for e in experts if e["email"] == email)["id"]


class TestExpertWorkflow:
    def test_expert_sees_only_own_bookings(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"]
        ).json()
        mine = client.get("/experts/bookings", headers=token_headers(
            login(client, "book.electrician@example.com")["access_token"]
        )).json()
        assert any(b["id"] == booking["id"] for b in mine)

        other = client.get("/experts/bookings", headers=token_headers(
            login(client, "book.plumber@example.com")["access_token"]
        )).json()
        assert all(b["id"] != booking["id"] for b in other)

    def test_expert_history_status_filter(self, client, world):
        headers = token_headers(login(client, "book.electrician@example.com")["access_token"])
        accepted = client.get(
            "/experts/bookings", params={"status": "PENDING"}, headers=headers
        ).json()
        assert all(b["status"] == "PENDING" for b in accepted)

    def test_accept_flow_pending_to_accepted(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time=AFTERNOON,
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        response = client.put(f"/experts/bookings/{booking['id']}/accept", headers=token)
        assert response.status_code == 200
        assert response.json()["status"] == "ACCEPTED"

    def test_accept_twice_400(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="11:30:00",
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        assert client.put(f"/experts/bookings/{booking['id']}/accept", headers=token).status_code == 200
        response = client.put(f"/experts/bookings/{booking['id']}/accept", headers=token)
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "INVALID_TRANSITION"

    def test_reject_flow_with_reason(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="12:30:00",
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        response = client.put(
            f"/experts/bookings/{booking['id']}/reject",
            headers=token,
            json={"reason": "Not available at requested time"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "REJECTED"
        assert body["cancellation_reason"] == "Not available at requested time"

    def test_reject_requires_reason_422(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="12:45:00",
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        response = client.put(
            f"/experts/bookings/{booking['id']}/reject",
            headers=token,
            json={"reason": "x"},
        )
        assert response.status_code == 422

    def test_complete_accepted_booking(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="13:30:00",
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        assert client.put(f"/experts/bookings/{booking['id']}/accept", headers=token).status_code == 200
        response = client.put(f"/experts/bookings/{booking['id']}/complete", headers=token)
        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"

    def test_cannot_complete_pending_400(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="14:00:00",
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        response = client.put(f"/experts/bookings/{booking['id']}/complete", headers=token)
        assert response.status_code == 400

    def test_cannot_accept_rejected_400(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="14:30:00",
        ).json()
        token = token_headers(login(client, "book.electrician@example.com")["access_token"])
        client.put(
            f"/experts/bookings/{booking['id']}/reject",
            headers=token, json={"reason": "cannot make it"},
        )
        response = client.put(f"/experts/bookings/{booking['id']}/accept", headers=token)
        assert response.status_code == 400

    def test_expert_cannot_touch_another_experts_booking(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="16:00:00",
        ).json()
        other = token_headers(login(client, "book.plumber@example.com")["access_token"])
        assert client.get(f"/bookings/{booking['id']}", headers=other).status_code == 403
        assert client.put(f"/experts/bookings/{booking['id']}/accept", headers=other).status_code == 403
        assert client.put(
            f"/experts/bookings/{booking['id']}/reject",
            headers=other, json={"reason": "not mine"},
        ).status_code == 403

    def test_missing_jwt_on_expert_bookings_401(self, client):
        assert client.get("/experts/bookings").status_code == 401

    def test_customer_cannot_use_expert_booking_endpoints_403(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="16:30:00",
        ).json()
        response = client.put(
            f"/experts/bookings/{booking['id']}/accept",
            headers=token_headers(world["customer1"]),
        )
        assert response.status_code == 403


class TestCustomerHistoryAndCancel:
    def test_customer_sees_own_history_only(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="17:00:00",
        ).json()
        mine = client.get("/bookings/my", headers=token_headers(world["customer1"])).json()
        assert any(b["id"] == booking["id"] for b in mine)
        other = client.get("/bookings/my", headers=token_headers(world["customer2"])).json()
        assert all(b["id"] != booking["id"] for b in other)

    def test_history_status_filter(self, client, world):
        response = client.get(
            "/bookings/my", params={"status": "PENDING"}, headers=token_headers(world["customer1"])
        )
        assert response.status_code == 200
        assert all(b["status"] == "PENDING" for b in response.json())

    def test_customer_can_view_own_booking_detail(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="17:30:00",
        ).json()
        response = client.get(f"/bookings/{booking['id']}", headers=token_headers(world["customer1"]))
        assert response.status_code == 200
        assert response.json()["id"] == booking["id"]

    def test_customer_cannot_view_others_booking_403(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="18:00:00",
        ).json()
        response = client.get(f"/bookings/{booking['id']}", headers=token_headers(world["customer2"]))
        assert response.status_code == 403

    def test_cancel_pending_booking(self, client, world):
        booking = _create_booking(
            client, world["customer2"], world["expert_id"], world["electrician"],
            scheduled_time="18:30:00",
        ).json()
        response = client.put(
            f"/bookings/{booking['id']}/cancel",
            headers=token_headers(world["customer2"]),
            json={"reason": "My schedule changed"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CANCELLED"
        assert body["cancellation_reason"] == "My schedule changed"

    def test_cancel_accepted_booking_allowed(self, client, world):
        booking = _create_booking(
            client, world["customer2"], world["expert_id"], world["electrician"],
            scheduled_time="19:00:00",
        ).json()
        etoken = token_headers(login(client, "book.electrician@example.com")["access_token"])
        client.put(f"/experts/bookings/{booking['id']}/accept", headers=etoken)
        response = client.put(
            f"/bookings/{booking['id']}/cancel",
            headers=token_headers(world["customer2"]),
            json={"reason": "plans changed after acceptance"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_cannot_cancel_completed_400(self, client, world):
        booking = _create_booking(
            client, world["customer2"], world["expert_id"], world["electrician"],
            scheduled_time="19:30:00",
        ).json()
        etoken = token_headers(login(client, "book.electrician@example.com")["access_token"])
        client.put(f"/experts/bookings/{booking['id']}/accept", headers=etoken)
        client.put(f"/experts/bookings/{booking['id']}/complete", headers=etoken)
        response = client.put(
            f"/bookings/{booking['id']}/cancel",
            headers=token_headers(world["customer2"]),
            json={"reason": "too late"},
        )
        assert response.status_code == 400

    def test_cannot_cancel_rejected_400(self, client, world):
        booking = _create_booking(
            client, world["customer2"], world["expert_id"], world["electrician"],
            scheduled_time="20:00:00",
        ).json()
        etoken = token_headers(login(client, "book.electrician@example.com")["access_token"])
        client.put(
            f"/experts/bookings/{booking['id']}/reject",
            headers=etoken, json={"reason": "declined"},
        )
        response = client.put(
            f"/bookings/{booking['id']}/cancel",
            headers=token_headers(world["customer2"]),
            json={"reason": "changed my mind"},
        )
        assert response.status_code == 400

    def test_cannot_cancel_twice_400(self, client, world):
        booking = _create_booking(
            client, world["customer2"], world["expert_id"], world["electrician"],
            scheduled_time="20:30:00",
        ).json()
        headers = token_headers(world["customer2"])
        client.put(f"/bookings/{booking['id']}/cancel", headers=headers, json={"reason": "first cancel"})
        response = client.put(
            f"/bookings/{booking['id']}/cancel", headers=headers, json={"reason": "second cancel"}
        )
        assert response.status_code == 400

    def test_cannot_cancel_someone_elses_booking_403(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="21:00:00",
        ).json()
        response = client.put(
            f"/bookings/{booking['id']}/cancel",
            headers=token_headers(world["customer2"]),
            json={"reason": "not mine"},
        )
        assert response.status_code == 403

    def test_expert_cannot_use_customer_cancel_403(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="21:30:00",
        ).json()
        response = client.put(
            f"/bookings/{booking['id']}/cancel",
            headers=token_headers(login(client, "book.electrician@example.com")["access_token"]),
            json={"reason": "experts cannot cancel"},
        )
        assert response.status_code == 403


class TestAdminBookingAccess:
    def test_admin_sees_all_bookings(self, client, world):
        response = client.get("/admin/bookings", headers=token_headers(world["customer1"]))
        assert response.status_code == 403
        admin = client.get("/admin/bookings", headers=token_headers(_admin(client)))
        assert admin.status_code == 200
        assert len(admin.json()) >= 1

    def test_admin_filters(self, client, world):
        admin = token_headers(_admin(client))
        by_status = client.get(
            "/admin/bookings", params={"status": "COMPLETED"}, headers=admin
        ).json()
        assert all(b["status"] == "COMPLETED" for b in by_status)
        by_service = client.get(
            "/admin/bookings", params={"service_id": world["electrician"]}, headers=admin
        ).json()
        assert all(b["service_id"] == world["electrician"] for b in by_service)
        by_customer = client.get(
            "/admin/bookings", params={"customer_id": 999999}, headers=admin
        ).json()
        assert by_customer == []

    def test_admin_can_view_booking_detail(self, client, world):
        booking = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="22:00:00",
        ).json()
        response = client.get(f"/bookings/{booking['id']}", headers=token_headers(_admin(client)))
        assert response.status_code == 200


class TestSnapshotsAndConflicts:
    def test_service_price_and_name_snapshot(self, client, world, admin_token):
        # Fresh service so we can mutate it without touching the seeds.
        svc = client.post(
            "/admin/services", headers=token_headers(admin_token),
            json={"name": f"Snapshot Svc {int(datetime.now().timestamp())}",
                  "description": "snapshot test", "base_price": 400},
        ).json()
        etoken = token_headers(login(client, "book.electrician@example.com")["access_token"])
        client.put(
            "/experts/profile", headers=etoken,
            json={"service_ids": [world["electrician"], svc["id"]]},
        )
        booking = _create_booking(client, world["customer1"], world["expert_id"], svc["id"],
                                  scheduled_time="22:30:00").json()
        # Admin changes name + price AFTER the booking.
        client.put(
            f"/admin/services/{svc['id']}", headers=token_headers(admin_token),
            json={"name": "Renamed Svc", "base_price": 999},
        )
        detail = client.get(f"/bookings/{booking['id']}", headers=token_headers(world["customer1"])).json()
        assert detail["service_name"] != "Renamed Svc"      # snapshot preserved
        assert float(detail["service_price"]) == 400.0      # snapshot preserved

    def test_conflicting_slot_409(self, client, world):
        slot = "23:30:00"
        first = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time=slot,
        )
        assert first.status_code == 201
        second = _create_booking(
            client, world["customer2"], world["expert_id"], world["electrician"],
            scheduled_time=slot,
        )
        assert second.status_code == 409
        assert second.json()["detail"]["error"]["code"] == "BOOKING_CONFLICT"

    def test_different_slot_same_day_ok(self, client, world):
        response = _create_booking(
            client, world["customer1"], world["expert_id"], world["electrician"],
            scheduled_time="23:45:00",
        )
        assert response.status_code == 201

    def test_missing_booking_404(self, client, world):
        response = client.get("/bookings/999999", headers=token_headers(world["customer1"]))
        assert response.status_code == 404
        response = client.put(
            "/bookings/999999/cancel",
            headers=token_headers(world["customer1"]),
            json={"reason": "missing"},
        )
        assert response.status_code == 404
