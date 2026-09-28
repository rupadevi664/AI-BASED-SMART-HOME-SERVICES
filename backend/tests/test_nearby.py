"""Phase 2 tests: Haversine utility + GET /experts/nearby behavior."""
import math

import pytest

from app.utils.geo import EARTH_RADIUS_KM, calculate_distance
from tests.conftest import (
    login,
    make_admin,
    register_customer,
    register_expert,
    set_active,
    token_headers,
)

ADMIN_EMAIL = "admin.nearby@example.com"

# Hyderabad coordinates for the scenario.
CUSTOMER_LAT, CUSTOMER_LON = 17.3850, 78.4867
# ~3.3 km north of the customer (0.03° latitude ≈ 3.33 km).
NEAR_LAT, NEAR_LON = 17.4150, 78.4867
# ~18 km away (well beyond the 10 km default radius).
FAR_LAT, FAR_LON = 17.5450, 78.6000


class TestHaversine:
    def test_zero_distance(self):
        assert calculate_distance(17.3850, 78.4867, 17.3850, 78.4867) == 0.0

    def test_known_distance_hyderabad_to_bengaluru(self):
        # Hyderabad ↔ Bengaluru is roughly 500-510 km by great circle.
        d = calculate_distance(17.3850, 78.4867, 12.9716, 77.5946)
        assert 495 < d < 520

    def test_one_degree_latitude_is_about_111km(self):
        d = calculate_distance(0.0, 0.0, 1.0, 0.0)
        assert math.isclose(d, EARTH_RADIUS_KM * math.pi / 180, rel_tol=1e-6)

    def test_symmetry(self):
        d1 = calculate_distance(10.0, 20.0, 30.0, 40.0)
        d2 = calculate_distance(30.0, 40.0, 10.0, 20.0)
        assert math.isclose(d1, d2)

    def test_none_coordinates_raise(self):
        with pytest.raises(ValueError):
            calculate_distance(None, 78.0, 17.0, 78.0)


