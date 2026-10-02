"""Manual live-location acceptance test client (Phase 5).

Runs the §34 acceptance flow against a running server:
customer + expert connect to `ws://…/ws/bookings/{id}/location`, the expert
streams a location_update, the customer receives it in real time, and the
REST latest/history endpoints return the stored points.

Usage (server running on 127.0.0.1:8000):
    python scripts/location_test.py

Creates its own fresh customer/expert/booking (test coordinates only), so it
is safe to run repeatedly. Exits 0 only when every check passes.
"""
import asyncio
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx
import websockets

# REQUIRED: lets the script import app.* when run as `python scripts/location_test.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000/ws/bookings"

# Test coordinates (Hyderabad area) — never personal location data.
LAT, LON = 17.3850, 78.4867


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=15)
    stamp = str(int(time.time()))
    cust_email = f"live.loc.customer.{stamp}@example.com"
    exp_email = f"live.loc.expert.{stamp}@example.com"

    from app.core.config import settings

    print("Setting up fresh customer + verified expert + ACCEPTED booking ...")
    assert c.post("/auth/register", json={
        "name": "Live Loc Customer", "email": cust_email,
        "phone": "9999999999", "password": "password123",
    }).status_code == 201
    r = c.post("/auth/register-expert", json={
        "name": "Live Loc Expert", "email": exp_email, "phone": "8888888888",
        "password": "password123", "skills": "wiring", "experience_years": 4,
        "location": "Hyderabad", "latitude": 17.44, "longitude": 78.39,
        "availability": "AVAILABLE", "service_ids": [1],
    })
    assert r.status_code == 201, r.text
    expert_profile_id = r.json()["expert_profile"]["id"]

    def login(email: str, password: str = "password123") -> str:
        resp = c.post("/auth/login", json={"email": email, "password": password})
        resp.raise_for_status()
        return resp.json()["access_token"]

    admin_token = login(settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)
    resp = c.put(
        f"/admin/experts/{expert_profile_id}/verification",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"verification_status": "VERIFIED"},
    )
    assert resp.status_code == 200, resp.text

    customer_token = login(cust_email)
    expert_token = login(exp_email)
    future = (date.today() + timedelta(days=5)).isoformat()
    r = c.post("/bookings", headers={"Authorization": f"Bearer {customer_token}"}, json={
        "expert_id": expert_profile_id, "service_id": 1,
        "service_address": "Madhapur, Hyderabad",
        "scheduled_date": future, "scheduled_time": "09:30:00",
    })
    assert r.status_code == 201, r.text
    booking_id = r.json()["id"]
    resp = c.put(f"/experts/bookings/{booking_id}/accept",
                 headers={"Authorization": f"Bearer {expert_token}"})
    assert resp.status_code == 200, resp.text
    print(f"Booking {booking_id} is ACCEPTED.\n")

    results: list[tuple[str, bool]] = []

    def loc_url(token: str) -> str:
        return f"{WS_BASE}/{booking_id}/location?token={token}"

    async def run_flow() -> None:

        async with websockets.connect(loc_url(expert_token)) as ws_e, \
                   websockets.connect(loc_url(customer_token)) as ws_c:
            # STEP 4/5: both connect.
            hello_e = json.loads(await ws_e.recv())
            hello_c = json.loads(await ws_c.recv())
            results.append(("expert CONNECTED frame", hello_e.get("type") == "connected"
                            and hello_e.get("role") == "expert"))
            results.append(("customer CONNECTED frame", hello_c.get("type") == "connected"
                            and hello_c.get("role") == "customer"))

            # STEP 6: expert sends the spec's exact sample payload.
            frame = {
                "type": "location_update", "latitude": LAT, "longitude": LON,
                "accuracy": 5.0, "heading": 90.0, "speed": 8.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            print(f"EXPERT sends: {json.dumps(frame)}")
            await ws_e.send(json.dumps(frame))

            # STEP 8: customer receives it in real time.
            received = json.loads(await asyncio.wait_for(ws_c.recv(), timeout=10))
            print(f"CUSTOMER received: {json.dumps(received)}")
            results.append(("customer received location_update in real time", (
                received.get("type") == "location_update"
                and received.get("booking_id") == booking_id
                and abs(received.get("latitude", 0) - LAT) < 1e-6
                and abs(received.get("longitude", 0) - LON) < 1e-6
                and received.get("accuracy") == 5.0
                and received.get("heading") == 90.0
                and received.get("speed") == 8.0
                and "timestamp" in received
            )))

            # The sender's own socket also receives the broadcast echo — drain
            # it so the next expert-socket read sees the throttle error.
            echo = json.loads(await asyncio.wait_for(ws_e.recv(), timeout=10))
            results.append(("expert receives own broadcast echo", (
                echo.get("type") == "location_update"
                and abs(echo.get("latitude", 0) - LAT) < 1e-6
            )))

            # §9: customer cannot send.
            await ws_c.send(json.dumps({"type": "location_update", "latitude": 1.0, "longitude": 1.0}))
            err = json.loads(await asyncio.wait_for(ws_c.recv(), timeout=10))
            results.append(("customer send attempt denied", err.get("type") == "error"
                            and "Only the assigned expert" in err.get("message", "")))

            # §17: immediate second update is throttled.
            await ws_e.send(json.dumps({"type": "location_update", "latitude": 2.0, "longitude": 2.0}))
            thr = json.loads(await asyncio.wait_for(ws_e.recv(), timeout=10))
            results.append(("rapid second update throttled", thr.get("type") == "error"
                            and "too frequently" in thr.get("message", "")))

        # STEP 9: latest location.
        r = c.get(f"/bookings/{booking_id}/location",
                  headers={"Authorization": f"Bearer {customer_token}"})
        ok = r.status_code == 200 and abs(r.json()["latitude"] - LAT) < 1e-6
        results.append(("GET /bookings/{id}/location returns latest", ok))

        # STEP 10: history.
        r = c.get(f"/bookings/{booking_id}/location/history",
                  headers={"Authorization": f"Bearer {customer_token}"})
        body = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and body.get("count") == 1 and len(body.get("points", [])) == 1
        results.append(("GET /bookings/{id}/location/history returns ASC history", ok))

        # §35: unrelated users and admin are denied.
        other = c.post("/auth/register", json={
            "name": "Outsider", "email": f"live.loc.outsider.{stamp}@example.com",
            "phone": "7777777777", "password": "password123"})
        assert other.status_code == 201
        outsider_token = login(f"live.loc.outsider.{stamp}@example.com")
        try:
            async with websockets.connect(loc_url(outsider_token)) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)
            denied = False  # got in — bad
        except Exception:
            denied = True
        results.append(("unrelated customer denied on WS", denied))
        results.append(("admin denied on REST latest",
                        c.get(f"/bookings/{booking_id}/location",
                              headers={"Authorization": f"Bearer {admin_token}"}).status_code == 403))

    asyncio.run(run_flow())

    print()
    passed = 0
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        passed += int(ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
