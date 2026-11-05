"""Mail regressions without a live database, model call, or external delivery.

Patch data/audit boundaries, not the template, risk logic, or tool schemas.
"""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.services.email_templates import compose_email
from backend.tools import actions
from backend.tools.common import reset_manager_text, set_manager_text


ORDER = dict(order_id="ORD-005", customer="TrendCart", product="Scarf", pieces=500,
             status="IN_PROGRESS", current_stage="KNITTING", due_date="2026-04-20",
             last_activity_date="2026-03-24")


@pytest.fixture
def mail_env(monkeypatch):
    orders = [deepcopy(ORDER)]
    events = []
    db = SimpleNamespace(
        get_order_by_id=lambda oid: next((r for r in orders if r["order_id"] == oid), None),
        in_progress_orders=lambda: [r for r in orders if r["status"] == "IN_PROGRESS"],
    )
    monkeypatch.setattr(actions, "get_db", lambda: db)
    # Throughput availability is unrelated to these regressions. Existing risk
    # assessment still runs on the dates/status above; no new risk arithmetic.
    monkeypatch.setattr(actions, "stage_medians", lambda db: {})
    monkeypatch.setattr(actions, "pace_fields", lambda order, medians: {})
    monkeypatch.setattr(actions, "flags_with_pace_tight", lambda flags, pace: flags)
    monkeypatch.setattr(actions, "record_event", lambda **kwargs: events.append(kwargs))
    return orders, events


def draft(**args):
    return json.loads(actions.draft_chase_email.invoke(args))


@pytest.mark.parametrize("text,expected", [
    ("请为 ORD-005 起草一封催办邮件，只生成草稿，不发送。", "zh"),
    ("Draft a chase email for ORD-005, but do not send it.", "en"),
    ("Draft ORD-005\n之前用中文提问", "en"),
    ("给 ORD-005 写信\nEarlier English request", "zh"),
])
def test_current_turn_language_and_no_send_proposal(mail_env, text, expected):
    token = set_manager_text(text)
    try:
        result = draft(order_id="ORD-005")
    finally:
        reset_manager_text(token)
    assert result["ok"]
    data = result["data"]
    email = data["draft"]
    assert email["language"] == expected
    assert ("请跟进" in email["subject"]) == (expected == "zh")
    assert ("您好" in email["body"]) == (expected == "zh")
    assert data["sent"] is False
    assert data["needs_confirmation"] is False
    assert "proposed_action" not in data
    assert email["to"] is None
    assert email["recipient_name"] is None
    assert "500" in email["body"] and "2026-04-20" in email["body"]
    assert "ORD-005" in email["subject"]
    assert mail_env[1][-1]["execution_status"] == "not_sent"


@pytest.mark.parametrize("language", ["zh", "en"])
def test_explicit_language_overrides_question(mail_env, language):
    token = set_manager_text("请为 ORD-005 起草英文邮件")
    try:
        result = draft(order_id="ORD-005", language=language)
    finally:
        reset_manager_text(token)
    assert result["data"]["draft"]["language"] == language


def test_customer_template_is_not_an_internal_production_instruction(mail_env):
    email = draft(order_id="ORD-005", audience="customer")["data"]["draft"]
    assert email["recipient_name"] == "TrendCart"
    assert "Dear TrendCart," in email["body"]
    assert "blockers" not in email["body"]
    assert "STALLED" not in email["body"]
    assert "STALLED" in email["risk_flags"]
    assert email["to"] is None
    assert "Draft only, not sent" in email["disclaimer"]


def test_all_overdue_customers_separate_orders_without_leaking_customers(mail_env):
    orders, events = mail_env
    orders[:] = [dict(ORDER, order_id="ORD-103", due_date="2026-03-30"),
                 dict(ORDER, order_id="ORD-120", due_date="2026-03-20"),
                 dict(ORDER, order_id="ORD-104", customer="OtherCo", due_date="2026-03-25"),
                 dict(ORDER, order_id="ORD-105", due_date="2026-04-01"),
                 dict(ORDER, order_id="ORD-106", status="COMPLETE", due_date="2026-03-20")]
    token = set_manager_text("Write an email to the customers who have overdue orders")
    try:
        data = draft(scope="overdue_customers")["data"]
    finally:
        reset_manager_text(token)
    assert data["count"] == 3
    assert [d["order_id"] for d in data["drafts"]] == ["ORD-103", "ORD-120", "ORD-104"]
    assert data["grouping"] == "one_draft_per_order"
    assert all(d["to"] is None for d in data["drafts"])
    assert "OtherCo" not in data["drafts"][0]["body"]
    assert "TrendCart" not in data["drafts"][2]["body"]
    assert "proposed_action" not in data
    assert events[-1]["execution_status"] == "not_sent"


