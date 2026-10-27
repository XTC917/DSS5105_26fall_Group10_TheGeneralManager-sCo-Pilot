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


def test_wording_change_does_not_need_a_tool():
    from backend.agent.answerability import _tools_from_payload

    verdict = _tools_from_payload(
        {
            "needs_tool": False,
            "has_tool": False,
            "tool": None,
            "reason": "The previous result only needs to be restated.",
        }
    )
    assert verdict.needs_tool is False
    assert verdict.has_tool is False
    assert verdict.tool is None


def test_focus_today_is_pinned_to_three_clarifications():
    from backend.agent.answerability import pinned_clarification

    gate = pinned_clarification("Is there anything I should focus on today?")
    assert gate is not None
    assert gate.limitation == "needs_clarification"
    labels = [option["label"] for option in gate.clarification["options"]]
    assert labels == [
        "You will be told which orders are the first, second, and third priorities today.",
        "You will be given today's full morning snapshot of at-risk orders, work in progress, stage output, and suspended workshops.",
        "You will be told which production queues and stages currently need attention.",
    ]
    assert gate.tools.readings == [
        "get_today_priority",
        "get_morning_briefing",
        "discover_factory_issues",
    ]
    assert pinned_clarification("What should we prioritize today?") is None


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
    assert card["options"][0]["message"] == "TrendCart orders in progress"


def test_conflicting_order_terms_stay_two_readings():
    from backend.agent.answerability import _AMBIGUITY_SYSTEM, interpretation_clarification

    assert "cannot describe the same orders" in _AMBIGUITY_SYSTEM
    assert "asking back to the user" in _AMBIGUITY_SYSTEM
    card = interpretation_clarification(
        "Show completed orders and their overdue time.",
        [
            {
                "tool": "find_orders",
                "label": "Show the completed orders.",
                "message": "Show the completed orders.",
            },
            {
                "tool": "get_orders_at_risk",
                "label": "Show the orders that are overdue.",
                "message": "Show the orders that are overdue.",
            },
        ],
    )
    assert [row["label"] for row in card["options"]] == [
        "Show the completed orders.",
        "Show the orders that are overdue.",
    ]


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
        "Look at how each order is doing, including status and due date.",
        "Look at how many pieces each stage finished.",
        "Look at how much each workshop can make in a day.",
    ]
    assert card["other_placeholder"] == "Other"
    assert card["other_submit"] == "Send"
    assert "order status" in card["options"][0]["message"]


def test_scope_clarification_uses_chinese_for_chinese_questions():
    card = scope_clarification("销售不在表里。", "销售怎么样？")
    assert [row["label"] for row in card["options"]] == [
        "看看各订单现在的状态和交期。",
        "看看各阶段完成了多少件。",
        "看看每个车间每天能做多少。",
    ]
    assert card["other_placeholder"] == "其他"
    assert card["other_submit"] == "发送"


def test_clarification_reply_judges_the_chosen_lookup():
    from backend.agent.answerability import _CHOSEN_READING, _data_system

    assert "already chose" not in _data_system(False)
    assert _CHOSEN_READING in _data_system(True)


def test_tool_coverage_allows_a_combination():
    from backend.agent.answerability import _TOOL_SYSTEM

    assert "combination of registered tools" in _TOOL_SYSTEM
    assert "only if a registered tool returns that fact" not in _TOOL_SYSTEM


def test_tool_lookup_table_marks_find_orders_as_list_lookup():
    from backend.agent.prompts import TOOL_LOOKUP_TABLE

    assert "| find_orders |" in TOOL_LOOKUP_TABLE
    assert "List lookup" in TOOL_LOOKUP_TABLE
    assert "orders.customer" in TOOL_LOOKUP_TABLE


def test_method_only_card_stays_clickable_options():
    from backend.agent.answerability import combine_clarification

    method = {
        "prompt": "Which of these did you mean?",
        "options": [
            {"label": "Completed orders.", "message": "Completed orders."},
            {"label": "Overdue orders.", "message": "Overdue orders."},
        ],
    }
    card = combine_clarification(method, [], "Show completed orders and their overdue time.")
    assert card["options"][0]["label"] == "Completed orders."
    assert "questions" not in card


def test_term_questions_join_a_method_without_replacing_it():
    from backend.agent.answerability import _terms_from_payload, combine_clarification

    method = {
        "prompt": "Which reading?",
        "options": [
            {"label": "At-risk orders.", "message": "At-risk orders."},
            {"label": "Overdue orders.", "message": "Overdue orders."},
        ],
    }
    terms = _terms_from_payload(
        {
            "terms": [
                {
                    "term": "large",
                    "prompt": "What piece count counts as large?",
                    "options": [
                        {
                            "tool": "find_orders + filter_rows",
                            "label": "At least 1,000 pieces",
                            "message": "pieces >= 1000",
                        },
                        {
                            "tool": "find_orders + filter_rows",
                            "label": "At least the median",
                            "message": "pieces at or above the median",
                        },
                        {
                            "tool": "not_a_tool",
                            "label": "By revenue",
                            "message": "Use revenue",
                        },
                    ],
                }
            ]
        }
    )
    card = combine_clarification(method, terms, "Are any large orders at high risk?")
    assert [item["id"] for item in card["questions"]] == ["method", "term-0"]
    assert [item["label"] for item in card["questions"][1]["options"]] == [
        "At least 1,000 pieces",
        "At least the median",
    ]
    assert "options" not in card


def test_clarification_drops_readings_the_tools_cannot_do():
    from backend.agent.answerability import _clarification_catalog, interpretation_clarification
    from backend.tools.registry import MVP_TOOLS

    catalog = _clarification_catalog()
    for tool in MVP_TOOLS:
        assert tool.name in catalog
    card = interpretation_clarification(
        "Show me the large orders.",
        [
            {
                "tool": "find_orders + filter_rows",
                "label": "Show orders with at least 1,000 pieces.",
                "message": "Show orders with at least 1,000 pieces.",
            },
            {
                "tool": "not_a_tool",
                "label": "Show orders by revenue.",
                "message": "Show orders by revenue.",
            },
            {
                "tool": "draw",
                "label": "Draw a chart with no rows.",
                "message": "Draw a chart with no rows.",
            },
        ],
    )
    assert card is None

