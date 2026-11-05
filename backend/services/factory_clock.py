"""One shared factory date. An administrator chooses it; every account reads it."""
from datetime import date

from backend.config import FACTORY_TODAY
from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect


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
