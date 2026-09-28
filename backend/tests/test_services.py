"""Phase 2 tests: service catalogue + admin service management."""
import pytest

from tests.conftest import login, make_admin, register_customer, register_expert, token_headers

ADMIN_EMAIL = "admin.services@example.com"

SEEDED = {
    "Electrician",
    "Plumber",
    "AC Repair",
    "Home Cleaning",
    "Carpenter",
    "Painting",
    "Pest Control",
    "Appliance Repair",
}


@pytest.fixture(scope="module")
def admin_token(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


class TestServiceList:
    def test_list_seeded_services_exactly_once(self, client):
        response = client.get("/services")
        assert response.status_code == 200
        names = [s["name"] for s in response.json()]
        assert SEEDED <= set(names)
        assert len(names) == len(set(names))  # no duplicates

    def test_service_fields_shape(self, client):
        body = client.get("/services").json()
        electrician = next(s for s in body if s["name"] == "Electrician")
        assert {"id", "name", "description", "base_price", "status"} <= set(electrician)
        assert electrician["status"] == "ACTIVE"


class TestServiceDetail:
    def test_get_service_by_id(self, client):
        services = client.get("/services").json()
        sid = next(s["id"] for s in services if s["name"] == "Plumber")
        response = client.get(f"/services/{sid}")
        assert response.status_code == 200
        assert response.json()["name"] == "Plumber"

    def test_invalid_service_id_404(self, client):
        response = client.get("/services/99999")
        assert response.status_code == 404

    def test_inactive_service_hidden_from_list_but_fetchable(self, client, admin_token):
        created = client.post(
            "/admin/services",
            headers=token_headers(admin_token),
            json={"name": "Hidden Service", "description": "temp", "base_price": 100},
        ).json()
        headers = token_headers(admin_token)
        client.put(f"/admin/services/{created['id']}", headers=headers, json={"status": "INACTIVE"})

        listed = client.get("/services").json()
        assert "Hidden Service" not in {s["name"] for s in listed}

        detail = client.get(f"/services/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "INACTIVE"


class TestAdminServiceManagement:
    def test_admin_creates_service_201(self, client, admin_token):
        response = client.post(
            "/admin/services",
            headers=token_headers(admin_token),
            json={"name": "Gardening", "description": "Garden maintenance", "base_price": 500},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Gardening"
        assert body["status"] == "ACTIVE"

    def test_duplicate_service_name_409(self, client, admin_token):
        headers = token_headers(admin_token)
        client.post(
            "/admin/services", headers=headers,
            json={"name": "DuplicateSvc", "description": "", "base_price": 10},
        )
        response = client.post(
            "/admin/services", headers=headers,
            json={"name": "DuplicateSvc", "description": "", "base_price": 10},
        )
        assert response.status_code == 409

    def test_customer_cannot_create_service_403(self, client):
        register_customer(client, email="svc.customer@example.com")
        token = login(client, "svc.customer@example.com")["access_token"]
        response = client.post(
            "/admin/services",
            headers=token_headers(token),
            json={"name": "Nope", "description": "", "base_price": 10},
        )
        assert response.status_code == 403

    def test_expert_cannot_create_service_403(self, client):
        register_expert(client, email="svc.expert@example.com")
        token = login(client, "svc.expert@example.com")["access_token"]
        response = client.post(
            "/admin/services",
            headers=token_headers(token),
            json={"name": "Nope2", "description": "", "base_price": 10},
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_create_service_401(self, client):
        response = client.post(
            "/admin/services", json={"name": "Nope3", "description": "", "base_price": 10}
        )
        assert response.status_code == 401

    def test_admin_updates_service(self, client, admin_token):
        headers = token_headers(admin_token)
        created = client.post(
            "/admin/services", headers=headers,
            json={"name": "Updatable Svc", "description": "before", "base_price": 100},
        ).json()
        response = client.put(
            f"/admin/services/{created['id']}",
            headers=headers,
            json={"description": "after", "base_price": 150, "status": "INACTIVE"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["description"] == "after"
        assert float(body["base_price"]) == 150.0
        assert body["status"] == "INACTIVE"
        assert body["id"] == created["id"]  # id never changes

    def test_update_missing_service_404(self, client, admin_token):
        response = client.put(
            "/admin/services/99999",
            headers=token_headers(admin_token),
            json={"description": "x"},
        )
        assert response.status_code == 404
