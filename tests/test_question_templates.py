"""Retrieve answer templates from evaluation/questions.json. No LLM."""

from __future__ import annotations

import json
import os

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from backend.agent.graph import _TEMPLATE_QUERY, _react_prompt
from backend.agent.prompts import format_retrieved_templates
from backend.services import question_templates as qt
from backend.services.question_templates import (
    accept_grounded_rewrite,
    compose_deep_dive_questions,
    retrieve_answer_templates,
    suggest_followups,
    supplement_templates_for_tools,
    without_foreign_order_templates,
)
from backend.services.question_templates import _has_cjk
from backend.services import question_templates as qt


@pytest.fixture(autouse=True)
def _offline_other_language(monkeypatch):
    monkeypatch.setattr(qt, "_pick_other_language", lambda _query: "")


def test_retrieval_is_two_same_language_and_one_other(monkeypatch):
    monkeypatch.setattr(qt, "_pick_other_language", lambda _query: "ETS-002")
    hits = retrieve_answer_templates("Which orders are likely to miss their due dates?")
    assert len(hits) == 3
    assert hits[0]["id"] == "Q001"
    assert all(not _has_cjk(hit["question"]) for hit in hits[:2])
    assert hits[2]["id"] == "ETS-002"
    assert _has_cjk(hits[2]["question"])

    monkeypatch.setattr(qt, "_pick_other_language", lambda _query: "Q001")
    chinese = retrieve_answer_templates("哪些订单可能会错过交期？")
    assert len(chinese) == 3
    assert all(_has_cjk(hit["question"]) for hit in chinese[:2])
    assert chinese[2]["id"] == "Q001"
    assert not _has_cjk(chinese[2]["question"])


def test_exact_question_is_top_hit():
    hits = retrieve_answer_templates("Which orders are likely to miss their due dates?")
    assert len(hits) >= 1
    assert hits[0]["id"] == "Q001"
    assert hits[0]["question"] == "Which orders are likely to miss their due dates?"
    assert hits[0]["expected_answer"]
    assert len(hits) == 2
    assert hits[0]["score"] >= hits[1]["score"]


def test_ord120_status_does_not_pull_risk_template():
    hits = retrieve_answer_templates("How is ORD-120 doing?")
    assert hits[0]["id"] == "Q007"
    assert hits[0]["relevant_tool"] == "get_order_status"


def test_question_bank_mtime_rebuilds_index(tmp_path, monkeypatch):
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "id": "Q003",
                        "question": "Why is ORD-120 considered risky?",
                        "expected_answer": "risk",
                    },
                    {
                        "id": "Q004",
                        "question": "Trace ORD-107 for me. What's its current situation?",
                        "expected_answer": "trace",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qt, "QUESTIONS_PATH", path)
    qt._index_at.cache_clear()
    hits = retrieve_answer_templates("How is ORD-120 doing?")
    assert [h["id"] for h in hits] == ["Q003", "Q004"]

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["questions"].append(
        {
            "id": "Q007",
            "question": "How is ORD-120 doing?",
            "expected_answer": "status",
        }
    )
    path.write_text(json.dumps(raw), encoding="utf-8")
    stamp = path.stat().st_mtime + 2
    os.utime(path, (stamp, stamp))
    hits = retrieve_answer_templates("How is ORD-120 doing?")
    assert hits[0]["id"] == "Q007"


def test_pace_wording_retrieves_working_templates():
    hits = retrieve_answer_templates(
        "Which orders are likely to miss their due dates in the next 7 days "
        "if production continues at the current pace?"
    )
    ids = [h["id"] for h in hits]
    assert "Q002" in ids or "Q001" in ids


def test_foreign_order_template_is_not_attached():
    q = "How is the TrendCart order doing?"
    hits = retrieve_answer_templates(q)
    kept = without_foreign_order_templates(q, hits)
    assert all("ORD-120" not in (hit["question"] or "") for hit in kept)
    named = without_foreign_order_templates("How is ORD-120 doing?", hits)
    assert any(hit["id"] == "Q007" for hit in named) or any(
        "ORD-120" in (hit.get("question") or "") for hit in named
    )


