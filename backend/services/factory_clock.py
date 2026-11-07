"""One shared factory date. An administrator chooses it; every account reads it."""
import re
from datetime import date
from typing import Any

from backend.config import FACTORY_TODAY
from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect


DATED_CSVS = ("orders.csv", "production_log.csv")


def query_date_for(clock: date, latest: date | None = None) -> date:
    """The chosen factory date is the date queries use."""
    return clock


def named_csvs(source: str) -> set[str]:
    text = source or ""
    return {name for name in DATED_CSVS if name in text}


def stale_csv_updates(db: Any, used: set[str], day: date) -> list[tuple[str, date]]:
    """CSVs this answer or board actually read whose newest record is before day."""
    latest = db.csv_latest_updates()
    stale: list[tuple[str, date]] = []
    for name in DATED_CSVS:
        if name not in used:
            continue
        updated = latest.get(name)
        if updated is not None and updated < day:
            stale.append((name, updated))
    return stale


def partial_update_note(
    stale: list[tuple[str, date]],
    question: str = "",
    *,
    bold: bool = True,
) -> str:
    """Say which used CSVs stop before the factory date. Empty when none do."""
    if not stale:
        return ""
    zh = bool(re.search(r"[\u4e00-\u9fff]", question or ""))
    labels = [_csv_label(name) for name, _day in stale]
    if zh:
        if len({day for _name, day in stale}) == 1:
            text = f"部分数据的更新时间截止 {stale[0][1].isoformat()}（{'、'.join(labels)}）。"
        else:
            bits = "、".join(f"{_csv_label(name)} {day.isoformat()}" for name, day in stale)
            text = f"部分数据的更新时间截止 {bits}。"
    elif len({day for _name, day in stale}) == 1:
        text = (
            "Some of the data used here was last updated through "
            f"{stale[0][1].isoformat()} ({', '.join(labels)})."
        )
    else:
        bits = ", ".join(f"{_csv_label(name)} {day.isoformat()}" for name, day in stale)
        text = f"Some of the data used here was last updated through {bits}."
    return f"**{text}**" if bold else text


def _csv_label(name: str) -> str:
    return name.removesuffix(".csv")


def query_factory_date() -> tuple[date, date]:
    """Return the saved clock. Queries use that same date."""
    clock = load_factory_date()
    return clock, clock


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
