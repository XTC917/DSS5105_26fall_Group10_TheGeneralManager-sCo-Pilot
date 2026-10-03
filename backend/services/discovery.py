"""Ranked factory-issue discovery from production_log. All ranking is deterministic Python.

Reuses the briefing stage-drop heuristic. Order-priority buckets live on
get_today_priority. Read-only: no writes to copilot_state.db.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from backend.config import FACTORY_TODAY, PRODUCTION_DROP_RATIO
from backend.services.briefing import unusual_stage_output
from backend.services.calculations import assess_order_risk, remaining_stages
from backend.services.database import FactoryDB
from backend.services.pace import (
    estimated_remaining_working_days,
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
    "V1 flags stage output below 0.70 × the 30-day median from production_log.",
    "production is the factory-wide queue and last-day vs 30-day median picture.",
    "Not a general anomaly detector. Issues the CSVs cannot define are omitted.",
    "production_log.csv is factory-wide (date × stage), not per order.",
    "Sort order is computed in Python. The model must not rerank.",
]

TODAY_PRIORITY_LIMITATIONS = [
    "1st/2nd/3rd buckets are Python grouping. Copy days_left; do not recompute.",
    "days_left = sum over remaining stages of pieces / 30-day stage median.",
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
        if not risk["at_risk"]:
            continue
        flags = list(risk["flags"])
        issue_type = primary_issue_type(flags)
        priority = PRIORITY_BY_TYPE[issue_type]
        computed = risk["computed"]
        oid = order["order_id"]
        stages_left = remaining_stages(order.get("current_stage") or "")
        days_left = estimated_remaining_working_days(
            int(order.get("pieces") or 0), stages_left, medians
        )
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
                    "factory_today": FACTORY_TODAY.isoformat(),
                    "flags": flags,
                },
                "result": True,
                "rank_score": risk["rank_score"],
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


def discover_factory_issues(db: FactoryDB, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
    collected = sort_issues(collect_stage_issues(db))
    returned = collected[:limit]
    counts = Counter(item["issue_type"] for item in collected)
    empty_message = None
    if not collected:
        empty_message = (
            "No issues matched the V1 discovery rules "
            "(stage output below 0.70 × 30-day median)."
        )
    return {
        "factory_today": FACTORY_TODAY.isoformat(),
        "as_of": FACTORY_TODAY.isoformat(),
        "limit": limit,
        "total_found": len(collected),
        "returned_count": len(returned),
        "counts_by_type": {
            ISSUE_STAGE_BELOW_BASELINE: int(counts.get(ISSUE_STAGE_BELOW_BASELINE, 0)),
        },
        "production": production_attention(db),
        "issues": returned,
        "message": empty_message,
        "limitations": list(LIMITATIONS),
    }


def get_today_priority(db: FactoryDB) -> dict[str, Any]:
    buckets = today_priority(db)
    return {
        "factory_today": FACTORY_TODAY.isoformat(),
        "as_of": FACTORY_TODAY.isoformat(),
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
    if issue_type == ISSUE_ORDER_OVERDUE:
        extra = [f for f in flags if f != "OVERDUE"]
        suffix = f" ({', '.join(extra)})" if extra else ""
        return f"{order_id} is overdue{suffix}"
    if issue_type == ISSUE_ORDER_TIGHT_DUE:
        extra = [f for f in flags if f != "TIGHT_DEADLINE"]
        suffix = f" ({', '.join(extra)})" if extra else ""
        return f"{order_id} has a tight due date{suffix}"
    extra = [f for f in flags if f != "STALLED"]
    suffix = f" ({', '.join(extra)})" if extra else ""
    return f"{order_id} is stalled{suffix}"


def _order_summary(order: dict[str, Any], flags: list[str], computed: dict[str, Any]) -> str:
    return (
        f"{order['order_id']} ({order['customer']} {order['product']}) is "
        f"{order['status']} at {order['current_stage']}, due {order['due_date']}, "
        f"last activity {order['last_activity_date']}. Flags: {', '.join(flags)}. "
        f"calendar_days_until_due={computed['calendar_days_until_due']}; "
        f"working_days_since_last_activity="
        f"{computed['working_days_since_last_activity']}."
    )