def test_empty_query_returns_nothing():
    assert retrieve_answer_templates("   ") == []


def test_template_prompt_block_is_style_only():
    hits = retrieve_answer_templates("What should we prioritize today?")
    text = format_retrieved_templates(hits)
    assert "Retrieved answer templates" in text
    assert "tool JSON" in text
    assert "sentence shape" in text
    assert "morning of 2026-04-01" in text
    assert "production_log stops on 2026-03-31" in text
    assert "April 1 order activity is not in the template data" in text
    assert "MUST redo the calculation" in text
    assert "field listing" in text
    assert "Q005" in text or "prioritize" in text.lower()
    assert "Few-shot answers" in __import__(
        "backend.agent.prompts", fromlist=["_PROMPT_TAIL"]
    )._PROMPT_TAIL


def test_templates_are_injected_only_after_tool_result():
    q = "Which orders are likely to miss their due dates?"
    token = _TEMPLATE_QUERY.set(q)
    try:
        before = _react_prompt({"messages": [HumanMessage(content=q)]})
        assert "Retrieved answer templates" not in before[0].content

        after = _react_prompt(
            {
                "messages": [
                    HumanMessage(content=q),
                    ToolMessage(
                        content='{"ok": true, "tool": "get_orders_at_risk"}',
                        tool_call_id="call-1",
                    ),
                ]
            }
        )
        assert "Retrieved answer templates" in after[0].content
        assert "Q001" in after[0].content
    finally:
        _TEMPLATE_QUERY.reset(token)


def test_supplement_adds_called_tool_template():
    q = "What should I be concerned about right now?"
    hits = retrieve_answer_templates(q)
    ids = [h["id"] for h in hits]
    assert "Q001" not in ids
    merged = supplement_templates_for_tools(q, hits, ["get_orders_at_risk"])
    merged_ids = [h["id"] for h in merged]
    assert merged_ids[: len(ids)] == ids
    assert "Q001" in merged_ids
    assert next(h for h in merged if h["id"] == "Q001")["relevant_tool"] == (
        "get_orders_at_risk"
    )


def test_supplement_skips_when_tool_already_covered():
    q = "Which orders are likely to miss their due dates?"
    hits = retrieve_answer_templates(q)
    assert hits[0]["id"] == "Q001"
    merged = supplement_templates_for_tools(q, hits, ["get_orders_at_risk"])
    assert [h["id"] for h in merged] == [h["id"] for h in hits]


def test_concern_turn_supplements_at_risk_template():
    q = "What should I be concerned about right now?"
    token = _TEMPLATE_QUERY.set(q)
    try:
        after = _react_prompt(
            {
                "messages": [
                    HumanMessage(content=q),
                    ToolMessage(
                        content='{"ok": true, "tool": "get_orders_at_risk"}',
                        tool_call_id="call-1",
                    ),
                    ToolMessage(
                        content='{"ok": true, "tool": "get_today_priority"}',
                        tool_call_id="call-2",
                    ),
                ]
            }
        )
        text = after[0].content
        assert "Q005" in text
        assert "Q001" in text
    finally:
        _TEMPLATE_QUERY.reset(token)


def test_followups_skip_the_question_just_asked():
    question = "Which orders are likely to miss their due dates?"
    hits = suggest_followups(question, asked=[question], focus="ORD-029 is due today.")
    assert hits
    assert len(hits) <= 3
    assert question not in hits


def test_followup_uses_the_order_from_this_turn():
    question = "How is ORD-107 doing?"
    hits = suggest_followups(question, asked=[question], focus="ORD-107 is in Packing.")
    assert hits
    assert question not in hits
    assert any("ORD-107" in hit for hit in hits)


def test_followups_are_local_and_empty_without_a_query():
    assert suggest_followups("") == []
    assert suggest_followups("   ", asked=["Which orders are at risk?"]) == []


