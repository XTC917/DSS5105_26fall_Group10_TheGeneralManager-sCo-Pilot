"""Structured morning briefing. All numbers come from existing Python rules."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from typing import Any

from backend.config import (
    FACTORY_TODAY,
    ORDER_LIFECYCLE_IN_ORDER,
    PRODUCTION_DROP_RATIO,
    PRODUCTION_STAGES_IN_ORDER,
)
from backend.services.calculations import assess_order_risk, is_working_day, parse_iso_date
from backend.services.pace import flags_with_pace_tight, pace_fields, stage_medians
from backend.services.database import FactoryDB
from backend.services.feasibility import stage_throughput_medians
from backend.tools.retrieval import get_orders_at_risk


def build_morning_briefing(db: FactoryDB) -> dict[str, Any]:
    """Return inspectable briefing facts. The LLM writes the prose."""
    risk_payload = json.loads(get_orders_at_risk.invoke({}))
    risk_data = risk_payload.get("data") or {}
    risk_orders = risk_data.get("orders") or []
    flag_counts = Counter()
    for row in risk_orders:
        for flag in row.get("flags") or []:
            flag_counts[flag] += 1

    in_progress = db.in_progress_orders()
    stage_counts = Counter(o["current_stage"] for o in in_progress)
    by_stage = {stage: int(stage_counts.get(stage, 0)) for stage in ORDER_LIFECYCLE_IN_ORDER}

    last_date, last_by_stage = last_working_day_output(db)
    unusual = unusual_stage_output(db)

    workshops = db.workshops()
    suspended = [
        {
            "workshop_id": w["workshop_id"],
            "name": w["name"],
            "status": w["status"],
            "notes": w.get("notes"),
        }
        for w in workshops
        if w.get("status") == "SUSPENDED"
    ]

    return {
        "factory_today": FACTORY_TODAY.isoformat(),
        "dashboard": build_dashboard(db),
        "in_progress_order_count": len(in_progress),
        "in_progress_by_stage": by_stage,
        "at_risk": {
            "count": len(risk_orders),
            "flag_counts": {
                "OVERDUE": int(flag_counts.get("OVERDUE", 0)),
                "STALLED": int(flag_counts.get("STALLED", 0)),
                "TIGHT_DEADLINE": int(flag_counts.get("TIGHT_DEADLINE", 0)),
            },
            "orders": [
                {
                    "order_id": r["order_id"],
                    "customer": r["customer"],
                    "product": r["product"],
                    "pieces": r["pieces"],
                    "due_date": r["due_date"],
                    "current_stage": r["current_stage"],
                    "flags": r["flags"],
                }
                for r in risk_orders
            ],
            "basis": risk_data.get("basis"),
        },
        "yesterday_output": {
            "date": last_date,
            "note": "Last working day in production_log.csv before factory today. Not per-order.",
            "by_stage": last_by_stage,
        },
        "unusual_stage_output": unusual,
        "suspended_workshops": suspended,
        "last_week": build_last_week(db),
        "limitations": [
            "The at_risk list is get_orders_at_risk with no flag: not-yet-overdue orders whose days_left exceeds working days until due. OVERDUE and STALLED are separate flags.",
            "last_week is the previous Monday–Saturday. It does not include today's in-progress or stalled orders.",
            "production_log.csv is factory-wide by stage, not per order.",
            "Unusual output uses last working day vs the same 30-day stage median as feasibility.",
            "No worker names, selling prices, or revenue are included because they are not in the data.",
            "This object is structured facts, not a canned briefing script.",
        ],
    }


def previous_working_week(today: date = FACTORY_TODAY) -> tuple[date, date]:
    """Monday–Saturday before the week that contains factory today."""
    monday = today - timedelta(days=today.weekday())
    start = monday - timedelta(days=7)
    return start, start + timedelta(days=5)


def _week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _late_days(order: dict[str, Any], done: date) -> int | None:
    late = order.get("days_late")
    if late is not None:
        return int(late)
    due = parse_iso_date(order.get("due_date"))
    if due is None:
        return None
    return (done - due).days


def build_last_week(db: FactoryDB, today: date = FACTORY_TODAY) -> dict[str, Any]:
    """Weekly completion mix, stage output, and last complete week's products."""
    start, end = previous_working_week(today)
    completions = []
    for order in db.find_orders(status="COMPLETE"):
        done = parse_iso_date(order.get("completed_date"))
        if done is None or done > today:
            continue
        completions.append({
            "product": order.get("product") or "",
            "customer": order.get("customer") or "",
            "pieces": int(order.get("pieces") or 0),
            "completed": done,
            "days_late": _late_days(order, done),
        })

    dated = [row["completed"] for row in completions]
    for row in db.production_log():
        parsed = parse_iso_date(row.get("date"))
        if parsed is not None and parsed <= today and is_working_day(parsed):
            dated.append(parsed)
    if not dated:
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "weeks": [],
            "products": [],
            "customers": [],
            "basis": "No weekly factory records are available.",
        }

    monday = _week_monday(min(dated))
    last_monday = _week_monday(today)
    weeks: list[dict[str, Any]] = []
    week_number = 1
    while monday <= last_monday:
        week_end = monday + timedelta(days=5)
        partial = week_end > today
        item = {
            "week": week_number,
            "start": monday.isoformat(),
            "end": (today if partial else week_end).isoformat(),
            "partial": partial,
            "on_time": 0,
            "overdue": 0,
            "completed": 0,
            **{stage: 0 for stage in PRODUCTION_STAGES_IN_ORDER},
        }
        weeks.append(item)
        monday += timedelta(days=7)
        week_number += 1
    by_start = {row["start"]: row for row in weeks}

    for row in completions:
        bucket = by_start.get(_week_monday(row["completed"]).isoformat())
        if bucket is None:
            continue
        if (row["days_late"] or 0) > 0:
            bucket["overdue"] += 1
        else:
            bucket["on_time"] += 1
        bucket["completed"] += 1
    for row in db.production_log():
        parsed = parse_iso_date(row.get("date"))
        stage = row.get("stage")
        if parsed is None or parsed > today or stage not in PRODUCTION_STAGES_IN_ORDER:
            continue
        if not is_working_day(parsed):
            continue
        bucket = by_start.get(_week_monday(parsed).isoformat())
        if bucket is None:
            continue
        bucket[stage] += int(row.get("pieces_completed") or 0)
    for row in weeks:
        total = row["completed"]
        row["on_time_percent"] = round(100 * row["on_time"] / total, 1) if total else 0
        row["overdue_percent"] = round(100 * row["overdue"] / total, 1) if total else 0

    products: dict[tuple[str, str], dict[str, Any]] = {}
    for row in completions:
        if not (start <= row["completed"] <= end):
            continue
        key = (row["product"], row["customer"])
        bucket = products.setdefault(key, {
            "product": row["product"],
            "customer": row["customer"],
            "pieces": 0,
        })
        bucket["pieces"] += row["pieces"]
    product_rows = sorted(products.values(), key=lambda item: (item["product"], -item["pieces"], item["customer"]))
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "weeks": weeks,
        "products": product_rows,
        "customers": sorted({row["customer"] for row in product_rows}),
        "basis": (
            "Each point is a Monday–Saturday factory week. The week containing factory today "
            "stops on that date, so it is shorter than six working days. "
            "Products are the previous complete Monday–Saturday. Brand is orders.customer. "
            "Stage pieces are factory-wide output, not finished garments."
        ),
    }


