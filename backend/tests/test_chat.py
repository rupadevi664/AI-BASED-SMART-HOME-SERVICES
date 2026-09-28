"""Phase 4 tests: booking WebSocket chat + REST message history."""
from datetime import date, timedelta

import pytest
from fastapi.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from tests.conftest import (
    login,
    make_admin,
    register_customer,
    register_expert,
    token_headers,
)

ADMIN_EMAIL = "admin.chat@example.com"
FUTURE_DATE = (date.today() + timedelta(days=4)).isoformat()


def _admin(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


@pytest.fixture(scope="module")
def admin_token(client):
    return _admin(client)


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


@pytest.fixture(scope="module")
def world(client, admin_token):
    electrician = next(
        s["id"] for s in client.get("/services").json() if s["name"] == "Electrician"
    )
    plumber = next(
        s["id"] for s in client.get("/services").json() if s["name"] == "Plumber"
    )

    register_expert(
        client, email="chat.expert@example.com",
        latitude=17.44, longitude=78.39, service_ids=[electrician],
    )
    expert_id = _verify_expert(client, admin_token, "chat.expert@example.com")
    expert_token = login(client, "chat.expert@example.com")["access_token"]

    register_expert(
        client, email="chat.other.expert@example.com",
        latitude=17.44, longitude=78.39, service_ids=[plumber],
    )
    _verify_expert(client, admin_token, "chat.other.expert@example.com")
    other_expert_token = login(client, "chat.other.expert@example.com")["access_token"]

    register_customer(client, email="chat.customer@example.com")
    customer_token = login(client, "chat.customer@example.com")["access_token"]
    register_customer(client, email="chat.other.customer@example.com")
    other_customer_token = login(client, "chat.other.customer@example.com")["access_token"]

    booking = client.post(
        "/bookings",
        headers=token_headers(customer_token),
        json={
            "expert_id": expert_id,
            "service_id": electrician,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": FUTURE_DATE,
            "scheduled_time": "10:30:00",
        },
    ).json()

    # A rejected booking to prove chat is blocked there.
    rejected = client.post(
        "/bookings",
        headers=token_headers(customer_token),
        json={
            "expert_id": expert_id,
            "service_id": electrician,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": FUTURE_DATE,
            "scheduled_time": "11:30:00",
        },
    ).json()
    client.put(
        f"/experts/bookings/{rejected['id']}/reject",
        headers=token_headers(expert_token),
        json={"reason": "cannot make it"},
    )

    # A cancelled booking too.
    cancelled = client.post(
        "/bookings",
        headers=token_headers(customer_token),
        json={
            "expert_id": expert_id,
            "service_id": electrician,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": FUTURE_DATE,
            "scheduled_time": "12:30:00",
        },
    ).json()
    client.put(
        f"/bookings/{cancelled['id']}/cancel",
        headers=token_headers(customer_token),
        json={"reason": "plans changed"},
    )

    return {
        "booking_id": booking["id"],
        "rejected_id": rejected["id"],
        "cancelled_id": cancelled["id"],
        "expert_id": expert_id,
        "customer_token": customer_token,
        "expert_token": expert_token,
        "other_customer_token": other_customer_token,
        "other_expert_token": other_expert_token,
    }


def _ws_url(booking_id: int, token: str) -> str:
    return f"/ws/bookings/{booking_id}?token={token}"


def _next_chat_event(ws):
    """Read frames until a chat message arrives (skipping join/leave events)."""
    while True:
        event = ws.receive_json()
        if event.get("type") in {"message", "error"}:
            return event


class TestWebSocketAuthentication:
    def test_connect_with_valid_jwt(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            event = ws.receive_json()
            assert event["type"] == "user_joined"

    def test_missing_jwt_rejected(self, client, world):
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(f"/ws/bookings/{world['booking_id']}"):
                pass

    def test_invalid_jwt_rejected(self, client, world):
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                f"/ws/bookings/{world['booking_id']}?token=not.a.jwt"
            ) as ws:
                ws.receive_json()

    def test_expired_jwt_rejected(self, client, world):
        expired = create_access_token("1", extra_claims={})  # valid token...
        from datetime import datetime, timedelta, timezone

        import jwt as pyjwt

        from app.core.config import settings

        expired = pyjwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                f"/ws/bookings/{world['booking_id']}?token={expired}"
            ) as ws:
                ws.receive_json()

    def test_booking_not_found(self, client, world):
        with pytest.raises((WebSocketDisconnect, AssertionError)):
            with client.websocket_connect(
                _ws_url(999999, world["customer_token"])
            ) as ws:
                ws.receive_json()


class TestWebSocketAuthorization:
    def test_customer_can_connect(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            assert ws.receive_json()["type"] == "user_joined"

    def test_assigned_expert_can_connect(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["expert_token"])
        ) as ws:
            assert ws.receive_json()["type"] == "user_joined"

    def test_unrelated_customer_denied(self, client, world):
        from fastapi.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _ws_url(world["booking_id"], world["other_customer_token"])
            ) as ws:
                ws.receive_json()

    def test_unrelated_expert_denied(self, client, world):
        from fastapi.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _ws_url(world["booking_id"], world["other_expert_token"])
            ) as ws:
                ws.receive_json()

    def test_admin_denied(self, client, world, admin_token):
        from fastapi.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(_ws_url(world["booking_id"], admin_token)) as ws:
                ws.receive_json()

    def test_rejected_booking_denied(self, client, world):
        from fastapi.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _ws_url(world["rejected_id"], world["customer_token"])
            ) as ws:
                ws.receive_json()

    def test_cancelled_booking_denied(self, client, world):
        from fastapi.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                _ws_url(world["cancelled_id"], world["customer_token"])
            ) as ws:
                ws.receive_json()


