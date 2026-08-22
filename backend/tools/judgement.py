"""Judgement tools: explicit, inspectable rules. Nothing here is hidden in a prompt."""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.services.database import get_db
from backend.services.feasibility import check_feasibility as run_feasibility
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)


class CheckFeasibilityInput(BaseModel):
    pieces: int = Field(..., description="How many garments are requested, e.g. 800")
    due_date: str = Field(
        ...,
        description="Due date as YYYY-MM-DD. If the user said 'August 25' and the dataset year is 2026, use 2026-08-25.",
    )
    product: Optional[str] = Field(
        default=None,
        description="Product name such as Hoodie. Used to map to TOPS or ACCESSORIES via orders.csv.",
    )
    category: Optional[str] = Field(
        default=None,
        description="TOPS or ACCESSORIES. Use this if the product is not in orders.csv.",
    )


@tool(args_schema=CheckFeasibilityInput)
def check_feasibility(
    pieces: int,
    due_date: str,
    product: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """Estimate whether the factory can take a new order by a due date.

    All arithmetic is done in Python. You must call this tool instead of calculating
    capacity yourself. The result includes a verdict, spare factory capacity,
    workshop overflow, and a limitations list — quote the limitations when relevant.

    Use for questions like "Can we take 800 hoodies by August 25?".
    """
    try:
        db = get_db()
        result = run_feasibility(
            db,
            pieces=pieces,
            due_date=due_date,
            product=product,
            category=category,
        )
        logger.info(
            "check_feasibility pieces=%s due=%s verdict=%s",
            pieces,
            due_date,
            result.get("data", {}).get("verdict") if result.get("ok") else result.get("error"),
        )
        return tool_json(result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("check_feasibility failed")
        return tool_error("check_feasibility", "INTERNAL", str(exc))