@pytest.fixture(scope="module")
def admin_token(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


@pytest.fixture(scope="module")
def customer_token(client):
    """Nearby search is for signed-in users; use a customer token in tests."""
    register_customer(client, email="nearby.customer@example.com")
    return login(client, "nearby.customer@example.com")["access_token"]


def _nearby(client, customer_token, **params):
    return client.get(
        "/experts/nearby", params=params, headers=token_headers(customer_token)
    )


def _verify(client, admin_token, email: str) -> int:
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
def scenario(client, admin_token):
    """Two verified Electricians near the customer, plus excluded experts."""
    services = {s["name"]: s["id"] for s in client.get("/services").json()}
    electrician, plumber = services["Electrician"], services["Plumber"]

    register_expert(
        client, email="near.electrician@example.com",
        latitude=NEAR_LAT, longitude=NEAR_LON, service_ids=[electrician],
    )
    near_id = _verify(client, admin_token, "near.electrician@example.com")

    register_expert(
        client, email="far.electrician@example.com",
        latitude=FAR_LAT, longitude=FAR_LON, service_ids=[electrician],
    )
    far_id = _verify(client, admin_token, "far.electrician@example.com")

    register_expert(
        client, email="near.plumber@example.com",
        latitude=NEAR_LAT, longitude=NEAR_LON, service_ids=[plumber],
    )
    _verify(client, admin_token, "near.plumber@example.com")

    # Unverified electrician near the customer (must never appear).
    register_expert(
        client, email="unverified.electrician@example.com",
        latitude=NEAR_LAT, longitude=NEAR_LON, service_ids=[electrician],
    )
    unverified_id = _expert_id(client, admin_token, "unverified.electrician@example.com")

    # Verified electrician with no coordinates (must never appear).
    register_expert(
        client, email="nocoords.electrician@example.com", service_ids=[electrician],
    )
    nocoords_id = _verify(client, admin_token, "nocoords.electrician@example.com")

    return {
        "electrician": electrician,
        "plumber": plumber,
        "near_id": near_id,
        "far_id": far_id,
        "unverified_id": unverified_id,
        "nocoords_id": nocoords_id,
    }


def _expert_id(client, admin_token, email: str) -> int:
    experts = client.get("/admin/experts", headers=token_headers(admin_token)).json()
    return next(e for e in experts if e["email"] == email)["id"]


class TestNearbySearch:
    def test_within_radius_only_and_sorted(self, client, customer_token, scenario):
        response = _nearby(
            client, customer_token,
            latitude=CUSTOMER_LAT, longitude=CUSTOMER_LON, radius_km=10,
        )
        assert response.status_code == 200
        body = response.json()
        ids = {e["expert_id"] for e in body}
        assert scenario["near_id"] in ids          # near verified expert found
        assert scenario["far_id"] not in ids       # beyond radius
        assert scenario["unverified_id"] not in ids  # not VERIFIED
        assert scenario["nocoords_id"] not in ids    # no coordinates
        assert all(e["distance_km"] <= 10 for e in body)
        distances = [e["distance_km"] for e in body]
        assert distances == sorted(distances)      # nearest first

    def test_response_shape_and_no_secrets(self, client, customer_token, scenario):
        body = _nearby(
            client, customer_token,
            latitude=CUSTOMER_LAT, longitude=CUSTOMER_LON, radius_km=10,
        ).json()
        assert body
        first = body[0]
        assert {"expert_id", "user_id", "name", "skills", "experience_years",
                "location", "latitude", "longitude", "availability",
                "verification_status", "distance_km", "services"} <= set(first)
        assert first["verification_status"] == "VERIFIED"
        assert "password_hash" not in first
        assert "password" not in first

    def test_distance_matches_haversine(self, client, customer_token, scenario):
        body = _nearby(
            client, customer_token,
            latitude=CUSTOMER_LAT, longitude=CUSTOMER_LON, radius_km=10,
        ).json()
        target = next(e for e in body if e["expert_id"] == scenario["near_id"])
        expected = calculate_distance(CUSTOMER_LAT, CUSTOMER_LON, NEAR_LAT, NEAR_LON)
        assert abs(target["distance_km"] - round(expected, 2)) < 0.01

    def test_service_filter(self, client, customer_token, scenario):
        body = _nearby(
            client, customer_token,
            latitude=CUSTOMER_LAT, longitude=CUSTOMER_LON,
            radius_km=10, service_id=scenario["electrician"],
        ).json()
        assert body, "expected at least one nearby electrician"
        for expert in body:
            assert any(s["id"] == scenario["electrician"] for s in expert["services"])

    def test_plumber_filter_excludes_electricians(self, client, customer_token, scenario):
        body = _nearby(
            client, customer_token,
            latitude=CUSTOMER_LAT, longitude=CUSTOMER_LON,
            radius_km=10, service_id=scenario["plumber"],
        ).json()
        for expert in body:
            names = {s["name"] for s in expert["services"]}
            assert "Electrician" not in names

    def test_no_experts_within_radius_returns_empty_200(self, client, customer_token, scenario):
        # Middle of the Indian Ocean — nothing within 5 km.
        response = _nearby(
            client, customer_token, latitude=-20.0, longitude=70.0, radius_km=5
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_invalid_latitude_422(self, client, customer_token):
        for bad in (-90.5, 91.0):
            response = _nearby(
                client, customer_token, latitude=bad, longitude=78.0, radius_km=10
            )
            assert response.status_code == 422

    def test_invalid_longitude_422(self, client, customer_token):
        for bad in (-180.5, 181.0):
            response = _nearby(
                client, customer_token, latitude=17.0, longitude=bad, radius_km=10
            )
            assert response.status_code == 422

    def test_invalid_radius_422(self, client, customer_token):
        for bad in (0.0, -5.0, 100.5):
            response = _nearby(
                client, customer_token, latitude=17.0, longitude=78.0, radius_km=bad
            )
            assert response.status_code == 422

    def test_unknown_service_id_404(self, client, customer_token):
        response = _nearby(
            client, customer_token,
            latitude=17.0, longitude=78.0, radius_km=10, service_id=424242,
        )
        assert response.status_code == 404

    def test_missing_jwt_401(self, client):
        response = client.get(
            "/experts/nearby",
            params={"latitude": 17.0, "longitude": 78.0, "radius_km": 10},
        )
        assert response.status_code == 401

    def test_invalid_jwt_401(self, client):
        response = client.get(
            "/experts/nearby",
            headers={"Authorization": "Bearer bad.token.value"},
            params={"latitude": 17.0, "longitude": 78.0, "radius_km": 10},
        )
        assert response.status_code == 401

    def test_inactive_verified_expert_excluded(self, client, customer_token, scenario):
        set_active("near.plumber@example.com", False)
        body = _nearby(
            client, customer_token,
            latitude=CUSTOMER_LAT, longitude=CUSTOMER_LON,
            radius_km=10, service_id=scenario["plumber"],
        ).json()
        assert body == []
        set_active("near.plumber@example.com", True)
