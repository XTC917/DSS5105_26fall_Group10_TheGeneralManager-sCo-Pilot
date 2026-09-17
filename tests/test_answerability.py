"""Stored-column clamp only. Tool coverage stays with the LLM verdict."""

from backend.agent.answerability import DataVerdict, ToolVerdict, apply_catalog


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


def test_tool_lookup_table_marks_find_orders_as_list_lookup():
    from backend.agent.prompts import TOOL_LOOKUP_TABLE

    assert "| find_orders |" in TOOL_LOOKUP_TABLE
    assert "List lookup" in TOOL_LOOKUP_TABLE
    assert "orders.customer" in TOOL_LOOKUP_TABLE
