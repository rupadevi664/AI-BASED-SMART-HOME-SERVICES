"""Phase 1 automated tests: registration, login, JWT, /auth/me, error cases."""
from app.core.config import settings
from app.models.user import UserRole
from tests.conftest import (
    PASSWORD,
    login,
    register_customer,
    register_expert,
    set_active,
    token_headers,
)

ADMIN_EMAIL = "admin@example.com"


# --- 1. Customer registration ------------------------------------------------


class TestCustomerRegistration:
    def test_register_customer_returns_201_and_safe_payload(self, client):
        body = register_customer(client, email="new.customer@example.com")
        assert body["name"] == "Test Customer"
        assert body["email"] == "new.customer@example.com"
        assert body["phone"] == "9999999999"
        assert body["role"] == UserRole.CUSTOMER.value
        assert body["is_active"] is True
        assert "id" in body and "created_at" in body
        # Plain password and hash must never appear in the response.
        raw = str(body)
        assert "password" not in raw
        assert "$2b$" not in raw

    def test_register_customer_duplicate_email_409(self, client):
        register_customer(client, email="dup.customer@example.com")
        response = client.post(
            "/auth/register",
            json={
                "name": "Second Customer",
                "email": "dup.customer@example.com",
                "phone": "9999999999",
                "password": "password123",
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_register_customer_invalid_payload_422(self, client):
        response = client.post(
            "/auth/register",
            json={"name": "X", "email": "not-an-email", "phone": "1", "password": "short"},
        )
        assert response.status_code == 422


# --- 2. Expert registration ---------------------------------------------------


class TestExpertRegistration:
    def test_register_expert_returns_201_with_profile(self, client):
        body = register_expert(client, email="new.expert@example.com")
        assert body["user"]["role"] == UserRole.EXPERT.value
        profile = body["expert_profile"]
        assert profile["skills"] == "wiring, fans, inverters"
        assert profile["experience_years"] == 5  # as entered by the expert
        assert profile["location"] == "Indiranagar, Bengaluru"
        assert profile["verification_status"] == "PENDING"
        assert profile["availability"] == "AVAILABLE"
        assert "$2b$" not in str(body)

    def test_register_expert_duplicate_email_409(self, client):
        register_expert(client, email="dup.expert@example.com")
        response = client.post(
            "/auth/register-expert",
            json={
                "name": "Second Expert",
                "email": "dup.expert@example.com",
                "phone": "8888888888",
                "password": "password123",
                "skills": "plumbing",
                "experience_years": 3,
                "location": "HSR Layout, Bengaluru",
                "availability": "AVAILABLE",
            },
        )
        assert response.status_code == 409

    def test_register_expert_negative_experience_422(self, client):
        response = client.post(
            "/auth/register-expert",
            json={
                "name": "Bad Expert",
                "email": "bad.expert@example.com",
                "phone": "8888888888",
                "password": "password123",
                "skills": "painting",
                "experience_years": -2,
                "location": "Koramangala, Bengaluru",
                "availability": "AVAILABLE",
            },
        )
        assert response.status_code == 422

    def test_expert_cannot_override_role_in_payload(self, client):
        """A client sending role=ADMIN is ignored — role is forced server-side."""
        response = client.post(
            "/auth/register",
            json={
                "name": "Role Sneak",
                "email": "sneak@example.com",
                "phone": "9999999999",
                "password": "password123",
                "role": "ADMIN",
            },
        )
        assert response.status_code == 201
        assert response.json()["role"] == UserRole.CUSTOMER.value


# --- 3. Login ------------------------------------------------------------------


class TestLogin:
    def test_login_success_returns_bearer_token(self, client):
        register_customer(client, email="login.customer@example.com")
        body = login(client, "login.customer@example.com")
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20

    def test_login_wrong_password_401_generic_message(self, client):
        register_customer(client, email="login2.customer@example.com")
        response = client.post(
            "/auth/login",
            json={"email": "login2.customer@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_login_unknown_email_401_generic_message(self, client):
        response = client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "whatever123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_login_inactive_user_403(self, client):
        register_customer(client, email="inactive.customer@example.com")
        set_active("inactive.customer@example.com", False)
        response = client.post(
            "/auth/login",
            json={"email": "inactive.customer@example.com", "password": PASSWORD},
        )
        assert response.status_code == 403


# --- 4. GET /auth/me -------------------------------------------------------------


class TestMe:
    def test_me_customer(self, client):
        register_customer(client, email="me.customer@example.com")
        token = login(client, "me.customer@example.com")["access_token"]
        response = client.get("/auth/me", headers=token_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "me.customer@example.com"
        assert body["role"] == UserRole.CUSTOMER.value
        assert "password" not in str(body).lower()
        assert body["expert_profile"] is None

    def test_me_expert_includes_profile_fields(self, client):
        register_expert(client, email="me.expert@example.com")
        token = login(client, "me.expert@example.com")["access_token"]
        response = client.get("/auth/me", headers=token_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["role"] == UserRole.EXPERT.value
        profile = body["expert_profile"]
        assert profile is not None
        assert profile["verification_status"] == "PENDING"
        assert profile["experience_years"] == 5


# --- 5. JWT handling ----------------------------------------------------------------


class TestJwt:
    def test_missing_jwt_401(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_invalid_jwt_401(self, client):
        response = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert response.status_code == 401

    def test_tampered_signature_401(self, client):
        register_customer(client, email="jwt.customer@example.com")
        token = login(client, "jwt.customer@example.com")["access_token"]
        # Keep the structure but break the signature.
        header, payload, _signature = token.split(".")
        response = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {header}.{payload}.badsig"}
        )
        assert response.status_code == 401

    def test_expired_jwt_401(self, client):
        register_customer(client, email="expired.customer@example.com")
        expired = create_token_with_expiry(-60)
        response = client.get("/auth/me", headers=token_headers(expired))
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_token_for_missing_user_401(self, client):
        register_customer(client, email="ghostid.customer@example.com")
        token = create_token_with_expiry(60, subject="424242")
        response = client.get("/auth/me", headers=token_headers(token))
        assert response.status_code == 401


def create_token_with_expiry(minutes: int, subject: str = "1") -> str:
    from datetime import datetime, timedelta, timezone

    import jwt as pyjwt

    return pyjwt.encode(
        {
            "sub": subject,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
