from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import email
from backend.services.auth import CurrentUser, get_current_user
from backend.services.conversation_history import create_conversation, delete_conversation, save_turn
from backend.services.pg_database import connect


@pytest.fixture
def email_client(monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")
    monkeypatch.setenv("EMAIL_TEST_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(email.router)
    user = CurrentUser(id=1, username="test_admin", email=None, role="ADMIN", status="ACTIVE")
    app.dependency_overrides[get_current_user] = lambda: user
    conversation_id = create_conversation(user.id)["id"]
    turn = save_turn(
        user.id, conversation_id, question="Draft an email for ORD-005", answer="Draft prepared.",
        response_json={"email_drafts": [
            {"order_id": "ORD-005", "subject": "Order update", "body": "Draft body",
             "language": "en", "audience": "customer"}
        ]},
    )
    path = f"/api/email/turns/{turn['id']}/drafts/0"
    try:
        with TestClient(app) as client:
            yield client, path
    finally:
        with connect(admin=True) as conn:
            conn.execute(
                """DELETE FROM copilot.email_send_attempts
                   WHERE draft_id IN (SELECT id FROM copilot.email_drafts WHERE conversation_id = %s)""",
                (conversation_id,),
            )
            conn.execute("DELETE FROM copilot.email_drafts WHERE conversation_id = %s", (conversation_id,))
        delete_conversation(user.id, conversation_id)


def _save(client, path, version=0, body="Reviewed body", recipient="recipient@example.com"):
    result = client.put(path, json={
        "version": version, "recipient_email": recipient, "subject": "Order update", "body": body,
    })
    assert result.status_code == 200, result.text
    return result.json()


def _send(client, draft):
    return client.post(f"/api/email/drafts/{draft['id']}/send", json={
        "version": draft["version"], "content_hash": draft["content_hash"],
    })


def test_only_confirmed_current_version_can_send_once(email_client, monkeypatch):
    client, path = email_client
    calls = []

    def provider(url, **kwargs):
        calls.append(kwargs)
        assert url == "https://api.resend.com/emails"
        return httpx.Response(200, json={"id": "mock-submitted"})

    monkeypatch.setattr(email.httpx, "post", provider)
    assert client.get(path).json()["version"] == 0
    first = _save(client, path)
    current = _save(client, path, version=first["version"], body="Latest body")
    assert client.get(path).json() == current
    assert _send(client, first).status_code == 409
    assert calls == []

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _send(client, current), range(2)))
    assert all(result.status_code == 200 for result in results)
    assert {result.json()["status"] for result in results} <= {"SENDING", "SUBMITTED"}
    assert _send(client, current).json()["status"] == "SUBMITTED"
    assert len(calls) == 1
    assert calls[0]["json"]["text"] == "Latest body"
    with connect(admin=True) as conn:
        attempt = conn.execute(
            """SELECT confirmed_by, payload_snapshot, idempotency_key, request_count, status
               FROM copilot.email_send_attempts WHERE draft_id = %s""",
            (UUID(current["id"]),),
        ).fetchone()
    assert attempt["confirmed_by"] == 1
    assert attempt["status"] == "SUBMITTED"
    assert attempt["request_count"] == 1
    assert attempt["payload_snapshot"] == calls[0]["json"]
    assert attempt["idempotency_key"] == calls[0]["headers"]["Idempotency-Key"]


def test_other_user_and_non_test_recipient_are_rejected(email_client, monkeypatch):
    client, path = email_client
    draft = _save(client, path, recipient="outside@example.com")
    monkeypatch.setattr(email.httpx, "post", lambda *a, **kw: pytest.fail("Unexpected provider call"))
    assert not draft["can_send"]
    assert _send(client, draft).status_code == 422
    client.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=2, username="test_employee", email=None, role="EMPLOYEE", status="ACTIVE"
    )
    assert client.get(path).status_code == 404
    assert _send(client, draft).status_code == 404


@pytest.mark.parametrize(("provider_code", "expected"), [(403, "FAILED"), (None, "UNKNOWN")])
def test_provider_rejection_or_timeout_is_recorded_without_resend(email_client, monkeypatch, provider_code, expected):
    client, path = email_client
    draft = _save(client, path)
    calls = []

    def provider(*args, **kwargs):
        calls.append(kwargs)
        if provider_code is None:
            raise httpx.ReadTimeout("mock timeout")
        return httpx.Response(provider_code)

    monkeypatch.setattr(email.httpx, "post", provider)
    assert _send(client, draft).json()["status"] == expected
    assert _send(client, draft).json()["status"] == expected
    assert len(calls) == 1
