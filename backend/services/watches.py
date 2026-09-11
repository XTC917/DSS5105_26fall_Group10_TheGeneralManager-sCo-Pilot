"""Standing watches: persist, evaluate, fire local alerts.

Business conditions are evaluated in Python against a factory `as_of` date.
The LLM must never decide whether a watch should fire.

Notification is a separate layer. V1 only has LocalWatchNotifier (the alert is
already in watch_events). A later EmailWatchNotifier can implement the same
protocol; notify failures must not un-fire a watch.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from backend.config import FACTORY_TODAY
from backend.services.audit import connect_state, record_event
from backend.services.calculations import parse_iso_date
from backend.services.database import get_db

logger = logging.getLogger(__name__)

CONDITION_INACTIVE = "ORDER_INACTIVE_BY_DATE"
STATUS_ACTIVE = "ACTIVE"
STATUS_FIRED = "FIRED"
STATUS_CANCELLED = "CANCELLED"
NOTIFY_LOCAL = "local"
EVENT_FIRED = "fired"
DELIVERY_LOCAL = "local_recorded"

ALLOWED_CONDITIONS = frozenset({CONDITION_INACTIVE})

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class WatchError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.candidates = candidates or []


@dataclass(frozen=True)
class NotificationResult:
    delivered: bool
    channel: str
    detail: str


class WatchNotifier(Protocol):
    """Delivery only. Must not decide whether the business condition is true."""

    def notify(self, watch: dict[str, Any], event: dict[str, Any]) -> NotificationResult:
        ...


class LocalWatchNotifier:
    """V1: the local alert is the watch_event row already written."""

    def notify(self, watch: dict[str, Any], event: dict[str, Any]) -> NotificationResult:
        return NotificationResult(
            delivered=True,
            channel=NOTIFY_LOCAL,
            detail="Local alert already recorded in watch_events.",
        )


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_check_date(raw: str, *, origin: date = FACTORY_TODAY) -> date:
    """Map ISO dates or weekday names onto the factory calendar.

    Factory today is Wednesday 2026-04-01, so Thursday → 2026-04-02.
    Does not use the computer clock.
    """
    text = (raw or "").strip()
    if not text:
        raise WatchError("INVALID_INPUT", "check_date is required.")
    try:
        parsed = parse_iso_date(text)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed
    key = text.lower().replace(".", "")
    if key not in _WEEKDAY_INDEX:
        raise WatchError(
            "INVALID_INPUT",
            "check_date must be YYYY-MM-DD or a weekday name (e.g. Thursday).",
        )
    target = _WEEKDAY_INDEX[key]
    delta = (target - origin.weekday()) % 7
    return origin + timedelta(days=delta)


def condition_inactive_by_date(
    order: dict[str, Any],
    *,
    check_date: date,
    as_of: date,
) -> tuple[bool, dict[str, Any]]:
    """ORDER_INACTIVE_BY_DATE. Pure; no LLM; no date.today()."""
    status = order.get("status")
    last_activity = parse_iso_date(order.get("last_activity_date"))
    met = (
        as_of >= check_date
        and status == "IN_PROGRESS"
        and last_activity is not None
        and last_activity < check_date
    )
    snapshot = {
        "order_id": order.get("order_id"),
        "status": status,
        "current_stage": order.get("current_stage"),
        "last_activity_date": last_activity.isoformat() if last_activity else None,
        "check_date": check_date.isoformat(),
        "as_of": as_of.isoformat(),
        "condition_type": CONDITION_INACTIVE,
        "formula": (
            "as_of >= check_date AND status == IN_PROGRESS "
            "AND last_activity_date < check_date"
        ),
        "inputs": {
            "as_of": as_of.isoformat(),
            "check_date": check_date.isoformat(),
            "status": status,
            "last_activity_date": last_activity.isoformat() if last_activity else None,
        },
        "result": met,
        "source_file": "orders.csv",
    }
    return met, snapshot


def _row_to_watch(row: Any) -> dict[str, Any]:
    item = dict(row)
    raw = item.get("params_json")
    if isinstance(raw, str):
        try:
            item["params"] = json.loads(raw)
        except json.JSONDecodeError:
            item["params"] = {}
    else:
        item["params"] = raw or {}
    return item


def list_watches(
    *,
    status: str | None = None,
    order_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if order_id:
        clauses.append("order_id = ? COLLATE NOCASE")
        params.append(order_id.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect_state() as conn:
        rows = conn.execute(
            f"SELECT * FROM watches{where} ORDER BY id DESC",
            tuple(params),
        ).fetchall()
    return [_row_to_watch(r) for r in rows]


def get_watch(watch_id: int) -> dict[str, Any] | None:
    with connect_state() as conn:
        row = conn.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)).fetchone()
    return _row_to_watch(row) if row else None


def list_watch_events(*, watch_id: int | None = None) -> list[dict[str, Any]]:
    with connect_state() as conn:
        if watch_id is not None:
            rows = conn.execute(
                "SELECT * FROM watch_events WHERE watch_id = ? ORDER BY id DESC",
                (watch_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM watch_events ORDER BY id DESC").fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw = item.get("snapshot_json")
        if isinstance(raw, str):
            try:
                item["snapshot"] = json.loads(raw)
            except json.JSONDecodeError:
                item["snapshot"] = None
        items.append(item)
    return items


def create_watch_row(
    *,
    order_id: str,
    condition_type: str,
    check_date: date,
    message: str,
) -> dict[str, Any]:
    if condition_type != CONDITION_INACTIVE:
        raise WatchError(
            "INVALID_INPUT",
            f"Unsupported condition_type {condition_type!r}. "
            f"V1 only supports {CONDITION_INACTIVE}.",
        )
    now = _now_utc()
    params = {"check_date": check_date.isoformat()}
    with connect_state() as conn:
        cur = conn.execute(
            """
            INSERT INTO watches (
                created_at, created_factory_today, order_id, condition_type,
                params_json, message, status, last_evaluated_as_of, fired_as_of,
                fired_at, notify_channel
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
            """,
            (
                now,
                FACTORY_TODAY.isoformat(),
                order_id,
                CONDITION_INACTIVE,
                json.dumps(params),
                message,
                STATUS_ACTIVE,
                NOTIFY_LOCAL,
            ),
        )
        watch_id = int(cur.lastrowid)
    watch = get_watch(watch_id)
    assert watch is not None
    return watch


def watch_summary(watch: dict[str, Any]) -> dict[str, Any]:
    params = watch.get("params") or {}
    return {
        "watch_id": watch["id"],
        "order_id": watch["order_id"],
        "condition_type": watch["condition_type"],
        "check_date": params.get("check_date"),
        "status": watch["status"],
        "message": watch.get("message"),
        "created_at": watch.get("created_at"),
        "fired_as_of": watch.get("fired_as_of"),
        "fired_at": watch.get("fired_at"),
    }


def resolve_watch_for_cancel(
    *,
    watch_id: int | None = None,
    order_id: str | None = None,
) -> dict[str, Any]:
    """Pick exactly one ACTIVE or FIRED watch. Cancelled rows are not eligible."""
    if watch_id is None and not (order_id or "").strip():
        raise WatchError("INVALID_INPUT", "Provide watch_id or order_id.")

    if watch_id is not None:
        watch = get_watch(int(watch_id))
        if watch is None:
            raise WatchError("NOT_FOUND", "No standing watch with that id.")
        if watch["status"] == STATUS_CANCELLED:
            raise WatchError("INVALID_INPUT", "That watch is already cancelled.")
        if watch["status"] not in {STATUS_ACTIVE, STATUS_FIRED}:
            raise WatchError(
                "INVALID_INPUT",
                f"Watch {watch_id} has status {watch['status']} and cannot be cancelled.",
            )
        if order_id and watch["order_id"].upper() != order_id.strip().upper():
            raise WatchError(
                "INVALID_INPUT",
                f"Watch {watch_id} is for {watch['order_id']}, not {order_id.strip()}.",
            )
        return watch

    open_rows = [
        row
        for row in list_watches(order_id=order_id.strip())
        if row["status"] in {STATUS_ACTIVE, STATUS_FIRED}
    ]
    if not open_rows:
        raise WatchError(
            "NOT_FOUND",
            f"No active or fired standing watch for {order_id.strip()}.",
        )
    if len(open_rows) > 1:
        raise WatchError(
            "AMBIGUOUS",
            "Several standing watches match. Confirm which watch_id to cancel.",
            candidates=[watch_summary(row) for row in open_rows],
        )
    return open_rows[0]


def cancel_watch_row(watch_id: int) -> dict[str, Any]:
    """Mark ACTIVE or FIRED as CANCELLED. Does not delete watch_events."""
    watch = get_watch(int(watch_id))
    if watch is None:
        raise WatchError("NOT_FOUND", "No standing watch with that id.")
    if watch["status"] == STATUS_CANCELLED:
        raise WatchError("INVALID_INPUT", "That watch is already cancelled.")
    if watch["status"] not in {STATUS_ACTIVE, STATUS_FIRED}:
        raise WatchError(
            "INVALID_INPUT",
            f"Watch {watch_id} has status {watch['status']} and cannot be cancelled.",
        )
    previous = watch["status"]
    with connect_state() as conn:
        cur = conn.execute(
            """
            UPDATE watches SET status = ?
            WHERE id = ? AND status IN (?, ?)
            """,
            (STATUS_CANCELLED, int(watch_id), STATUS_ACTIVE, STATUS_FIRED),
        )
        if cur.rowcount != 1:
            raise WatchError("INVALID_INPUT", "Watch was not cancelled (status already changed).")
    updated = get_watch(int(watch_id))
    assert updated is not None
    updated["previous_status"] = previous
    return updated


def _serialize_active(watch: dict[str, Any]) -> dict[str, Any]:
    params = watch.get("params") or {}
    return {
        "watch_id": watch["id"],
        "order_id": watch["order_id"],
        "condition_type": watch["condition_type"],
        "check_date": params.get("check_date"),
        "message": watch.get("message"),
        "status": watch["status"],
        "notify_channel": watch.get("notify_channel"),
    }


def _serialize_fired(watch: dict[str, Any], event: dict[str, Any] | None) -> dict[str, Any]:
    params = watch.get("params") or {}
    snapshot = (event or {}).get("snapshot") or {}
    return {
        "watch_id": watch["id"],
        "order_id": watch["order_id"],
        "condition_type": watch["condition_type"],
        "check_date": params.get("check_date") or snapshot.get("check_date"),
        "message": watch.get("message"),
        "status": watch["status"],
        "last_activity_date": snapshot.get("last_activity_date"),
        "order_status": snapshot.get("status"),
        "current_stage": snapshot.get("current_stage"),
        "as_of": snapshot.get("as_of") or watch.get("fired_as_of"),
        "fired_as_of": watch.get("fired_as_of"),
        "fired_at": watch.get("fired_at"),
        "notify_channel": watch.get("notify_channel"),
        "snapshot": snapshot,
    }


def _fire_watch(
    watch: dict[str, Any],
    *,
    as_of: date,
    snapshot: dict[str, Any],
    notifier: WatchNotifier,
) -> dict[str, Any] | None:
    """Persist FIRED + watch_event, then notify. Notify must not roll back fire."""
    now = _now_utc()
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, default=str)
    try:
        with connect_state() as conn:
            cur = conn.execute(
                """
                UPDATE watches
                SET status = ?, fired_as_of = ?, fired_at = ?, last_evaluated_as_of = ?
                WHERE id = ? AND status = ?
                """,
                (
                    STATUS_FIRED,
                    as_of.isoformat(),
                    now,
                    as_of.isoformat(),
                    watch["id"],
                    STATUS_ACTIVE,
                ),
            )
            if cur.rowcount != 1:
                return None
            event_cur = conn.execute(
                """
                INSERT INTO watch_events (
                    watch_id, event_type, as_of, timestamp, snapshot_json, delivery_status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    watch["id"],
                    EVENT_FIRED,
                    as_of.isoformat(),
                    now,
                    snapshot_json,
                    DELIVERY_LOCAL,
                ),
            )
            event_id = int(event_cur.lastrowid)
    except sqlite3.IntegrityError:
        logger.info("watch_id=%s already has a fired event", watch["id"])
        return None

    event = {
        "id": event_id,
        "watch_id": watch["id"],
        "event_type": EVENT_FIRED,
        "as_of": as_of.isoformat(),
        "timestamp": now,
        "snapshot": snapshot,
        "delivery_status": DELIVERY_LOCAL,
    }
    record_event(
        event_type="watch_fired",
        tool="evaluate_active_watches",
        inputs={
            "watch_id": watch["id"],
            "order_id": watch["order_id"],
            "condition_type": watch["condition_type"],
            "as_of": as_of.isoformat(),
        },
        result_ok=True,
        result_summary=(
            f"{watch['order_id']} {CONDITION_INACTIVE} fired as_of={as_of.isoformat()}"
        ),
        execution_status="fired",
        target=watch["order_id"],
    )
    try:
        notifier.notify(watch, event)
    except Exception:  # noqa: BLE001 — delivery must not un-fire
        logger.exception(
            "WatchNotifier failed after fire watch_id=%s; event remains recorded",
            watch["id"],
        )
    return event


