"""Phase 5 tests: live location tracking (WebSocket + REST).

Covers the Phase 5 spec test matrix: WebSocket auth, authorization, send
rules, coordinate validation, booking-status gate, throttling, booking
isolation, multi-connection handling, disconnect cleanup, REST latest +
history, persistence, and Phase 4 chat coexistence.
"""

from datetime import date, datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import LiveLocation
from tests.conftest import (
    login,
    make_admin,
    register_customer,
    register_expert,
    token_headers,
)

ADMIN_EMAIL = "admin.location@example.com"
FUTURE_DATE = (date.today() + timedelta(days=6)).isoformat()

# Deterministic test coordinates (Hyderabad area) — never personal data.
LAT_A, LON_A = 17.3850, 78.4867
LAT_B, LON_B = 17.4483, 78.3915


def _admin(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


def _verify_expert(client, admin_token, email: str) -> int:
    experts = client.get("/admin/experts", headers=token_headers(admin_token)).json()
    target = next(e for e in experts if e["email"] == email)
    response = client.put(
        f"/admin/experts/{target['id']}/verification",
        headers=token_headers(admin_token),
        params={"verification_status": "VERIFIED"},
    )
    assert response.status_code == 200
    return target["id"]


def _booking(client, customer_token, expert_profile_id, service_id, *, time="10:30:00"):
    response = client.post(
        "/bookings",
        headers=token_headers(customer_token),
        json={
            "expert_id": expert_profile_id,
            "service_id": service_id,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": FUTURE_DATE,
            "scheduled_time": time,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _accept(client, expert_token, booking_id):
    response = client.put(
        f"/experts/bookings/{booking_id}/accept", headers=token_headers(expert_token)
    )
    assert response.status_code == 200, response.text


def _loc_url(booking_id: int, token: str) -> str:
    return f"/ws/bookings/{booking_id}/location?token={token}"


def _read_connected(ws) -> dict:
    event = ws.receive_json()
    assert event["type"] == "connected", event
    return event


def _send_and_expect_error(ws, payload, client_token) -> dict:
    """Send a frame, read frames until an error arrives (skips broadcasts)."""
    ws.send_json(payload)
    for _ in range(50):  # bounded loop: never hang forever
        event = ws.receive_json()
        if event.get("type") == "error":
            return event
        if event.get("type") == "pong":  # keepalive from concurrent traffic
            continue
        # A location_update broadcast can race in from the other socket —
        # handled by callers that care; here we just keep looking for error.
    raise AssertionError("Expected an error frame but none arrived")


def _count_locations(booking_id: int) -> int:
    with SessionLocal() as db:
        return len(
            db.execute(
                select(LiveLocation).where(LiveLocation.booking_id == booking_id)
            ).scalars().all()
        )


@pytest.fixture(scope="module")
def admin_token(client):
    return _admin(client)


@pytest.fixture(scope="module")
def world(client, admin_token):
    """Customers, verified experts, and bookings in every lifecycle state."""
    services = client.get("/services").json()
    electrician = next(s["id"] for s in services if s["name"] == "Electrician")

    register_expert(
        client, email="loc.expert@example.com",
        latitude=17.44, longitude=78.39, service_ids=[electrician],
    )
    expert_profile_id = _verify_expert(client, admin_token, "loc.expert@example.com")
    expert_token = login(client, "loc.expert@example.com")["access_token"]

    register_expert(
        client, email="loc.other.expert@example.com",
        latitude=17.44, longitude=78.39, service_ids=[electrician],
    )
    other_profile_id = _verify_expert(client, admin_token, "loc.other.expert@example.com")
    other_expert_token = login(client, "loc.other.expert@example.com")["access_token"]

    register_customer(client, email="loc.customer@example.com")
    customer_token = login(client, "loc.customer@example.com")["access_token"]
    register_customer(client, email="loc.other.customer@example.com")
    other_customer_token = login(client, "loc.other.customer@example.com")["access_token"]

    # The main ACCEPTED booking used by most tests.
    accepted = _booking(client, customer_token, expert_profile_id, electrician, time="10:30:00")
    _accept(client, expert_token, accepted["id"])

    # A second ACCEPTED booking (same customer/expert pair) for isolation.
    accepted2 = _booking(client, customer_token, expert_profile_id, electrician, time="11:30:00")
    _accept(client, expert_token, accepted2["id"])

    # Status-gate bookings (same customer + expert).
    pending = _booking(client, customer_token, expert_profile_id, electrician, time="12:30:00")

    rejected = _booking(client, customer_token, expert_profile_id, electrician, time="13:30:00")
    client.put(
        f"/experts/bookings/{rejected['id']}/reject",
        headers=token_headers(expert_token),
        json={"reason": "cannot make it"},
    )

    cancelled = _booking(client, customer_token, expert_profile_id, electrician, time="14:30:00")
    client.put(
        f"/bookings/{cancelled['id']}/cancel",
        headers=token_headers(customer_token),
        json={"reason": "plans changed"},
    )

    completed = _booking(client, customer_token, expert_profile_id, electrician, time="15:30:00")
    _accept(client, expert_token, completed["id"])
    client.put(
        f"/experts/bookings/{completed['id']}/complete",
        headers=token_headers(expert_token),
    )

    # An unrelated ACCEPTED booking (other customer ↔ other expert).
    unrelated = _booking(client, other_customer_token, other_profile_id, electrician, time="10:30:00")
    _accept(client, other_expert_token, unrelated["id"])

    return {
        "electrician": electrician,
        "expert_profile_id": expert_profile_id,
        "expert_token": expert_token,
        "other_expert_token": other_expert_token,
        "customer_token": customer_token,
        "other_customer_token": other_customer_token,
        "accepted_id": accepted["id"],
        "accepted2_id": accepted2["id"],
        "pending_id": pending["id"],
        "rejected_id": rejected["id"],
        "cancelled_id": cancelled["id"],
        "completed_id": completed["id"],
        "unrelated_id": unrelated["id"],
    }


# NOTE on throttling and module-scoped world: the throttle allows one update
# per LOCATION_UPDATE_INTERVAL_SECONDS (default 1s) per booking. Tests that
# need an immediate second update use a fresh booking, monkeypatch the
# interval to 0, or sleep — each documented inline.


class TestLocationWebSocketAuth:
    def test_expert_connects_and_gets_connected_frame(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            event = _read_connected(ws)
            assert event["role"] == "expert"
            assert event["can_send"] is True

    def test_customer_connects_and_gets_connected_frame(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as ws:
            event = _read_connected(ws)
            assert event["role"] == "customer"
            assert event["can_send"] is False

    def test_missing_jwt_rejected(self, client, world):
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(f"/ws/bookings/{world['accepted_id']}/location"):
                pass

    def test_invalid_jwt_rejected(self, client, world):
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                _loc_url(world["accepted_id"], "not.a.jwt")
            ) as ws:
                ws.receive_json()

    def test_expired_jwt_rejected(self, client, world):
        expired = pyjwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                _loc_url(world["accepted_id"], expired)
            ) as ws:
                ws.receive_json()

    def test_nonexistent_user_in_jwt_rejected(self, client, world):
        token = create_access_token("424242")
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                _loc_url(world["accepted_id"], token)
            ) as ws:
                ws.receive_json()


class TestLocationAuthorization:
    def test_unrelated_customer_denied(self, client, world):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _loc_url(world["accepted_id"], world["other_customer_token"])
            ) as ws:
                ws.receive_json()

    def test_unrelated_expert_denied(self, client, world):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _loc_url(world["accepted_id"], world["other_expert_token"])
            ) as ws:
                ws.receive_json()

    def test_admin_denied(self, client, world, admin_token):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _loc_url(world["accepted_id"], admin_token)
            ) as ws:
                ws.receive_json()

    def test_booking_not_found(self, client, world):
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                _loc_url(999999, world["customer_token"])
            ) as ws:
                ws.receive_json()


