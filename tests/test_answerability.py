"""Stored-column clamp only. Tool coverage stays with the LLM verdict."""

from backend.agent.answerability import (
    DataVerdict,
    ToolVerdict,
    apply_catalog,
    scope_clarification,
)


def test_missing_data_clears_tool_even_if_llm_claimed_one():
    data, tools = apply_catalog(
        DataVerdict(kind="fact", stored=True, table=None, column="selling_price"),
        ToolVerdict(has_tool=True, tool="find_orders"),
    )
    assert data.stored is False
    assert tools.has_tool is False
    assert tools.tool is None


def test_stored_column_keeps_llm_has_tool_true():
    data, tools = apply_catalog(
        DataVerdict(kind="fact", stored=True, table="orders", column="current_stage"),
        ToolVerdict(has_tool=True, tool="get_order_status"),
    )
    assert data.stored is True
    assert tools.has_tool is True
    assert tools.tool == "get_order_status"


def test_stored_column_keeps_llm_has_tool_false():
    data, tools = apply_catalog(
        DataVerdict(
            kind="fact",
            stored=True,
            table="production_log",
            column="pieces_completed",
        ),
        ToolVerdict(has_tool=False, tool=None),
    )
    assert data.stored is True
    assert tools.has_tool is False
    assert tools.tool is None


def test_does_not_remap_tool_names():
    data, tools = apply_catalog(
        DataVerdict(
            kind="fact",
            stored=True,
            table="production_log",
            column="pieces_completed",
        ),
        ToolVerdict(has_tool=True, tool="find_orders"),
    )
    assert tools.has_tool is True
    assert tools.tool == "find_orders"


def test_workshop_stored_does_not_force_no_tool():
    data, tools = apply_catalog(
        DataVerdict(kind="fact", stored=True, table="workshops", column="cost_per_piece"),
        ToolVerdict(has_tool=False, tool=None),
    )
    assert data.stored is True
    assert tools.has_tool is False


def test_action_kind_keeps_llm_tool_choice():
    data, tools = apply_catalog(
        DataVerdict(kind="action", stored=False),
        ToolVerdict(has_tool=True, tool="draft_chase_email"),
    )
    assert data.stored is True
    assert tools.has_tool is True
    assert tools.tool == "draft_chase_email"


def test_risk_follow_up_keeps_previous_orders(db):
    from backend.agent.answerability import continues_prior_rows

    prior = '{"orders": [{"order_id": "ORD-015"}]}'
    assert continues_prior_rows("are their any at risk?", prior) is True
    assert continues_prior_rows("How is the TrendCart order doing?", prior) is False
    assert continues_prior_rows("are their any at risk?", "") is False


def test_named_customer_is_an_order_field(db):
    from backend.agent.answerability import named_order_field

    assert named_order_field("How is the TrendCart order doing?") == ("orders", "customer")
    assert named_order_field("How is ORD-120 doing?") == ("orders", "order_id")
    assert named_order_field("How is the sales doing?") is None


def test_different_answers_keep_the_models_wording():
    from backend.agent.answerability import interpretation_clarification

    card = interpretation_clarification(
        "How is the TrendCart order doing?",
        [
            {
                "tool": "find_orders",
                "label": "TrendCart orders in progress",
                "message": "How are TrendCart's in-progress orders doing?",
            },
            {
                "tool": "get_orders_at_risk",
                "label": "TrendCart orders that may miss due dates",
                "message": "Which TrendCart orders may miss their due dates?",
            },
        ],
        ask="For TrendCart, which of these did you mean?",
    )
    assert card is not None
    assert card["prompt"] == "For TrendCart, which of these did you mean?"
    assert card["other_placeholder"] == "Other"
    assert card["options"][0]["label"] == "TrendCart orders in progress"
    assert card["options"][0]["message"] == "How are TrendCart's in-progress orders doing?"


def test_one_row_and_the_list_are_one_answer():
    from backend.agent.answerability import interpretation_clarification

    assert (
        interpretation_clarification(
            "How is the TrendCart order doing?",
            [
                {
                    "tool": "get_order_status",
                    "label": "One TrendCart order",
                    "message": "Which TrendCart order should I open?",
                },
                {
                    "tool": "find_orders",
                    "label": "All TrendCart orders",
                    "message": "List every TrendCart order.",
                },
            ],
        )
        is None
    )


def test_scope_clarification_offers_real_scopes_and_other():
    card = scope_clarification("Sales performance is not tracked.", "How is the sales doing?")
    assert card["other_placeholder"] == "Other"
    assert "stored column" not in card["prompt"]
    assert "Which of these" in card["prompt"]
    assert [row["label"] for row in card["options"]] == [
        "Orders",
        "Output",
        "Workshop capacity",
    ]
    assert card["other_placeholder"] == "Other"
    assert card["other_submit"] == "Send"
    assert "order status" in card["options"][0]["message"]


def test_scope_clarification_uses_chinese_for_chinese_questions():
    card = scope_clarification("销售不在表里。", "销售怎么样？")
    assert [row["label"] for row in card["options"]] == ["订单", "产量", "车间产能"]
    assert card["other_placeholder"] == "其他"
    assert card["other_submit"] == "发送"


def test_tool_lookup_table_marks_find_orders_as_list_lookup():
    from backend.agent.prompts import TOOL_LOOKUP_TABLE

    assert "| find_orders |" in TOOL_LOOKUP_TABLE
    assert "List lookup" in TOOL_LOOKUP_TABLE
    assert "orders.customer" in TOOL_LOOKUP_TABLE
