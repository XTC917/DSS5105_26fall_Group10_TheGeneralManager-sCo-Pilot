"""Pure, inspectable calculations.

The LLM must never compute these values itself. Every function here is
deterministic and returns enough intermediate numbers for tracing.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Any

from backend.config import (
    CLOSED_WEEKDAY,
    FACTORY_TODAY,
    STAGE_COMPLETE,
    STAGES_IN_ORDER,
    STALL_WORKING_DAYS,
)


def parse_iso_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def is_working_day(day: date) -> bool:
    """Factory is open Monday–Saturday and closed on Sunday."""
    return day.weekday() != CLOSED_WEEKDAY


def count_working_days(
    start: date,
    end: date,
    *,
    include_start: bool = True,
    include_end: bool = True,
) -> int:
    """Count Mon–Sat days in the given range. Returns 0 if the range is empty."""
    if end < start:
        return 0
    first = start if include_start else start + timedelta(days=1)
    last = end if include_end else end - timedelta(days=1)
    if last < first:
        return 0
    total = 0
    cursor = first
    while cursor <= last:
        if is_working_day(cursor):
            total += 1
        cursor += timedelta(days=1)
    return total


def remaining_stages(current_stage: str) -> list[str]:
    """Stages still required, including the current stage.

    COMPLETE has none. Unknown stage names return an empty list so callers
    can surface a limitation instead of guessing.
    """
    if current_stage == STAGE_COMPLETE:
        return []
    if current_stage not in STAGES_IN_ORDER:
        return []
    idx = STAGES_IN_ORDER.index(current_stage)
    return list(STAGES_IN_ORDER[idx:])


def calendar_days_between(start: date, end: date) -> int:
    """Signed calendar-day difference (end - start). Matches orders.days_late convention."""
    return (end - start).days


def working_days_until_due(due: date, today: date = FACTORY_TODAY) -> int:
    """Working days from today through due_date, inclusive. 0 if already overdue."""
    if due < today:
        return 0
    return count_working_days(today, due)


def working_days_since_activity(last_activity: date, today: date = FACTORY_TODAY) -> int:
    """Working days after last_activity_date up to and including today."""
    return count_working_days(last_activity, today, include_start=False, include_end=True)


def order_computed_fields(order: dict[str, Any], today: date = FACTORY_TODAY) -> dict[str, Any]:
    """Derived fields for a single order row. All arithmetic lives here."""
    due = parse_iso_date(order.get("due_date"))
    last_activity = parse_iso_date(order.get("last_activity_date"))
    completed = parse_iso_date(order.get("completed_date"))
    current_stage = order.get("current_stage") or ""
    stages_left = remaining_stages(current_stage)

    calendar_until_due = calendar_days_between(today, due) if due else None
    working_until_due = working_days_until_due(due, today) if due else None
    calendar_since_activity = (
        calendar_days_between(last_activity, today) if last_activity else None
    )
    working_since_activity = (
        working_days_since_activity(last_activity, today) if last_activity else None
    )

    return {
        "factory_today": today.isoformat(),
        "calendar_days_until_due": calendar_until_due,
        "working_days_until_due_inclusive": working_until_due,
        "calendar_days_since_last_activity": calendar_since_activity,
        "working_days_since_last_activity": working_since_activity,
        "remaining_stages": stages_left,
        "remaining_stage_count": len(stages_left),
        "completed_date": completed.isoformat() if completed else None,
        "is_overdue": bool(
            order.get("status") == "IN_PROGRESS" and due is not None and due < today
        ),
        "is_stalled": bool(
            order.get("status") == "IN_PROGRESS"
            and working_since_activity is not None
            and working_since_activity >= STALL_WORKING_DAYS
        ),
        "is_tight_deadline": bool(
            order.get("status") == "IN_PROGRESS"
            and due is not None
            and due >= today
            and working_until_due is not None
            and working_until_due < len(stages_left)
        ),
    }


def assess_order_risk(order: dict[str, Any], today: date = FACTORY_TODAY) -> dict[str, Any]:
    """Inspectable risk flags for one order.

    Definitions (also in docs/tool_spec.md):

    * OVERDUE — status is IN_PROGRESS and due_date < factory today.
    * STALLED — status is IN_PROGRESS and working days since last_activity_date
      (excluding that date, including today) >= STALL_WORKING_DAYS.
    * TIGHT_DEADLINE — status is IN_PROGRESS, not yet overdue, and
      working_days_until_due_inclusive < remaining_stage_count.
      This is a conservative heuristic: we do not know pieces remaining at
      the current stage, so we require at least one working day per remaining
      stage.

    COMPLETE orders are never flagged.
    """
    computed = order_computed_fields(order, today)
    flags: list[str] = []
    calculations: list[dict[str, Any]] = []

    if order.get("status") != "IN_PROGRESS":
        return {
            "at_risk": False,
            "flags": [],
            "computed": computed,
            "calculations": calculations,
            "basis": "Only IN_PROGRESS orders are assessed for operational risk.",
        }

    due = parse_iso_date(order.get("due_date"))
    last_activity = parse_iso_date(order.get("last_activity_date"))

    if computed["is_overdue"]:
        flags.append("OVERDUE")
        calculations.append(
            {
                "name": "overdue",
                "formula": "status == IN_PROGRESS AND due_date < factory_today",
                "inputs": {
                    "due_date": due.isoformat() if due else None,
                    "factory_today": today.isoformat(),
                    "calendar_days_until_due": computed["calendar_days_until_due"],
                },
                "result": True,
            }
        )

    if computed["is_stalled"]:
        flags.append("STALLED")
        calculations.append(
            {
                "name": "stalled",
                "formula": (
                    "working_days(last_activity_date + 1 day, today) "
                    f">= {STALL_WORKING_DAYS}"
                ),
                "inputs": {
                    "last_activity_date": last_activity.isoformat() if last_activity else None,
                    "factory_today": today.isoformat(),
                    "working_days_since_last_activity": computed[
                        "working_days_since_last_activity"
                    ],
                    "threshold_working_days": STALL_WORKING_DAYS,
                },
                "result": True,
            }
        )

    if computed["is_tight_deadline"]:
        flags.append("TIGHT_DEADLINE")
        calculations.append(
            {
                "name": "tight_deadline",
                "formula": (
                    "working_days_until_due_inclusive < remaining_stage_count "
                    "(at least one working day per remaining stage)"
                ),
                "inputs": {
                    "working_days_until_due_inclusive": computed[
                        "working_days_until_due_inclusive"
                    ],
                    "remaining_stages": computed["remaining_stages"],
                    "remaining_stage_count": computed["remaining_stage_count"],
                },
                "result": True,
            }
        )

    # Rank: overdue first (more days late = more urgent), then tight, then stalled.
    days_overdue = 0
    if computed["is_overdue"] and computed["calendar_days_until_due"] is not None:
        days_overdue = abs(computed["calendar_days_until_due"])
    rank_score = (
        days_overdue * 1000
        + (500 if computed["is_tight_deadline"] else 0)
        + (computed["working_days_since_last_activity"] or 0)
    )

    return {
        "at_risk": bool(flags),
        "flags": flags,
        "rank_score": rank_score,
        "computed": computed,
        "calculations": calculations,
        "basis": (
            "OVERDUE: due_date < 2026-04-01. "
            f"STALLED: idle >= {STALL_WORKING_DAYS} working days. "
            "TIGHT_DEADLINE: working days left < remaining stages."
        ),
    }


def median_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(median(values))


def workshop_effective_capacity(
    workshop: dict[str, Any],
    working_days: int,
    pieces_requested: int,
) -> dict[str, Any]:
    """How many pieces an ACTIVE workshop could take for one new batch.

    available_production_days = max(0, working_days - pickup_lead_days - current_queue_days)
    raw_output = capacity_pieces_per_day * (1 - defect_rate) * available_production_days
    If max_batch_pieces is set, cap at that (trial workshops).
    """
    capacity = float(workshop["capacity_pieces_per_day"])
    lead = float(workshop["pickup_lead_days"])
    defect = float(workshop["defect_rate"])
    queue = float(workshop["current_queue_days"] or 0)
    max_batch = workshop.get("max_batch_pieces")
    available_days = max(0.0, working_days - lead - queue)
    raw_output = capacity * (1.0 - defect) * available_days
    capped = raw_output
    if max_batch is not None and max_batch != "":
        capped = min(raw_output, float(max_batch))
    takeable = min(capped, float(pieces_requested))
    return {
        "workshop_id": workshop["workshop_id"],
        "name": workshop["name"],
        "status": workshop["status"],
        "makes": workshop["makes"],
        "available_production_days": available_days,
        "raw_output_after_defects": raw_output,
        "max_batch_pieces": max_batch,
        "effective_pieces": int(capped) if capped == int(capped) else capped,
        "takeable_for_this_order": takeable,
        "formula": (
            "available_days = max(0, working_days - pickup_lead_days - current_queue_days); "
            "raw = capacity_pieces_per_day * (1 - defect_rate) * available_days; "
            "effective = min(raw, max_batch_pieces) if max_batch_pieces else raw"
        ),
        "inputs": {
            "working_days": working_days,
            "capacity_pieces_per_day": capacity,
            "pickup_lead_days": lead,
            "current_queue_days": queue,
            "defect_rate": defect,
            "max_batch_pieces": max_batch,
        },
    }