def test_grounded_rewrite_replaces_only_the_named_order():
    template = "Why is ORD-061 considered risky?"
    asked = ["How is ORD-062 doing?"]
    assert accept_grounded_rewrite(template, "Why is ORD-062 considered risky?", asked)
    assert not accept_grounded_rewrite(template, "Why is ORD-061 considered risky?", asked)
    assert not accept_grounded_rewrite(template, "What is the margin of ORD-062?", asked)
    assert not accept_grounded_rewrite(template, "Why is ORD-062 considered risky?", ["Compare ORD-062 and ORD-063"])


def test_compose_drops_invented_questions_and_keeps_a_grounded_rewrite(monkeypatch):
    monkeypatch.setattr(
        qt,
        "_ranked_followups",
        lambda *args, **kwargs: [
            {
                "id": "T1",
                "question": "Why is ORD-061 considered risky?",
                "relevant_tool": "trace_order",
            }
        ],
    )
    monkeypatch.setattr(
        qt,
        "_draft_with_model",
        lambda *args, **kwargs: [
            {"source_id": "T1", "question": "What is the margin of ORD-062?"},
            {"source_id": "T1", "question": "Why is ORD-062 considered risky?"},
        ],
    )
    assert compose_deep_dive_questions("How is ORD-062 doing?") == [
        "Why is ORD-062 considered risky?"
    ]


def test_compose_drops_a_same_kind_order_swap(monkeypatch):
    monkeypatch.setattr(
        qt,
        "_ranked_followups",
        lambda *args, **kwargs: [
            {
                "id": "T1",
                "question": "How is ORD-061 doing?",
                "relevant_tool": "get_order_status",
            }
        ],
    )
    monkeypatch.setattr(
        qt,
        "_draft_with_model",
        lambda *args, **kwargs: [
            {"source_id": "T1", "question": "How is ORD-062 doing?"},
        ],
    )
    assert compose_deep_dive_questions("How is ORD-062 doing?") == []


def test_compose_rewrites_a_foreign_template_order_without_the_model(monkeypatch):
    monkeypatch.setattr(
        qt,
        "_ranked_followups",
        lambda *args, **kwargs: [
            {
                "id": "T1",
                "question": "Why is ORD-061 considered risky?",
                "relevant_tool": "trace_order",
            }
        ],
    )
    monkeypatch.setattr(qt, "_draft_with_model", lambda *args, **kwargs: [])
    hits = compose_deep_dive_questions("How is ORD-062 doing?")
    assert hits == ["Why is ORD-062 considered risky?"]
    assert all("ORD-061" not in hit for hit in hits)


def test_compose_follows_the_latest_order_not_an_earlier_one(monkeypatch):
    monkeypatch.setattr(
        qt,
        "_ranked_followups",
        lambda *args, **kwargs: [
            {
                "id": "T1",
                "question": "Why is ORD-061 considered risky?",
                "relevant_tool": "trace_order",
            }
        ],
    )
    monkeypatch.setattr(
        qt,
        "_draft_with_model",
        lambda *args, **kwargs: [
            {"source_id": "T1", "question": "Why is ORD-005 considered risky?"},
        ],
    )
    hits = compose_deep_dive_questions(
        "How is ORD-029 doing?",
        asked=["How is ORD-005 doing?", "How is ORD-029 doing?"],
    )
    assert hits == ["Why is ORD-029 considered risky?"]
    assert all("ORD-005" not in hit for hit in hits)


def test_compose_stops_when_the_reply_says_the_order_is_missing(monkeypatch):
    monkeypatch.setattr(
        qt,
        "_ranked_followups",
        lambda *args, **kwargs: [
            {
                "id": "T1",
                "question": "Why is ORD-061 considered risky?",
                "relevant_tool": "trace_order",
            }
        ],
    )
    monkeypatch.setattr(
        qt,
        "_draft_with_model",
        lambda *args, **kwargs: [
            {"source_id": "T1", "question": "Why is ORD-000 considered risky?"},
        ],
    )
    hits = compose_deep_dive_questions(
        "How is ORD-000 doing?",
        answer="ORD-000 is not in orders.csv.",
    )
    assert hits == []
