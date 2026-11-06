"""Tracing tools: show the source rows and calculations behind a claim."""

from __future__ import annotations

import logging
import math
import statistics

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import factory_date
from backend.services.calculations import (
    assess_order_risk,
    calendar_days_between,
    order_computed_fields,
    parse_iso_date,
)
from backend.services.database import get_db
from backend.services.pace import flags_with_pace_tight, pace_fields, snapshot_timeline, stage_medians
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)


class TraceOrderInput(BaseModel):
    order_id: str = Field(..., description="Order id the manager wrote.")


@tool(args_schema=TraceOrderInput)
def trace_order(order_id: str) -> str:
    """Return the source row, snapshot stage history, pace estimate, and risk flags.

    Use when the manager asks why an order is risky or to trace its situation.
    Stage history comes from app.snapshot (entry date per stage), not production_log.
    Remaining work days are the max of the pace estimate and the remaining stage count.
    """
    tool_name = "trace_order"
    try:
        if not order_id_named_by_manager(order_id):
            return ungrounded_order_error(tool_name, order_id)
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
        medians = stage_medians(db)
        pace = pace_fields(order, medians)
        flags = flags_with_pace_tight(list(risk["flags"]), pace)
        snap = snapshot_timeline(db, order["order_id"])
        consider_workshop = bool(
            computed.get("is_overdue")
            and (pace["estimated_remaining_working_days"] or 0) >= 5
        )

        production = db.production_log()
        last_date = max((row["date"] for row in production), default=None)

        logger.info("trace_order %s flags=%s", order["order_id"], flags)
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "order": order,
                    "computed": computed,
                    "pace": pace,
                    "snapshot": snap,
                    "consider_external_workshop": consider_workshop,
                    "risk": {
                        "at_risk": bool(flags),
                        "flags": flags,
                        "basis": (
                            "OVERDUE: due_date before the active factory date. "
                            "STALLED: idle >= 3 working days. "
                            "TIGHT_DEADLINE: not overdue, due within 3 calendar days, "
                            "and days_left exceeds working days until due."
                        ),
                    },
                    "limitations": [
                        "production_log.csv is factory-wide daily output by stage, "
                        "not a per-order history. Per-order stage entry dates are "
                        f"from app.snapshot. last_activity_date={order['last_activity_date']}.",
                        f"The production log ends on {last_date}; factory today is {computed['factory_today']}.",
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [order],
                    "calculations": [
                        row
                        for row in risk["calculations"]
                        if row.get("name") != "tight_deadline"
                    ]
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
                    ]
                    + [
                        {
                            "name": "estimated_remaining_working_days",
                            "formula": pace["formula"],
                            "result": pace["estimated_remaining_working_days"],
                        },
                        {
                            "name": "calendar_days_order_to_first_production",
                            "formula": "first snapshot stage that is not ORDERED minus order_date",
                            "result": snap["calendar_days_order_to_first_production"],
                        },
                    ],
                    "basis": (
                        "OVERDUE: due_date before the active factory date. "
                        "STALLED: idle >= 3 working days. "
                        "TIGHT_DEADLINE: not overdue, due within 3 calendar days, "
                        "and days_left exceeds working days until due. "
                        "days_left = max(sum over remaining stages of pieces / 30-day stage median, remaining stage count)."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("trace_order failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


def _one_decimal(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 1)


def _stage_spans(history: list[dict]) -> list[dict]:
    spans = []
    for index, row in enumerate(history):
        start = parse_iso_date(row.get("date"))
        nxt = history[index + 1] if index + 1 < len(history) else None
        end = parse_iso_date(nxt.get("date")) if nxt else None
        spans.append(
            {
                "stage": row.get("stage"),
                "entry_date": row.get("date"),
                "calendar_days_until_next": (
                    calendar_days_between(start, end) if start and end else None
                ),
            }
        )
    return spans


def _cycle_days(row: dict) -> int | None:
    start = parse_iso_date(row.get("order_date"))
    end = parse_iso_date(row.get("completed_date"))
    if start is None or end is None:
        return None
    return calendar_days_between(start, end)


@tool(args_schema=TraceOrderInput)
def compare_order_progress(order_id: str) -> str:
    """Compare one order with completed orders of the same category and similar size.

    Similar size is 80% to 120% of this order's pieces. The typical cycle is the
    median calendar days from order_date to completed_date among those peers.
    Use for "progressed normally" against the same category and a similar size.
    """
    tool_name = "compare_order_progress"
    try:
        if not order_id_named_by_manager(order_id):
            return ungrounded_order_error(tool_name, order_id)
        db = get_db()
        order = db.get_order_by_id(order_id)
        if order is None:
            return tool_error(tool_name, "NOT_FOUND", f"{order_id} is not in orders.csv.")

        pieces = int(order["pieces"])
        low = math.floor(pieces * 0.8)
        high = math.ceil(pieces * 1.2)
        today = factory_date()
        order_date = parse_iso_date(order.get("order_date"))
        elapsed = calendar_days_between(order_date, today) if order_date else None
        history = db.order_snapshot_history(order["order_id"])
        snap = snapshot_timeline(db, order["order_id"])

        peers = []
        for row in db.find_orders(category=order["category"]):
            if str(row["order_id"]).upper() == str(order["order_id"]).upper():
                continue
            if not (low <= int(row["pieces"]) <= high):
                continue
            cycle = _cycle_days(row) if row.get("status") == "COMPLETE" else None
            peers.append(
                {
                    "order_id": row["order_id"],
                    "product": row["product"],
                    "pieces": int(row["pieces"]),
                    "status": row["status"],
                    "order_date": str(row["order_date"]),
                    "completed_date": None if row.get("completed_date") is None else str(row["completed_date"]),
                    "cycle_calendar_days": cycle,
                }
            )

        completed = [row for row in peers if row["cycle_calendar_days"] is not None]
        same_product = [row for row in completed if row["product"] == order["product"]]
        cycles = [row["cycle_calendar_days"] for row in completed]
        product_cycles = [row["cycle_calendar_days"] for row in same_product]
        median = _one_decimal(statistics.median(cycles)) if cycles else None
        product_median = _one_decimal(statistics.median(product_cycles)) if product_cycles else None
        if median is None or elapsed is None:
            verdict = "no_completed_peers"
        elif order.get("status") == "COMPLETE":
            verdict = "finished_within_typical_cycle" if elapsed <= median else "finished_slower_than_typical_cycle"
        else:
            verdict = "within_typical_cycle" if elapsed <= median else "slower_than_typical_cycle"

        peer_stage_rows = 0
        for row in peers:
            extra = [
                item
                for item in db.order_snapshot_history(row["order_id"])
                if item.get("stage") not in {"ORDERED", "COMPLETE"}
            ]
            if extra:
                peer_stage_rows += 1

        logger.info(
            "compare_order_progress %s peers=%s verdict=%s",
            order["order_id"],
            len(completed),
            verdict,
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "subject": {
                        "order_id": order["order_id"],
                        "product": order["product"],
                        "category": order["category"],
                        "pieces": pieces,
                        "status": order["status"],
                        "current_stage": order["current_stage"],
                        "order_date": snap["order_date"],
                        "elapsed_calendar_days": elapsed,
                        "calendar_days_order_to_first_production": snap[
                            "calendar_days_order_to_first_production"
                        ],
                        "stage_spans": _stage_spans(history),
                    },
                    "size_band": {
                        "min_pieces": low,
                        "max_pieces": high,
                        "rule": "80% to 120% of this order's pieces, inclusive",
                    },
                    "peers": peers,
                    "completed_peer_count": len(completed),
                    "same_product_completed_count": len(same_product),
                    "cycle_calendar_days": {
                        "median": median,
                        "min": min(cycles) if cycles else None,
                        "max": max(cycles) if cycles else None,
                        "same_product_median": product_median,
                    },
                    "calendar_days_versus_median": (
                        None if median is None or elapsed is None else _one_decimal(elapsed - median)
                    ),
                    "verdict": verdict,
                    "peer_stage_history_count": peer_stage_rows,
                    "limitations": [
                        "Similar size is 80% to 120% of this order's pieces. "
                        "Same category is orders.category.",
                        "The typical cycle is the median calendar days from order_date "
                        "to completed_date among completed peers. In-progress peers are listed "
                        "and are not in that median.",
                        "Peer stage-by-stage durations are omitted when a peer snapshot "
                        "has no stage other than ORDERED or COMPLETE.",
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {
                        "order_id": order["order_id"],
                        "category": order["category"],
                        "min_pieces": low,
                        "max_pieces": high,
                    },
                    "rows": [order, *peers],
                    "calculations": [
                        {
                            "name": "elapsed_calendar_days",
                            "formula": "factory date minus order_date",
                            "result": elapsed,
                        },
                        {
                            "name": "peer_cycle_median",
                            "formula": "median of completed peer cycle calendar days",
                            "result": median,
                        },
                        {"name": "verdict", "formula": "elapsed compared with the peer median", "result": verdict},
                    ],
                    "basis": (
                        "Same category is orders.category. Similar size is 80% to 120% of pieces. "
                        "A completed peer's cycle is completed_date minus order_date."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("compare_order_progress failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
