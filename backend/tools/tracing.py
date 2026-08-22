"""Tracing tools: show the source rows and calculations behind a claim."""

from __future__ import annotations

import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.services.calculations import assess_order_risk, order_computed_fields
from backend.services.database import get_db
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)


class TraceOrderInput(BaseModel):
    order_id: str = Field(..., description="Exact order id such as ORD-120")


@tool(args_schema=TraceOrderInput)
def trace_order(order_id: str) -> str:
    """Return the source row and calculations for one order.

    Use when the manager asks "why is this order at risk?", "where did that number
    come from?", or when you have just made a factual claim about an order and
    need to attach evidence.

    Note: production_log.csv is factory-wide (date × stage), not per order.
    Per-order evidence is the orders.csv row plus derived date/stage fields.
    """
    tool_name = "trace_order"
    try:
        db = get_db()
        order = db.get_order_by_id(order_id)
        if order is None:
            return tool_error(
                tool_name,
                "NOT_FOUND",
                f"{order_id} is not in orders.csv.",
            )

        computed = order_computed_fields(order)
        risk = assess_order_risk(order)

        # production_log cannot be joined to a single order. We still return the
        # last factory-wide day so the UI can show the limitation clearly.
        production = db.production_log()
        last_date = max((row["date"] for row in production), default=None)

        logger.info("trace_order %s flags=%s", order["order_id"], risk["flags"])
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "order": order,
                    "computed": computed,
                    "risk": {
                        "at_risk": risk["at_risk"],
                        "flags": risk["flags"],
                        "basis": risk["basis"],
                    },
                    "limitations": [
                        "production_log.csv is factory-wide daily output by stage, "
                        "not a per-order history. This order's only activity timestamp "
                        f"is last_activity_date={order['last_activity_date']}.",
                        f"The production log ends on {last_date}; factory today is 2026-04-01.",
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [order],
                    "calculations": risk["calculations"]
                    + [
                        {
                            "name": name,
                            "formula": "see backend.services.calculations.order_computed_fields",
                            "result": computed[name],
                        }
                        for name in (
                            "calendar_days_until_due",
                            "working_days_until_due_inclusive",
                            "working_days_since_last_activity",
                            "remaining_stages",
                        )
                    ],
                    "basis": risk["basis"],
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("trace_order failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
