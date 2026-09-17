"""Pace estimates: remaining work vs 30-day stage throughput.

days_needed = sum over remaining stages of pieces / stage_30day_median.
Medians are the same lookback as feasibility / briefing (not LLM arithmetic).
"""

from __future__ import annotations

from typing import Any

from backend.config import PRODUCTION_STAGES_IN_ORDER, STAGE_COMPLETE
from backend.services.calculations import (
    calendar_days_between,
    order_computed_fields,
    parse_iso_date,
    remaining_stages,
)
from backend.services.database import FactoryDB
from backend.services.feasibility import stage_throughput_medians

# Immediate "will miss due" window: due today through +3 calendar days.
MISS_DUE_CALENDAR_HORIZON = 3
# "Next 7 days" excludes due-today and barely-short orders (slack < 1 day).
NEXT_WEEK_MIN_CALENDAR_DAYS = 1
NEXT_WEEK_MAX_CALENDAR_DAYS = 7
PACE_SLACK_DAYS = 1.0
# Overdue and already at PACKING, or < 1 remaining estimated day.
NEAR_COMPLETE_DAYS = 1.0
# Overdue with at least this many calendar days late (and not near-complete).
URGENT_OVERDUE_MIN_LATE_DAYS = 3


def stage_medians(db: FactoryDB) -> dict[str, float]:
    raw = stage_throughput_medians(db)["medians_pieces_per_working_day"]
    return {stage: float(raw[stage]) for stage in PRODUCTION_STAGES_IN_ORDER if raw.get(stage)}


def estimated_remaining_working_days(
    pieces: int,
    stages: list[str],
    medians: dict[str, float],
) -> float | None:
    """sum_s pieces / median_s for remaining production stages."""
    if not stages or pieces <= 0:
        return 0.0 if stages == [] else None
    total = 0.0
    for stage in stages:
        if stage == STAGE_COMPLETE:
            continue
        median = medians.get(stage)
        if not median:
            return None
        total += pieces / median
    return round(total, 1)


def pace_fields(order: dict[str, Any], medians: dict[str, float]) -> dict[str, Any]:
    computed = order_computed_fields(order)
    stages = remaining_stages(order.get("current_stage") or "")
    pieces = int(order.get("pieces") or 0)
    estimated = estimated_remaining_working_days(pieces, stages, medians)
    working = computed["working_days_until_due_inclusive"]
    calendar = computed["calendar_days_until_due"]
    slack = None
    if estimated is not None and working is not None:
        slack = round(estimated - working, 1)
    return {
        "order_id": order["order_id"],
        "customer": order["customer"],
        "product": order["product"],
        "pieces": pieces,
        "due_date": order["due_date"],
        "order_date": order.get("order_date"),
        "current_stage": order["current_stage"],
        "last_activity_date": order["last_activity_date"],
        "status": order.get("status"),
        "calendar_days_until_due": calendar,
        "working_days_until_due_inclusive": working,
        "remaining_stages": stages,
        "remaining_stage_count": len(stages),
        "estimated_remaining_working_days": estimated,
        "pace_slack_working_days": slack,
        "formula": (
            "estimated_remaining_working_days = sum_over_remaining_stages "
            "pieces / 30-day_median(stage)"
        ),
    }


def _is_pace_miss(row: dict[str, Any], *, min_slack: float = 0.0) -> bool:
    est = row["estimated_remaining_working_days"]
    working = row["working_days_until_due_inclusive"]
    if est is None or working is None:
        return False
    if row["calendar_days_until_due"] is not None and row["calendar_days_until_due"] < 0:
        return False
    return est - working >= min_slack and est > working


def likely_to_miss_due_dates(db: FactoryDB) -> list[dict[str, Any]]:
    """Not overdue; due within 3 calendar days; cannot finish at 30-day stage pace."""
    medians = stage_medians(db)
    rows = []
    for order in db.in_progress_orders():
        row = pace_fields(order, medians)
        cal = row["calendar_days_until_due"]
        if cal is None or cal < 0 or cal > MISS_DUE_CALENDAR_HORIZON:
            continue
        if _is_pace_miss(row, min_slack=0.0):
            rows.append(row)
    rows.sort(key=lambda r: (r["calendar_days_until_due"], -r["estimated_remaining_working_days"]))
    return rows


