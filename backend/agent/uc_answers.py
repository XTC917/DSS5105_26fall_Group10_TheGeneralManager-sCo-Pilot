"""Pinned answers for an exact question. Not a similarity match.

Add another object under answers in data/uc_answers.json.
Delete this module, that file, and the call in run_agent to remove it.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from functools import lru_cache
from typing import Any

from backend.config import PROJECT_ROOT
from backend.services.calculations import is_working_day, parse_iso_date

logger = logging.getLogger(__name__)

ANSWERS_PATH = PROJECT_ROOT / "data" / "uc_answers.json"
# Same order and colors as the weekly briefing "4-stage complete pieces" chart.
_STAGE_LINES = (
    ("ASSEMBLY", "#4c78a8"),
    ("KNITTING", "#f28e2b"),
    ("PACKING", "#8d8d8d"),
    ("WASHING", "#e6b325"),
)
_STAGE_DAILY_DAYS = 30


def stage_daily_chart(log: list[dict[str, Any]], today: date, days: int = _STAGE_DAILY_DAYS) -> dict[str, Any]:
    """Daily pieces for the last N working days before today, plus each stage mean."""
    found: set[date] = set()
    for row in log:
        day = parse_iso_date(row.get("date"))
        if day is not None and day < today and is_working_day(day):
            found.add(day)
    chosen = sorted(found)[-days:]
    totals = {day: {stage: 0 for stage, _color in _STAGE_LINES} for day in chosen}
    allowed = set(chosen)
    for row in log:
        day = parse_iso_date(row.get("date"))
        stage = row.get("stage")
        if day not in allowed or stage not in totals.get(day, {}):
            continue
        totals[day][stage] += int(row.get("pieces_completed") or 0)
    count = len(chosen)
    means = {
        stage: round(sum(totals[day][stage] for day in chosen) / count, 1) if count else 0
        for stage, _color in _STAGE_LINES
    }
    data = []
    for day in chosen:
        item = {"date": day.isoformat(), **totals[day]}
        for stage, _color in _STAGE_LINES:
            item[f"{stage}_mean"] = means[stage]
        data.append(item)
    return {
        "type": "stage_daily",
        "title": "4-stage complete pieces",
        "subtitle": "Past 30 working days. Dashed line is the mean.",
        "stages": [
            {"key": stage, "color": color, "mean": means[stage]}
            for stage, color in _STAGE_LINES
        ],
        "data": data,
    }


@lru_cache(maxsize=1)
def _load(mtime: float) -> tuple[dict[str, Any], ...]:
    if not ANSWERS_PATH.is_file():
        return ()
    raw = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))
    rows = []
    for row in raw.get("answers") or []:
        question = row.get("question")
        answer = row.get("answer")
        if isinstance(question, str) and question and isinstance(answer, str) and answer:
            rows.append(row)
    return tuple(rows)


def match_uc_answer(message: str) -> dict[str, Any] | None:
    """Return the pinned answer only when the message is the same string."""
    text = message or ""
    mtime = ANSWERS_PATH.stat().st_mtime if ANSWERS_PATH.is_file() else 0.0
    for row in _load(mtime):
        if text == row.get("question"):
            logger.info("uc answer hit")
            return row
    return None


def uc_why_traces() -> list[dict[str, Any]]:
    """Rows that make Why show the pinned four steps. Not a tool call."""
    return [{
        "tool": "uc_answer",
        "rows": [
            {
                "order_id": "ORD-029",
                "customer": "Northwind Apparel",
                "product": "Beanie",
                "pieces": 1500,
                "due_date": "2026-04-01",
                "current_stage": "WASHING",
            },
            {
                "order_id": "ORD-108",
                "customer": "Harbor Knits",
                "product": "Scarf",
                "pieces": 2000,
                "due_date": "2026-04-03",
                "current_stage": "ASSEMBLY",
            },
            {
                "order_id": "ORD-103",
                "customer": "Bright Basics",
                "product": "Scarf",
                "pieces": 2000,
                "due_date": "2026-04-04",
                "current_stage": "ASSEMBLY",
            },
        ],
        "calculations": [{"name": "days_left"}],
    }]


def play_uc_answer(message: str, progress) -> dict[str, Any] | None:
    """Hold each listed stage, then return the pinned reply. No model call."""
    row = match_uc_answer(message)
    if row is None:
        return None
    stage_ms = int(row.get("stage_ms") or 1500)
    for stage in row.get("stages") or []:
        if progress:
            progress(str(stage))
        time.sleep(max(0, stage_ms) / 1000)
    charts = []
    if row.get("reserve_chart"):
        from backend.config import FACTORY_TODAY
        from backend.services.database import get_db

        charts = [stage_daily_chart(get_db().production_log(), FACTORY_TODAY)]
    return {
        "answer": str(row.get("answer") or ""),
        "tools_used": [],
        "traces": uc_why_traces(),
        "proposed_actions": [],
        "clarification": None,
        "limitation": None,
        "charts": charts,
        "tables": [],
        "instant": True,
        "routing_intent": "uc_answer",
    }
