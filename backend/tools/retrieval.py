"""Retrieval tools: factual lookups from the factory tables.

No judgement lives here — these functions return rows plus derived date/stage
fields computed in backend.services.calculations.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import PRODUCTION_STAGES_IN_ORDER
from backend.services.calculations import assess_order_risk, order_computed_fields
from backend.services.database import get_db
from backend.services.pace import (
    flags_with_pace_tight,
    likely_to_miss_due_dates,
    likely_to_miss_due_next_n_days,
    pace_fields,
    stage_pace_rates,
    would_miss_due_date,
)
from backend.tools.common import (
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
    lookback_working_days: Optional[int] = Field(
        default=None,
        description=(
            "Recent working days that set the pace. Omit for the 30-day median. "
            "If the manager names another window, such as the last 5 days, pass that "
            "number. The pace then uses the average daily pieces over those working days."
        ),
    )


class GetOrdersAtRiskInput(BaseModel):
    flag: Optional[str] = Field(
        default=None,
        description=(
            "Optional: OVERDUE or STALLED for those flags only. "
            "TIGHT_DEADLINE or omit for orders likely to miss a due date still ahead."
        ),
    )
    stage: Optional[str] = Field(
        default=None,
        description=(
            "Stage whose future daily output the manager fixed, e.g. ASSEMBLY. "
            "Pass with pieces_per_day. Omit both when they did not fix a rate."
        ),
    )
    pieces_per_day: Optional[float] = Field(
        default=None,
        description=(
            "Fixed pieces per working day for stage, e.g. 455. "
            "Replaces that stage's pace rate only. Other stages stay on the 30-day median, "
            "or on the named-window average when lookback_working_days is set."
        ),
    )
    lookback_working_days: Optional[int] = Field(
        default=None,
        description=(
            "Recent working days that set the pace. Omit for the 30-day median. "
            "If the manager names another window, such as the last 5 days, pass that "
            "number. The pace then uses the average daily pieces over those working days."
        ),
    )


def _reject_lookback(tool_name: str, lookback_working_days: Optional[int]) -> str | None:
    if lookback_working_days is None:
        return None
    if lookback_working_days < 1 or lookback_working_days > 60:
        return tool_error(
            tool_name,
            "INVALID_INPUT",
            "lookback_working_days must be from 1 to 60.",
        )
    return None


@tool(args_schema=GetOrderStatusInput)
def get_order_status(
    order_id: Optional[str] = None,
    customer: Optional[str] = None,
    product: Optional[str] = None,
    lookback_working_days: Optional[int] = None,
) -> str:
    """Look up one order from orders.csv.

    Pass order_id, or the customer and/or product they named.
    If several rows match, the result is AMBIGUOUS — ask which order_id.
    """
    tool_name = "get_order_status"
    try:
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

        rejected = _reject_lookback(tool_name, lookback_working_days)
        if rejected:
            return rejected
        order = rows[0]
        computed = order_computed_fields(order)
        risk = assess_order_risk(order)
        rates, pace_window = stage_pace_rates(db, lookback_working_days)
        pace = pace_fields(order, rates, rate_label=pace_window["rate_label"])
        flags = flags_with_pace_tight(list(risk["flags"]), pace)
        computed = {
            **computed,
            "is_tight_deadline": "TIGHT_DEADLINE" in flags,
            "days_left": pace["days_left"],
        }
        logger.info("get_order_status hit %s flags=%s", order["order_id"], flags)
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "order": order,
                    "computed": computed,
                    "flags": flags,
                    "pace_window": pace_window,
                },
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
                            "days_left",
                            "is_tight_deadline",
                        )
                    ],
                    "basis": (
                        "Single row from orders.csv. Date differences use factory today "
                        f"{computed['factory_today']} and skip Sundays. "
                        "TIGHT_DEADLINE: not overdue, due today through +3 calendar days, "
                        "and days_left exceeds working days until due. "
                        f"days_left = max(sum over remaining stages of pieces / {pace_window['rate_label']}, "
                        "remaining stage count)."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 — tools must not crash the agent
        logger.exception("get_order_status failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=GetOrdersAtRiskInput)
def get_orders_at_risk(
    flag: Optional[str] = None,
    stage: Optional[str] = None,
    pieces_per_day: Optional[float] = None,
    lookback_working_days: Optional[int] = None,
) -> str:
    """List orders likely to miss a due date, plus separate overdue and stalled flags.

    data.orders with no flag and no fixed rate — same rows as likely_to_miss_due_dates.
      Not overdue. Due today through +3 calendar days.
      days_left = max(sum over remaining stages of pieces / 30-day median, remaining stage count).
      Included when days_left exceeds working days until due.
    stage + pieces_per_day — the manager fixed that stage's future output.
      Replaces only that stage's 30-day median. Other stages stay on the median.
      data.orders is then every not-yet-overdue in-progress order whose days_left
      exceeds working days until due. Do not answer that hypothetical from the median.
    flag=OVERDUE or flag=STALLED — that flag only. Not the miss-due list.
    data.likely_to_miss_due_next_7_days — tomorrow through 7 calendar days ahead
      (not due today) and at least one working day short at the same pace.
      Use for "next 7 days".
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
        rejected = _reject_lookback(tool_name, lookback_working_days)
        if rejected:
            return rejected
        named_stage = (stage or "").strip()
        has_stage = bool(named_stage)
        has_rate = pieces_per_day is not None
        if has_stage != has_rate:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "Pass stage and pieces_per_day together, or omit both.",
            )
        medians, pace_window = stage_pace_rates(db, lookback_working_days)
        medians = dict(medians)
        rate_label = pace_window["rate_label"]
        assumption = None
        if has_stage:
            stage_key = named_stage.upper()
            if stage_key not in PRODUCTION_STAGES_IN_ORDER:
                return tool_error(
                    tool_name,
                    "INVALID_INPUT",
                    "stage must be KNITTING, ASSEMBLY, WASHING, or PACKING.",
                )
            if pieces_per_day <= 0:
                return tool_error(
                    tool_name,
                    "INVALID_INPUT",
                    "pieces_per_day must be greater than 0.",
                )
            medians[stage_key] = float(pieces_per_day)
            assumption = {
                "stage": stage_key,
                "pieces_per_day": float(pieces_per_day),
                "replaces": f"{rate_label} for this stage only",
            }
        in_progress = db.in_progress_orders()
        flagged: list[dict[str, Any]] = []
        for order in in_progress:
            risk = assess_order_risk(order)
            pace = pace_fields(order, medians, rate_label=rate_label)
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

        miss_due = likely_to_miss_due_dates(db, medians, rate_label=rate_label)
        miss_week = likely_to_miss_due_next_n_days(db, medians, rate_label=rate_label)
        miss_any = would_miss_due_date(db, medians, rate_label=rate_label) if assumption else []
        by_id = {row["order_id"]: row for row in flagged}
        if assumption and (flag_norm is None or flag_norm == "TIGHT_DEADLINE"):
            assessed = []
            for row in miss_any:
                card = by_id.get(row["order_id"])
                if card is None:
                    card = {
                        "order_id": row["order_id"],
                        "customer": row["customer"],
                        "product": row["product"],
                        "pieces": row["pieces"],
                        "due_date": row["due_date"],
                        "current_stage": row["current_stage"],
                        "last_activity_date": row["last_activity_date"],
                        "flags": [],
                        "rank_score": 0,
                        "computed": {},
                        "pace": row,
                    }
                else:
                    card = {**card, "pace": row}
                assessed.append(card)
        elif flag_norm is None or flag_norm == "TIGHT_DEADLINE":
            assessed = [by_id[row["order_id"]] for row in miss_due if row["order_id"] in by_id]
        else:
            assessed = [row for row in flagged if flag_norm in row["flags"]]
            assessed.sort(key=lambda r: r["rank_score"], reverse=True)
        rate_words = (
            f"the average daily pieces over the last {pace_window['lookback_working_days']} working days"
            if pace_window["statistic"] == "average"
            else "the 30-day median"
        )
        logger.info("get_orders_at_risk returned %s rows (flag=%s)", len(assessed), flag_norm)
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "count": len(assessed),
                    "flag_filter": flag_norm,
                    "assumption": assumption,
                    "pace_window": pace_window,
                    "stage_rates_pieces_per_day": medians,
                    "orders": assessed,
                    "likely_to_miss_due_dates": {
                        "count": len(miss_due),
                        "order_ids": [r["order_id"] for r in miss_due],
                        "orders": miss_due,
                        "basis": (
                            (
                                "Not the same rows as data.orders while a stage rate is fixed. "
                                "Not overdue. Due today through +3 calendar days. "
                                f"{assumption['stage']} uses {assumption['pieces_per_day']} pieces per day; "
                                f"other stages use {rate_words}."
                            )
                            if assumption
                            else (
                                "Same rows as data.orders when flag is omitted. "
                                "Not overdue. Due today through +3 calendar days. "
                                "days_left = max(sum over remaining stages of pieces / "
                                f"{rate_words}, remaining stage count). "
                                "Included when days_left exceeds working days until due."
                            )
                        ),
                    },
                    "likely_to_miss_due_next_7_days": {
                        "count": len(miss_week),
                        "order_ids": [r["order_id"] for r in miss_week],
                        "orders": miss_week,
                        "basis": (
                            "Tomorrow through 7 calendar days ahead (not due today). "
                            "Same pace formula. Requires at least 1 extra working day short."
                        ),
                    },
                    "basis": (
                        (
                            f"data.orders uses {assumption['pieces_per_day']} pieces per working day "
                            f"for {assumption['stage']} instead of that stage's pace rate. "
                            f"Other stages still use {rate_words}. "
                            "Included orders are not yet overdue and days_left exceeds "
                            "working days until due. There is no 3-day window on this list."
                        )
                        if assumption
                        else (
                            "data.orders with no flag is the miss-due list: not overdue, "
                            "due today through +3 calendar days, and days_left "
                            f"(max of pieces / {rate_words} over remaining stages "
                            "and remaining stage count) "
                            "exceeds working days until due. "
                            "flag=OVERDUE is due_date before the active factory date. "
                            "flag=STALLED is idle >= 3 working days. "
                            "Those two flags are not the miss-due list. "
                            "Next 7 days is data.likely_to_miss_due_next_7_days."
                        )
                    ),
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {
                        "status": "IN_PROGRESS",
                        "flag": flag_norm,
                        "stage": None if assumption is None else assumption["stage"],
                        "pieces_per_day": None if assumption is None else assumption["pieces_per_day"],
                    },
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
