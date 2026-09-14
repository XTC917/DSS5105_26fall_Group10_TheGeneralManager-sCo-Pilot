"""Retrieve answer templates from evaluation/questions.json. No LLM."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, ToolMessage

from backend.agent.graph import _TEMPLATE_QUERY, _react_prompt
from backend.agent.prompts import format_retrieved_templates
from backend.services.question_templates import retrieve_answer_templates


def test_exact_question_is_top_hit():
    hits = retrieve_answer_templates("How is ORD-120 doing?")
    assert len(hits) == 3
    assert hits[0]["id"] == "Q001"
    assert hits[0]["question"] == "How is ORD-120 doing?"
    assert hits[0]["expected_answer"]
    assert hits[0]["score"] >= hits[1]["score"] >= hits[2]["score"]


def test_risk_wording_retrieves_risk_templates():
    hits = retrieve_answer_templates("Which orders need attention?")
    ids = [h["id"] for h in hits]
    assert "Q011" in ids or "Q003" in ids
    assert any("risk" in h["question"].lower() or "attention" in h["question"].lower() for h in hits)


def test_empty_query_returns_nothing():
    assert retrieve_answer_templates("   ") == []


def test_template_prompt_block_is_style_only():
    hits = retrieve_answer_templates("Give me this morning's briefing")
    text = format_retrieved_templates(hits)
    assert "Retrieved answer templates" in text
    assert "tool JSON" in text
    assert "Q033" in text or "briefing" in text.lower()


def test_templates_are_injected_only_after_tool_result():
    token = _TEMPLATE_QUERY.set("How is ORD-120 doing?")
    try:
        before = _react_prompt({"messages": [HumanMessage(content="How is ORD-120 doing?")]})
        assert "Retrieved answer templates" not in before[0].content

        after = _react_prompt(
            {
                "messages": [
                    HumanMessage(content="How is ORD-120 doing?"),
                    ToolMessage(
                        content='{"ok": true, "tool": "get_order_status"}',
                        tool_call_id="call-1",
                    ),
                ]
            }
        )
        assert "Retrieved answer templates" in after[0].content
        assert "Q001" in after[0].content
    finally:
        _TEMPLATE_QUERY.reset(token)
