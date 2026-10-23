"""Factory-wide daily output by stage for the last N working days.

production_log is one row per stage per day. This tool does not rank
stability, count finished orders, or measure queue length.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import FACTORY_TODAY, PRODUCTION_STAGES_IN_ORDER
from backend.services.calculations import is_working_day, parse_iso_date
from backend.services.database import get_db
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)

MAX_WORKING_DAYS = 60


class GetStageOutputInput(BaseModel):
    working_days: int = Field(
        default=30,
        ge=1,
        le=MAX_WORKING_DAYS,
        description=(
            "How many working days of production_log to include, ending the "
            "last working day before factory today. Sundays are closed and "
            "are not counted. Default 30."
        ),
    )


def _working_dates(log: list[dict[str, Any]], today: date) -> list[date]:
    found: set[date] = set()
    for row in log:
        day = parse_iso_date(row.get("date"))
        if day is not None and day < today and is_working_day(day):
            found.add(day)
    return sorted(found)


def _pieces_by_day(
    log: list[dict[str, Any]], window: set[date]
) -> dict[date, dict[str, int]]:
    totals: dict[date, dict[str, int]] = {day: {} for day in window}
    for row in log:
        day = parse_iso_date(row.get("date"))
        stage = row.get("stage")
        if day not in window or stage not in PRODUCTION_STAGES_IN_ORDER:
            continue
        totals[day][stage] = totals[day].get(stage, 0) + int(row["pieces_completed"])
    return totals


@tool(args_schema=GetStageOutputInput)
def get_stage_output(working_days: int = 30) -> str:
    """Daily factory output for knitting, assembly, washing, and packing.

    Use when the manager wants the stage output series over recent working
    days. Copy the series. Do not rank which stage is most unstable.
    This is not order completions and not a queue length.
    """
    tool_name = "get_stage_output"
    try:
        if working_days < 1 or working_days > MAX_WORKING_DAYS:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"working_days must be from 1 to {MAX_WORKING_DAYS}.",
            )
        log = get_db().production_log()
        available = _working_dates(log, FACTORY_TODAY)
        chosen = available[-working_days:]
        daily = _pieces_by_day(log, set(chosen))
        series = [
            {
                "date": day.isoformat(),
                **{stage: daily[day].get(stage, 0) for stage in PRODUCTION_STAGES_IN_ORDER},
            }
            for day in chosen
        ]
        logger.info(
            "get_stage_output days=%s requested=%s",
            len(chosen),
            working_days,
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "factory_today": FACTORY_TODAY.isoformat(),
                    "window_working_days_requested": working_days,
                    "window_working_days": len(chosen),
                    "date_from": chosen[0].isoformat() if chosen else None,
                    "date_to": chosen[-1].isoformat() if chosen else None,
                    "series": series,
                    "limitations": [
                        "Factory-wide production_log totals by date and stage. Not per order.",
                        "Does not measure queue length or orders waiting at a stage.",
                        "Does not rank stage stability.",
                        "The window is the last N working days before factory today. Sundays are excluded.",
                        "A short or unfinished week is only the working days already in the log. Missing days are not filled in.",
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "production_log.csv",
                    "filter": {
                        "factory_today": FACTORY_TODAY.isoformat(),
                        "working_days": working_days,
                    },
                    "rows": series,
                    "calculations": [],
                    "basis": "Working days before 2026-04-01, Sundays excluded. Pieces are copied from production_log.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_stage_output failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
