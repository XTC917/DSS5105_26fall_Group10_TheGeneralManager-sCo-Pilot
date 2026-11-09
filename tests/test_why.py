"""Evidence explanations stay grounded in the current tool result."""
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agent.graph import parse_agent_result
from backend.services.why import attach_prior_evidence, build_why


def test_risk_explanation_uses_current_tool_comparison_not_reference_example():
    data = {
        "order": {"order_id": "ORD-108", "customer": "Actual customer"},
        "pace": {"estimated_remaining_working_days": 8.4, "working_days_until_due_inclusive": 3},
        "risk": {"flags": ["TIGHT_DEADLINE"]},
        "limitations": ["This is an estimate."],
    }
    trace = {
        "tool": "trace_order",
        "source_file": "orders.csv",
        "rows": [data["order"]],
        "calculations": [{"name": "estimated_remaining_working_days", "result": 8.4, "formula": "see backend.services.private"}],
    }
    parsed = parse_agent_result(
        {
            "messages": [
                HumanMessage("Why is ORD-108 risky?"),
                ToolMessage(
                    content=json.dumps({"ok": True, "tool": "trace_order", "data": data, "trace": trace}),
                    tool_call_id="1",
                ),
                AIMessage("It may miss its due date."),
            ]
        },
        "c",
    )
    why = build_why("Why is ORD-108 risky?", parsed)
    text = json.dumps(why)
    assert len(why["steps"]) == 4
    assert "8.4 working days" in text and "3 working days available" in text
    assert "TrendCart" not in text and "backend.services" not in text
    assert why["limitations"] == ["This is an estimate."]
    assert why["sources"][0]["rows"][0]["Customer"] == "Actual customer"


def test_stage_only_trace_does_not_use_the_old_empty_wording():
    why = build_why("Are there any unusual production issues I should know about today?", {
        "answer": "Assembly is slow.",
        "traces": [{
            "tool": "discover_factory_issues",
            "source_file": "production_log.csv",
            "rows": [{"stage": "ASSEMBLY", "issue_id": "stage:ASSEMBLY"}],
            "calculations": [{"name": "total_found", "result": 1}],
        }],
    })
    text = json.dumps(why)
    assert "Stage: ASSEMBLY" not in text
    assert "No numeric calculation" not in text
    assert "business causation" not in text
    assert "did not include a comparison" in text


def test_stage_issue_explanation_states_the_median_comparison():
    why = build_why("Are there any unusual production issues I should know about today?", {
        "answer": "Assembly is slow.",
        "traces": [{
            "tool": "discover_factory_issues",
            "source_file": "production_log.csv",
            "rows": [{"stage": "ASSEMBLY"}],
            "calculations": [{"name": "total_found", "result": 1}],
        }],
        "evidence_results": [{
            "tool": "discover_factory_issues",
            "data": {
                "production": {
                    "in_progress_order_count": 34,
                    "in_progress_by_stage": {"KNITTING": 12, "ASSEMBLY": 10, "WASHING": 10, "PACKING": 2},
                    "stage_vs_30day_median": [{
                        "stage": "ASSEMBLY",
                        "last_working_date": "2026-03-31",
                        "last_day_pieces": 455,
                        "lookback_median": 758,
                        "ratio_to_median": 0.6,
                        "flagged": True,
                    }],
                },
            },
        }],
    })
    text = json.dumps(why)
    assert "455" in text and "758" in text and "60%" in text
    assert "No numeric calculation" not in text
    assert "Stage: ASSEMBLY" not in text
    assert "30-working-day median" in why["sources"][0]["label"]


def test_filter_rows_is_not_listed_as_a_source():
    why = build_why("Which Harbor Knits orders are in progress?", {
        "answer": "Two orders.",
        "traces": [
            {
                "tool": "find_orders",
                "source_file": "orders.csv",
                "rows": [
                    {"order_id": "ORD-1", "customer": "Harbor Knits"},
                    {"order_id": "ORD-2", "customer": "Harbor Knits"},
                    {"order_id": "ORD-3", "customer": "Harbor Knits"},
                ],
            },
            {
                "tool": "filter_rows",
                "source_file": "find_orders",
                "rows": [
                    {"order_id": "ORD-1", "customer": "Harbor Knits"},
                    {"order_id": "ORD-2", "customer": "Harbor Knits"},
                ],
            },
        ],
    })
    assert [source["name"] for source in why["sources"]] == ["orders.csv"]


def test_no_rows_or_calculations_does_not_claim_verification():
    why = build_why("Why?", {"answer": "Unknown", "traces": []})
    assert "did not include a record" in why["steps"][1]["items"][0]
    assert "did not include a comparison" in why["steps"][2]["items"][0]


def test_chinese_and_clarification_do_not_choose_an_order():
    why = build_why("为什么有风险？", {"clarification": {"options": []}, "traces": []})
    assert why["language"] == "zh"
    assert "先确认" in why["steps"][3]["items"][0]


def test_follow_up_reuses_sources_without_inventing_new_calls():
    payload = {
        "ok": True,
        "tool": "trace_order",
        "trace": {
            "tool": "trace_order",
            "source_file": "orders.csv",
            "rows": [{"order_id": "ORD-108", "customer": "Actual customer"}],
        },
        "data": {"order": {"order_id": "ORD-108"}, "limitations": ["Estimate only."]},
    }
    messages = [
        HumanMessage("Why is ORD-108 risky?"),
        ToolMessage(content=json.dumps(payload), tool_call_id="1"),
        AIMessage("8.4 days."),
        HumanMessage("How was it calculated?"),
        AIMessage("From the stage medians."),
    ]
    response = {"answer": "From the stage medians.", "tools_used": []}
    attach_prior_evidence(response, messages)
    why = build_why("How was it calculated?", response)
    assert why["sources"][0]["rows"][0]["Order"] == "ORD-108"
    assert "not queried again" in why["source_context"]
    assert response["tools_used"] == []
    assert why["limitations"] == ["Estimate only."]


def test_follow_up_does_not_reuse_before_a_failed_lookup_or_override_current_data():
    prior = ToolMessage(
        content=json.dumps({"ok": True, "tool": "trace_order", "trace": {"rows": [{"order_id": "ORD-108"}]}}),
        tool_call_id="1",
    )
    failed = ToolMessage(
        content=json.dumps({"ok": False, "tool": "trace_order", "error": {"code": "NOT_FOUND"}}),
        tool_call_id="2",
    )
    messages = [HumanMessage("Old"), prior, HumanMessage("Unknown order"), failed, HumanMessage("Why?")]
    response = {"tools_used": []}
    attach_prior_evidence(response, messages)
    assert "evidence_reused" not in response
    current = {"evidence_results": [{"tool": "get_order_status", "data": {}}]}
    attach_prior_evidence(current, messages)
    assert "evidence_reused" not in current
