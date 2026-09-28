"""Phase 1 automated tests: role-based access control matrix.

CUSTOMER: /users/customer → 200, /experts/profile → 403, /admin/dashboard → 403
EXPERT:   /users/customer → 403, /experts/profile → 200, /admin/dashboard → 403
ADMIN:    /users/customer → 403, /experts/profile → 403, /admin/dashboard → 200
"""
import pytest

from tests.conftest import (
    login,
    make_admin,
    register_customer,
    register_expert,
    token_headers,
)

ADMIN_EMAIL = "admin.roles@example.com"

PROTECTED = [
    ("/users/customer", 200, "CUSTOMER"),
    ("/experts/profile", 200, "EXPERT"),
    ("/admin/dashboard", 200, "ADMIN"),
]


@pytest.fixture(scope="module")
def users(client):
    """Register one account per role once for this module."""
    register_customer(client, email="roles.customer@example.com")
    register_expert(client, email="roles.expert@example.com")
    make_admin(email=ADMIN_EMAIL)
    return {
        "CUSTOMER": login(client, "roles.customer@example.com")["access_token"],
        "EXPERT": login(client, "roles.expert@example.com")["access_token"],
        "ADMIN": login(client, ADMIN_EMAIL)["access_token"],
    }


class TestRoleMatrix:
    @pytest.mark.parametrize("path,expected_status,required_role", PROTECTED)
    def test_each_role_against_each_endpoint(self, client, users, path, expected_status, required_role):
        headers = token_headers(users[required_role])
        response = client.get(path, headers=headers)
        assert response.status_code == expected_status, response.text

    def test_customer_cannot_access_expert_endpoint(self, client, users):
        response = client.get("/experts/profile", headers=token_headers(users["CUSTOMER"]))
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_customer_cannot_access_admin_endpoint(self, client, users):
        response = client.get("/admin/dashboard", headers=token_headers(users["CUSTOMER"]))
        assert response.status_code == 403

    def test_expert_cannot_access_admin_endpoint(self, client, users):
        response = client.get("/admin/dashboard", headers=token_headers(users["EXPERT"]))
        assert response.status_code == 403

    def test_expert_cannot_access_customer_endpoint(self, client, users):
        response = client.get("/users/customer", headers=token_headers(users["EXPERT"]))
        assert response.status_code == 403

    def test_admin_cannot_access_customer_and_expert_endpoints(self, client, users):
        assert client.get("/users/customer", headers=token_headers(users["ADMIN"])).status_code == 403
        assert client.get("/experts/profile", headers=token_headers(users["ADMIN"])).status_code == 403

    def test_missing_jwt_on_protected_endpoints_401(self, client):
        for path, *_ in PROTECTED:
            assert client.get(path).status_code == 401

    def test_invalid_jwt_on_protected_endpoints_401(self, client):
        for path, *_ in PROTECTED:
            response = client.get(path, headers={"Authorization": "Bearer invalid.token.value"})
            assert response.status_code == 401


class TestAdminDashboard:
    def test_admin_dashboard_stats(self, client, users):
        response = client.get("/admin/dashboard", headers=token_headers(users["ADMIN"]))
        assert response.status_code == 200
        stats = response.json()["stats"]
        assert stats["total_users"] >= 3
        assert stats["total_experts"] >= 1
        assert stats["total_customers"] >= 1
        assert stats["total_services"] >= 8  # seeded catalogue present


class TestCustomerEndpoint:
    def test_customer_endpoint_welcome(self, client, users):
        response = client.get("/users/customer", headers=token_headers(users["CUSTOMER"]))
        assert response.status_code == 200
        assert "customer area" in response.json()["message"]


class TestExpertEndpoint:
    def test_expert_endpoint_profile_fields(self, client, users):
        response = client.get("/experts/profile", headers=token_headers(users["EXPERT"]))
        assert response.status_code == 200
        body = response.json()
        # Phase 2 contract: flat full profile with user info and services.
        assert body["email"] == "roles.expert@example.com"
        assert body["verification_status"] == "PENDING"
        assert isinstance(body["services"], list)
        assert "password_hash" not in body
