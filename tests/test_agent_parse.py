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
