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
from backend.services.pace import (
    flags_with_pace_tight,
    likely_to_miss_due_dates,
    likely_to_miss_due_next_n_days,
    pace_fields,
    stage_medians,
)
from backend.tools.common import (
    order_id_named_by_manager,
    several_orders_message,
    tool_error,
    tool_json,
    ungrounded_order_error,
    value_named_by_manager,
)

logger = logging.getLogger(__name__)


class GetOrderStatusInput(BaseModel):
    order_id: Optional[str] = Field(
        default=None,
        description="Order id the manager wrote. Omit when they did not write one.",
    )
    customer: Optional[str] = Field(
        default=None,
        description="Customer name as written by the manager. Case-insensitive exact match.",
    )
    product: Optional[str] = Field(
        default=None,
        description="Product name as in orders.csv, e.g. Hoodie. Case-insensitive exact match.",
    )


class GetOrdersAtRiskInput(BaseModel):
    flag: Optional[str] = Field(
        default=None,
        description=(
            "Optional: OVERDUE or STALLED for those flags only. "
            "TIGHT_DEADLINE or omit for orders likely to miss a due date still ahead."
        ),
    )


@tool(args_schema=GetOrderStatusInput)
def get_order_status(
    order_id: Optional[str] = None,
    customer: Optional[str] = None,
    product: Optional[str] = None,
) -> str:
    """Look up one order from orders.csv.

    Pass order_id only when the manager wrote that id.
    Otherwise pass the customer and/or product they named.
    If several rows match, the result is AMBIGUOUS — ask which order_id.
    Do not choose an id from an example or an answer template.
    """
    tool_name = "get_order_status"
    try:
        if order_id and not order_id_named_by_manager(order_id):
            return ungrounded_order_error(tool_name, order_id)
        for spoken in (customer, product):
            if spoken and not value_named_by_manager(spoken):
                return ungrounded_order_error(tool_name, spoken)
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
                        "message": several_orders_message(len(rows)),
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
    """List orders likely to miss a due date, plus separate overdue and stalled flags.

    data.orders with no flag — same rows as likely_to_miss_due_dates.
      Not overdue. Due today through +3 calendar days.
      days_left = max(sum over remaining stages of pieces / 30-day median, remaining stage count).
      Included when days_left exceeds working days until due.
    flag=OVERDUE or flag=STALLED — that flag only. Not the miss-due list.
    data.likely_to_miss_due_next_7_days — due in 1–7 calendar days and at least
      one working day short at the same pace. Use for "next 7 days".
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
        medians = stage_medians(db)
        in_progress = db.in_progress_orders()
        flagged: list[dict[str, Any]] = []
        for order in in_progress:
            risk = assess_order_risk(order)
            pace = pace_fields(order, medians)
            flags = flags_with_pace_tight(list(risk["flags"]), pace)
            if not flags:
                continue
            flagged.append(
                {
                    "order_id": order["order_id"],
                    "customer": order["customer"],
                    "product": order["product"],
                    "pieces": order["pieces"],
                    "due_date": order["due_date"],
                    "current_stage": order["current_stage"],
                    "last_activity_date": order["last_activity_date"],
                    "flags": flags,
                    "rank_score": risk["rank_score"],
                    "computed": risk["computed"],
                    "pace": pace,
                }
            )

        miss_due = likely_to_miss_due_dates(db)
        miss_week = likely_to_miss_due_next_n_days(db)
        by_id = {row["order_id"]: row for row in flagged}
        if flag_norm is None or flag_norm == "TIGHT_DEADLINE":
            assessed = [by_id[row["order_id"]] for row in miss_due if row["order_id"] in by_id]
        else:
            assessed = [row for row in flagged if flag_norm in row["flags"]]
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
                    "likely_to_miss_due_dates": {
                        "count": len(miss_due),
                        "order_ids": [r["order_id"] for r in miss_due],
                        "orders": miss_due,
                        "basis": (
                            "Same rows as data.orders when flag is omitted. "
                            "Not overdue. Due today through +3 calendar days. "
                            "days_left = max(sum over remaining stages of pieces / "
                            "30-day median pieces_completed, remaining stage count). "
                            "Included when days_left exceeds working days until due."
                        ),
                    },
                    "likely_to_miss_due_next_7_days": {
                        "count": len(miss_week),
                        "order_ids": [r["order_id"] for r in miss_week],
                        "orders": miss_week,
                        "basis": (
                            "Due in 1–7 calendar days (not due today). "
                            "Same pace formula. Requires at least 1 extra working day short."
                        ),
                    },
                    "basis": (
                        "data.orders with no flag is the miss-due list: not overdue, "
                        "due today through +3 calendar days, and days_left "
                        "(max of pieces / 30-day stage median over remaining stages "
                        "and remaining stage count) "
                        "exceeds working days until due. "
                        "flag=OVERDUE is due_date < 2026-04-01. "
                        "flag=STALLED is idle >= 3 working days. "
                        "Those two flags are not the miss-due list. "
                        "Next 7 days is data.likely_to_miss_due_next_7_days."
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
