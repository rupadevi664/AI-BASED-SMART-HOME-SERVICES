"""Manual WebSocket chat test client (Phase 4).

Runs the §32 acceptance flow against a live server: customer and expert
connect to the same booking room and exchange messages in real time.

Usage (server running):
    python scripts/websocket_test.py            # uses newest booking for CUST
    python scripts/websocket_test.py 9          # explicit booking id

Re-run scripts/setup_chat_booking.py first to mint fresh accounts + booking.
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000/ws/bookings"
CUSTOMER = ("live.chat.customer.1790615601@example.com", "password123")
EXPERT = ("live.chat.expert.1790615601@example.com", "password123")


def login(email: str, password: str) -> str:
    with httpx.Client(base_url=BASE, timeout=15) as client:
        response = client.post("/auth/login", json={"email": email, "password": password})
        response.raise_for_status()
        return response.json()["access_token"]


async def main() -> int:
    booking_id = int(sys.argv[1]) if len(sys.argv) > 1 else None

    customer_token = login(*CUSTOMER)
    expert_token = login(*EXPERT)

    if booking_id is None:
        with httpx.Client(base_url=BASE, timeout=15) as client:
            bookings = client.get(
                "/bookings/my", headers={"Authorization": f"Bearer {customer_token}"}
            ).json()
            if not bookings:
                print("No bookings for the test customer. Run setup_chat_booking.py first.")
                return 1
            booking_id = bookings[0]["id"]
    print(f"Using booking {booking_id}")

    events: asyncio.Queue = asyncio.Queue()
    results = []

    async with websockets.connect(
        f"{WS_BASE}/{booking_id}?token={customer_token}"
    ) as ws_c, websockets.connect(
        f"{WS_BASE}/{booking_id}?token={expert_token}"
    ) as ws_e:

        async def drain(ws, tag: str):
            while True:
                event = json.loads(await ws.recv())
                await events.put((tag, event))

        task_c = asyncio.create_task(drain(ws_c, "CUSTOMER"))
        task_e = asyncio.create_task(drain(ws_e, "EXPERT"))

        async def wait_for(tag: str, wtype: str, check=None) -> dict:
            while True:
                who, event = await asyncio.wait_for(events.get(), timeout=10)
                if who == tag and event.get("type") == wtype and (check is None or check(event)):
                    return event

        print("Waiting for join events...")
        await wait_for("CUSTOMER", "user_joined")
        await wait_for("EXPERT", "user_joined")
        results.append(("both connected (user_joined received)", True))

        print("\nCUSTOMER sends: Hello, when will you arrive?")
        await ws_c.send(json.dumps({"type": "message", "message": "Hello, when will you arrive?"}))
        received = await wait_for(
            "EXPERT", "message", lambda e: e.get("message") == "Hello, when will you arrive?"
        )
        print(f"EXPERT received: {json.dumps(received, indent=1)}")
        ok = (
            received.get("sender_role") == "CUSTOMER"
            and received.get("booking_id") == booking_id
            and "timestamp" in received
        )
        results.append(("expert received customer message in real time", ok))

        print("\nEXPERT sends: I will arrive at 10 AM.")
        await ws_e.send(json.dumps({"type": "message", "message": "I will arrive at 10 AM."}))
        received = await wait_for(
            "CUSTOMER", "message", lambda e: e.get("message") == "I will arrive at 10 AM."
        )
        print(f"CUSTOMER received: {json.dumps(received, indent=1)}")
        results.append(("customer received expert message in real time",
                        received.get("sender_role") == "EXPERT"))

        await ws_c.send(json.dumps({"type": "ping"}))
        await wait_for("CUSTOMER", "pong")
        results.append(("ping -> pong", True))

        task_c.cancel()
        task_e.cancel()

    with httpx.Client(base_url=BASE, timeout=15) as client:
        history = client.get(
            f"/bookings/{booking_id}/messages",
            headers={"Authorization": f"Bearer {customer_token}"},
        ).json()
        texts = [m["message"] for m in history]
        ok = "Hello, when will you arrive?" in texts and "I will arrive at 10 AM." in texts
        print(f"\nREST history ({len(history)} messages):")
        for m in history[-4:]:
            print(f"  [{m['created_at']}] sender={m['sender_id']}: {m['message']}")
        results.append(("GET /bookings/{id}/messages returns both messages", ok))

    print()
    passed = 0
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        passed += int(ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
