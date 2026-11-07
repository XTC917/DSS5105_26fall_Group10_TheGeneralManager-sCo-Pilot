"""Ranked factory issues. All ranking is deterministic Python.

P1 is an overdue order, P2 is a stalled or tight-due order, and P3 is a stage
whose last working day is below its 30-day baseline. Read-only.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from backend.config import PRODUCTION_DROP_RATIO, factory_date
from backend.services.briefing import unusual_stage_output
from backend.services.calculations import assess_order_risk
from backend.services.database import FactoryDB
from backend.services.pace import (
    flags_with_pace_tight,
    pace_fields,
    pace_tight_rank,
    production_attention,
    stage_medians,
    today_priority,
)

DEFAULT_LIMIT = 5
MAX_LIMIT = 20

ISSUE_ORDER_OVERDUE = "ORDER_OVERDUE"
ISSUE_ORDER_STALLED = "ORDER_STALLED"
ISSUE_ORDER_TIGHT_DUE = "ORDER_TIGHT_DUE"
ISSUE_STAGE_BELOW_BASELINE = "STAGE_BELOW_BASELINE"

# P1 overdue; P2 stalled or tight; P3 stage below baseline.
PRIORITY_BY_TYPE = {
    ISSUE_ORDER_OVERDUE: 1,
    ISSUE_ORDER_STALLED: 2,
    ISSUE_ORDER_TIGHT_DUE: 2,
    ISSUE_STAGE_BELOW_BASELINE: 3,
}
SEVERITY_BY_PRIORITY = {1: "high", 2: "medium", 3: "low"}

LIMITATIONS = [
    "Overdue in-progress orders are P1. Stalled or tight-due orders are P2. A stage is P3 when its last working day is below 0.70 × the 30-day median.",
    "One issue per order. OVERDUE wins over TIGHT_DEADLINE and STALLED.",
    "production includes the queue and each stage's median window as working_days of date and pieces.",
    "Not a general anomaly detector. Issues the CSVs cannot define are omitted.",
    "production_log.csv is factory-wide (date × stage), not per order.",
    "Sort order is computed in Python. The model must not rerank.",
]

TODAY_PRIORITY_LIMITATIONS = [
    "1st/2nd/3rd buckets are Python grouping. Copy days_left; do not recompute.",
    "days_left = max(sum over remaining stages of pieces / 30-day stage median, remaining stage count).",
]


def primary_issue_type(flags: list[str]) -> str:
    """One type per order. OVERDUE wins; else TIGHT (matches existing rank_score); else STALLED."""
    if "OVERDUE" in flags:
        return ISSUE_ORDER_OVERDUE
    if "TIGHT_DEADLINE" in flags:
        return ISSUE_ORDER_TIGHT_DUE
    if "STALLED" in flags:
        return ISSUE_ORDER_STALLED
    raise ValueError(f"no mapped issue type for flags={flags}")


def collect_order_risk_issues(db: FactoryDB) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    medians = stage_medians(db)
    for order in db.in_progress_orders():
        risk = assess_order_risk(order)
        pace = pace_fields(order, medians)
        flags = flags_with_pace_tight(list(risk["flags"]), pace)
        if not flags:
            continue
        issue_type = primary_issue_type(flags)
        priority = PRIORITY_BY_TYPE[issue_type]
        computed = risk["computed"]
        oid = order["order_id"]
        days_left = pace["days_left"]
        issues.append(
            {
                "issue_id": f"order:{oid}",
                "issue_type": issue_type,
                "priority": priority,
                "severity": SEVERITY_BY_PRIORITY[priority],
                "title": _order_title(oid, issue_type, flags),
                "summary": _order_summary(order, flags, computed),
                "order_id": oid,
                "source": "orders.csv",
                "source_file": "orders.csv",
                "rule": risk["basis"],
                "inputs": {
                    "order_id": oid,
                    "status": order["status"],
                    "due_date": order["due_date"],
                    "last_activity_date": order["last_activity_date"],
                    "current_stage": order["current_stage"],
                    "factory_today": factory_date().isoformat(),
                    "flags": flags,
                },
                "result": True,
                "rank_score": pace_tight_rank(risk["rank_score"], flags),
                "evidence": {
                    "flags": flags,
                    "order": {
                        "order_id": oid,
                        "customer": order["customer"],
                        "product": order["product"],
                        "pieces": order["pieces"],
                        "due_date": order["due_date"],
                        "status": order["status"],
                        "current_stage": order["current_stage"],
                        "last_activity_date": order["last_activity_date"],
                    },
                    "computed": {
                        "calendar_days_until_due": computed["calendar_days_until_due"],
                        "working_days_until_due_inclusive": computed[
                            "working_days_until_due_inclusive"
                        ],
                        "working_days_since_last_activity": computed[
                            "working_days_since_last_activity"
                        ],
                        "remaining_stage_count": computed["remaining_stage_count"],
                        "days_left": days_left,
                    },
                    "calculations": risk["calculations"],
                },
            }
        )
    return issues


def collect_stage_issues(db: FactoryDB) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in unusual_stage_output(db):
        if not row.get("flagged"):
            continue
        stage = row["stage"]
        priority = PRIORITY_BY_TYPE[ISSUE_STAGE_BELOW_BASELINE]
        issues.append(
            {
                "issue_id": f"stage:{stage}",
                "issue_type": ISSUE_STAGE_BELOW_BASELINE,
                "priority": priority,
                "severity": SEVERITY_BY_PRIORITY[priority],
                "title": f"{stage} output is below its 30-day baseline",
                "summary": (
                    f"{stage} last working day ({row['last_working_date']}) "
                    f"produced {row['last_day_pieces']} pieces versus lookback median "
                    f"{row['lookback_median']} (ratio {row['ratio_to_median']}; "
                    f"flag if ratio < {PRODUCTION_DROP_RATIO})."
                ),
                "stage": stage,
                "source": "production_log.csv",
                "source_file": "production_log.csv",
                "rule": row["rule"],
                "inputs": {
                    "stage": stage,
                    "last_working_date": row["last_working_date"],
                    "latest_output": row["last_day_pieces"],
                    "median_30d": row["lookback_median"],
                    "threshold": PRODUCTION_DROP_RATIO,
                },
                "result": True,
                "latest_output": row["last_day_pieces"],
                "median_30d": row["lookback_median"],
                "ratio": row["ratio_to_median"],
                "threshold": PRODUCTION_DROP_RATIO,
                "evidence": {
                    "stage": stage,
                    "last_working_date": row["last_working_date"],
                    "last_day_pieces": row["last_day_pieces"],
                    "lookback_median": row["lookback_median"],
                    "ratio_to_median": row["ratio_to_median"],
                    "threshold": PRODUCTION_DROP_RATIO,
                    "flagged": True,
                    "note": "production_log is factory-wide date × stage, not per order.",
                },
            }
        )
    return issues


def sort_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic: priority ASC, then existing risk rank / worse stage ratio, then id."""
    return sorted(issues, key=_sort_tuple)


