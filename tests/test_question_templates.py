"""Retrieve answer templates from evaluation/questions.json. No LLM."""

from __future__ import annotations

import json
import os

from langchain_core.messages import HumanMessage, ToolMessage

from backend.agent.graph import _TEMPLATE_QUERY, _react_prompt
from backend.agent.prompts import format_retrieved_templates
from backend.services import question_templates as qt
from backend.services.question_templates import retrieve_answer_templates


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
    assert [h["id"] for h in hits] == ["Q007", "Q008"]
    assert "Q003" not in [h["id"] for h in hits]


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


def test_empty_query_returns_nothing():
    assert retrieve_answer_templates("   ") == []


def test_template_prompt_block_is_style_only():
    hits = retrieve_answer_templates("What should we prioritize today?")
    text = format_retrieved_templates(hits)
    assert "Retrieved answer templates" in text
    assert "tool JSON" in text
    assert "Q005" in text or "prioritize" in text.lower()


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