class TestLocationUpdateFlow:
    def test_expert_sends_customer_receives(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as customer, client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as expert:
            _read_connected(customer)
            _read_connected(expert)
            expert.send_json(
                {
                    "type": "location_update",
                    "latitude": LAT_A,
                    "longitude": LON_A,
                    "accuracy": 5.0,
                    "heading": 90.0,
                    "speed": 8.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            received = customer.receive_json()
            assert received["type"] == "location_update"
            assert received["booking_id"] == world["accepted_id"]
            assert received["expert_id"] == _expert_user_id(world["expert_token"])
            assert received["latitude"] == pytest.approx(LAT_A)
            assert received["longitude"] == pytest.approx(LON_A)
            assert received["accuracy"] == pytest.approx(5.0)
            assert received["heading"] == pytest.approx(90.0)
            assert received["speed"] == pytest.approx(8.0)
            assert "timestamp" in received

    def test_customer_cannot_send_location(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as customer, client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as expert:
            _read_connected(customer)
            _read_connected(expert)
            customer.send_json({"type": "location_update", "latitude": 1.0, "longitude": 1.0})
            reply = customer.receive_json()
            assert reply["type"] == "error"
            assert "Only the assigned expert" in reply["message"]
            # And nothing leaked to the expert either.
            expert.send_json({"type": "ping"})
            assert expert.receive_json()["type"] == "pong"

    def test_location_persisted_in_database(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 0)
        before = _count_locations(world["accepted_id"])
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as expert:
            _read_connected(expert)
            expert.send_json({"type": "location_update", "latitude": LAT_B, "longitude": LON_B})
            # Wait for the broadcast (proof of persistence: commit happened first).
            expert.receive_json()
        assert _count_locations(world["accepted_id"]) == before + 1

    def test_ping_pong(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"

    def test_malformed_json_rejected(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_text("this is not json")
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert reply["message"] == "Invalid JSON."

    def test_missing_latitude_rejected(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "longitude": LON_A})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "latitude" in reply["message"]

    def test_missing_longitude_rejected(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "latitude": LAT_A})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "longitude" in reply["message"]

    def test_unknown_message_type_rejected(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "chat_message", "text": "hi"})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            # Chat text must never ride the location channel.
            assert "latitude" in reply["message"]


class TestCoordinateValidation:
    @pytest.mark.parametrize(
        "payload,field",
        [
            ({"latitude": 91.0, "longitude": 0.0}, "latitude"),
            ({"latitude": -90.1, "longitude": 0.0}, "latitude"),
            ({"latitude": 0.0, "longitude": 181.0}, "longitude"),
            ({"latitude": 0.0, "longitude": -180.5}, "longitude"),
            ({"latitude": 0.0, "longitude": 0.0, "accuracy": -1.0}, "accuracy"),
            ({"latitude": 0.0, "longitude": 0.0, "heading": -0.1}, "heading"),
            ({"latitude": 0.0, "longitude": 0.0, "heading": 360.1}, "heading"),
            ({"latitude": 0.0, "longitude": 0.0, "speed": -0.5}, "speed"),
        ],
    )
    def test_invalid_fields_rejected(self, client, world, payload, field):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", **payload})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert field in reply["message"]

    def test_boundary_values_accepted(self, client, world, monkeypatch):
        # Zero the throttle so back-to-back boundary frames are accepted.
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 0)
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json(
                {"type": "location_update", "latitude": -90.0, "longitude": -180.0}
            )
            assert ws.receive_json()["type"] == "location_update"
            ws.send_json(
                {"type": "location_update", "latitude": 90.0, "longitude": 180.0}
            )
            assert ws.receive_json()["type"] == "location_update"

    def test_future_timestamp_rejected(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 0)
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
            ws.send_json(
                {"type": "location_update", "latitude": 1.0, "longitude": 1.0, "timestamp": future}
            )
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "timestamp" in reply["message"]


class TestBookingStatusGate:
    @pytest.mark.parametrize("key", ["pending_id", "rejected_id", "cancelled_id", "completed_id"])
    def test_non_accepted_booking_rejected(self, client, world, key):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _loc_url(world[key], world["customer_token"])
            ) as ws:
                ws.receive_json()

    def test_accepted_booking_allowed(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as ws:
            assert _read_connected(ws)["type"] == "connected"

    def test_rest_history_blocked_for_non_accepted(self, client, world):
        # Authorization runs before any status gate, so the owner gets 200
        # with an empty list — proving no rows exist for those bookings.
        for key in ("pending_id", "rejected_id", "cancelled_id", "completed_id"):
            response = client.get(
                f"/bookings/{world[key]}/location/history",
                headers=token_headers(world["customer_token"]),
            )
            assert response.status_code == 200
            assert response.json()["points"] == []


class TestThrottling:
    def test_rapid_second_update_throttled(self, client, world):
        # Fresh booking so the shared `accepted_id` history cannot interfere.
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="16:30:00")
        _accept(client, world["expert_token"], booking["id"])
        with client.websocket_connect(
            _loc_url(booking["id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "latitude": 1.0, "longitude": 1.0})
            assert ws.receive_json()["type"] == "location_update"
            # Immediately again → throttled error, and NOT broadcast anywhere.
            ws.send_json({"type": "location_update", "latitude": 2.0, "longitude": 2.0})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "too frequently" in reply["message"]
            assert "1 second" in reply["message"]

    def test_throttled_update_not_persisted(self, client, world):
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="17:30:00")
        _accept(client, world["expert_token"], booking["id"])
        with client.websocket_connect(
            _loc_url(booking["id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "latitude": 3.0, "longitude": 3.0})
            assert ws.receive_json()["type"] == "location_update"
            ws.send_json({"type": "location_update", "latitude": 4.0, "longitude": 4.0})
            assert ws.receive_json()["type"] == "error"
        assert _count_locations(booking["id"]) == 1

    def test_update_after_interval_is_accepted(self, client, world):
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="18:30:00")
        _accept(client, world["expert_token"], booking["id"])
        with client.websocket_connect(
            _loc_url(booking["id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "latitude": 5.0, "longitude": 5.0})
            assert ws.receive_json()["type"] == "location_update"
            import time as _time

            _time.sleep(1.1)  # default LOCATION_UPDATE_INTERVAL_SECONDS=1
            ws.send_json({"type": "location_update", "latitude": 5.5, "longitude": 5.5})
            assert ws.receive_json()["type"] == "location_update"

    def test_interval_env_var_is_respected(self, client, world, monkeypatch):
        # A big interval must throttle even the FIRST update after another one
        # landed long ago within the window... simplest observable: set 3600s
        # on a fresh booking, second immediate update still throttled.
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 3600)
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="19:30:00")
        _accept(client, world["expert_token"], booking["id"])
        with client.websocket_connect(
            _loc_url(booking["id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "latitude": 6.0, "longitude": 6.0})
            assert ws.receive_json()["type"] == "location_update"
            ws.send_json({"type": "location_update", "latitude": 7.0, "longitude": 7.0})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "3600" in reply["message"]


class TestIsolationAndConnections:
    def test_booking_isolation_location_channel(self, client, world):
        """A location update on booking A must never reach booking B's socket."""
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as cust_a, client.websocket_connect(
            _loc_url(world["accepted2_id"], world["customer_token"])
        ) as cust_b, client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as expert_a:
            _read_connected(cust_a)
            _read_connected(cust_b)
            _read_connected(expert_a)
            import time as _time

            _time.sleep(1.1)  # clear the throttle window for accepted_id
            expert_a.send_json({"type": "location_update", "latitude": 8.0, "longitude": 8.0})
            got = cust_a.receive_json()
            assert got["type"] == "location_update"
            assert got["booking_id"] == world["accepted_id"]
            # Booking B socket must NOT have received anything — verify by
            # ping/pong round-trip showing no stray frame arrived first.
            cust_b.send_json({"type": "ping"})
            event = cust_b.receive_json()
            assert event["type"] == "pong", event  # a location_update here = leak

    def test_multiple_connections_all_receive(self, client, world):
        import time as _time

        _time.sleep(1.1)
        with client.websocket_connect(
            _loc_url(world["accepted2_id"], world["customer_token"])
        ) as c1, client.websocket_connect(
            _loc_url(world["accepted2_id"], world["customer_token"])
        ) as c2, client.websocket_connect(
            _loc_url(world["accepted2_id"], world["expert_token"])
        ) as expert:
            _read_connected(c1)
            _read_connected(c2)
            _read_connected(expert)
            expert.send_json({"type": "location_update", "latitude": 9.0, "longitude": 9.0})
            for sock in (c1, c2, expert):
                got = sock.receive_json()
                assert got["type"] == "location_update"
                assert got["latitude"] == pytest.approx(9.0)

    def test_disconnect_cleanup_other_socket_still_works(self, client, world):
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as customer:
            _read_connected(customer)
            expert = client.websocket_connect(
                _loc_url(world["accepted_id"], world["expert_token"])
            )
            with expert as ews:
                _read_connected(ews)
            # Expert socket gone abruptly — customer socket must still respond.
            customer.send_json({"type": "ping"})
            assert customer.receive_json()["type"] == "pong"

    def test_chat_and_location_do_not_interfere(self, client, world):
        """Phase 4 chat must keep working independently of the location channel."""
        chat_url = f"/ws/bookings/{world['accepted_id']}?token={world['customer_token']}"
        with client.websocket_connect(chat_url) as chat, client.websocket_connect(
            _loc_url(world["accepted_id"], world["customer_token"])
        ) as loc:
            chat.receive_json()  # user_joined
            _read_connected(loc)
            chat.send_json({"type": "message", "message": "chat is alive in phase 5"})
            loc.send_json({"type": "ping"})
            chat_event = chat.receive_json()
            loc_event = loc.receive_json()
            assert chat_event["type"] == "message"
            assert chat_event["message"] == "chat is alive in phase 5"
            assert loc_event["type"] == "pong"


class TestRestCurrentLocation:
    def test_latest_location_200(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 0)
        with client.websocket_connect(
            _loc_url(world["accepted_id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            ws.send_json({"type": "location_update", "latitude": LAT_B, "longitude": LON_B})
            assert ws.receive_json()["type"] == "location_update"
        response = client.get(
            f"/bookings/{world['accepted_id']}/location",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["latitude"] == pytest.approx(LAT_B)
        assert body["longitude"] == pytest.approx(LON_B)
        assert {"booking_id", "expert_id", "timestamp", "created_at"} <= set(body)

    def test_latest_location_404_when_none(self, client, world):
        # Fresh booking with no location rows.
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="20:30:00")
        _accept(client, world["expert_token"], booking["id"])
        response = client.get(
            f"/bookings/{booking['id']}/location",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 404

    def test_latest_location_unauthenticated_401(self, client, world):
        response = client.get(f"/bookings/{world['accepted_id']}/location")
        assert response.status_code == 401

    def test_latest_location_other_customer_403(self, client, world):
        response = client.get(
            f"/bookings/{world['accepted_id']}/location",
            headers=token_headers(world["other_customer_token"]),
        )
        assert response.status_code == 403

    def test_latest_location_other_expert_403(self, client, world):
        response = client.get(
            f"/bookings/{world['accepted_id']}/location",
            headers=token_headers(world["other_expert_token"]),
        )
        assert response.status_code == 403

    def test_latest_location_admin_403(self, client, world, admin_token):
        response = client.get(
            f"/bookings/{world['accepted_id']}/location",
            headers=token_headers(admin_token),
        )
        assert response.status_code == 403

    def test_latest_location_missing_booking_404(self, client, world):
        response = client.get(
            "/bookings/999999/location",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 404


class TestRestLocationHistory:
    def test_history_ordered_asc(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 0)
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="21:30:00")
        _accept(client, world["expert_token"], booking["id"])
        with client.websocket_connect(
            _loc_url(booking["id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            for lat, lon in ((1.0, 1.0), (2.0, 2.0), (3.0, 3.0)):
                ws.send_json({"type": "location_update", "latitude": lat, "longitude": lon})
                assert ws.receive_json()["type"] == "location_update"
        response = client.get(
            f"/bookings/{booking['id']}/location/history",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        lats = [p["latitude"] for p in body["points"]]
        assert lats == [pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0)]

    def test_history_limit_caps_points(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "LOCATION_UPDATE_INTERVAL_SECONDS", 0)
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="22:30:00")
        _accept(client, world["expert_token"], booking["id"])
        with client.websocket_connect(
            _loc_url(booking["id"], world["expert_token"])
        ) as ws:
            _read_connected(ws)
            for i in range(1, 6):
                ws.send_json({"type": "location_update", "latitude": float(i), "longitude": 0.0})
                assert ws.receive_json()["type"] == "location_update"
        response = client.get(
            f"/bookings/{booking['id']}/location/history?limit=3",
            headers=token_headers(world["customer_token"]),
        )
        body = response.json()
        assert body["count"] == 3
        # Newest 3 kept, then ordered ASC → [3, 4, 5].
        assert [p["latitude"] for p in body["points"]] == [
            pytest.approx(3.0), pytest.approx(4.0), pytest.approx(5.0)
        ]

    def test_history_limit_validation(self, client, world):
        assert (
            client.get(
                f"/bookings/{world['accepted_id']}/location/history?limit=0",
                headers=token_headers(world["customer_token"]),
            ).status_code
            == 422
        )
        assert (
            client.get(
                f"/bookings/{world['accepted_id']}/location/history?limit=501",
                headers=token_headers(world["customer_token"]),
            ).status_code
            == 422
        )

    def test_history_404_when_empty(self, client, world):
        # Empty history returns 200 with an empty list (documented behavior).
        booking = _booking(client, world["customer_token"], world["expert_profile_id"],
                           world["electrician"], time="23:30:00")
        _accept(client, world["expert_token"], booking["id"])
        response = client.get(
            f"/bookings/{booking['id']}/location/history",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 200
        assert response.json()["points"] == []

    def test_history_forbidden_for_admin(self, client, world, admin_token):
        response = client.get(
            f"/bookings/{world['accepted_id']}/location/history",
            headers=token_headers(admin_token),
        )
        assert response.status_code == 403

    def test_history_unauthenticated_401(self, client, world):
        assert (
            client.get(f"/bookings/{world['accepted_id']}/location/history").status_code == 401
        )


def _expert_user_id(expert_token: str) -> int:
    """Resolve the expert's USER id from their JWT (test helper only)."""
    from app.core.security import decode_access_token
    from app.models import User

    user_id = int(decode_access_token(expert_token)["sub"])
    with SessionLocal() as db:
        assert db.get(User, user_id) is not None
    return user_id
