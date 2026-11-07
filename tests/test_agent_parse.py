"""Agent result parsing. No external LLM."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agent.graph import (
    _TEMPLATE_QUERY,
    _display_needed,
    _drop_superseded_error_tables,
    _model_turn,
    _prefetch_args,
    _react_prompt,
    parse_agent_result,
)


def _tool(name: str, call_id: str) -> ToolMessage:
    return ToolMessage(
        content='{"ok": true, "tool": "%s", "trace": {"tool": "%s"}}' % (name, name),
        tool_call_id=call_id,
        name=name,
    )


def test_list_shaped_tool_message_still_proposes_confirmation():
    payload = {
        "ok": True,
        "tool": "cancel_watch",
        "data": {
            "needs_confirmation": True,
            "proposed_action": {
                "type": "cancel_watch",
                "order_id": "ORD-120",
                "watch_id": 42,
                "requires_confirmation": True,
                "confirmed": False,
            },
        },
    }
    result = {
        "messages": [
            HumanMessage(content="Cancel the watch on ORD-120."),
            AIMessage(content="", tool_calls=[{"name": "cancel_watch", "id": "1", "args": {}}]),
            ToolMessage(
                content=[{"type": "text", "text": json.dumps(payload)}],
                tool_call_id="1",
                name="cancel_watch",
            ),
            AIMessage(content="Cancellation proposed for watch 42 on ORD-120. Click Confirm to stop it."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["proposed_actions"][0]["order_id"] == "ORD-120"
    assert parsed["proposed_actions"][0]["type"] == "cancel_watch"


def test_email_confirm_box_is_restored_when_the_reply_asks_for_it():
    payload = {
        "ok": True,
        "tool": "send_email",
        "data": {
            "needs_confirmation": True,
            "draft": {"order_id": "ORD-120", "language": "en", "audience": "customer"},
        },
    }
    result = {
        "messages": [
            HumanMessage(content="Send the chase email for ORD-120."),
            AIMessage(content="", tool_calls=[{"name": "send_email", "id": "1", "args": {}}]),
            ToolMessage(content="Result:\n" + json.dumps(payload), tool_call_id="1", name="send_email"),
            AIMessage(content="The email is ready. Click Confirm to record the simulated send."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["proposed_actions"] == [
        {
            "type": "send_email",
            "order_id": "ORD-120",
            "language": "en",
            "audience": "customer",
            "requires_confirmation": True,
            "confirmed": False,
        }
    ]


def test_note_and_reminder_confirm_boxes_are_restored():
    note = {
        "ok": True,
        "tool": "add_order_note",
        "data": {
            "needs_confirmation": True,
            "order_id": "ORD-120",
            "note": "Check packing",
        },
    }
    reminder = {
        "ok": True,
        "tool": "create_reminder",
        "data": {
            "needs_confirmation": True,
            "order_id": "ORD-120",
            "remind_on": "2026-04-02",
            "message": "Check packing",
        },
    }
    note_parsed = parse_agent_result(
        {
            "messages": [
                HumanMessage(content="Note ORD-120."),
                ToolMessage(content="Result:\n" + json.dumps(note), tool_call_id="1", name="add_order_note"),
                AIMessage(content="Click Confirm to save the note."),
            ]
        },
        "thread-1",
    )
    assert note_parsed["proposed_actions"] == [
        {
            "type": "add_order_note",
            "order_id": "ORD-120",
            "note": "Check packing",
            "requires_confirmation": True,
            "confirmed": False,
        }
    ]
    reminder_parsed = parse_agent_result(
        {
            "messages": [
                HumanMessage(content="Remind me about ORD-120."),
                ToolMessage(content="Result:\n" + json.dumps(reminder), tool_call_id="1", name="create_reminder"),
                AIMessage(content="Click Confirm to save the reminder."),
            ]
        },
        "thread-1",
    )
    assert reminder_parsed["proposed_actions"] == [
        {
            "type": "create_reminder",
            "order_id": "ORD-120",
            "remind_on": "2026-04-02",
            "message": "Check packing",
            "requires_confirmation": True,
            "confirmed": False,
        }
    ]


def test_confirm_sentence_without_a_tool_does_not_invent_a_box():
    result = {
        "messages": [
            HumanMessage(content="Cancel the watch."),
            AIMessage(content="Cancellation proposed for watch 42 on ORD-120. Click Confirm to stop it."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["proposed_actions"] == []
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


def test_several_matching_orders_become_a_clarification_card():
    payload = {
        "ok": False,
        "tool": "get_order_status",
        "error": {
            "code": "AMBIGUOUS",
            "message": "17 orders match. Pick one, or type the order you mean.",
            "candidates": [
                {"order_id": "ORD-005", "product": "Scarf", "pieces": 500, "current_stage": "KNITTING"},
                {"order_id": "ORD-120", "product": "Vest", "pieces": 1500, "current_stage": "ASSEMBLY"},
            ],
        },
    }
    result = {
        "messages": [
            HumanMessage(content="How is the TrendCart order doing?"),
            AIMessage(content="", tool_calls=[{"name": "get_order_status", "id": "1", "args": {}}]),
            ToolMessage(content=json.dumps(payload), tool_call_id="1", name="get_order_status"),
            ToolMessage(
                content=json.dumps({"ok": True, "tool": "render_table", "data": {"table": {"title": "TrendCart"}}}),
                tool_call_id="2",
                name="render_table",
            ),
            AIMessage(content="TrendCart has 17 orders, so I can't identify one without guessing."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["limitation"] == "needs_clarification"
    assert parsed["tables"] == []
    assert parsed["answer"] == "17 orders match. Pick one, or type the order you mean."
    labels = [option["label"] for option in parsed["clarification"]["options"]]
    assert labels[0].startswith("Show me ORD-005")
    assert "ORD-120" in labels[1]
    assert parsed["clarification"]["other_submit"] == "Send"


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


def test_parse_agent_result_returns_chart_and_table_from_latest_turn():
    chart = {
        "type": "bar",
        "title": "Orders by stage",
        "data": [{"stage": "KNITTING", "count": 3}],
        "category_key": "stage",
        "value_keys": ["count"],
    }
    table = {
        "title": "At-risk orders",
        "columns": [{"key": "order_id", "label": "Order"}],
        "rows": [{"order_id": "ORD-120"}],
    }
    result = {
        "messages": [
            HumanMessage(content="Show the stage comparison as a chart and a table"),
            ToolMessage(
                content=json.dumps({"ok": True, "tool": "draw", "data": {"chart": chart}}),
                tool_call_id="chart-1",
                name="draw",
            ),
            ToolMessage(
                content=json.dumps({"ok": True, "tool": "render_table", "data": {"table": table}}),
                tool_call_id="table-1",
                name="render_table",
            ),
            AIMessage(content="Here is the stage comparison."),
        ]
    }
    parsed = parse_agent_result(result, "thread-1")
    assert parsed["charts"] == [chart]
    assert parsed["tables"] == [table]
    assert parsed["tools_used"] == ["draw", "render_table"]


def test_a_later_table_hides_the_failed_call_table():
    error = {
        "title": "Order lookup error",
        "columns": [{"key": "code", "label": "Code"}, {"key": "message", "label": "Message"}],
        "rows": [{"code": "INVALID_INPUT", "message": "Provide at least one filter."}],
    }
    orders = {
        "title": "All orders",
        "columns": [{"key": "customer", "label": "Customer"}],
        "rows": [{"customer": "TrendCart"}],
    }
    assert _drop_superseded_error_tables([error, orders], []) == [orders]
    assert _drop_superseded_error_tables([error], []) == [error]


def test_clarification_reply_is_wrapped_only_for_the_model():
    chosen = "I'll give you today's overall order and production snapshot."
    original = "How is sales doing?"
    wrapped = _model_turn(chosen, clarification_reply=True, original_question=original)
    assert wrapped.startswith(original)
    assert "The following is the clarification of that question:" in wrapped
    assert chosen in wrapped
    assert "The clarification decides what this question means." in wrapped
    assert _model_turn(chosen, clarification_reply=False) == chosen
    chinese = "给我今天的订单和生产快照。"
    zh = _model_turn(chinese, clarification_reply=True, original_question="销售怎么样？")
    assert zh.startswith("销售怎么样？")
    assert "以下内容是对这个问题的澄清：" in zh
    assert "以澄清为准。" in zh
    assert chinese in zh


def test_reply_is_written_before_the_display_tool():
    token = _TEMPLATE_QUERY.set("Which orders are likely to miss their due dates?")
    try:
        system = _react_prompt(
            {
                "messages": [
                    HumanMessage(content="Which orders are likely to miss their due dates?"),
                    _tool("get_orders_at_risk", "call-1"),
                ]
            }
        )[0].content
    finally:
        _TEMPLATE_QUERY.reset(token)
    assert "write the reply now" in system
    assert "Do not call draw or render_table in this message." in system
    assert "call a different registered tool" in system
    assert "MUST be exactly one tool call" not in system


def test_prefetch_runs_only_when_the_arguments_are_determined():
    assert _prefetch_args("get_morning_briefing", "How is the factory doing?") == {}
    assert _prefetch_args("get_orders_at_risk", "Which orders are at risk?") == {}
    assert _prefetch_args("trace_order", "How is ORD-120 doing?") == {"order_id": "ORD-120"}
    assert _prefetch_args("trace_order", "Compare ORD-120 and ORD-005") is None
    assert _prefetch_args("find_orders", "List TrendCart orders") is None
    assert _prefetch_args("draft_chase_email", "Email ORD-120") is None


def test_display_waits_until_a_lookup_has_rows_and_no_chart():
    turn = [
        HumanMessage(content="Which orders are at risk?"),
        _tool("get_orders_at_risk", "call-1"),
        AIMessage(content="Three orders may miss their due dates."),
    ]
    assert _display_needed(turn) is True
    turn.append(_tool("render_table", "call-2"))
    assert _display_needed(turn) is False
