"""Live acceptance test for Phase 1 + Phase 2 — runs against a real server.

Usage (server must be up, e.g. `uvicorn app.main:app --port 8000`):
    python scripts/live_acceptance.py [base_url]

Prints a PASS/FAIL line per scenario and exits non-zero on any failure.
Admin credentials come from ADMIN_EMAIL / ADMIN_PASSWORD in the environment.
"""
import sys
import time

import httpx

sys.path.insert(0, ".")

from app.core.config import settings

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

results = []


def check(name: str, condition: bool, extra: str = "") -> None:
    results.append((name, condition))
    suffix = f"  -> {extra}" if (extra and not condition) else ""
    print(f"{'PASS' if condition else 'FAIL'}  {name}{suffix}")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=15)
    uniq = f"live{int(time.time())}"  # unique per run (emails are unique keys)

    # Health + docs ---------------------------------------------------------
    r = c.get("/")
    check("GET / health", r.status_code == 200 and r.json()["status"] == "ok")
    r = c.get("/docs")
    check("GET /docs (Swagger)", r.status_code == 200 and "Swagger" in r.text)
    r = c.get("/openapi.json")
    tags = {t for p in r.json()["paths"].values() for m in p.values() for t in m.get("tags", [])}
    check(
        "OpenAPI tags (Phase 1 + 2)",
        {"Authentication", "Users", "Experts", "Admin", "Services"} <= tags,
        str(tags),
    )

    # Admin login ------------------------------------------------------------
    admin_login = c.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    check("admin login", admin_login.status_code == 200, admin_login.text)
    admin_headers = {"Authorization": f"Bearer {admin_login.json().get('access_token', '')}"}

    # =========== PHASE 1 FLOWS =================================================
    r = c.post(
        "/auth/register",
        json={
            "name": "Live Customer",
            "email": f"live.customer.{uniq}@example.com",
            "phone": "9999999999",
            "password": "password123",
        },
    )
    check("P1 customer register 201", r.status_code == 201, r.text)
    check("P1 no password_hash in response", "$2b$" not in r.text)
    check("P1 role forced to CUSTOMER", r.json().get("role") == "CUSTOMER", r.text)

    r = c.post(
        "/auth/register",
        json={
            "name": "Live Customer",
            "email": f"live.customer.{uniq}@example.com",
            "phone": "9999999999",
            "password": "password123",
        },
    )
    check("P1 duplicate email 409", r.status_code == 409)

    r = c.post(
        "/auth/login",
        json={"email": f"live.customer.{uniq}@example.com", "password": "password123"},
    )
    check("P1 customer login 200 + bearer", r.status_code == 200 and r.json()["token_type"] == "bearer")
    customer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = c.get("/auth/me", headers=customer_headers)
    check("P1 GET /auth/me 200", r.status_code == 200 and r.json()["role"] == "CUSTOMER")

    r = c.get("/users/customer", headers=customer_headers)
    check("P1 customer -> /users/customer 200", r.status_code == 200)
    r = c.get("/experts/profile", headers=customer_headers)
    check("P1 customer -> /experts/profile 403", r.status_code == 403)
    r = c.get("/admin/dashboard", headers=customer_headers)
    check("P1 customer -> /admin/dashboard 403", r.status_code == 403)

    r = c.post(
        "/auth/login",
        json={"email": f"live.customer.{uniq}@example.com", "password": "wrong"},
    )
    check(
        "P1 invalid login 401 generic",
        r.status_code == 401 and r.json()["detail"] == "Incorrect email or password",
    )
    r = c.get("/auth/me")
    check("P1 missing JWT 401", r.status_code == 401)
    r = c.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    check("P1 invalid JWT 401", r.status_code == 401)

    # =========== PHASE 2 FLOWS =================================================
    # Service catalogue -------------------------------------------------------
    r = c.get("/services")
    check("P2 GET /services 200", r.status_code == 200)
    services = {s["name"]: s["id"] for s in r.json()}
    check(
        "P2 8 seeded services present once",
        len(r.json()) == len({s["name"] for s in r.json()})
        and {"Electrician", "Plumber", "AC Repair", "Home Cleaning", "Carpenter",
             "Painting", "Pest Control", "Appliance Repair"} <= set(services),
        str(sorted(services)),
    )
    electrician_id = services["Electrician"]

    r = c.get(f"/services/{electrician_id}")
    check("P2 GET /services/{id} 200", r.status_code == 200 and r.json()["name"] == "Electrician")
    r = c.get("/services/999999")
    check("P2 missing service 404", r.status_code == 404)

    # Admin service management -------------------------------------------------
    r = c.post(
        "/admin/services",
        headers=customer_headers,
        json={"name": "Hack", "description": "x", "base_price": 10},
    )
    check("P2 customer cannot create service 403", r.status_code == 403)

    r = c.post(
        "/admin/services",
        headers=admin_headers,
        json={"name": f"Gardening {uniq}", "description": "Garden maintenance", "base_price": 500},
    )
    check("P2 admin creates service 201", r.status_code == 201, r.text)
    gardening_id = r.json()["id"]

    r = c.put(
        f"/admin/services/{gardening_id}",
        headers=admin_headers,
        json={"description": "Updated", "base_price": 550},
    )
    check("P2 admin updates service 200", r.status_code == 200 and r.json()["base_price"] == 550)

    r = c.post(
        "/admin/services",
        headers=admin_headers,
        json={"name": f"Gardening {uniq}", "description": "dup", "base_price": 500},
    )
    check("P2 duplicate service name 409", r.status_code == 409)

    # Expert registration with services + coordinates ---------------------------
    expert_email = f"live.expert.{uniq}@example.com"
    r = c.post(
        "/auth/register-expert",
        json={
            "name": "Ravi Kumar",
            "email": expert_email,
            "phone": "8888888888",
            "password": "password123",
            "skills": "Electrical wiring, AC repair",
            "experience_years": 5,
            "location": "Hyderabad",
            "latitude": 17.4150,   # ~3.3 km north of the customer below
            "longitude": 78.4867,
            "availability": "AVAILABLE",
            "service_ids": [electrician_id],
        },
    )
    check("P2 expert register 201 with services", r.status_code == 201, r.text)
    profile = r.json().get("expert_profile", {})
    check("P2 register response has services + PENDING",
          {s["name"] for s in profile.get("services", [])} == {"Electrician"}
          and profile.get("verification_status") == "PENDING")
    check("P2 coordinates stored",
          float(profile.get("latitude", 0)) == 17.4150 and float(profile.get("longitude", 0)) == 78.4867)

    r = c.post(
        "/auth/register-expert",
        json={
            "name": "Broken Expert",
            "email": f"broken.expert.{uniq}@example.com",
            "phone": "8888888888",
            "password": "password123",
            "skills": "Anything",
            "experience_years": 1,
            "location": "Nowhere",
            "service_ids": [999999],
        },
    )
    check("P2 unknown service_id on register 404 (rollback)", r.status_code == 404)
    r = c.post(
        "/auth/register",
        json={"name": "Broken Expert", "email": f"broken.expert.{uniq}@example.com",
              "phone": "8888888888", "password": "password123"},
    )
    check("P2 rollback left no user behind (email free)", r.status_code == 201)

    # Expert profile management ---------------------------------------------------
    r = c.post(
        "/auth/login",
        json={"email": expert_email, "password": "password123"},
    )
    expert_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = c.get("/experts/profile", headers=expert_headers)
    check("P2 GET /experts/profile 200 flat shape",
          r.status_code == 200 and r.json()["email"] == expert_email
          and isinstance(r.json()["services"], list), r.text[:200])

    r = c.put(
        "/experts/profile",
        headers=expert_headers,
        json={"experience_years": 7, "availability": "UNAVAILABLE"},
    )
    check("P2 PUT /experts/profile 200", r.status_code == 200 and r.json()["experience_years"] == 7)
    r = c.put(
        "/experts/profile",
        headers=expert_headers,
        json={"availability": "AVAILABLE", "latitude": 17.4150, "longitude": 78.4867},
    )
    check("P2 expert re-available + coords", r.status_code == 200 and r.json()["availability"] == "AVAILABLE")
    r = c.put("/experts/profile", headers=expert_headers, json={"latitude": 95.0})
    check("P2 invalid latitude 422", r.status_code == 422)

    # Verification ------------------------------------------------------------------
    r = c.put(
        "/admin/experts/1/verification",
        headers=customer_headers,
        params={"verification_status": "VERIFIED"},
    )
    check("P2 customer cannot verify 403", r.status_code == 403)

    r = c.get("/admin/experts", headers=admin_headers)
    check("P2 admin experts list 200", r.status_code == 200)
    target = next((e for e in r.json() if e["email"] == expert_email), None)
    check("P2 registered expert in admin list", target is not None)

    r = c.put(
        f"/admin/experts/{target['id']}/verification",
        headers=admin_headers,
        params={"verification_status": "VERIFIED"},
    )
    check(
        "P2 admin verifies expert 200",
        r.status_code == 200 and r.json()["verification_status"] == "VERIFIED",
        r.text[:200],
    )

    # Nearby search ------------------------------------------------------------------
    r = c.get(
        "/experts/nearby",
        headers=customer_headers,
        params={"latitude": 17.3850, "longitude": 78.4867, "radius_km": 10},
    )
    check("P2 nearby 200", r.status_code == 200, r.text[:300])
    body = r.json()
    check("P2 nearby finds verified expert", any(e["expert_id"] == target["id"] for e in body))
    check("P2 nearby sorted by distance",
          [e["distance_km"] for e in body] == sorted(e["distance_km"] for e in body))
    check("P2 distances <= radius", all(e["distance_km"] <= 10 for e in body))
    near = next((e for e in body if e["expert_id"] == target["id"]), {})
    check(
        "P2 distance ~3.3 km (Haversine)",
        3.0 <= near.get("distance_km", 99) <= 3.7,
        str(near.get("distance_km")),
    )
    check("P2 nearby shape has services list",
          isinstance(near.get("services"), list) and "password_hash" not in near)

    r = c.get(
        "/experts/nearby",
        headers=customer_headers,
        params={"latitude": 17.3850, "longitude": 78.4867, "radius_km": 10,
                "service_id": services["Pest Control"]},
    )
    check("P2 service filter excludes non-matching", r.status_code == 200 and r.json() == [])

    r = c.get(
        "/experts/nearby",
        headers=customer_headers,
        params={"latitude": -20.0, "longitude": 70.0, "radius_km": 5},
    )
    check("P2 empty area returns 200 []", r.status_code == 200 and r.json() == [])

    r = c.get(
        "/experts/nearby",
        headers=customer_headers,
        params={"latitude": 17.3850, "longitude": 78.4867, "radius_km": 10, "service_id": 999999},
    )
    check("P2 nearby unknown service 404", r.status_code == 404)

    r = c.get(
        "/experts/nearby",
        params={"latitude": 17.3850, "longitude": 78.4867, "radius_km": 10},
    )
    check("P2 nearby missing JWT 401", r.status_code == 401)

    r = c.get(
        "/experts/nearby",
        headers=customer_headers,
        params={"latitude": 91.0, "longitude": 78.4867, "radius_km": 10},
    )
    check("P2 nearby invalid latitude 422", r.status_code == 422)

    # =========== PHASE 3 FLOWS (full manual acceptance) ========================
    from datetime import date, timedelta

    future = (date.today() + timedelta(days=2)).isoformat()
    slot = "10:30:00"

    # STEP 1-3: customer + verified expert already exist from the flows above.
    # STEP 4-5: services + nearby search already exercised above.

    # STEP 6: customer creates booking
    r = c.post(
        "/bookings",
        headers=customer_headers,
        json={
            "expert_id": target["id"],
            "service_id": electrician_id,
            "service_address": "Madhapur, Hyderabad",
            "service_latitude": 17.4483,
            "service_longitude": 78.3915,
            "scheduled_date": future,
            "scheduled_time": slot,
            "customer_notes": "Need electrical wiring repair",
        },
    )
    check("P3 POST /bookings 201", r.status_code == 201, r.text[:300])
    booking = r.json()
    check("P3 booking starts PENDING", booking.get("status") == "PENDING")
    check("P3 price snapshot from catalogue", float(booking.get("service_price", 0)) == 299.0,
          str(booking.get("service_price")))
    check("P3 name snapshot", booking.get("service_name") == "Electrician")

    r = c.post(
        "/bookings",
        headers=customer_headers,
        json={
            "expert_id": target["id"],
            "service_id": electrician_id,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": future,
            "scheduled_time": slot,
        },
    )
    check("P3 duplicate slot conflict 409", r.status_code == 409)

    r = c.post(
        "/bookings",
        headers=customer_headers,
        json={
            "expert_id": target["id"],
            "service_id": electrician_id,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": "2020-01-01",
            "scheduled_time": slot,
        },
    )
    check("P3 past date 400", r.status_code == 400)

    # STEP 7: expert sees the booking
    r = c.get("/experts/bookings", headers=expert_headers)
    check("P3 expert sees own bookings", r.status_code == 200 and
          any(b["id"] == booking["id"] for b in r.json()))

    # Expert workflow
    r = c.put(f"/experts/bookings/{booking['id']}/accept", headers=expert_headers)
    check(
        "P3 expert accept -> ACCEPTED",
        r.status_code == 200 and r.json()["status"] == "ACCEPTED",
        r.text[:200],
    )
    r = c.put(f"/experts/bookings/{booking['id']}/accept", headers=expert_headers)
    check("P3 accept twice 400", r.status_code == 400)

    # STEP 9: complete
    r = c.put(f"/experts/bookings/{booking['id']}/complete", headers=expert_headers)
    check("P3 expert complete -> COMPLETED", r.status_code == 200 and r.json()["status"] == "COMPLETED")
    r = c.put(
        f"/bookings/{booking['id']}/cancel",
        headers=customer_headers,
        json={"reason": "too late"},
    )
    check("P3 completed cannot be cancelled 400", r.status_code == 400)

    # STEP 10: customer history
    r = c.get("/bookings/my", headers=customer_headers)
    check("P3 customer history shows booking", r.status_code == 200 and
          any(b["id"] == booking["id"] for b in r.json()))
    r = c.get("/bookings/my", params={"status": "COMPLETED"}, headers=customer_headers)
    check("P3 history status filter", r.status_code == 200 and
          all(b["status"] == "COMPLETED" for b in r.json()))

    # Details + access control
    r = c.get(f"/bookings/{booking['id']}", headers=customer_headers)
    check("P3 customer views own booking detail", r.status_code == 200)
    r = c.get(f"/bookings/{booking['id']}", headers=admin_headers)
    check("P3 admin views booking detail", r.status_code == 200)
    r = c.get("/admin/bookings", headers=admin_headers)
    check("P3 admin sees all bookings", r.status_code == 200 and len(r.json()) >= 1)
    r = c.get("/admin/bookings", params={"status": "COMPLETED", "service_id": electrician_id},
              headers=admin_headers)
    check("P3 admin filters work", r.status_code == 200 and
          all(b["status"] == "COMPLETED" for b in r.json()))
    r = c.get("/admin/bookings", headers=customer_headers)
    check("P3 customer cannot use admin bookings 403", r.status_code == 403)
    r = c.get("/bookings/999999", headers=customer_headers)
    check("P3 missing booking 404", r.status_code == 404)
    r = c.post("/bookings", json={"expert_id": 1, "service_id": 1,
                                  "service_address": "Somewhere", "scheduled_date": future,
                                  "scheduled_time": slot})
    check("P3 missing JWT on create 401", r.status_code == 401)

    # Price snapshot across a catalogue change (new service + new booking)
    r = c.post(
        "/admin/services",
        headers=admin_headers,
        json={"name": f"Snapshot Svc {uniq}", "description": "snapshot", "base_price": 400},
    )
    snap_svc = r.json()["id"]
    r = c.put("/experts/profile", headers=expert_headers,
              json={"service_ids": [electrician_id, snap_svc]})
    assert r.status_code == 200, r.text
    r = c.post(
        "/bookings",
        headers=customer_headers,
        json={
            "expert_id": target["id"],
            "service_id": snap_svc,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": future,
            "scheduled_time": "11:00:00",
        },
    )
    check("P3 second booking 201", r.status_code == 201, r.text[:200])
    snap_booking = r.json()
    r = c.put(f"/admin/services/{snap_svc}", headers=admin_headers, json={"base_price": 999})
    check("P3 admin price change ok", r.status_code == 200)
    r = c.get(f"/bookings/{snap_booking['id']}", headers=customer_headers)
    check("P3 snapshot preserved after price change",
          r.status_code == 200 and float(r.json()["service_price"]) == 400.0,
          r.text[:200])

    # Cancel + reject flows on fresh bookings
    r = c.post(
        "/bookings",
        headers=customer_headers,
        json={
            "expert_id": target["id"],
            "service_id": electrician_id,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": future,
            "scheduled_time": "12:00:00",
        },
    )
    b2 = r.json()
    r = c.put(f"/bookings/{b2['id']}/cancel", headers=customer_headers,
              json={"reason": "My schedule changed"})
    check("P3 customer cancel PENDING -> CANCELLED", r.status_code == 200 and
          r.json()["status"] == "CANCELLED" and r.json()["cancellation_reason"] == "My schedule changed")
    r = c.put(f"/bookings/{b2['id']}/cancel", headers=customer_headers, json={"reason": "again"})
    check("P3 cancel twice 400", r.status_code == 400)

    r = c.post(
        "/bookings",
        headers=customer_headers,
        json={
            "expert_id": target["id"],
            "service_id": electrician_id,
            "service_address": "Madhapur, Hyderabad",
            "scheduled_date": future,
            "scheduled_time": "13:00:00",
        },
    )
    b3 = r.json()
    r = c.put(f"/experts/bookings/{b3['id']}/reject", headers=expert_headers,
              json={"reason": "Not available at requested time"})
    check("P3 expert reject -> REJECTED + reason", r.status_code == 200 and
          r.json()["status"] == "REJECTED" and
          r.json()["cancellation_reason"] == "Not available at requested time")
    r = c.put(f"/experts/bookings/{b3['id']}/accept", headers=expert_headers)
    check("P3 accept rejected 400", r.status_code == 400)

    # API surface -----------------------------------------------------------------
    paths = c.get("/openapi.json").json()["paths"]
    n_ops = sum(len(m) for m in paths.values())
    check("openapi has >= 26 operations", n_ops >= 26, str(n_ops))
    tags = {t for p in paths.values() for m in p.values() for t in m.get("tags", [])}
    check("Bookings tag present", "Bookings" in tags, str(sorted(tags)))

    print(f"\n{sum(1 for _, ok in results if ok)}/{len(results)} checks passed")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
