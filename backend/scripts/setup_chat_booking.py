"""Create a fresh customer + verified expert + booking for the live chat test.

Usage (server running):
    python scripts/setup_chat_booking.py
Prints CUST_EMAIL / EXP_EMAIL / BOOKING_ID for websocket_test.py.
"""
import os
import sys
import time
from datetime import date, timedelta

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:8000"


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=15)
    u = str(int(time.time()))
    cust_email = f"live.chat.customer.{u}@example.com"
    exp_email = f"live.chat.expert.{u}@example.com"

    from app.core.config import settings

    r = c.post(
        "/auth/register",
        json={"name": "Live Chat Customer", "email": cust_email, "phone": "9999999999",
              "password": "password123"},
    )
    print("customer:", r.status_code)
    r = c.post(
        "/auth/register-expert",
        json={"name": "Live Chat Expert", "email": exp_email, "phone": "8888888888",
              "password": "password123", "skills": "wiring", "experience_years": 4,
              "location": "Hyderabad", "latitude": 17.44, "longitude": 78.39,
              "availability": "AVAILABLE", "service_ids": [1]},
    )
    print("expert:", r.status_code)
    expert_profile_id = r.json()["expert_profile"]["id"]

    def login(email: str, password: str = "password123") -> str:
        resp = c.post("/auth/login", json={"email": email, "password": password})
        resp.raise_for_status()
        return resp.json()["access_token"]

    admin = login(settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)

    r = c.put(
        f"/admin/experts/{expert_profile_id}/verification",
        headers={"Authorization": f"Bearer {admin}"},
        params={"verification_status": "VERIFIED"},
    )
    print("verify:", r.status_code)

    future = (date.today() + timedelta(days=5)).isoformat()
    r = c.post(
        "/bookings",
        headers={"Authorization": f"Bearer {login(cust_email)}"},
        json={
            "expert_id": expert_profile_id,
            "service_id": 1,
            "service_address": "Madhapur, Hyderabad",
            "service_latitude": 17.4483,
            "service_longitude": 78.3915,
            "scheduled_date": future,
            "scheduled_time": "09:30:00",
            "customer_notes": "Live chat acceptance booking",
        },
    )
    print("booking:", r.status_code, r.json().get("id"), r.json().get("status"))
    print(f"CUST_EMAIL={cust_email}")
    print(f"EXP_EMAIL={exp_email}")
    print(f"BOOKING_ID={r.json().get('id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
