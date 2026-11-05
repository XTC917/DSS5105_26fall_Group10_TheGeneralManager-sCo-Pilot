"""Persistent, per-account factory dates for the demo."""
from datetime import date, timedelta

from backend.config import FACTORY_TODAY
from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect


def load_factory_date(user_id: int) -> date:
    with connect(admin=True) as conn:
        row = conn.execute(
            f"SELECT factory_date FROM {COPILOT_SCHEMA}.factory_clocks WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    return row["factory_date"] if row else FACTORY_TODAY


def advance_factory_date(user_id: int, expected: date) -> date | None:
    """Advance exactly once for the date shown by the caller."""
    if not FACTORY_TODAY <= expected < date.max:
        return None
    with connect(admin=True) as conn:
        conn.execute(
            f"""INSERT INTO {COPILOT_SCHEMA}.factory_clocks (user_id, factory_date)
                VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING""",
            (user_id, FACTORY_TODAY),
        )
        row = conn.execute(
            f"""UPDATE {COPILOT_SCHEMA}.factory_clocks SET factory_date = %s
                WHERE user_id = %s AND factory_date = %s RETURNING factory_date""",
            (expected + timedelta(days=1), user_id, expected),
        ).fetchone()
    return row["factory_date"] if row else None
