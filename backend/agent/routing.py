"""Inspectable pre-routing. Runs before the LLM picks a tool.

This is not a second agent and it does no arithmetic. If an intercept regex
matches, we return a limitation and never call an unrelated tool.

Fill FINANCIAL_KEYWORDS / WORKER_KEYWORDS / OTHER_MISSING_KEYWORDS to enable
short-circuit. Leave them empty (current default) so nothing is intercepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PROCEED = "proceed"
UNSUPPORTED = "unsupported"
ACTION_NOT_IMPLEMENTED = "action_not_implemented"  # unused; actions are now registered tools

# VERBOSE regex alternatives. Empty string = this bucket does not intercept.
FINANCIAL_KEYWORDS = r""
WORKER_KEYWORDS = r""
OTHER_MISSING_KEYWORDS = r""


def _compile_intercept(terms: str) -> re.Pattern[str] | None:
    if not (terms or "").strip():
        return None
    return re.compile(terms, re.IGNORECASE | re.VERBOSE)


_FINANCIAL = _compile_intercept(FINANCIAL_KEYWORDS)
_WORKERS = _compile_intercept(WORKER_KEYWORDS)
_OTHER_MISSING = _compile_intercept(OTHER_MISSING_KEYWORDS)

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

    if _FINANCIAL is not None and _FINANCIAL.search(text):
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

    if _WORKERS is not None and _WORKERS.search(text):
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

    if _OTHER_MISSING is not None and _OTHER_MISSING.search(text):
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