def test_no_overdue_orders_is_empty_not_invented(mail_env):
    assert draft(scope="overdue_customers")["data"]["drafts"] == []


@pytest.mark.parametrize("args", [{}, {"order_id": "  "},
    {"order_id": "ORD-005", "scope": "overdue_customers"},
    {"scope": "overdue_customers", "audience": "internal"}])
def test_invalid_scope_or_missing_id(mail_env, args):
    assert draft(**args)["error"]["code"] == "INVALID_INPUT"


def test_unknown_id_and_ungrounded_id(mail_env):
    assert draft(order_id="ORD-999")["error"]["code"] == "NOT_FOUND"
    token = set_manager_text("Draft a letter for ORD-120")
    try:
        assert draft(order_id="ORD-005")["error"]["code"] == "UNGROUNDED_ID"
    finally:
        reset_manager_text(token)


def test_invalid_language_rejected_by_tool_schema(mail_env):
    with pytest.raises(ValidationError):
        draft(order_id="ORD-005", language="fr")


@pytest.mark.parametrize("confirmed", [False, True])
def test_send_remains_explicitly_simulated(mail_env, confirmed):
    result = json.loads(actions.send_email.invoke(dict(order_id="ORD-005", confirmed=confirmed, language="zh")))
    assert result["data"]["sent"] is False
    assert result["data"]["draft"]["language"] == "zh"
    if confirmed:
        assert result["data"]["execution_status"] == "SIMULATED"
    else:
        assert result["data"]["proposed_action"]["language"] == "zh"


def test_confirmation_preserves_email_language_and_audience(mail_env):
    from backend.services.confirm_actions import confirm_proposed_action
    proposed = json.loads(actions.send_email.invoke(dict(order_id="ORD-005", language="zh", audience="internal")))
    confirmed = confirm_proposed_action(proposed["data"]["proposed_action"])
    assert confirmed["data"]["draft"]["language"] == "zh"
    assert confirmed["data"]["draft"]["audience"] == "internal"
    assert confirmed["data"]["sent"] is False


def test_complete_and_missing_fields_do_not_invent_work_or_dates():
    row = dict(ORDER, status="COMPLETE", current_stage="COMPLETE", last_activity_date=None)
    email = compose_email(row, [], language="zh", audience="internal")
    assert "系统记录该订单已完成" in email["body"]
    assert "预计完成时间" not in email["body"]
    assert "最后活动日期为 未提供" in email["body"]
    assert "None" not in email["body"]


@pytest.mark.parametrize("batch", [False, True])
def test_agent_keeps_email_paragraphs_and_no_confirmation_action(mail_env, batch):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from backend.agent.graph import _react_prompt, parse_agent_result
    payload = draft(scope="overdue_customers") if batch else draft(order_id="ORD-005", language="zh")
    messages = [HumanMessage(content="Draft an email"),
                ToolMessage(content=json.dumps(payload), tool_call_id="email-1", name="draft_chase_email"),
                AIMessage(content="Draft only, not sent.")]
    system = _react_prompt({"messages": messages})[0].content
    assert "An email tool returned this turn" in system
    assert "Otherwise your next message MUST be exactly one tool call" not in system
    assert parse_agent_result({"messages": messages}, "mail-test")["proposed_actions"] == []


@pytest.mark.parametrize("order_id", ["ORD-005", "ORD-103", "ORD-120"])
def test_repository_csv_facts_with_real_risk_and_pace(monkeypatch, order_id):
    import csv
    from backend.config import DATA_DIR
    with (DATA_DIR / "orders.csv").open(encoding="utf-8-sig", newline="") as f:
        orders = list(csv.DictReader(f))
    with (DATA_DIR / "production_log.csv").open(encoding="utf-8-sig", newline="") as f:
        log = list(csv.DictReader(f))
    row = next(r for r in orders if r["order_id"] == order_id)
    db = SimpleNamespace(get_order_by_id=lambda oid: row, production_log=lambda: log)
    monkeypatch.setattr(actions, "get_db", lambda: db)
    monkeypatch.setattr(actions, "record_event", lambda **kwargs: None)
    email = draft(order_id=order_id, language="zh")["data"]["draft"]
    for key in ("order_id", "customer", "product", "pieces", "due_date", "last_activity_date"):
        assert str(row[key]) in email["body"]
    assert email["to"] is None
