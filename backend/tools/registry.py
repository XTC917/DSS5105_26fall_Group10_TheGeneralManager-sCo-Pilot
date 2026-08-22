"""The four tools registered with the LangGraph agent in this MVP."""

from __future__ import annotations

from backend.tools.judgement import check_feasibility
from backend.tools.retrieval import get_order_status, get_orders_at_risk
from backend.tools.tracing import trace_order

MVP_TOOLS = [
    get_order_status,
    get_orders_at_risk,
    trace_order,
    check_feasibility,
]
