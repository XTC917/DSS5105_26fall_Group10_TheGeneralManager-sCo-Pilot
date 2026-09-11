"""Structured morning briefing. All numbers come from existing Python rules."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from backend.config import (
    FACTORY_TODAY,
    PRODUCTION_DROP_RATIO,
    STAGES_IN_ORDER,
)
from backend.services.calculations import is_working_day, parse_iso_date
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
    by_stage = {stage: int(stage_counts.get(stage, 0)) for stage in STAGES_IN_ORDER}

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
        "limitations": [
            "Risk flags reuse get_orders_at_risk / assess_order_risk. COMPLETE orders are excluded.",
            "production_log.csv is factory-wide by stage, not per order.",
            "Unusual output uses last working day vs the same 30-day stage median as feasibility.",
            "No worker names, selling prices, or revenue are included because they are not in the data.",
            "This object is structured facts, not a canned briefing script.",
        ],
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
        if parse_iso_date(row["date"]) == last and row["stage"] in STAGES_IN_ORDER:
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
    for stage in STAGES_IN_ORDER:
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
