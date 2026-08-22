"""Inspectable pre-routing. Runs before the LLM picks a tool.

This is not a second agent and it does no arithmetic. It only decides whether
the requested information exists in the Track 1 tables. If it does not, we
return a limitation and never call an unrelated tool.

Available columns (do not invent others):

* orders: order_id, customer, product, category, pieces, order_date, due_date,
  status, current_stage, last_activity_date, completed_date, days_late
* production_log: date, stage, pieces_completed
* workshops: workshop_id, name, capacity_pieces_per_day, pickup_lead_days,
  defect_rate, cost_per_piece, makes, status, max_batch_pieces,
  current_queue_days, notes

Not in the dataset: selling price, revenue, profit, worker names.
workshop cost_per_piece is a subcontractor charge, not a garment selling price.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PROCEED = "proceed"
UNSUPPORTED = "unsupported"
ACTION_NOT_IMPLEMENTED = "action_not_implemented"

# Workshop cost_per_piece is in workshops.csv. Do not treat "cost" alone as
# missing selling-price data.
_FINANCIAL = re.compile(
    r"""
    \b(
        revenues? |
        profits? |
        (gross\s+)?margin |
        ebitda |
        selling[-\s]?prices? |
        unit[-\s]?prices? |
        sale\s+prices? |
        sales\s+(revenue|total|income) |
        turnover |
        (net\s+)?income\s+from |
        how\s+much\s+(money\s+)?(did\s+we|have\s+we|we)\s+(make|made|earn|earned) |
        what\s+did\s+we\s+(make|earn)\s+from |
        what\s+did\s+\w+\s+pay\s+(us|you) |
        garment\s+prices? |
        (hoodie|beanie|scarf|vest|cardigan)\s+prices?
    )\b
    |营收|利润|售价|销售额|营业收入
    """,
    re.IGNORECASE | re.VERBOSE,
)

_WORKERS = re.compile(
    r"""
    \b(
        who\s+is\s+(working|assigned|on\s+duty) |
        worker\s+names? |
        operators? |
        employees? |
        staff\s+members? |
        packing\s+manager |
        knitters?
    )\b
    |工人|员工姓名
    """,
    re.IGNORECASE | re.VERBOSE,
)

_OTHER_MISSING = re.compile(
    r"""
    \b(
        customer\s+(phone|email|address) |
        raw\s+materials? |
        fabric\s+inventory |
        machine\s+serial |
        tracking\s+number
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ACTION = re.compile(
    r"""
    \b(
        (draft|send|write)\s+(an?\s+)?(chase[- ]up\s+)?emails? |
        email\s+(the\s+)?(customer|workshop) |
        chase\s+(them|the\s+customer)\s+up |
        add\s+(an?\s+)?notes? |
        create\s+(a\s+)?reminders? |
        remind\s+me |
        set\s+(a\s+)?reminder
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class RoutingDecision:
    intent: str
    short_circuit: bool
    reason: str
    answer: str | None = None
    missing: list[str] = field(default_factory=list)
    suggested_tool: str | None = None


def route_query(message: str) -> RoutingDecision:
    """Classify a manager question before any tool is selected."""
    text = (message or "").strip()
    if not text:
        return RoutingDecision(
            intent=UNSUPPORTED,
            short_circuit=True,
            reason="empty_query",
            answer="Please ask a factory operations question.",
            missing=[],
        )

    if _ACTION.search(text):
        return RoutingDecision(
            intent=ACTION_NOT_IMPLEMENTED,
            short_circuit=True,
            reason="action_tools_not_in_mvp",
            answer=(
                "I cannot do that yet. Email, order notes, and reminders are not "
                "implemented in this MVP. When they are added, the system will "
                "propose the action, wait for your explicit confirmation, execute "
                "it, and write an audit record. Nothing has been sent or saved."
            ),
            missing=["action_confirmation_flow", "audit_log"],
        )

    if _FINANCIAL.search(text):
        return RoutingDecision(
            intent=UNSUPPORTED,
            short_circuit=True,
            reason="no_selling_price_or_revenue",
            answer=(
                "I cannot answer that from the available factory data because no "
                "selling-price, revenue, or profit field is provided. "
                "orders.csv has piece counts and dates, not what the customer paid. "
                "workshops.csv cost_per_piece is what an outside workshop charges "
                "us, not a garment selling price. I will not invent a number."
            ),
            missing=["selling_price", "revenue", "profit"],
        )

    if _WORKERS.search(text):
        return RoutingDecision(
            intent=UNSUPPORTED,
            short_circuit=True,
            reason="no_worker_names",
            answer=(
                "I cannot answer that from the available factory data because "
                "the tables do not contain worker names, operators, or staff "
                "assignments. I will not invent a person."
            ),
            missing=["worker_name", "operator", "staff_assignment"],
        )

    if _OTHER_MISSING.search(text):
        return RoutingDecision(
            intent=UNSUPPORTED,
            short_circuit=True,
            reason="field_not_in_dataset",
            answer=(
                "I cannot answer that from the available factory data. The "
                "supplied files are orders, factory-wide daily production by "
                "stage, and outside-workshop profile cards. That requested "
                "field is not among them."
            ),
            missing=["requested_field_not_in_csvs"],
        )

    return RoutingDecision(
        intent=PROCEED,
        short_circuit=False,
        reason="in_scope_for_registered_tools",
        suggested_tool=None,
    )
