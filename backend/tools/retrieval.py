"""Retrieval tools: factual lookups from the factory tables.

No judgement lives here — these functions return rows plus derived date/stage
fields computed in backend.services.calculations.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.services.calculations import assess_order_risk, order_computed_fields
from backend.services.database import get_db
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)


class GetOrderStatusInput(BaseModel):
    order_id: Optional[str] = Field(
        default=None,
        description="Exact order id such as ORD-120. Prefer this when known.",
    )
    customer: Optional[str] = Field(
        default=None,
        description="Customer name as in orders.csv, e.g. TrendCart. Case-insensitive exact match.",
    )
    product: Optional[str] = Field(
        default=None,
        description="Product name as in orders.csv, e.g. Hoodie. Case-insensitive exact match.",
    )


class GetOrdersAtRiskInput(BaseModel):
    flag: Optional[str] = Field(
        default=None,
        description="Optional filter: OVERDUE, STALLED, or TIGHT_DEADLINE. Omit to return all at-risk orders.",
    )


@tool(args_schema=GetOrderStatusInput)
def get_order_status(
    order_id: Optional[str] = None,
    customer: Optional[str] = None,
    product: Optional[str] = None,
) -> str:
    """Look up order status from orders.csv.

    Use for questions like "how is ORD-120 doing?" or "what is the TrendCart hoodie status?".
    If several rows match, the result is AMBIGUOUS — ask the manager to pick an order_id.
    Do not guess which order they mean.
    """
    tool_name = "get_order_status"
    try:
        if not order_id and not customer and not product:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "Provide order_id, customer, and/or product.",
            )

        db = get_db()
        rows = db.find_orders(order_id=order_id, customer=customer, product=product)
        filters = {
            k: v
            for k, v in {"order_id": order_id, "customer": customer, "product": product}.items()
            if v
        }

        if not rows:
            return tool_error(
                tool_name,
                "NOT_FOUND",
                "No order matches those filters in orders.csv.",
                filter=filters,
            )

        if len(rows) > 1:
            candidates = [
                {
                    "order_id": r["order_id"],
                    "customer": r["customer"],
                    "product": r["product"],
                    "pieces": r["pieces"],
                    "due_date": r["due_date"],
                    "status": r["status"],
                    "current_stage": r["current_stage"],
                }
                for r in rows
            ]
            return tool_json(
                {
                    "ok": False,
                    "tool": tool_name,
                    "error": {
                        "code": "AMBIGUOUS",
                        "message": (
                            f"{len(rows)} orders match. Ask the manager to specify an order_id. "
                            "Do not pick one yourself."
                        ),
                        "filter": filters,
                        "candidates": candidates,
                    },
                }
            )

        order = rows[0]
        computed = order_computed_fields(order)
        logger.info("get_order_status hit %s", order["order_id"])
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {"order": order, "computed": computed},
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": filters,
                    "rows": [order],
                    "calculations": [
                        {
                            "name": name,
                            "result": computed[name],
                        }
                        for name in (
                            "calendar_days_until_due",
                            "working_days_until_due_inclusive",
                            "working_days_since_last_activity",
                            "remaining_stage_count",
                        )
                    ],
                    "basis": (
                        "Single row from orders.csv. Date differences use factory today "
                        "2026-04-01 and skip Sundays."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 — tools must not crash the agent
        logger.exception("get_order_status failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=GetOrdersAtRiskInput)
def get_orders_at_risk(flag: Optional[str] = None) -> str:
    """List in-progress orders that are overdue, stalled, or on a tight deadline.

    Risk flags are computed in Python (see assess_order_risk), not by the LLM:
    - OVERDUE: due_date < 2026-04-01
    - STALLED: idle at least 3 working days
    - TIGHT_DEADLINE: remaining working days < remaining stages

    Use this when the manager asks which orders are at risk, late, stuck, or slipping.
    """
    tool_name = "get_orders_at_risk"
    try:
        allowed = {None, "OVERDUE", "STALLED", "TIGHT_DEADLINE"}
        flag_norm = flag.upper() if flag else None
        if flag_norm not in allowed:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "flag must be OVERDUE, STALLED, TIGHT_DEADLINE, or omitted.",
            )

        db = get_db()
        in_progress = db.in_progress_orders()
        assessed: list[dict[str, Any]] = []
        for order in in_progress:
            risk = assess_order_risk(order)
            if not risk["at_risk"]:
                continue
            if flag_norm and flag_norm not in risk["flags"]:
                continue
            assessed.append(
                {
                    "order_id": order["order_id"],
                    "customer": order["customer"],
                    "product": order["product"],
                    "pieces": order["pieces"],
                    "due_date": order["due_date"],
                    "current_stage": order["current_stage"],
                    "last_activity_date": order["last_activity_date"],
                    "flags": risk["flags"],
                    "rank_score": risk["rank_score"],
                    "computed": risk["computed"],
                }
            )

        assessed.sort(key=lambda r: r["rank_score"], reverse=True)
        logger.info("get_orders_at_risk returned %s rows (flag=%s)", len(assessed), flag_norm)
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "count": len(assessed),
                    "flag_filter": flag_norm,
                    "orders": assessed,
                    "basis": (
                        "OVERDUE: due_date < 2026-04-01. "
                        "STALLED: working days since last_activity_date >= 3. "
                        "TIGHT_DEADLINE: working days until due < remaining stage count. "
                        "Only IN_PROGRESS orders. Ranked overdue first."
                    ),
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {"status": "IN_PROGRESS", "flag": flag_norm},
                    "rows": [
                        {
                            "order_id": r["order_id"],
                            "flags": r["flags"],
                            "due_date": r["due_date"],
                            "last_activity_date": r["last_activity_date"],
                            "current_stage": r["current_stage"],
                        }
                        for r in assessed
                    ],
                    "calculations": [],
                    "basis": "See data.basis. Full per-order arithmetic is in each order's computed fields.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_orders_at_risk failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
