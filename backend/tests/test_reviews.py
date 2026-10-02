"""Phase 6 tests: reviews & ratings.

Covers: role/ownership/COMPLETED gates, one-review-per-booking, 1-5 bounds
(422), average-rating aggregates on the expert and the public expert endpoint.
"""
from datetime import date, timedelta

import pytest

from app.core.database import SessionLocal
from app.models import ExpertProfile
from tests.conftest import login, make_admin, register_customer, register_expert, token_headers

ADMIN_EMAIL = "admin.review@example.com"
FUTURE_DATE = (date.today() + timedelta(days=7)).isoformat()


def _admin_token(client):
    make_admin(email=ADMIN_EMAIL)
    return login(client, ADMIN_EMAIL)["access_token"]


def _verify_expert(client, admin_token, email):
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
def admin_token(client):
    return _admin_token(client)


@pytest.fixture(scope="module")
def world(client, admin_token):
    """Customer + verified expert with bookings in the needed states."""
    services = client.get("/services").json()
    electrician = next(s["id"] for s in services if s["name"] == "Electrician")

    register_expert(
        client, email="rev.expert@example.com",
        latitude=17.44, longitude=78.39, service_ids=[electrician],
    )
    expert_profile_id = _verify_expert(client, admin_token, "rev.expert@example.com")
    expert_token = login(client, "rev.expert@example.com")["access_token"]

    register_customer(client, email="rev.customer@example.com")
    customer_token = login(client, "rev.customer@example.com")["access_token"]
    register_customer(client, email="rev.other.customer@example.com")
    other_customer_token = login(client, "rev.other.customer@example.com")["access_token"]

    def _make_booking(time_str, complete=False):
        response = client.post(
            "/bookings",
            headers=token_headers(customer_token),
            json={
                "expert_id": expert_profile_id,
                "service_id": electrician,
                "service_address": "Madhapur, Hyderabad",
                "scheduled_date": FUTURE_DATE,
                "scheduled_time": time_str,
            },
        )
        assert response.status_code == 201, response.text
        booking = response.json()
        if complete:
            assert (
                client.put(
                    f"/experts/bookings/{booking['id']}/accept",
                    headers=token_headers(expert_token),
                ).status_code
                == 200
            )
            assert (
                client.put(
                    f"/experts/bookings/{booking['id']}/complete",
                    headers=token_headers(expert_token),
                ).status_code
                == 200
            )
        return booking

    completed = _make_booking("10:00:00", complete=True)
    completed2 = _make_booking("11:00:00", complete=True)
    accepted_only = _make_booking("12:00:00", complete=False)
    client.put(
        f"/experts/bookings/{accepted_only['id']}/accept",
        headers=token_headers(expert_token),
    )

    return {
        "electrician": electrician,
        "expert_profile_id": expert_profile_id,
        "expert_token": expert_token,
        "customer_token": customer_token,
        "other_customer_token": other_customer_token,
        "completed_id": completed["id"],
        "completed2_id": completed2["id"],
        "accepted_id": accepted_only["id"],
    }


def _review_payload(booking_id, rating=5, comment="Great service"):
    return {"booking_id": booking_id, "rating": rating, "comment": comment}


