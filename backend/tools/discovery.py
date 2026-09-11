"""Read-only discovery tools.

find_orders: user-directed filters on orders.csv.
discover_factory_issues: ranked issues from defined Python rules.
No generated SQL. No side effects.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import STAGE_COMPLETE, STAGES_IN_ORDER
from backend.services.database import get_db
from backend.services.discovery import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    discover_factory_issues as run_discover_factory_issues,
)
from backend.services.feasibility import match_known_products
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)

ALLOWED_STATUS = {"IN_PROGRESS", "COMPLETE"}
ALLOWED_STAGE = set(STAGES_IN_ORDER) | {STAGE_COMPLETE}
MAX_ROWS = 60


class FindOrdersInput(BaseModel):
    customer: Optional[str] = Field(
        default=None,
        description="Customer name as in orders.csv, e.g. TrendCart. Case-insensitive exact match.",
    )
    product: Optional[str] = Field(
        default=None,
        description=(
            "Product name as spoken (Hoodie, hoodies, Beanie). "
            "Mapped to names that already exist in orders.csv."
        ),
    )
    status: Optional[str] = Field(
        default=None,
        description="IN_PROGRESS or COMPLETE.",
    )
    current_stage: Optional[str] = Field(
        default=None,
        description="KNITTING, ASSEMBLY, WASHING, PACKING, or COMPLETE.",
    )


def _summary(row: dict) -> dict:
    return {
        "order_id": row["order_id"],
        "customer": row["customer"],
        "product": row["product"],
        "pieces": row["pieces"],
        "due_date": row["due_date"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "last_activity_date": row["last_activity_date"],
    }


@tool(args_schema=FindOrdersInput)
def find_orders(
    customer: Optional[str] = None,
    product: Optional[str] = None,
    status: Optional[str] = None,
    current_stage: Optional[str] = None,
) -> str:
    """List orders matching customer, product, status, and/or stage.

    Use to find order ids or list several orders. Always return every match.
    Never pick one order silently. If the manager asks how a named customer
    or product is doing (status of "the TrendCart order"), use get_order_status
    instead — that tool returns AMBIGUOUS when several rows match.

    Do not use this tool for revenue, workers, or feasibility.
    """
    tool_name = "find_orders"
    try:
        if not customer and not product and not status and not current_stage:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "Provide at least one of customer, product, status, or current_stage.",
            )

        status_norm = status.strip().upper() if status else None
        stage_norm = current_stage.strip().upper() if current_stage else None
        if status_norm and status_norm not in ALLOWED_STATUS:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "status must be IN_PROGRESS or COMPLETE.",
                allowed=sorted(ALLOWED_STATUS),
            )
        if stage_norm and stage_norm not in ALLOWED_STAGE:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "current_stage must be KNITTING, ASSEMBLY, WASHING, PACKING, or COMPLETE.",
                allowed=sorted(ALLOWED_STAGE),
            )

        db = get_db()
        product_names = None
        matched_product = None
        if product:
            hits = match_known_products(db.list_products(), product)
            if hits:
                product_names = [row["product"] for row in hits]
                matched_product = product_names[0]
            else:
                product_names = [product.strip()]

        rows = db.find_orders(
            customer=customer,
            products=product_names,
            status=status_norm,
            current_stage=stage_norm,
        )
        filters = {
            k: v
            for k, v in {
                "customer": customer,
                "product": product,
                "matched_product": matched_product,
                "status": status_norm,
                "current_stage": stage_norm,
            }.items()
            if v
        }
        truncated = len(rows) > MAX_ROWS
        visible = rows[:MAX_ROWS]
        logger.info("find_orders count=%s filter=%s", len(rows), filters)
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "count": len(rows),
                    "truncated": truncated,
                    "filter": filters,
                    "orders": [_summary(row) for row in visible],
                    "order_ids": [row["order_id"] for row in visible],
                    "note": (
                        "All matching rows are listed. If the manager asked about "
                        "one order and several match, ask for an order_id."
                    ),
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": filters,
                    "rows": [_summary(row) for row in visible],
                    "calculations": [],
                    "basis": (
                        "Deterministic filters on orders.csv. No generated SQL. "
                        "Product plurals map only to names already in the file."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("find_orders failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


class DiscoverFactoryIssuesInput(BaseModel):
    limit: int = Field(
        default=DEFAULT_LIMIT,
        description="Maximum number of ranked issues to return (1–20). Default 5.",
    )


@tool(args_schema=DiscoverFactoryIssuesInput)
def discover_factory_issues(limit: int = DEFAULT_LIMIT) -> str:
    """Ranked factory issues from defined Python rules (not a general anomaly detector).

    Use when the manager asks what to be concerned about, the biggest factory
    problems, what to pay attention to, or to find top issues. Python discovers
    and sorts: overdue / stalled / tight-deadline orders, and stages whose last
    working-day output is below 0.70 × the 30-day median.

    Do NOT use for a named customer's order list (find_orders), a specific
    order's status (get_order_status), the at-risk order list only
    (get_orders_at_risk), a morning briefing script (get_morning_briefing),
    revenue, or workers.
    """
    tool_name = "discover_factory_issues"
    try:
        if not isinstance(limit, int) or isinstance(limit, bool):
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"limit must be an integer from 1 to {MAX_LIMIT}.",
            )
        if limit < 1 or limit > MAX_LIMIT:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"limit must be an integer from 1 to {MAX_LIMIT}.",
            )
        db = get_db()
        data = run_discover_factory_issues(db, limit=limit)
        logger.info(
            "discover_factory_issues total=%s returned=%s",
            data["total_found"],
            data["returned_count"],
        )
        issues = data["issues"]
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": data,
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv, production_log.csv",
                    "filter": {
                        "factory_today": data["factory_today"],
                        "limit": limit,
                    },
                    "rows": [
                        {
                            "issue_id": item["issue_id"],
                            "issue_type": item["issue_type"],
                            "priority": item["priority"],
                            "order_id": item.get("order_id"),
                            "stage": item.get("stage"),
                        }
                        for item in issues
                    ],
                    "calculations": [
                        {
                            "name": "total_found",
                            "result": data["total_found"],
                        },
                        {
                            "name": "counts_by_type",
                            "result": data["counts_by_type"],
                        },
                    ],
                    "basis": (
                        "Order issues reuse assess_order_risk. Stage issues reuse "
                        "the briefing last-day vs 0.70 × 30-day-median rule. "
                        "Sorted by priority, then existing rank_score / ratio, then id."
                    ),
                },
            }
        )
    except ValueError as exc:
        return tool_error(tool_name, "INVALID_INPUT", str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("discover_factory_issues failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
