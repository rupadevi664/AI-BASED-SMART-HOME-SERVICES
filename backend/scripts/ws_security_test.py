"""Security acceptance test (Phase 4 §33): only booking participants connect.

Usage: python scripts/ws_security_test.py <booking_id>
Creates fresh intruder accounts, then checks:
  assigned CUSTOMER -> ALLOWED, unrelated CUSTOMER -> DENIED,
  unrelated EXPERT  -> DENIED, ADMIN -> DENIED.
"""
import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/bookings"
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))

from app.core.config import settings  # noqa: E402


def login(email: str, password: str = "password123") -> str:
    with httpx.Client(base_url=BASE, timeout=15) as c:
        r = c.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


async def try_connect(token: str, label: str) -> tuple[str, str, str]:
    try:
        async with websockets.connect(f"{WS}/{sys.argv[1]}?token={token}") as ws:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            return label, "ACCEPTED", msg.get("type", "?")
    except Exception as ex:
        return label, "DENIED", type(ex).__name__


async def main() -> int:
    u = str(int(time.time()))
    with httpx.Client(base_url=BASE, timeout=15) as c:
        c.post("/auth/register", json={
            "name": "Intruder Cust", "email": f"intruder.cust.{u}@example.com",
            "phone": "7777777777", "password": "password123"})
        c.post("/auth/register-expert", json={
            "name": "Intruder Expert", "email": f"intruder.exp.{u}@example.com",
            "phone": "6666666666", "password": "password123", "skills": "plumbing",
            "experience_years": 1, "location": "SomeCity", "availability": "AVAILABLE",
            "service_ids": [1]})

    cust_token = login("live.chat.customer.1790615601@example.com")
    intruder_cust = login(f"intruder.cust.{u}@example.com")
    intruder_expert = login(f"intruder.exp.{u}@example.com")
    admin = login(settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)

    checks = []
    for token, label, expect in [
        (cust_token, "assigned CUSTOMER", "ACCEPTED"),
        (intruder_cust, "unrelated CUSTOMER", "DENIED"),
        (intruder_expert, "unrelated EXPERT", "DENIED"),
        (admin, "ADMIN", "DENIED"),
    ]:
        label, verdict, detail = await try_connect(token, label)
        ok = verdict == expect
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {label:20s} -> {verdict} ({detail}), expected {expect}")

    print(f"\n{sum(checks)}/{len(checks)} security checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
