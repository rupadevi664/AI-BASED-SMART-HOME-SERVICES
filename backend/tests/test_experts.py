"""Phase 2 tests: expert profile management, expert-services, verification."""
import pytest

from tests.conftest import (
    PASSWORD,
    login,
    make_admin,
    register_customer,
    register_expert,
    token_headers,
)

ADMIN_EMAIL = "admin.experts@example.com"
CUSTOMER_EMAIL = "expert.customer@example.com"


@pytest.fixture(scope="module")
def admin_token(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


@pytest.fixture(scope="module")
def service_ids(client):
    body = client.get("/services").json()
    by_name = {s["name"]: s["id"] for s in body}
    return by_name


class TestExpertRegistrationWithServices:
    def test_register_expert_with_coordinates_and_services(self, client, service_ids):
        response = client.post(
            "/auth/register-expert",
            json={
                "name": "Ravi Kumar",
                "email": "ravi@example.com",
                "phone": "9999999999",
                "password": PASSWORD,
                "skills": "Electrical wiring",
                "experience_years": 5,
                "location": "Hyderabad",
                "latitude": 17.3850,
                "longitude": 78.4867,
                "availability": "AVAILABLE",
                "service_ids": [service_ids["Electrician"], service_ids["AC Repair"]],
            },
        )
        assert response.status_code == 201, response.text
        profile = response.json()["expert_profile"]
        assert float(profile["latitude"]) == 17.3850
        assert float(profile["longitude"]) == 78.4867
        assert profile["verification_status"] == "PENDING"
        assert {s["name"] for s in profile["services"]} == {"Electrician", "AC Repair"}

    def test_register_expert_with_unknown_service_rolls_back(self, client):
        """Unknown service id → 404 and NO user/profile/link rows left behind."""
        response = client.post(
            "/auth/register-expert",
            json={
                "name": "Ghost Expert",
                "email": "ghost.expert@example.com",
                "phone": "9999999999",
                "password": PASSWORD,
                "skills": "Anything",
                "experience_years": 1,
                "location": "Nowhere",
                "service_ids": [424242],
            },
        )
        assert response.status_code == 404
        # The user must not exist (transaction rolled back).
        dup = client.post(
            "/auth/register",
            json={
                "name": "Ghost Expert",
                "email": "ghost.expert@example.com",
                "phone": "9999999999",
                "password": PASSWORD,
            },
        )
        assert dup.status_code == 201  # email free again → nothing was created


class TestExpertProfileManagement:
    def test_get_own_profile_full_shape(self, client):
        register_expert(client, email="prof.expert@example.com")
        token = login(client, "prof.expert@example.com")["access_token"]
        response = client.get("/experts/profile", headers=token_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "prof.expert@example.com"
        assert {"id", "user_id", "name", "email", "phone", "skills", "experience_years",
                "location", "latitude", "longitude", "verification_status",
                "availability", "services"} <= set(body)
        assert "password_hash" not in body

    def test_expert_updates_profile_fields(self, client, service_ids):
        register_expert(client, email="upd.expert@example.com")
        token = login(client, "upd.expert@example.com")["access_token"]
        headers = token_headers(token)

        response = client.put(
            "/experts/profile",
            headers=headers,
            json={
                "skills": "Electrical wiring, AC repair",
                "experience_years": 7,
                "location": "Hyderabad",
                "latitude": 17.3850,
                "longitude": 78.4867,
                "availability": "UNAVAILABLE",
                "service_ids": [service_ids["Electrician"], service_ids["Plumber"]],
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["experience_years"] == 7  # manually entered, stored verbatim
        assert body["availability"] == "UNAVAILABLE"
        assert {s["name"] for s in body["services"]} == {"Electrician", "Plumber"}

        # Second update: replacing services again must not duplicate rows.
        response = client.put(
            "/experts/profile", headers=headers,
            json={"service_ids": [service_ids["Electrician"]]},
        )
        assert response.status_code == 200
        assert [s["name"] for s in response.json()["services"]] == ["Electrician"]

    def test_update_with_unknown_service_404(self, client):
        register_expert(client, email="badsvc.expert@example.com")
        token = login(client, "badsvc.expert@example.com")["access_token"]
        response = client.put(
            "/experts/profile",
            headers=token_headers(token),
            json={"service_ids": [987654]},
        )
        assert response.status_code == 404

    def test_update_with_invalid_coordinates_422(self, client):
        register_expert(client, email="badcoord.expert@example.com")
        token = login(client, "badcoord.expert@example.com")["access_token"]
        response = client.put(
            "/experts/profile",
            headers=token_headers(token),
            json={"latitude": 91.0},
        )
        assert response.status_code == 422
        response = client.put(
            "/experts/profile",
            headers=token_headers(token),
            json={"longitude": -181.0},
        )
        assert response.status_code == 422

    def test_customer_cannot_access_expert_profile_endpoints(self, client):
        register_customer(client, email=CUSTOMER_EMAIL)
        token = login(client, CUSTOMER_EMAIL)["access_token"]
        assert client.get("/experts/profile", headers=token_headers(token)).status_code == 403
        assert client.put(
            "/experts/profile", headers=token_headers(token), json={"skills": "hack"}
        ).status_code == 403

    def test_admin_cannot_use_expert_profile_endpoints(self, client, admin_token):
        assert client.get("/experts/profile", headers=token_headers(admin_token)).status_code == 403


class TestExpertVerification:
    def test_admin_verifies_expert(self, client, admin_token):
        register_expert(client, email="verif.expert@example.com")
        experts = client.get(
            "/admin/experts", headers=token_headers(admin_token)
        ).json()
        target = next(e for e in experts if e["email"] == "verif.expert@example.com")

        response = client.put(
            f"/admin/experts/{target['id']}/verification",
            headers=token_headers(admin_token),
            params={"verification_status": "VERIFIED"},
        )
        assert response.status_code == 200
        assert response.json()["verification_status"] == "VERIFIED"

    def test_admin_rejects_expert(self, client, admin_token):
        register_expert(client, email="reject.expert@example.com")
        experts = client.get("/admin/experts", headers=token_headers(admin_token)).json()
        target = next(e for e in experts if e["email"] == "reject.expert@example.com")
        response = client.put(
            f"/admin/experts/{target['id']}/verification",
            headers=token_headers(admin_token),
            params={"verification_status": "REJECTED"},
        )
        assert response.status_code == 200
        assert response.json()["verification_status"] == "REJECTED"

    def test_invalid_status_value_422(self, client, admin_token):
        response = client.put(
            "/admin/experts/1/verification",
            headers=token_headers(admin_token),
            params={"verification_status": "MAYBE"},
        )
        assert response.status_code == 422

    def test_missing_expert_404(self, client, admin_token):
        response = client.put(
            "/admin/experts/99999/verification",
            headers=token_headers(admin_token),
            params={"verification_status": "VERIFIED"},
        )
        assert response.status_code == 404

    def test_customer_cannot_verify_403(self, client):
        register_customer(client, email="noverify.customer@example.com")
        token = login(client, "noverify.customer@example.com")["access_token"]
        response = client.put(
            "/admin/experts/1/verification",
            headers=token_headers(token),
            params={"verification_status": "VERIFIED"},
        )
        assert response.status_code == 403

    def test_expert_cannot_verify_403(self, client):
        register_expert(client, email="selfverify.expert@example.com")
        token = login(client, "selfverify.expert@example.com")["access_token"]
        response = client.put(
            "/admin/experts/1/verification",
            headers=token_headers(token),
            params={"verification_status": "VERIFIED"},
        )
        assert response.status_code == 403
