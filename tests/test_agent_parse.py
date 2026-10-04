"""Agent result parsing. No external LLM."""

from __future__ import annotations

import json

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


def test_parse_agent_result_returns_chart_from_latest_turn():
    chart = {
        "type": "bar",
        "title": "Orders by stage",
        "data": [{"stage": "KNITTING", "count": 3}],
        "category_key": "stage",
        "value_keys": ["count"],
    }
    result = {
        "messages": [
            HumanMessage(content="Compare orders by stage"),
            ToolMessage(
                content='{"ok": true, "tool": "draw", "data": {"chart": '
                + json.dumps(chart)
                + "}}",
                tool_call_id="chart-1",
                name="draw",
            ),
            AIMessage(content="Here is the stage comparison."),
        ]
    }

    parsed = parse_agent_result(result, "thread-1")

    assert parsed["charts"] == [chart]
    assert parsed["tools_used"] == ["draw"]


def test_parse_agent_result_returns_table_from_latest_turn():
    table = {
        "title": "At-risk orders",
        "columns": [{"key": "order_id", "label": "Order"}],
        "rows": [{"order_id": "ORD-120"}],
    }
    result = {
        "messages": [
            HumanMessage(content="List at-risk orders in a table"),
            ToolMessage(
                content=json.dumps({"ok": True, "tool": "render_table", "data": {"table": table}}),
                tool_call_id="table-1",
                name="render_table",
            ),
            AIMessage(content="Here are the at-risk orders."),
        ]
    }

    parsed = parse_agent_result(result, "thread-1")

    assert parsed["tables"] == [table]
    assert parsed["tools_used"] == ["render_table"]
