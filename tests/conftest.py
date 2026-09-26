"""Test wiring: separate test DATABASE + fresh tables before every test.

Why a separate database? Tests TRUNCATE everything. Run them against your
dev DB and you'd wipe your demo data. Isolation = you can run tests
anytime without fear.

Why drop/create tables per test? Total isolation — test A can never make
test B pass or fail. Our schema is tiny so this costs milliseconds.
(Bigger projects use alembic + truncation for speed; same idea.)
"""
import os

# MUST be set before any `app.*` import: pydantic-settings gives OS env
# vars priority over .env, so the whole app (engine included) binds to
# the TEST database, never your real one.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://eve:eve_secret@localhost:5433/eve_healthcare_test"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

ADMIN_URL = "postgresql+psycopg://eve:eve_secret@localhost:5433/postgres"
TEST_URL = os.environ["DATABASE_URL"]

# 1. Create the test database if it doesn't exist yet (idempotent).
admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
with admin_engine.connect() as conn:
    exists = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = 'eve_healthcare_test'")
    ).scalar()
    if not exists:
        conn.execute(text("CREATE DATABASE eve_healthcare_test"))
admin_engine.dispose()

# 2. Separate engine for tests (NullPool: no lingering pooled connections).
engine = create_engine(TEST_URL)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    """Drop-in replacement for app's get_db — same contract, test engine."""
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


# Dependency override: FastAPI routes get_test sessions instead of real ones.
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def fresh_db():
    """Empty, fully-built schema before EVERY test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client(fresh_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user(client):
    """Registered user + auth header (exercises signup AND login)."""
    client.post(
        "/auth/signup",
        json={"email": "test@x.com", "full_name": "Tester", "password": "password123"},
    )
    token = client.post(
        "/auth/login",
        json={"email": "test@x.com", "password": "password123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def catalog(client, user):
    """A centre offering CBC at ₹500 → ids needed by booking tests."""
    centre = client.post(
        "/centres", json={"name": "Lab X", "location": "Delhi"}, headers=user
    ).json()
    test = client.post(
        "/centres/tests", json={"name": "CBC", "description": "blood"}, headers=user
    ).json()
    offer = client.post(
        f"/centres/{centre['id']}/tests",
        json={"test_id": test["id"], "price": 500},
        headers=user,
    ).json()
    return {"centre_id": centre["id"], "test_id": test["id"], "offer_id": offer["id"]}


@pytest.fixture()
def booking(client, user, catalog):
    """One PENDING booking for the catalog fixture."""
    r = client.post(
        "/bookings",
        json={
            "centre_test_id": catalog["offer_id"],
            "appointment_datetime": "2027-06-01T10:00:00Z",
        },
        headers=user,
    )
    assert r.status_code == 201, r.text
    return r.json()
