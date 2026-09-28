"""Pytest configuration: isolated SQLite in-memory database for the whole suite.

The DATABASE_URL env var is set BEFORE any app import so it overrides the
value in backend/.env — tests never touch MySQL or production credentials.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory SQLite

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models import User
from app.models.user import UserRole

CUSTOMER_EMAIL = "customer@example.com"
EXPERT_EMAIL = "expert@example.com"
ADMIN_EMAIL = "admin@example.com"
PASSWORD = "password123"


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create the full schema once per session; drop it at the end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client(database):
    """TestClient wired to the shared in-memory database.

    The app lifespan (table creation + service seeding) runs on enter.
    """
    with TestClient(app) as c:
        yield c


# --- Shared helpers (imported by the test modules) --------------------------


def register_customer(client, email: str = CUSTOMER_EMAIL, **overrides) -> dict:
    payload = {
        "name": overrides.get("name", "Test Customer"),
        "email": email,
        "phone": overrides.get("phone", "9999999999"),
        "password": overrides.get("password", PASSWORD),
    }
    payload.update(overrides.get("extra", {}))
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def register_expert(client, email: str = EXPERT_EMAIL, **overrides) -> dict:
    payload = {
        "name": overrides.get("name", "Test Expert"),
        "email": email,
        "phone": overrides.get("phone", "8888888888"),
        "password": overrides.get("password", PASSWORD),
        "skills": overrides.get("skills", "wiring, fans, inverters"),
        "experience_years": overrides.get("experience_years", 5),
        "location": overrides.get("location", "Indiranagar, Bengaluru"),
        "availability": overrides.get("availability", "AVAILABLE"),
    }
    for key in ("latitude", "longitude", "service_ids"):
        if key in overrides:
            payload[key] = overrides[key]
    payload.update(overrides.get("extra", {}))
    response = client.post("/auth/register-expert", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def login(client, email: str, password: str = PASSWORD) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def token_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_admin(email: str = ADMIN_EMAIL, password: str = PASSWORD) -> int:
    """Create an ADMIN user directly in the test database (idempotent); returns the user id."""
    with SessionLocal() as db:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing is not None:
            return existing.id
        user = User(
            name="Test Admin",
            email=email,
            phone="0000000000",
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def set_active(email: str, active: bool) -> None:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user.is_active = active
        db.commit()