def evaluate_active_watches(
    as_of: date,
    *,
    get_order: Callable[[str], dict[str, Any] | None] | None = None,
    notifier: WatchNotifier | None = None,
) -> dict[str, Any]:
    """Evaluate ACTIVE watches at factory `as_of`. No scheduler. No date.today()."""
    if not isinstance(as_of, date):
        raise WatchError("INVALID_INPUT", "as_of must be a date.")
    lookup = get_order or (lambda oid: get_db().get_order_by_id(oid))
    channel = notifier or LocalWatchNotifier()
    newly_fired: list[dict[str, Any]] = []

    for watch in list_watches(status=STATUS_ACTIVE):
        order = lookup(watch["order_id"])
        check_raw = (watch.get("params") or {}).get("check_date")
        check_date = parse_iso_date(check_raw)
        if order is None or check_date is None:
            with connect_state() as conn:
                conn.execute(
                    "UPDATE watches SET last_evaluated_as_of = ? WHERE id = ?",
                    (as_of.isoformat(), watch["id"]),
                )
            continue

        if watch["condition_type"] != CONDITION_INACTIVE:
            with connect_state() as conn:
                conn.execute(
                    "UPDATE watches SET last_evaluated_as_of = ? WHERE id = ?",
                    (as_of.isoformat(), watch["id"]),
                )
            continue

        met, snapshot = condition_inactive_by_date(
            order, check_date=check_date, as_of=as_of
        )
        if not met:
            with connect_state() as conn:
                conn.execute(
                    "UPDATE watches SET last_evaluated_as_of = ? WHERE id = ?",
                    (as_of.isoformat(), watch["id"]),
                )
            continue

        event = _fire_watch(watch, as_of=as_of, snapshot=snapshot, notifier=channel)
        if event:
            newly_fired.append(_serialize_fired({**watch, "status": STATUS_FIRED}, event))

    return {
        "as_of": as_of.isoformat(),
        "newly_fired_count": len(newly_fired),
        "newly_fired": newly_fired,
    }


def evaluate_and_list(
    as_of: date,
    *,
    get_order: Callable[[str], dict[str, Any] | None] | None = None,
    notifier: WatchNotifier | None = None,
) -> dict[str, Any]:
    """Run evaluation then return the full board (all fired + remaining active)."""
    evaluate_active_watches(as_of, get_order=get_order, notifier=notifier)
    events_by_watch: dict[int, dict[str, Any]] = {}
    for event in list_watch_events():
        wid = int(event["watch_id"])
        if wid not in events_by_watch:
            events_by_watch[wid] = event
    fired = [
        _serialize_fired(watch, events_by_watch.get(int(watch["id"])))
        for watch in list_watches(status=STATUS_FIRED)
    ]
    active = [_serialize_active(watch) for watch in list_watches(status=STATUS_ACTIVE)]
    cancelled = [
        watch_summary(watch) for watch in list_watches(status=STATUS_CANCELLED)
    ]
    return {
        "as_of": as_of.isoformat(),
        "fired": fired,
        "active": active,
        "cancelled": cancelled,
    }