def last_working_day_output(db: FactoryDB) -> tuple[str | None, dict[str, int]]:
    log = db.production_log()
    working_dates = []
    for row in log:
        parsed = parse_iso_date(row["date"])
        if parsed is None:
            continue
        if parsed < FACTORY_TODAY and is_working_day(parsed):
            working_dates.append(parsed)
    if not working_dates:
        return None, {}
    last = max(working_dates)
    by_stage: dict[str, int] = {}
    for row in log:
        if parse_iso_date(row["date"]) == last and row["stage"] in PRODUCTION_STAGES_IN_ORDER:
            by_stage[row["stage"]] = int(row["pieces_completed"])
    return last.isoformat(), by_stage


def unusual_stage_output(db: FactoryDB) -> list[dict[str, Any]]:
    """Last working day vs the same 30-day median used by feasibility.

    Flag if last-day pieces < PRODUCTION_DROP_RATIO × lookback median.
    production_log is factory-wide (date × stage), not per order.
    """
    throughput = stage_throughput_medians(db)
    last_date, last_by_stage = last_working_day_output(db)
    unusual: list[dict[str, Any]] = []
    for stage in PRODUCTION_STAGES_IN_ORDER:
        median = throughput["medians_pieces_per_working_day"].get(stage)
        last_pieces = last_by_stage.get(stage)
        if median and last_pieces is not None and median > 0:
            ratio = last_pieces / median
            unusual.append(
                {
                    "stage": stage,
                    "last_working_date": last_date,
                    "last_day_pieces": last_pieces,
                    "lookback_median": median,
                    "ratio_to_median": round(ratio, 3),
                    "flagged": ratio < PRODUCTION_DROP_RATIO,
                    "rule": (
                        f"flag if last working day pieces < "
                        f"{PRODUCTION_DROP_RATIO} × lookback median"
                    ),
                }
            )
    return unusual


