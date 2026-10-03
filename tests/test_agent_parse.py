"""Agent result parsing. No external LLM."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agent.graph import parse_agent_result


def _tool(name: str, call_id: str) -> ToolMessage:
    return ToolMessage(
        content='{"ok": true, "tool": "%s", "trace": {"tool": "%s"}}' % (name, name),
        tool_call_id=call_id,
        name=name,
    )


def test_parse_agent_result_keeps_only_latest_turn_tools():
    result = {
        "messages": [
            HumanMessage(content="How is ORD-120 doing?"),
            AIMessage(content="", tool_calls=[{"name": "get_order_status", "id": "1", "args": {}}]),
            _tool("get_order_status", "1"),
            AIMessage(content="ORD-120 is overdue."),
            HumanMessage(content="Which orders are at risk?"),
            AIMessage(content="", tool_calls=[{"name": "get_orders_at_risk", "id": "2", "args": {}}]),
            _tool("get_orders_at_risk", "2"),
            AIMessage(content="10 orders need attention."),
            HumanMessage(content="Can we take 800 hoodies by August 25?"),
            AIMessage(content="", tool_calls=[{"name": "check_feasibility", "id": "3", "args": {}}]),
            _tool("check_feasibility", "3"),
            AIMessage(content="Feasible in-house under the heuristic."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["tools_used"] == ["check_feasibility"]
    assert parsed["traces"] == [{"tool": "check_feasibility"}]
    assert "Feasible in-house" in parsed["answer"]
    assert parsed["clarification"] is None


def test_several_matching_orders_are_not_a_clarification_card():
    payload = {
        "ok": False,
        "tool": "get_order_status",
        "error": {
            "code": "AMBIGUOUS",
            "message": "17 orders match. Pick one, or type the order you mean.",
            "candidates": [
                {"order_id": "ORD-005", "product": "Scarf", "current_stage": "KNITTING"},
                {"order_id": "ORD-120", "product": "Vest", "current_stage": "ASSEMBLY"},
            ],
        },
    }
    result = {
        "messages": [
            HumanMessage(content="How is the TrendCart order doing?"),
            AIMessage(content="", tool_calls=[{"name": "get_order_status", "id": "1", "args": {}}]),
            ToolMessage(content=__import__("json").dumps(payload), tool_call_id="1", name="get_order_status"),
            AIMessage(content="I will check ORD-120."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["clarification"] is None
    assert parsed["answer"] == "I will check ORD-120."


def test_find_orders_list_is_not_a_clarification_card():
    payload = {
        "ok": True,
        "tool": "find_orders",
        "data": {
            "count": 2,
            "orders": [
                {"order_id": "ORD-005", "product": "Scarf", "current_stage": "KNITTING"},
                {"order_id": "ORD-120", "product": "Vest", "current_stage": "ASSEMBLY"},
            ],
        },
    }
    result = {
        "messages": [
            HumanMessage(content="How is the TrendCart order doing?"),
            ToolMessage(content=__import__("json").dumps(payload), tool_call_id="1", name="find_orders"),
            AIMessage(content="I found 2 TrendCart orders."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["clarification"] is None
    assert parsed["answer"] == "I found 2 TrendCart orders."


def test_ungrounded_order_id_does_not_become_an_order_card():
    listed = {
        "ok": True,
        "tool": "find_orders",
        "data": {
            "orders": [
                {"order_id": "ORD-005", "product": "Scarf", "current_stage": "KNITTING"},
                {"order_id": "ORD-120", "product": "Vest", "current_stage": "ASSEMBLY"},
            ],
        },
    }
    refused = {
        "ok": False,
        "tool": "get_order_status",
        "error": {
            "code": "UNGROUNDED_ID",
            "message": "ORD-120 was not in the manager's question.",
        },
    }
    result = {
        "messages": [
            HumanMessage(content="How is the TrendCart order doing?"),
            ToolMessage(content=__import__("json").dumps(listed), tool_call_id="1", name="find_orders"),
            ToolMessage(content=__import__("json").dumps(refused), tool_call_id="2", name="get_order_status"),
            AIMessage(content="As of 2026-04-01, ORD-120 for TrendCart is overdue."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["clarification"] is None
    assert "overdue" not in parsed["answer"]
    assert parsed["answer"].startswith("ORD-120 was not")


def test_list_all_orders_does_not_offer_buttons():
    payload = {
        "ok": True,
        "tool": "find_orders",
        "data": {
            "orders": [
                {"order_id": "ORD-005", "product": "Scarf"},
                {"order_id": "ORD-120", "product": "Vest"},
            ],
        },
    }
    result = {
        "messages": [
            HumanMessage(content="List all TrendCart orders."),
            ToolMessage(content=__import__("json").dumps(payload), tool_call_id="1", name="find_orders"),
            AIMessage(content="I found 2 TrendCart orders."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["clarification"] is None
    assert "I found 2" in parsed["answer"]
