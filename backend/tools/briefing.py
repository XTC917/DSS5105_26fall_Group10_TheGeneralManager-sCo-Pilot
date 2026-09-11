"""Morning briefing tool. Returns structured facts; the LLM writes the prose."""

from __future__ import annotations

import logging

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.services.briefing import build_morning_briefing
from backend.services.database import get_db
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)


class MorningBriefingInput(BaseModel):
    unused: Optional[str] = Field(
        default=None,
        description="Leave empty. This tool takes no filters.",
    )


@tool(args_schema=MorningBriefingInput)
def get_morning_briefing(unused: Optional[str] = None) -> str:
    """Structured morning operations briefing from factory tables.

    Use when the manager asks for this morning's briefing or a daily ops summary.
    Reuses get_orders_at_risk for risk flags. Do not invent extra facts.
    Summarize the JSON; do not treat it as a script.
    For only the at-risk list, get_orders_at_risk is enough.
    For ranked "what should I be concerned about", use discover_factory_issues.
    """
    tool_name = "get_morning_briefing"
    try:
        data = build_morning_briefing(get_db())
        logger.info(
            "get_morning_briefing at_risk=%s in_progress=%s",
            data["at_risk"]["count"],
            data["in_progress_order_count"],
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": data,
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv, production_log.csv, workshops.csv",
                    "filter": {"factory_today": data["factory_today"]},
                    "rows": data["at_risk"]["orders"],
                    "calculations": [
                        {
                            "name": "at_risk_count",
                            "result": data["at_risk"]["count"],
                        },
                        {
                            "name": "flag_counts",
                            "result": data["at_risk"]["flag_counts"],
                        },
                    ],
                    "basis": (
                        "Risk flags reuse get_orders_at_risk. Stage output compares "
                        "the last working day in production_log to the 30-day median. "
                        "No selling prices or worker names."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_morning_briefing failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