def discover_factory_issues(db: FactoryDB, limit: int | None = DEFAULT_LIMIT) -> dict[str, Any]:
    collected = sort_issues(collect_order_risk_issues(db) + collect_stage_issues(db))
    if limit is None:
        returned = collected
    else:
        if limit < 1 or limit > MAX_LIMIT:
            raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
        stages = [item for item in collected if item["issue_type"] == ISSUE_STAGE_BELOW_BASELINE]
        orders = [item for item in collected if item["issue_type"] != ISSUE_STAGE_BELOW_BASELINE]
        kept_stages = stages[:limit]
        returned = sort_issues(orders[: max(limit - len(kept_stages), 0)] + kept_stages)
    counts = Counter(item["issue_type"] for item in collected)
    empty_message = None
    if not collected:
        empty_message = (
            "No issues found."
        )
    return {
        "factory_today": factory_date().isoformat(),
        "as_of": factory_date().isoformat(),
        "limit": len(returned) if limit is None else limit,
        "total_found": len(collected),
        "returned_count": len(returned),
        "counts_by_type": {
            ISSUE_ORDER_OVERDUE: int(counts.get(ISSUE_ORDER_OVERDUE, 0)),
            ISSUE_ORDER_STALLED: int(counts.get(ISSUE_ORDER_STALLED, 0)),
            ISSUE_ORDER_TIGHT_DUE: int(counts.get(ISSUE_ORDER_TIGHT_DUE, 0)),
            ISSUE_STAGE_BELOW_BASELINE: int(counts.get(ISSUE_STAGE_BELOW_BASELINE, 0)),
        },
        "production": production_attention(db),
        "issues": returned,
        "message": empty_message,
        "limitations": list(LIMITATIONS),
    }


