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

from backend.config import PRODUCTION_DROP_RATIO, PROJECT_ROOT
from backend.services.calculations import is_working_day, median_or_none, parse_iso_date

logger = logging.getLogger(__name__)

ANSWERS_PATH = PROJECT_ROOT / "data" / "uc_answers.json"
_ASSEMBLY = "ASSEMBLY"
_ASSEMBLY_COLOR = "#4c78a8"
_ALERT_COLOR = "#bf5145"
_STAGE_DAILY_DAYS = 30
_LABEL_DATE = "2026-03-31"


def stage_daily_chart(
    log: list[dict[str, Any]],
    today: date,
    days: int = _STAGE_DAILY_DAYS,
    median: float | None = None,
) -> dict[str, Any]:
    """Assembly pieces for the last N working days, its 30-day median, and the alert line."""
    found: set[date] = set()
    for row in log:
        day = parse_iso_date(row.get("date"))
        if day is not None and day < today and is_working_day(day):
            found.add(day)
    chosen = sorted(found)[-days:]
    totals = {day: 0 for day in chosen}
    recorded: list[int] = []
    for row in log:
        day = parse_iso_date(row.get("date"))
        if day not in totals or row.get("stage") != _ASSEMBLY:
            continue
        pieces = int(row.get("pieces_completed") or 0)
        totals[day] += pieces
        recorded.append(pieces)
    if median is None:
        median = median_or_none(recorded if recorded else list(totals.values()))
    median_value = round(float(median or 0), 1)
    threshold = round(median_value * PRODUCTION_DROP_RATIO, 1)
    data = [
        {
            "date": day.isoformat(),
            _ASSEMBLY: totals[day],
            "median": median_value,
            "alert_threshold": threshold,
        }
        for day in chosen
    ]
    return {
        "type": "stage_daily",
        "title": "Assembly complete pieces",
        "subtitle": "Past 30 working days.",
        "label_date": _LABEL_DATE,
        "stages": [{"key": _ASSEMBLY, "color": _ASSEMBLY_COLOR, "median": median_value}],
        "threshold": threshold,
        "threshold_color": _ALERT_COLOR,
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


_BRIEFING_SOURCE = "orders.csv, production_log.csv, workshops.csv"


def compose_uc_why(message: str, answer: str, source_trace: dict[str, Any] | None) -> dict[str, Any]:
    """Keep the pinned four steps. The source line names the briefing files only."""
    from backend.services.why import build_why

    why = build_why(message, {"answer": answer, "traces": uc_why_traces()})
    name = _BRIEFING_SOURCE
    count = 0
    if isinstance(source_trace, dict) and source_trace.get("source_file"):
        name = str(source_trace["source_file"])
        count = len([row for row in source_trace.get("rows") or [] if isinstance(row, dict)])
    why["sources"] = [{"name": name, "row_count": count, "rows": [], "summary_only": True}]
    return why


def _briefing_source_trace() -> dict[str, Any] | None:
    from backend.tools.briefing import get_morning_briefing

    try:
        payload = json.loads(get_morning_briefing.invoke({}))
    except Exception:  # noqa: BLE001
        logger.exception("uc briefing source failed")
        return None
    trace = payload.get("trace") if isinstance(payload, dict) else None
    if isinstance(trace, dict) and trace.get("source_file"):
        return trace
    return None


def play_uc_answer(message: str, progress) -> dict[str, Any] | None:
    """Hold each listed stage, then return the pinned reply. No model call."""
    row = match_uc_answer(message)
    if row is None:
        return None
    answer = str(row.get("answer") or "")
    charts = []
    source_trace = None
    if row.get("reserve_chart"):
        from backend.config import FACTORY_TODAY
        from backend.services.database import get_db
        from backend.services.feasibility import stage_throughput_medians

        db = get_db()
        medians = stage_throughput_medians(db)["medians_pieces_per_working_day"]
        charts = [stage_daily_chart(db.production_log(), FACTORY_TODAY, median=medians.get(_ASSEMBLY))]
        source_trace = _briefing_source_trace()
    stage_ms = int(row.get("stage_ms") or 1500)
    for stage in row.get("stages") or []:
        if progress:
            progress(str(stage))
        time.sleep(max(0, stage_ms) / 1000)
    return {
        "answer": answer,
        "why": compose_uc_why(message, answer, source_trace),
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