def likely_to_miss_due_next_n_days(db: FactoryDB) -> list[dict[str, Any]]:
    """Due in 1–7 calendar days and at least one working day short at current pace."""
    medians = stage_medians(db)
    rows = []
    for order in db.in_progress_orders():
        row = pace_fields(order, medians)
        cal = row["calendar_days_until_due"]
        if cal is None or cal < NEXT_WEEK_MIN_CALENDAR_DAYS or cal > NEXT_WEEK_MAX_CALENDAR_DAYS:
            continue
        if _is_pace_miss(row, min_slack=PACE_SLACK_DAYS):
            rows.append(row)
    rows.sort(key=lambda r: (r["calendar_days_until_due"], -r["estimated_remaining_working_days"]))
    return rows


def today_priority(db: FactoryDB) -> dict[str, Any]:
    """Three buckets for 'what should we prioritize today?'."""
    medians = stage_medians(db)
    first: list[dict[str, Any]] = []
    second: list[dict[str, Any]] = []
    third: list[dict[str, Any]] = []
    for order in db.in_progress_orders():
        row = pace_fields(order, medians)
        cal = row["calendar_days_until_due"]
        overdue = bool(cal is not None and cal < 0)
        late_days = abs(cal) if overdue else 0
        packing = row["current_stage"] == "PACKING"
        near = packing or (
            row["estimated_remaining_working_days"] is not None
            and row["estimated_remaining_working_days"] < NEAR_COMPLETE_DAYS
        )
        if overdue and near:
            first.append(row)
        elif (cal == 0) or (overdue and late_days >= URGENT_OVERDUE_MIN_LATE_DAYS and not near):
            second.append(row)
        elif (
            not overdue
            and cal is not None
            and 1 <= cal <= MISS_DUE_CALENDAR_HORIZON
            and _is_pace_miss(row, min_slack=0.0)
        ):
            third.append(row)
    first.sort(key=lambda r: r["calendar_days_until_due"])  # more overdue first (more negative)
    second.sort(key=lambda r: (0 if r["calendar_days_until_due"] == 0 else 1, r["calendar_days_until_due"]))
    third.sort(key=lambda r: r["calendar_days_until_due"])
    return {
        "1st_priority": first,
        "2nd_priority": second,
        "3rd_priority": third,
        "rule": (
            "1st: overdue and close to done (PACKING or estimated remaining days "
            f"< {NEAR_COMPLETE_DAYS}). "
            "2nd: due today, or overdue by at least "
            f"{URGENT_OVERDUE_MIN_LATE_DAYS} calendar days and not close to done. "
            "3rd: not overdue, due within "
            f"{MISS_DUE_CALENDAR_HORIZON} calendar days, and estimated remaining "
            "working days exceed working days until due."
        ),
    }


def production_attention(db: FactoryDB) -> dict[str, Any]:
    """Factory-wide production picture (not the at-risk order list)."""
    from backend.services.briefing import last_working_day_output, unusual_stage_output
    in_progress = db.in_progress_orders()
    by_stage = {stage: 0 for stage in ("KNITTING", "ASSEMBLY", "WASHING", "PACKING")}
    for order in in_progress:
        stage = order.get("current_stage")
        if stage in by_stage:
            by_stage[stage] += 1
    last_date, last_by_stage = last_working_day_output(db)
    unusual = unusual_stage_output(db)
    flagged = [row for row in unusual if row.get("flagged")]
    return {
        "in_progress_order_count": len(in_progress),
        "in_progress_by_stage": by_stage,
        "yesterday_output": {
            "date": last_date,
            "by_stage": last_by_stage,
            "note": "Last working day in production_log.csv before factory today.",
        },
        "stage_vs_30day_median": unusual,
        "flagged_stages": flagged,
        "basis": (
            "Queue counts are IN_PROGRESS orders by current_stage. "
            "Output is factory-wide production_log, last working day vs 30-day median."
        ),
    }


def snapshot_timeline(db: FactoryDB, order_id: str) -> dict[str, Any]:
    """Stage entry dates from app.snapshot plus delay from order_date to first production stage."""
    history = db.order_snapshot_history(order_id)
    order = db.get_order_by_id(order_id) or {}
    order_date = parse_iso_date(order.get("order_date"))
    first_production = None
    for row in history:
        if row["stage"] not in {"ORDERED", "COMPLETE"}:
            first_production = parse_iso_date(row["date"])
            break
    delay = None
    if order_date and first_production:
        delay = calendar_days_between(order_date, first_production)
    return {
        "history": history,
        "order_date": order_date.isoformat() if order_date else None,
        "first_production_stage_date": first_production.isoformat() if first_production else None,
        "calendar_days_order_to_first_production": delay,
    }
