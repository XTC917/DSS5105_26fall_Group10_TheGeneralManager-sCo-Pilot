"""Shared fixtures for the PostgreSQL Phase 1 backend.

The session `db` fixture requires a live PostgreSQL baseline
(`alembic upgrade head` plus seed data). Tests that do not need a database
must not request this fixture.
"""

from __future__ import annotations

import json
import os

import pytest

TEST_AUTH_SECRET = "test-auth-secret-key-with-at-least-32-chars"

os.environ.setdefault("AUTH_SECRET_KEY", TEST_AUTH_SECRET)

from backend.services.database import get_db, init_db
from backend.services.request_context import set_current_user


@pytest.fixture(scope="session")
def db():
    init_db()
    return get_db()


@pytest.fixture
def clean_state(db):
    from backend.services.audit import clear_state

    clear_state()
    yield
    clear_state()
    set_current_user(None)


@pytest.fixture
def test_user():
    """Authenticated identity for copilot state tests (satisfies NOT NULL user_id)."""
    from backend.services.auth import CurrentUser

    user = CurrentUser(id=2, username="test_employee", email=None, role="EMPLOYEE", status="ACTIVE")
    set_current_user(user)
    yield user
    set_current_user(None)


def _auth_headers(user_id: int, role: str) -> dict[str, str]:
    import jwt

    token = jwt.encode({"sub": str(user_id), "role": role}, TEST_AUTH_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(monkeypatch):
    """Bearer headers for admin-protected HTTP endpoints."""
    monkeypatch.setenv("AUTH_SECRET_KEY", TEST_AUTH_SECRET)
    return _auth_headers(1, "ADMIN")


@pytest.fixture
def employee_auth_headers(monkeypatch):
    """Bearer headers matching the test_user identity."""
    monkeypatch.setenv("AUTH_SECRET_KEY", TEST_AUTH_SECRET)
    return _auth_headers(2, "EMPLOYEE")


def parse_tool(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data
