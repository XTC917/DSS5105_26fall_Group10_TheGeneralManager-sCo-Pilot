"""Project-wide constants.

Business logic uses the active factory date. FACTORY_TODAY is the dataset baseline.
The dataset declares that "today" is 2026-04-01.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Always load the repo-root .env, even if uvicorn's cwd is elsewhere.
load_dotenv(PROJECT_ROOT / ".env", override=True)
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "factory.db"
SEMANTIC_LAYER_PATH = DATA_DIR / "semantic_layer.yaml"
LOG_DIR = PROJECT_ROOT / "logs"
# Local notes/reminders/audit. Survives CSV reload of factory.db.
STATE_DB_PATH = DATA_DIR / "copilot_state.db"

# Dataset clock — do not replace this with date.today().
FACTORY_TODAY = date(2026, 4, 1)
_factory_date: ContextVar[date] = ContextVar("factory_date", default=FACTORY_TODAY)


def factory_date() -> date:
    return _factory_date.get()


@contextmanager
def using_factory_date(day: date):
    """Keep the business date fixed for the duration of one request."""
    token = _factory_date.set(day)
    try:
        yield
    finally:
        _factory_date.reset(token)

# Order lifecycle: ORDERED is an order state, not a production_log stage.
# Production stages (production_log grain) are KNITTING -> ASSEMBLY -> WASHING -> PACKING.
ORDER_LIFECYCLE_IN_ORDER = ("ORDERED", "KNITTING", "ASSEMBLY", "WASHING", "PACKING")
PRODUCTION_STAGES_IN_ORDER = ("KNITTING", "ASSEMBLY", "WASHING", "PACKING")
# Kept for backwards compatibility: full order lifecycle including ORDERED.
STAGES_IN_ORDER = ORDER_LIFECYCLE_IN_ORDER
ORDERED_STAGE = "ORDERED"
STAGE_COMPLETE = "COMPLETE"

# Sunday = 6 in Python's datetime.weekday(). Factory is closed on Sundays.
CLOSED_WEEKDAY = 6

# An in-progress order is STALLED when this many working days have passed
# since last_activity_date (not counting last_activity_date itself).
STALL_WORKING_DAYS = 3

# Feasibility: use this many trailing working days of production_log to
# estimate typical factory throughput (median pieces/day per stage).
THROUGHPUT_LOOKBACK_WORKING_DAYS = 30

# Morning briefing: flag a stage if last working day's output is below this
# fraction of the lookback median. Inspectable; not hidden in a prompt.
PRODUCTION_DROP_RATIO = 0.70
