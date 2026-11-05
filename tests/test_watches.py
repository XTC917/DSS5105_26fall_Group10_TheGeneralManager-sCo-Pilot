"""Standing watches: propose/confirm, as_of evaluation, idempotent fire. No LLM."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from backend.config import factory_date
from backend.main import app
from backend.services.audit import list_audit
from backend.services.auth import CurrentUser
from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect
from backend.services.request_context import set_current_user
from backend.services.watches import (
    CONDITION_INACTIVE,
    evaluate_active_watches,
    evaluate_and_list,
    list_watch_events,
    list_watches,
    resolve_check_date,
)
from backend.tools.watches import cancel_watch, create_watch, list_watches as list_watches_tool
from tests.conftest import parse_tool


def _create(order_id: str, check_date: str, *, confirmed: bool, message: str = "watch"):
    return parse_tool(
        create_watch.invoke(
            {
                "order_id": order_id,
                "check_date": check_date,
                "condition_type": CONDITION_INACTIVE,
                "message": message,
                "confirmed": confirmed,
            }
        )
    )


def test_thursday_resolves_from_factory_today_not_wall_clock():
    assert resolve_check_date("Thursday") == date(2026, 4, 2)
    assert resolve_check_date("thursday") == date(2026, 4, 2)
    assert resolve_check_date("2026-04-02") == date(2026, 4, 2)


def test_unconfirmed_watch_is_not_persisted(db, clean_state, test_user):
    payload = _create("ORD-005", "Thursday", confirmed=False)
    assert payload["ok"] is True
    assert payload["data"]["saved"] is False
    assert payload["data"]["needs_confirmation"] is True
    assert payload["data"]["check_date"] == "2026-04-02"
    assert list_watches() == []
    assert list_watch_events() == []


def test_confirmed_watch_is_active(db, clean_state, test_user):
    payload = _create("ORD-005", "2026-04-02", confirmed=True)
    assert payload["ok"] is True
    assert payload["data"]["saved"] is True
    assert payload["data"]["status"] == "ACTIVE"
    rows = list_watches()
    assert len(rows) == 1
    assert rows[0]["order_id"] == "ORD-005"
    assert rows[0]["status"] == "ACTIVE"
    assert rows[0]["condition_type"] == CONDITION_INACTIVE
    assert rows[0]["params"]["check_date"] == "2026-04-02"
    assert rows[0]["notify_channel"] == "local"


def test_does_not_fire_before_check_date(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    evaluate_active_watches(date(2026, 4, 1))
    rows = list_watches()
    assert rows[0]["status"] == "ACTIVE"
    assert list_watch_events() == []


def test_fires_on_check_date(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    evaluate_active_watches(date(2026, 4, 2))
    rows = list_watches()
    assert rows[0]["status"] == "FIRED"
    events = list_watch_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "fired"
    assert events[0]["delivery_status"] == "local_recorded"
    snapshot = events[0]["snapshot"]
    assert snapshot["order_id"] == "ORD-005"
    assert snapshot["status"] == "IN_PROGRESS"
    assert snapshot["last_activity_date"] == "2026-03-24"
    assert snapshot["check_date"] == "2026-04-02"
    assert snapshot["as_of"] == "2026-04-02"
    audit = [row for row in list_audit(limit=20) if row["event_type"] == "watch_fired"]
    assert len(audit) == 1
    assert audit[0]["target"] == "ORD-005"
    assert audit[0]["factory_today"] == date(2026, 4, 2)


def test_repeat_evaluate_does_not_refire(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    evaluate_active_watches(date(2026, 4, 2))
    evaluate_active_watches(date(2026, 4, 3))
    assert len(list_watch_events()) == 1
    assert list_watches()[0]["status"] == "FIRED"
    audit = [row for row in list_audit(limit=50) if row["event_type"] == "watch_fired"]
    assert len(audit) == 1


def test_recent_activity_does_not_fire(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)

    def moved(_order_id: str) -> dict:
        return {
            "order_id": "ORD-005",
            "status": "IN_PROGRESS",
            "current_stage": "KNITTING",
            "last_activity_date": "2026-04-02",
        }

    evaluate_active_watches(date(2026, 4, 2), get_order=moved)
    assert list_watches()[0]["status"] == "ACTIVE"
    assert list_watch_events() == []


def test_complete_order_cannot_create_inactive_watch(db, clean_state, test_user):
    payload = _create("ORD-058", "Thursday", confirmed=True)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
    assert list_watches() == []


def test_advance_date_syncs_watch_board_and_briefing(
    clean_state, test_user, employee_auth_headers, admin_auth_headers, monkeypatch,
):
    _create("ORD-005", "2026-04-02", confirmed=True)
    _create("ORD-107", "2026-04-03", confirmed=True)

    def run_agent_on_factory_date(message, conversation_id, **kwargs):
        from backend.agent.prompts import build_system_prompt
        from backend.tools.retrieval import get_order_status

        today = factory_date().isoformat()
        assert f"Factory clock: today is {today}." in build_system_prompt()
        order = parse_tool(get_order_status.invoke({"order_id": "ORD-029"}))["data"]
        return {
            "answer": f"{today}: {order['computed']['calendar_days_until_due']}",
            "conversation_id": conversation_id,
            "tools_used": ["get_order_status"],
        }

    monkeypatch.setattr("backend.main.llm_is_configured", lambda: True)
    monkeypatch.setattr("backend.main.run_agent", run_agent_on_factory_date)
    base = "2026-04-01"
    next_day = "2026-04-02"
    date_path = "/api/factory-date"
    try:
        with TestClient(app) as client:
            def get(path, headers=employee_auth_headers):
                response = client.get(path, headers=headers)
                assert response.status_code == 200, response.text
                return response.json()

            waiting = get("/api/watches?as_of=2026-04-01")
            assert waiting["as_of"] == base
            assert waiting["fired"] == []
            assert {row["order_id"] for row in waiting["active"]} == {"ORD-005", "ORD-107"}
            assert client.get("/api/watches?as_of=2026-04-02", headers=employee_auth_headers).status_code == 409
            before = get("/api/briefing")["dashboard"]["orders"]
            assert next(row for row in before if row["order_id"] == "ORD-029")["bucket"] == "TODAY"
            assert client.post(date_path, json={"factory_date": next_day}).status_code == 401
            assert client.post(
                date_path, headers=employee_auth_headers, json={"factory_date": next_day}
            ).status_code == 403
            chosen = client.post(date_path, headers=admin_auth_headers, json={"factory_date": next_day})
            assert chosen.status_code == 200
            assert chosen.json()["factory_today"] == next_day

            board = get("/api/watches")
            assert board["as_of"] == next_day
            assert [row["order_id"] for row in board["active"]] == ["ORD-107"]
            alert, = board["fired"]
            assert alert["order_id"] == "ORD-005"
            assert alert["fired_as_of"] == next_day
            assert alert["last_activity_date"] == "2026-03-24"
            assert get("/api/watches") == board
            audit = [row for row in get("/api/audit")["items"] if row["event_type"] == "watch_fired"]
            assert [row["factory_today"] for row in audit] == [next_day]

            briefing = get("/api/briefing")
            assert briefing["factory_today"] == get("/api/discovery")["as_of"] == next_day
            overdue = next(row for row in briefing["dashboard"]["orders"] if row["order_id"] == "ORD-029")
            assert overdue["bucket"] == "OVERDUE"
            assert get("/api/health")["factory_today"] == next_day
            assert get("/api/briefing", admin_auth_headers)["factory_today"] == next_day
            assert get("/api/watches", admin_auth_headers)["as_of"] == next_day

            conversation = client.post("/api/conversations", headers=employee_auth_headers).json()
            request = {"message": "How long until ORD-029 is due?", "conversation_id": conversation["id"]}
            chat = client.post("/api/chat", headers=employee_auth_headers, json=request)
            assert chat.status_code == 200, chat.text
            assert chat.json()["answer"] == f"{next_day}: -1"
            stream = client.post("/api/chat/stream", headers=employee_auth_headers, json=request)
            assert stream.status_code == 200
            assert f'"answer": "{next_day}: -1"' in stream.text
    finally:
        with connect(admin=True) as conn:
            conn.execute(f"DELETE FROM {COPILOT_SCHEMA}.factory_clocks")


def test_notifier_failure_does_not_unfire(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)

    class BoomNotifier:
        def notify(self, watch, event):
            raise RuntimeError("smtp down")

    evaluate_active_watches(date(2026, 4, 2), notifier=BoomNotifier())
    assert list_watches()[0]["status"] == "FIRED"
    assert len(list_watch_events()) == 1


def test_evaluate_and_list_shape(db, clean_state, test_user):
    _create("ORD-005", "Thursday", confirmed=True)
    board = evaluate_and_list(date(2026, 4, 2))
    assert set(board) >= {"as_of", "fired", "active"}
    assert board["as_of"] == "2026-04-02"
    assert len(board["fired"]) == 1
    assert board["active"] == []


def _cancel(order_id=None, watch_id=None, *, confirmed: bool):
    payload = {"confirmed": confirmed}
    if order_id is not None:
        payload["order_id"] = order_id
    if watch_id is not None:
        payload["watch_id"] = watch_id
    return parse_tool(cancel_watch.invoke(payload))


def test_unconfirmed_cancel_does_not_change_status(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    payload = _cancel("ORD-005", confirmed=False)
    assert payload["ok"] is True
    assert payload["data"]["cancelled"] is False
    assert payload["data"]["needs_confirmation"] is True
    assert list_watches()[0]["status"] == "ACTIVE"


def test_confirmed_cancel_active_watch_does_not_fire(db, clean_state, test_user):
    created = _create("ORD-005", "2026-04-02", confirmed=True)
    payload = _cancel("ORD-005", confirmed=True)
    assert payload["ok"] is True
    assert payload["data"]["cancelled"] is True
    assert payload["data"]["status"] == "CANCELLED"
    assert payload["data"]["previous_status"] == "ACTIVE"
    assert payload["data"]["watch_id"] == created["data"]["watch_id"]
    evaluate_active_watches(date(2026, 4, 2))
    assert list_watches()[0]["status"] == "CANCELLED"
    assert list_watch_events() == []
    board = evaluate_and_list(date(2026, 4, 2))
    assert board["fired"] == []
    assert board["active"] == []
    assert len(board["cancelled"]) == 1
    assert board["cancelled"][0]["status"] == "CANCELLED"


def test_cancel_fired_watch_leaves_alerts_list(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    evaluate_active_watches(date(2026, 4, 2))
    assert list_watches()[0]["status"] == "FIRED"
    payload = _cancel("ORD-005", confirmed=True)
    assert payload["data"]["previous_status"] == "FIRED"
    assert payload["data"]["status"] == "CANCELLED"
    assert len(list_watch_events()) == 1
    board = evaluate_and_list(date(2026, 4, 2))
    assert board["fired"] == []
    assert board["active"] == []
    assert len(board["cancelled"]) == 1
    assert board["cancelled"][0]["order_id"] == "ORD-005"


def test_cancel_missing_watch_is_not_found(db, clean_state, test_user):
    payload = _cancel("ORD-005", confirmed=True)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_cancel_already_cancelled_is_rejected(db, clean_state, test_user):
    created = _create("ORD-005", "2026-04-02", confirmed=True)
    watch_id = created["data"]["watch_id"]
    _cancel("ORD-005", confirmed=True)
    by_order = _cancel("ORD-005", confirmed=True)
    assert by_order["ok"] is False
    assert by_order["error"]["code"] == "NOT_FOUND"
    by_id = _cancel(watch_id=watch_id, confirmed=True)
    assert by_id["ok"] is False
    assert by_id["error"]["code"] == "INVALID_INPUT"


def test_cancel_ambiguous_when_several_watches(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    _create("ORD-005", "2026-04-03", confirmed=True)
    payload = _cancel("ORD-005", confirmed=True)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "AMBIGUOUS"
    assert len(payload["error"]["candidates"]) == 2
    watch_id = payload["error"]["candidates"][0]["watch_id"]
    picked = _cancel(watch_id=watch_id, confirmed=True)
    assert picked["ok"] is True
    assert picked["data"]["watch_id"] == watch_id
    remaining = [row for row in list_watches() if row["status"] != "CANCELLED"]
    assert len(remaining) == 1


def test_list_watches_tool_keeps_cancelled_for_trace(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    _create("ORD-107", "2026-04-02", confirmed=True)
    listed = parse_tool(list_watches_tool.invoke({"order_id": "ORD-005"}))
    assert listed["ok"] is True
    assert listed["data"]["count"] == 1
    _cancel("ORD-005", confirmed=True)
    after = parse_tool(list_watches_tool.invoke({}))
    by_id = {row["order_id"]: row for row in after["data"]["watches"]}
    assert by_id["ORD-005"]["status"] == "CANCELLED"
    assert by_id["ORD-107"]["status"] == "ACTIVE"
    assert after["data"]["cancelled_count"] == 1
    assert after["data"]["active_count"] == 1


def test_watch_rows_are_isolated_by_authenticated_user(db, clean_state, test_user):
    _create("ORD-005", "2026-04-02", confirmed=True)
    assert len(list_watches()) == 1

    set_current_user(
        CurrentUser(
            id=1,
            username="test_admin",
            email=None,
            role="ADMIN",
            status="ACTIVE",
        )
    )
    assert list_watches() == []
