"""Evidence explanations must stay grounded and keep provider reasoning separate."""
import json
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from backend.agent.graph import build_model, parse_agent_result
from backend.services.why import build_why, reasoning_summaries


def test_risk_explanation_uses_current_tool_comparison_not_reference_example():
    data = {"order": {"order_id": "ORD-108", "customer": "Actual customer"},
            "pace": {"estimated_remaining_working_days": 8.4, "working_days_until_due_inclusive": 3},
            "risk": {"flags": ["TIGHT_DEADLINE"]}, "limitations": ["This is an estimate."]}
    trace = {"tool": "trace_order", "source_file": "orders.csv", "rows": [data["order"]],
             "calculations": [{"name": "estimated_remaining_working_days", "result": 8.4,
                               "formula": "see backend.services.private"}]}
    parsed = parse_agent_result({"messages": [HumanMessage("Why is ORD-108 risky?"),
        ToolMessage(content=json.dumps({"ok": True, "tool": "trace_order", "data": data, "trace": trace}), tool_call_id="1"),
        AIMessage("It may miss its due date.")]}, "c")
    why = build_why("Why is ORD-108 risky?", parsed)
    text = json.dumps(why)
    assert len(why["steps"]) == 4
    assert "8.4 working days" in text and "3 working days available" in text
    assert "TrendCart" not in text and "backend.services" not in text
    assert why["limitations"] == ["This is an estimate."]
    assert why["sources"][0]["rows"][0]["Customer"] == "Actual customer"


def test_no_rows_or_calculations_does_not_claim_verification():
    why = build_why("Why?", {"answer": "Unknown", "traces": []})
    assert "verification is unavailable" in why["steps"][1]["items"][0]
    assert "No numeric calculation" in why["steps"][2]["items"][0]


def test_chinese_and_clarification_do_not_choose_an_order():
    why = build_why("为什么有风险？", {"clarification": {"options": []}, "traces": []})
    assert why["language"] == "zh"
    assert "先确认" in why["steps"][3]["items"][0]


def test_summary_only_reads_explicit_summary_text_and_current_turn(monkeypatch):
    monkeypatch.setenv("OPENAI_REASONING_SUMMARY", "auto")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    content = [{"type": "reasoning", "summary": [{"type": "summary_text", "text": "Verified public summary"},
                {"type": "reasoning_text", "text": "PRIVATE"}], "encrypted_content": "SECRET"},
               {"type": "text", "text": "Answer"}]
    old = AIMessage(content=[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "OLD"}]}])
    parsed = parse_agent_result({"messages": [HumanMessage("Old"), old, HumanMessage("New"), AIMessage(content=content)]}, "c")
    assert parsed["reasoning_summary"] == ["Verified public summary"]
    assert parsed["answer"] == "Answer"
    monkeypatch.delenv("OPENAI_REASONING_SUMMARY")
    assert parse_agent_result({"messages": [AIMessage(content=content)]}, "c")["reasoning_summary"] == []
    assert reasoning_summaries([AIMessage(content="text only")]) == []


def test_provider_summary_is_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("OPENAI_REASONING_SUMMARY", raising=False)
    assert build_model().reasoning is None
    monkeypatch.setenv("OPENAI_REASONING_SUMMARY", "auto")
    assert build_model().reasoning == {"summary": "auto"}


def test_follow_up_reuses_sources_without_inventing_new_calls_or_old_summary():
    from backend.services.why import attach_prior_evidence
    payload = {"ok": True, "tool": "trace_order", "trace": {"tool": "trace_order", "source_file": "orders.csv",
        "rows": [{"order_id": "ORD-108", "customer": "Actual customer"}]},
        "data": {"order": {"order_id": "ORD-108"}, "limitations": ["Estimate only."]}}
    messages = [HumanMessage("Why is ORD-108 risky?"),
        ToolMessage(content=json.dumps(payload), tool_call_id="1"), AIMessage("8.4 days."),
        HumanMessage("How was it calculated?"), AIMessage("From the stage medians.")]
    response = {"answer": "From the stage medians.", "tools_used": [], "reasoning_summary": []}
    attach_prior_evidence(response, messages)
    why = build_why("How was it calculated?", response)
    assert why["sources"][0]["rows"][0]["Order"] == "ORD-108"
    assert "not queried again" in why["source_context"]
    assert response["tools_used"] == [] and response["reasoning_summary"] == []
    assert why["limitations"] == ["Estimate only."]


def test_follow_up_does_not_reuse_before_a_failed_lookup_or_override_current_data():
    from backend.services.why import attach_prior_evidence
    prior = ToolMessage(content=json.dumps({"ok": True, "tool": "trace_order", "trace": {"rows": [{"order_id": "ORD-108"}]}}), tool_call_id="1")
    failed = ToolMessage(content=json.dumps({"ok": False, "tool": "trace_order", "error": {"code": "NOT_FOUND"}}), tool_call_id="2")
    messages = [HumanMessage("Old"), prior, HumanMessage("Unknown order"), failed, HumanMessage("Why?")]
    response = {"tools_used": []}
    attach_prior_evidence(response, messages)
    assert "evidence_reused" not in response
    current = {"evidence_results": [{"tool": "get_order_status", "data": {}}]}
    attach_prior_evidence(current, messages)
    assert "evidence_reused" not in current


def test_tool_planning_summary_is_not_shown_as_business_explanation():
    plan = AIMessage(content=[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "I will draw a chart next."}]}],
                     tool_calls=[{"name": "draw", "args": {}, "id": "chart-1"}])
    assert reasoning_summaries([plan, AIMessage("The requested order fits.")]) == []
    final = AIMessage(content=[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "The request fits the tool's spare capacity."}]},
                               {"type": "text", "text": "The requested order fits."}])
    assert reasoning_summaries([plan, final]) == ["The request fits the tool's spare capacity."]
