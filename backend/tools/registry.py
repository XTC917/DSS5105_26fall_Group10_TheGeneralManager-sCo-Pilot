"""Tools registered with the LangGraph agent."""

from __future__ import annotations

from backend.tools.actions import (
    add_order_note,
    create_reminder,
    draft_chase_email,
    get_recent_actions,
    send_email,
)
from backend.tools.briefing import get_morning_briefing
from backend.tools.discovery import discover_factory_issues, find_orders
from backend.tools.judgement import check_feasibility
from backend.tools.retrieval import get_order_status, get_orders_at_risk
from backend.tools.tracing import trace_order
from backend.tools.watches import cancel_watch, create_watch, list_watches

MVP_TOOLS = [
    get_order_status,
    get_orders_at_risk,
    get_morning_briefing,
    find_orders,
    discover_factory_issues,
    trace_order,
    check_feasibility,
    draft_chase_email,
    send_email,
    add_order_note,
    create_reminder,
    create_watch,
    list_watches,
    cancel_watch,
    get_recent_actions,
]
