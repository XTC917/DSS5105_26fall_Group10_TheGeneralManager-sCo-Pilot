"""Project-wide constants.

Business logic must use FACTORY_TODAY, not the machine clock.
The dataset declares that "today" is 2026-04-01.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "factory.db"
LOG_DIR = PROJECT_ROOT / "logs"

# Dataset clock — do not replace this with date.today().
FACTORY_TODAY = date(2026, 4, 1)

# Production sequence from Factory_Primer.md / data_dictionary.md
STAGES_IN_ORDER = ("KNITTING", "ASSEMBLY", "WASHING", "PACKING")
STAGE_COMPLETE = "COMPLETE"

# Sunday = 6 in Python's datetime.weekday(). Factory is closed on Sundays.
CLOSED_WEEKDAY = 6

# An in-progress order is STALLED when this many working days have passed
# since last_activity_date (not counting last_activity_date itself).
STALL_WORKING_DAYS = 3

# Feasibility: use this many trailing working days of production_log to
# estimate typical factory throughput (median pieces/day per stage).
THROUGHPUT_LOOKBACK_WORKING_DAYS = 30