def build_dashboard(db: FactoryDB) -> dict[str, Any]:
    """Full active-order coverage; deadline buckets are mutually exclusive."""
    previous = FACTORY_TODAY - timedelta(days=1)
    while not is_working_day(previous):
        previous -= timedelta(days=1)
    medians = stage_medians(db)
    active = []
    buckets = Counter()
    for order in db.in_progress_orders():
        risk = assess_order_risk(order)
        pace = pace_fields(order, medians)
        days = risk["computed"]["calendar_days_until_due"]
        # calendar_days_until_due counts today through the due date.
        # Due today is 1. The date windows stay today, +1..+2, and +3..+7.
        bucket = ("UNKNOWN" if days is None else "OVERDUE" if days < 0 else
                  "TODAY" if days == 1 else "TWO_DAYS" if days <= 3 else
                  "WEEK" if days <= 8 else "LATER")
        flags = flags_with_pace_tight(risk["flags"], pace)
        buckets[bucket] += 1
        active.append({
            **{key: order.get(key) for key in (
                "order_id", "customer", "product", "pieces", "due_date",
                "current_stage", "last_activity_date")},
            "bucket": bucket, "flags": flags, "computed": risk["computed"],
            "estimated_remaining_working_days": pace["estimated_remaining_working_days"],
        })
    active.sort(key=lambda row: (
        row["computed"]["calendar_days_until_due"] is None,
        row["computed"]["calendar_days_until_due"] or 0, row["order_id"]))
    completed = []
    for order in db.find_orders(status="COMPLETE"):
        done = parse_iso_date(order.get("completed_date"))
        if done != previous:
            continue
        due = parse_iso_date(order.get("due_date"))
        completed.append({
            **{key: order.get(key) for key in (
                "order_id", "customer", "product", "pieces", "due_date", "completed_date")},
            "days_late": (done - due).days if due else None,
        })
    return {
        "completion_date": previous.isoformat(),
        "completed_orders": completed,
        "orders": active,
        "deadline_buckets": dict(buckets),
        "metrics": {
            "active": len(active),
            "overdue": buckets["OVERDUE"],
            "due_soon": buckets["TODAY"] + buckets["TWO_DAYS"],
            "stalled": sum("STALLED" in row["flags"] for row in active),
            "attention": sum(bool(row["flags"]) for row in active),
        },
        "basis": {
            "deadlines": "calendar_days_until_due counts today through the due date (due today = 1). Due soon is due today through 2 calendar days ahead.",
            "stalled": "No activity for at least 3 working days; Sundays excluded. Flags can overlap.",
            "pace": "Factory stage throughput estimate, not a committed delivery date or a capacity allocation.",
        },
    }