class TestRealtimeMessaging:
    def test_customer_sends_expert_receives(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as customer, client.websocket_connect(
            _ws_url(world["booking_id"], world["expert_token"])
        ) as expert:
            customer.receive_json()  # user_joined
            expert.receive_json()   # user_joined

            customer.send_json({"type": "message", "message": "Hello, when will you arrive?"})
            received = expert.receive_json()
            assert received["type"] == "message"
            assert received["message"] == "Hello, when will you arrive?"
            assert received["sender_role"] == "CUSTOMER"
            assert received["booking_id"] == world["booking_id"]
            assert "timestamp" in received

    def test_expert_sends_customer_receives(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as customer, client.websocket_connect(
            _ws_url(world["booking_id"], world["expert_token"])
        ) as expert:
            customer.receive_json()
            expert.receive_json()

            expert.send_json({"type": "message", "message": "I will arrive at 10 AM."})
            received = _next_chat_event(customer)
            assert received["type"] == "message"
            assert received["message"] == "I will arrive at 10 AM."
            assert received["sender_role"] == "EXPERT"

    def test_sender_receives_own_message_broadcast(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as customer:
            customer.receive_json()
            customer.send_json({"type": "message", "message": "Note to self"})
            received = customer.receive_json()
            assert received["message"] == "Note to self"

    def test_message_persisted_in_database(self, client, world):
        text = "DB persistence check"
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as customer:
            customer.receive_json()
            customer.send_json({"type": "message", "message": text})
            _next_chat_event(customer)

        history = client.get(
            f"/bookings/{world['booking_id']}/messages",
            headers=token_headers(world["customer_token"]),
        ).json()
        assert any(m["message"] == text for m in history)

    def test_empty_message_rejected(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            ws.receive_json()
            ws.send_json({"type": "message", "message": "   "})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "1-2000" in reply["message"]

    def test_oversized_message_rejected(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            ws.receive_json()
            ws.send_json({"type": "message", "message": "x" * 2001})
            reply = ws.receive_json()
            assert reply["type"] == "error"

    def test_invalid_json_rejected(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            ws.receive_json()
            ws.send_text("this is not json")
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert reply["message"] == "Invalid JSON."

    def test_unsupported_type_rejected(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            ws.receive_json()
            ws.send_json({"type": "reaction", "emoji": "🎉"})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "Unsupported message type" in reply["message"]

    def test_ping_pong(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            reply = ws.receive_json()
            assert reply["type"] == "pong"

    def test_message_trimmed(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws:
            ws.receive_json()
            ws.send_json({"type": "message", "message": "  hello trim  "})
            reply = ws.receive_json()
            assert reply["message"] == "hello trim"

    def test_multiple_connections_same_user(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws1, client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as ws2, client.websocket_connect(
            _ws_url(world["booking_id"], world["expert_token"])
        ) as expert:
            for ws in (ws1, ws2, expert):
                ws.receive_json()  # user_joined

            ws1.send_json({"type": "message", "message": "broadcast to all"})
            # Both customer sockets and the expert socket receive it.
            got1 = _next_chat_event(ws1)
            got2 = _next_chat_event(ws2)
            got_expert = _next_chat_event(expert)
            assert got1["message"] == got2["message"] == got_expert["message"] == "broadcast to all"

    def test_disconnect_cleanup_other_stays_connected(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as customer:
            customer.receive_json()
            expert = client.websocket_connect(
                _ws_url(world["booking_id"], world["expert_token"])
            )
            with expert as ews:
                ews.receive_json()
                # Expert leaves abruptly.
            # Customer should still be able to chat.
            customer.send_json({"type": "message", "message": "still here?"})
            reply = _next_chat_event(customer)
            assert reply["message"] == "still here?"


class TestMessageHistoryREST:
    def test_history_ordered_and_complete(self, client, world):
        with client.websocket_connect(
            _ws_url(world["booking_id"], world["customer_token"])
        ) as customer, client.websocket_connect(
            _ws_url(world["booking_id"], world["expert_token"])
        ) as expert:
            customer.receive_json()
            expert.receive_json()
            customer.send_json({"type": "message", "message": "first message"})
            _next_chat_event(customer)
            expert.send_json({"type": "message", "message": "second message"})
            _next_chat_event(expert)

        history = client.get(
            f"/bookings/{world['booking_id']}/messages",
            headers=token_headers(world["customer_token"]),
        ).json()
        texts = [m["message"] for m in history]
        assert "first message" in texts and "second message" in texts
        # ASC order: 'first' must appear before 'second'.
        assert texts.index("first message") < texts.index("second message")
        assert {"id", "booking_id", "sender_id", "message", "created_at"} <= set(history[0])

    def test_history_forbidden_for_other_customer(self, client, world):
        response = client.get(
            f"/bookings/{world['booking_id']}/messages",
            headers=token_headers(world["other_customer_token"]),
        )
        assert response.status_code == 403

    def test_history_forbidden_for_other_expert(self, client, world):
        response = client.get(
            f"/bookings/{world['booking_id']}/messages",
            headers=token_headers(world["other_expert_token"]),
        )
        assert response.status_code == 403

    def test_history_forbidden_for_admin(self, client, world, admin_token):
        response = client.get(
            f"/bookings/{world['booking_id']}/messages",
            headers=token_headers(admin_token),
        )
        assert response.status_code == 403

    def test_history_unauthenticated_401(self, client, world):
        assert client.get(f"/bookings/{world['booking_id']}/messages").status_code == 401

    def test_history_missing_booking_404(self, client, world):
        response = client.get(
            "/bookings/999999/messages",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 404
