"""UI Confirm / Dismiss for proposed actions. No LLM."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.watches import list_watches
from backend.tools.watches import create_watch
from tests.conftest import parse_tool


def _client(db, monkeypatch):
    monkeypatch.setattr("backend.main.init_db", lambda *args, **kwargs: db)
    return TestClient(app)


def test_ui_confirm_creates_watch(db, clean_state, monkeypatch):
    proposed = parse_tool(
        create_watch.invoke(
            {
                "order_id": "ORD-005",
                "check_date": "2026-04-02",
                "confirmed": False,
            }
        )
    )
    action = proposed["data"]["proposed_action"]
    with _client(db, monkeypatch) as client:
        res = client.post("/api/actions/confirm", json={"action": action})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["type"] == "create_watch"
    rows = list_watches()
    assert len(rows) == 1
    assert rows[0]["status"] == "ACTIVE"
    assert rows[0]["order_id"] == "ORD-005"


def test_ui_dismiss_does_not_create_watch(db, clean_state, monkeypatch):
    proposed = parse_tool(
        create_watch.invoke(
            {
                "order_id": "ORD-005",
                "check_date": "2026-04-02",
                "confirmed": False,
            }
        )
    )
    action = proposed["data"]["proposed_action"]
    with _client(db, monkeypatch) as client:
        res = client.post("/api/actions/decline", json={"action": action})
    assert res.status_code == 200
    assert res.json()["declined"] is True
    assert list_watches() == []


def test_ui_confirm_rejects_unknown_type(db, clean_state, monkeypatch):
    with _client(db, monkeypatch) as client:
        res = client.post(
            "/api/actions/confirm",
            json={"action": {"type": "run_sql", "order_id": "ORD-005"}},
        )
    assert res.status_code == 400
    assert list_watches() == []


def test_ui_confirm_cancel_watch(db, clean_state, monkeypatch):
    parse_tool(
        create_watch.invoke(
            {
                "order_id": "ORD-005",
                "check_date": "2026-04-02",
                "confirmed": True,
            }
        )
    )
    from backend.tools.watches import cancel_watch

    proposed = parse_tool(cancel_watch.invoke({"order_id": "ORD-005", "confirmed": False}))
    action = proposed["data"]["proposed_action"]
    with _client(db, monkeypatch) as client:
        res = client.post("/api/actions/confirm", json={"action": action})
    assert res.status_code == 200
    assert list_watches()[0]["status"] == "CANCELLED"