class TestCreateReview:
    def test_requires_auth(self, client, world):
        assert client.post("/reviews", json=_review_payload(world["completed_id"])).status_code == 401

    def test_expert_role_rejected(self, client, world):
        response = client.post(
            "/reviews",
            headers=token_headers(world["expert_token"]),
            json=_review_payload(world["completed_id"]),
        )
        assert response.status_code == 403
        assert response.json()["detail"]["error"]["code"] == "INVALID_ROLE"

    def test_missing_booking_404(self, client, world):
        response = client.post(
            "/reviews",
            headers=token_headers(world["customer_token"]),
            json=_review_payload(999999),
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "BOOKING_NOT_FOUND"

    def test_other_customer_403(self, client, world):
        response = client.post(
            "/reviews",
            headers=token_headers(world["other_customer_token"]),
            json=_review_payload(world["completed_id"]),
        )
        assert response.status_code == 403

    def test_not_completed_400(self, client, world):
        response = client.post(
            "/reviews",
            headers=token_headers(world["customer_token"]),
            json=_review_payload(world["accepted_id"]),
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "BOOKING_NOT_COMPLETED"

    @pytest.mark.parametrize("rating", [0, 6, -1, 99])
    def test_rating_out_of_bounds_422(self, client, world, rating):
        response = client.post(
            "/reviews",
            headers=token_headers(world["customer_token"]),
            json=_review_payload(world["completed2_id"], rating=rating),
        )
        assert response.status_code == 422

    def test_happy_path_creates_review_and_updates_expert(self, client, world):
        response = client.post(
            "/reviews",
            headers=token_headers(world["customer_token"]),
            json=_review_payload(world["completed_id"], rating=5, comment="Excellent work"),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["booking_id"] == world["completed_id"]
        assert body["rating"] == 5
        assert body["customer"]["name"] == "Test Customer"
        assert body["expert_id"] == world["expert_profile_id"]

        # Expert aggregate updated.
        with SessionLocal() as db:
            expert = db.get(ExpertProfile, world["expert_profile_id"])
            assert float(expert.rating_avg) == 5.0
            assert expert.rating_count == 1

    def test_duplicate_review_409(self, client, world):
        response = client.post(
            "/reviews",
            headers=token_headers(world["customer_token"]),
            json=_review_payload(world["completed_id"], rating=4),
        )
        assert response.status_code == 409
        assert response.json()["detail"]["error"]["code"] == "REVIEW_ALREADY_EXISTS"


class TestExpertReviews:
    def test_public_endpoint_no_auth_required(self, client, world):
        response = client.get(f"/reviews/expert/{world['expert_profile_id']}")
        assert response.status_code == 200
        body = response.json()
        assert body["total_reviews"] == 1
        assert body["average_rating"] == pytest.approx(5.0)
        assert len(body["reviews"]) == 1
        assert body["reviews"][0]["comment"] == "Excellent work"

    def test_unknown_expert_returns_empty(self, client):
        response = client.get("/reviews/expert/999999")
        assert response.status_code == 200
        body = response.json()
        assert body["total_reviews"] == 0
        assert body["average_rating"] is None
        assert body["reviews"] == []

    def test_average_rounds_to_two_decimals(self, client, world):
        # A second completed booking + review of 4 → avg 4.5.
        services = client.get("/services").json()
        electrician = next(s["id"] for s in services if s["name"] == "Electrician")
        other_token = login(client, "rev.customer@example.com")["access_token"]
        # Make another completed booking at a free slot.
        resp = client.post(
            "/bookings",
            headers=token_headers(other_token),
            json={
                "expert_id": world["expert_profile_id"],
                "service_id": electrician,
                "service_address": "Madhapur, Hyderabad",
                "scheduled_date": (date.today() + timedelta(days=8)).isoformat(),
                "scheduled_time": "13:00:00",
            },
        )
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        expert_token = login(client, "rev.expert@example.com")["access_token"]
        client.put(f"/experts/bookings/{booking['id']}/accept", headers=token_headers(expert_token))
        client.put(f"/experts/bookings/{booking['id']}/complete", headers=token_headers(expert_token))
        resp = client.post(
            "/reviews",
            headers=token_headers(other_token),
            json=_review_payload(booking["id"], rating=4, comment="Very good"),
        )
        assert resp.status_code == 201, resp.text

        body = client.get(f"/reviews/expert/{world['expert_profile_id']}").json()
        assert body["total_reviews"] == 2
        assert body["average_rating"] == pytest.approx(4.5)


class TestBookingReview:
    def test_booking_review_lookup(self, client, world):
        response = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 200
        assert response.json()["booking_id"] == world["completed_id"]

    def test_booking_review_404_when_none(self, client, world):
        response = client.get(
            f"/reviews/booking/{world['completed2_id']}",
            headers=token_headers(world["customer_token"]),
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "REVIEW_NOT_FOUND"

    def test_booking_review_denied_for_other_customer(self, client, world):
        response = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["other_customer_token"]),
        )
        assert response.status_code == 403


class TestUpdateDelete:
    def test_update_rating_and_comment(self, client, world):
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        response = client.put(
            f"/reviews/{review['id']}",
            headers=token_headers(world["customer_token"]),
            json={"rating": 3, "comment": "It was okay"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rating"] == 3
        assert body["comment"] == "It was okay"

        # Aggregate followed the edit.
        body = client.get(f"/reviews/expert/{world['expert_profile_id']}").json()
        assert body["average_rating"] == pytest.approx(3.5)  # (3 + 4) / 2

    def test_update_out_of_bounds_422(self, client, world):
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        response = client.put(
            f"/reviews/{review['id']}",
            headers=token_headers(world["customer_token"]),
            json={"rating": 7},
        )
        assert response.status_code == 422

    def test_other_customer_cannot_update(self, client, world):
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        response = client.put(
            f"/reviews/{review['id']}",
            headers=token_headers(world["other_customer_token"]),
            json={"rating": 1},
        )
        assert response.status_code == 403

    def test_expert_cannot_delete_others_review(self, client, world):
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        response = client.delete(
            f"/reviews/{review['id']}", headers=token_headers(world["expert_token"])
        )
        assert response.status_code == 403

    def test_delete_by_owner_and_recount(self, client, world):
        # Delete the second review (rating 4) → one review left (rating 3).
        second = client.get(
            f"/reviews/booking/{world['completed2_id']}",
            headers=token_headers(world["customer_token"]),
        )
        assert second.status_code == 404  # never reviewed completed2 yet
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        response = client.delete(
            f"/reviews/{review['id']}", headers=token_headers(world["customer_token"])
        )
        assert response.status_code == 204

        body = client.get(f"/reviews/expert/{world['expert_profile_id']}").json()
        assert body["total_reviews"] == 1  # the rating-4 review remains
        assert body["average_rating"] == pytest.approx(4.0)

        # Expert aggregate column in DB is consistent too.
        with SessionLocal() as db:
            expert = db.get(ExpertProfile, world["expert_profile_id"])
            assert expert.rating_count == 1

    def test_admin_can_delete_any_review(self, client, world, admin_token):
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        # Re-create a review first (the owner deleted the earlier one).
        client.post(
            "/reviews",
            headers=token_headers(world["customer_token"]),
            json=_review_payload(world["completed_id"], rating=5, comment="Round two"),
        )
        review = client.get(
            f"/reviews/booking/{world['completed_id']}",
            headers=token_headers(world["customer_token"]),
        ).json()
        response = client.delete(f"/reviews/{review['id']}", headers=token_headers(admin_token))
        assert response.status_code == 204
