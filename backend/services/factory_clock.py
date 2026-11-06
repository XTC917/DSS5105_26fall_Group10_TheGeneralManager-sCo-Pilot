"""One shared factory date. An administrator chooses it; every account reads it."""
import re
from datetime import date, timedelta

from backend.config import FACTORY_TODAY
from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect


def query_date_for(clock: date, latest: date | None) -> date:
    """Use the day after the newest record when the clock is two or more days ahead.

    Factory queries only see the day before their date, so that day is the latest
    record itself.
    """
    if latest is not None and (clock - latest).days >= 2:
        return latest + timedelta(days=1)
    return clock


def data_hold_note(as_of: date, question: str = "") -> str:
    """English unless the manager's question contains Chinese."""
    day = as_of.isoformat()
    if re.search(r"[\u4e00-\u9fff]", question or ""):
        return f"**回答截止到 {day}，之后的数据还未更新。**"
    return f"**Data is current through {day}. Records after that date have not been updated.**"


def query_factory_date() -> tuple[date, date]:
    """Return the saved clock and the date data queries should use."""
    from backend.services.database import FactoryDB

    clock = load_factory_date()
    return clock, query_date_for(clock, FactoryDB().latest_record_date())


def load_factory_date() -> date:
    with connect(admin=True) as conn:
        row = conn.execute(
            f"SELECT factory_date FROM {COPILOT_SCHEMA}.factory_clocks WHERE id = 1",
        ).fetchone()
    return row["factory_date"] if row else FACTORY_TODAY


def set_factory_date(day: date) -> date:
    """Replace the shared factory date. Any calendar day is allowed."""
    with connect(admin=True) as conn:
        row = conn.execute(
            f"""INSERT INTO {COPILOT_SCHEMA}.factory_clocks (id, factory_date)
                VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET factory_date = EXCLUDED.factory_date
                RETURNING factory_date""",
            (day,),
        ).fetchone()
    return row["factory_date"]
