"""Action tools: drafts, confirmation, local persist. No LLM / SMTP."""

from __future__ import annotations

from backend.services.audit import list_notes, list_reminders
from backend.tools.actions import (
    add_order_note,
    create_reminder,
    draft_chase_email,
    get_recent_actions,
    send_email,
)
from tests.conftest import parse_tool


def test_draft_chase_email_uses_order_fields_and_is_not_sent(db, clean_state):
    payload = parse_tool(draft_chase_email.invoke({"order_id": "ORD-120"}))
    assert payload["ok"] is True
    data = payload["data"]
    assert data["sent"] is False
    assert data["draft"]["order_id"] == "ORD-120"
    assert "TrendCart" in data["draft"]["to"]
    assert "1500" in data["draft"]["body"]
    assert "ORD-120" in data["draft"]["subject"]
    assert "not in orders.csv" in data["draft"]["to"]
    assert any("not" in item.lower() and "sent" in item.lower() for item in data["limitations"])


def test_draft_chase_email_not_found(db, clean_state):
    payload = parse_tool(draft_chase_email.invoke({"order_id": "ORD-999"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_send_email_without_confirmation_is_not_sent(db, clean_state):
    payload = parse_tool(send_email.invoke({"order_id": "ORD-120", "confirmed": False}))
    assert payload["ok"] is True
    assert payload["data"]["sent"] is False
    assert payload["data"]["needs_confirmation"] is True


def test_send_email_confirmed_is_still_simulated(db, clean_state):
    payload = parse_tool(send_email.invoke({"order_id": "ORD-120", "confirmed": True}))
    assert payload["ok"] is True
    assert payload["data"]["sent"] is False
    assert payload["data"]["execution_status"] == "SIMULATED"


def test_add_order_note_requires_confirmation(db, clean_state, test_user):
    proposed = parse_tool(
        add_order_note.invoke(
            {"order_id": "ORD-107", "note": "Chase packing tomorrow", "confirmed": False}
        )
    )
    assert proposed["data"]["saved"] is False
    assert list_notes(order_id="ORD-107") == []

    saved = parse_tool(
        add_order_note.invoke(
            {"order_id": "ORD-107", "note": "Chase packing tomorrow", "confirmed": True}
        )
    )
    assert saved["data"]["saved"] is True
    notes = list_notes(order_id="ORD-107")
    assert len(notes) == 1
    assert notes[0]["note"] == "Chase packing tomorrow"
    assert notes[0]["user_id"] == test_user.id


def test_add_order_note_empty_and_missing(db, clean_state, test_user):
    empty = parse_tool(add_order_note.invoke({"order_id": "ORD-107", "note": "   "}))
    assert empty["error"]["code"] == "INVALID_INPUT"
    missing = parse_tool(
        add_order_note.invoke({"order_id": "ORD-999", "note": "hello", "confirmed": True})
    )
    assert missing["error"]["code"] == "NOT_FOUND"
    assert list_notes(order_id="ORD-999") == []


def test_create_reminder_factory_tomorrow(db, clean_state, test_user):
    proposed = parse_tool(
        create_reminder.invoke(
            {
                "order_id": "ORD-005",
                "remind_on": "2026-04-02",
                "message": "Recheck stall",
                "confirmed": False,
            }
        )
    )
    assert proposed["data"]["saved"] is False
    assert proposed["data"]["remind_on"] == "2026-04-02"
    assert list_reminders() == []

    saved = parse_tool(
        create_reminder.invoke(
            {
                "order_id": "ORD-005",
                "remind_on": "2026-04-02",
                "message": "Recheck stall",
                "confirmed": True,
            }
        )
    )
    assert saved["data"]["saved"] is True
    assert saved["data"]["notified"] is False
    rows = list_reminders(user_id=test_user.id)
    assert len(rows) == 1
    assert str(rows[0]["remind_on"]) == "2026-04-02"


def test_create_reminder_invalid_date(db, clean_state):
    payload = parse_tool(
        create_reminder.invoke(
            {"order_id": "ORD-005", "remind_on": "tomorrow", "message": "check"}
        )
    )
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_get_recent_actions_reads_audit(db, clean_state):
    parse_tool(draft_chase_email.invoke({"order_id": "ORD-120"}))
    payload = parse_tool(get_recent_actions.invoke({"limit": 10}))
    assert payload["ok"] is True
    assert payload["data"]["count"] >= 1
    tools = {item.get("tool") for item in payload["data"]["items"]}
    assert "draft_chase_email" in tools
