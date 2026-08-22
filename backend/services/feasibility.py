"""Inspectable feasibility estimate for a hypothetical new order.

MVP model — deliberately simple and fully documented in docs/tool_spec.md.

What this DOES:
  * Count remaining factory working days (Mon–Sat) from FACTORY_TODAY through due_date.
  * Estimate factory bottleneck throughput as the minimum of the per-stage
    medians of pieces_completed over the last N working days in production_log.
  * Treat the sum of IN_PROGRESS order pieces as competing demand
    (conservative: we do not know remaining work per order).
  * Add overflow capacity from ACTIVE workshops that can make the category.

What this does NOT do (TODO, do not invent):
  * Model sequential pipeline latency (first garment needs all four stages).
  * Split a new order across several workshop batches over time.
  * Use selling price / margin — those columns do not exist for factory orders.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.config import (
    FACTORY_TODAY,
    STAGES_IN_ORDER,
    THROUGHPUT_LOOKBACK_WORKING_DAYS,
)
from backend.services.calculations import (
    is_working_day,
    median_or_none,
    parse_iso_date,
    working_days_until_due,
    workshop_effective_capacity,
)
from backend.services.database import FactoryDB


def resolve_category(db: FactoryDB, product: str | None, category: str | None) -> dict[str, Any]:
    """Map a product name to TOPS / ACCESSORIES using orders.csv only."""
    if category:
        cat = category.strip().upper()
        if cat not in {"TOPS", "ACCESSORIES"}:
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "category must be TOPS or ACCESSORIES.",
                },
            }
        return {"ok": True, "category": cat, "matched_product": None}

    if not product:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_INPUT",
                "message": "Provide product or category (TOPS / ACCESSORIES).",
            },
        }

    products = db.list_products()
    exact = [p for p in products if p["product"].lower() == product.strip().lower()]
    if len(exact) == 1:
        return {
            "ok": True,
            "category": exact[0]["category"],
            "matched_product": exact[0]["product"],
        }
    if len(exact) > 1:
        cats = {p["category"] for p in exact}
        if len(cats) == 1:
            return {"ok": True, "category": next(iter(cats)), "matched_product": exact[0]["product"]}

    contains = [p for p in products if product.strip().lower() in p["product"].lower()]
    cats = {p["category"] for p in contains}
    if len(cats) == 1:
        return {
            "ok": True,
            "category": next(iter(cats)),
            "matched_product": contains[0]["product"] if len(contains) == 1 else None,
        }
    if not contains:
        return {
            "ok": False,
            "error": {
                "code": "UNKNOWN_PRODUCT",
                "message": (
                    f"Product '{product}' is not in orders.csv. "
                    "Pass category='TOPS' or category='ACCESSORIES'."
                ),
                "known_products": sorted({p["product"] for p in products}),
            },
        }
    return {
        "ok": False,
        "error": {
            "code": "AMBIGUOUS",
            "message": f"Product '{product}' matches more than one category. Pass category explicitly.",
            "matches": contains,
        },
    }


def stage_throughput_medians(db: FactoryDB, today: date = FACTORY_TODAY) -> dict[str, Any]:
    """Median pieces_completed per stage on the last N working days (Sundays excluded)."""
    log = db.production_log()
    by_stage: dict[str, list[int]] = {s: [] for s in STAGES_IN_ORDER}
    working_dates = sorted(
        {
            parse_iso_date(row["date"])
            for row in log
            if parse_iso_date(row["date"]) is not None
            and is_working_day(parse_iso_date(row["date"]))  # type: ignore[arg-type]
            and parse_iso_date(row["date"]) < today  # type: ignore[operator]
        }
    )
    lookback_dates = set(working_dates[-THROUGHPUT_LOOKBACK_WORKING_DAYS:])
    used_rows: list[dict[str, Any]] = []
    for row in log:
        d = parse_iso_date(row["date"])
        if d in lookback_dates and row["stage"] in by_stage:
            by_stage[row["stage"]].append(int(row["pieces_completed"]))
            used_rows.append(row)

    medians = {stage: median_or_none(vals) for stage, vals in by_stage.items()}
    present = [m for m in medians.values() if m is not None]
    bottleneck_stage = None
    bottleneck_median = None
    if present:
        bottleneck_stage = min(
            (s for s in STAGES_IN_ORDER if medians[s] is not None),
            key=lambda s: medians[s] or 0,
        )
        bottleneck_median = medians[bottleneck_stage]

    return {
        "lookback_working_days": THROUGHPUT_LOOKBACK_WORKING_DAYS,
        "lookback_date_from": min(lookback_dates).isoformat() if lookback_dates else None,
        "lookback_date_to": max(lookback_dates).isoformat() if lookback_dates else None,
        "medians_pieces_per_working_day": medians,
        "bottleneck_stage": bottleneck_stage,
        "bottleneck_median": bottleneck_median,
        "source_file": "production_log.csv",
        "source_row_count": len(used_rows),
    }


def check_feasibility(
    db: FactoryDB,
    *,
    pieces: int,
    due_date: str,
    product: str | None = None,
    category: str | None = None,
    today: date = FACTORY_TODAY,
) -> dict[str, Any]:
    if pieces <= 0:
        return _error("INVALID_INPUT", "pieces must be a positive integer.")

    due = parse_iso_date(due_date)
    if due is None:
        return _error("INVALID_INPUT", "due_date must be YYYY-MM-DD.")

    cat_result = resolve_category(db, product, category)
    if not cat_result.get("ok"):
        return cat_result
    resolved_category = cat_result["category"]

    working_days = working_days_until_due(due, today)
    throughput = stage_throughput_medians(db, today)
    wip = db.in_progress_orders()
    wip_pieces = int(sum(int(o["pieces"]) for o in wip))

    bottleneck = throughput["bottleneck_median"]
    factory_window_capacity = (bottleneck or 0) * working_days
    spare_factory = max(0.0, factory_window_capacity - wip_pieces)
    in_house_ok = pieces <= spare_factory and working_days > 0 and due >= today

    eligible_workshops = db.workshops(status="ACTIVE", category=resolved_category)
    workshop_rows = [
        workshop_effective_capacity(w, working_days, pieces) for w in eligible_workshops
    ]
    workshop_total = sum(float(w["effective_pieces"]) for w in workshop_rows)
    with_workshops_ok = pieces <= (spare_factory + workshop_total) and due >= today and working_days > 0

    limitations = [
        "Competing demand is the full piece count of every IN_PROGRESS order; "
        "the dataset does not say how many pieces remain at the current stage.",
        "Factory throughput is the bottleneck-stage median over the last "
        f"{THROUGHPUT_LOOKBACK_WORKING_DAYS} working days in production_log.csv. "
        "Pipeline latency across four sequential stages is not modelled in this MVP.",
        "Each workshop is modelled as at most one new batch in this window. "
        "SUSPENDED workshops are excluded.",
        "This estimate is not a promise of delivery; it is a capacity arithmetic check.",
    ]

    if due < today:
        verdict = "NOT_FEASIBLE"
        summary = "The due date is already before factory today (2026-04-01)."
    elif working_days == 0:
        verdict = "NOT_FEASIBLE"
        summary = "No remaining working days before the due date."
    elif in_house_ok:
        verdict = "FEASIBLE_IN_HOUSE"
        summary = (
            f"{pieces} pieces fit in estimated spare factory capacity "
            f"({int(spare_factory)} pieces) before {due.isoformat()}."
        )
    elif with_workshops_ok:
        verdict = "FEASIBLE_WITH_WORKSHOPS"
        summary = (
            f"{pieces} pieces do not fit in spare factory capacity "
            f"({int(spare_factory)}) but can fit if ACTIVE workshops are used "
            f"(+{int(workshop_total)} estimated pieces)."
        )
    else:
        verdict = "NOT_FEASIBLE"
        summary = (
            f"{pieces} pieces exceed spare factory capacity ({int(spare_factory)}) "
            f"plus ACTIVE workshop overflow ({int(workshop_total)}) in {working_days} working days."
        )

    calculations = [
        {
            "name": "working_days_until_due",
            "formula": "count of Mon-Sat days from factory_today through due_date inclusive",
            "inputs": {"factory_today": today.isoformat(), "due_date": due.isoformat()},
            "result": working_days,
        },
        {
            "name": "factory_window_capacity",
            "formula": "bottleneck_median_pieces_per_day * working_days",
            "inputs": {
                "bottleneck_stage": throughput["bottleneck_stage"],
                "bottleneck_median": bottleneck,
                "working_days": working_days,
            },
            "result": factory_window_capacity,
        },
        {
            "name": "spare_factory_capacity",
            "formula": "max(0, factory_window_capacity - sum(pieces of IN_PROGRESS orders))",
            "inputs": {
                "factory_window_capacity": factory_window_capacity,
                "in_progress_order_count": len(wip),
                "in_progress_pieces": wip_pieces,
            },
            "result": spare_factory,
        },
        {
            "name": "workshop_overflow",
            "formula": "sum of effective_pieces over ACTIVE workshops that can make the category",
            "inputs": {"category": resolved_category, "workshop_count": len(workshop_rows)},
            "result": workshop_total,
        },
    ]

    return {
        "ok": True,
        "tool": "check_feasibility",
        "data": {
            "verdict": verdict,
            "summary": summary,
            "feasible_in_house": in_house_ok,
            "feasible_with_workshops": with_workshops_ok,
            "pieces": pieces,
            "due_date": due.isoformat(),
            "product": product,
            "matched_product": cat_result.get("matched_product"),
            "category": resolved_category,
            "working_days": working_days,
            "in_progress_pieces": wip_pieces,
            "spare_factory_capacity": spare_factory,
            "workshop_overflow_pieces": workshop_total,
            "throughput": throughput,
            "workshops": workshop_rows,
            "limitations": limitations,
        },
        "trace": {
            "tool": "check_feasibility",
            "source_file": "production_log.csv + orders.csv + workshops.csv",
            "filter": {
                "pieces": pieces,
                "due_date": due.isoformat(),
                "category": resolved_category,
            },
            "rows": [
                {
                    "in_progress_order_id": o["order_id"],
                    "pieces": o["pieces"],
                    "current_stage": o["current_stage"],
                }
                for o in wip
            ],
            "calculations": calculations,
            "basis": (
                "Bottleneck median throughput vs remaining working days, "
                "minus IN_PROGRESS piece count, plus ACTIVE workshop overflow."
            ),
        },
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "tool": "check_feasibility", "error": {"code": code, "message": message}}