def discover_priority_board(db: FactoryDB) -> dict[str, Any]:
    """Every order in the today-priority buckets. The prose answer names only a few."""
    buckets = today_priority(db)
    orders = {order["order_id"]: order for order in db.in_progress_orders()}
    issues: list[dict[str, Any]] = []
    for priority, key, issue_type in (
        (1, "1st_priority", "PRIORITY_NEAR_COMPLETE"),
        (2, "2nd_priority", "PRIORITY_URGENT"),
        (3, "3rd_priority", "PRIORITY_UPCOMING"),
    ):
        for card in buckets[key]:
            order = orders[card["order_id"]]
            risk = assess_order_risk(order)
            computed = risk["computed"]
            issues.append(
                {
                    "issue_id": f"order:{card['order_id']}",
                    "issue_type": issue_type,
                    "priority": priority,
                    "severity": SEVERITY_BY_PRIORITY[priority],
                    "title": _priority_title(card, priority),
                    "summary": buckets["rule"],
                    "order_id": card["order_id"],
                    "source": "orders.csv",
                    "source_file": "orders.csv",
                    "rule": buckets["rule"],
                    "evidence": {
                        "flags": risk["flags"],
                        "order": {
                            "order_id": card["order_id"],
                            "customer": card["customer"],
                            "product": card["product"],
                            "pieces": card["pieces"],
                            "due_date": card["due_date"],
                            "status": order.get("status"),
                            "current_stage": card["current_stage"],
                            "last_activity_date": order.get("last_activity_date"),
                        },
                        "computed": {
                            "calendar_days_until_due": card["calendar_days_until_due"],
                            "working_days_until_due_inclusive": computed[
                                "working_days_until_due_inclusive"
                            ],
                            "working_days_since_last_activity": computed[
                                "working_days_since_last_activity"
                            ],
                            "remaining_stage_count": computed["remaining_stage_count"],
                            "days_left": card["days_left"],
                        },
                    },
                }
            )
    counts = Counter(item["issue_type"] for item in issues)
    return {
        "factory_today": factory_date().isoformat(),
        "as_of": factory_date().isoformat(),
        "limit": len(issues),
        "total_found": len(issues),
        "returned_count": len(issues),
        "counts_by_type": {
            "PRIORITY_NEAR_COMPLETE": int(counts.get("PRIORITY_NEAR_COMPLETE", 0)),
            "PRIORITY_URGENT": int(counts.get("PRIORITY_URGENT", 0)),
            "PRIORITY_UPCOMING": int(counts.get("PRIORITY_UPCOMING", 0)),
        },
        "production": production_attention(db),
        "issues": issues,
        "message": None if issues else "No issues found.",
        "limitations": [
            "Same buckets as get_today_priority. Every matching order is listed.",
            buckets["rule"],
            "The written answer may name only some of these orders.",
        ],
    }


def _priority_title(card: dict[str, Any], priority: int) -> str:
    order_id = card["order_id"]
    if priority == 1:
        return f"{order_id} is overdue and close to completion"
    if priority == 2 and card.get("calendar_days_until_due") == 1:
        return f"{order_id} is due today"
    if priority == 2:
        return f"{order_id} is overdue with work still remaining"
    return f"{order_id} may miss its due date"


def get_today_priority(db: FactoryDB) -> dict[str, Any]:
    buckets = today_priority(db)
    return {
        "factory_today": factory_date().isoformat(),
        "as_of": factory_date().isoformat(),
        "today_priority": buckets,
        "limitations": list(TODAY_PRIORITY_LIMITATIONS),
    }


def _sort_tuple(issue: dict[str, Any]) -> tuple:
    if issue["issue_type"] == ISSUE_STAGE_BELOW_BASELINE:
        ratio = issue.get("ratio")
        if ratio is None:
            ratio = 1.0
        return (issue["priority"], ratio, issue["issue_id"])
    rank = issue.get("rank_score") or 0
    return (issue["priority"], -int(rank), issue["issue_id"])


def _order_title(order_id: str, issue_type: str, flags: list[str]) -> str:
    stalled = "STALLED" in flags
    if issue_type == ISSUE_ORDER_OVERDUE:
        return f"{order_id} is overdue and stalled" if stalled else f"{order_id} is overdue"
    if issue_type == ISSUE_ORDER_TIGHT_DUE:
        return (
            f"{order_id} has a tight due date and is stalled"
            if stalled
            else f"{order_id} has a tight due date"
        )
    return f"{order_id} is stalled"


def _order_summary(order: dict[str, Any], flags: list[str], computed: dict[str, Any]) -> str:
    return (
        f"{order['order_id']} ({order['customer']} {order['product']}) is "
        f"{order['status']} at {order['current_stage']}, due {order['due_date']}, "
        f"last activity {order['last_activity_date']}. Flags: {', '.join(flags)}. "
        f"calendar_days_until_due={computed['calendar_days_until_due']}; "
        f"working_days_since_last_activity="
        f"{computed['working_days_since_last_activity']}."
    )
