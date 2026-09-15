"""Agent-facing standing-watch tool. Propose → confirm → persist.

The model maps natural language onto a typed condition. Python resolves
weekday names on the factory calendar and later evaluates whether the
condition is true. The model must not say whether the watch has fired.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import FACTORY_TODAY
from backend.services.audit import record_event
from backend.services.database import get_db
from backend.services.request_context import get_current_user_id
from backend.services.watches import (
    CONDITION_INACTIVE,
    WatchError,
    cancel_watch_row,
    create_watch_row,
    list_watches as load_watches,
    resolve_check_date,
    resolve_watch_for_cancel,
    watch_summary,
)
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)


class CreateWatchInput(BaseModel):
    order_id: str = Field(..., description="Exact order id such as ORD-005.")
    check_date: str = Field(
        ...,
        description=(
            "Factory-calendar deadline: YYYY-MM-DD or a weekday name. "
            "Pass Thursday or 'Thursday' as spoken; Python maps it from "
            "factory today 2026-04-01 (Wednesday) to 2026-04-02. "
            "Do not compute the ISO date yourself."
        ),
    )
    condition_type: str = Field(
        default=CONDITION_INACTIVE,
        description=(
            "V1 only supports ORDER_INACTIVE_BY_DATE "
            "(order still IN_PROGRESS and last_activity_date before check_date)."
        ),
    )
    message: Optional[str] = Field(
        default=None,
        description="Manager's wording, for display only. Not evaluated.",
    )
    confirmed: bool = Field(
        default=False,
        description="Must be false unless the manager explicitly confirmed creating the watch.",
    )


@tool(args_schema=CreateWatchInput)
def create_watch(
    order_id: str,
    check_date: str,
    condition_type: str = CONDITION_INACTIVE,
    message: Optional[str] = None,
    confirmed: bool = False,
) -> str:
    """Propose or save a standing watch. Does not decide if the condition is true.

    Use when the manager asks to be told if an order has not moved by a date
    (e.g. "Tell me if ORD-005 hasn't moved by Thursday"). Pass weekday names
    through as spoken. Do not calculate whether the order is already inactive.
    """
    tool_name = "create_watch"
    try:
        kind = (condition_type or CONDITION_INACTIVE).strip()
        if kind != CONDITION_INACTIVE:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"V1 only supports {CONDITION_INACTIVE}.",
                allowed=[CONDITION_INACTIVE],
            )
        try:
            when = resolve_check_date(check_date)
        except WatchError as exc:
            return tool_error(tool_name, exc.code, exc.message)

        order = get_db().get_order_by_id(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        if order.get("status") != "IN_PROGRESS":
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                (
                    f"{order['order_id']} is {order.get('status')}, not IN_PROGRESS. "
                    "ORDER_INACTIVE_BY_DATE watches are not created for completed orders."
                ),
            )

        text = (message or "").strip() or (
            f"Tell me if {order['order_id']} hasn't moved by {when.isoformat()}."
        )
        payload = {
            "order_id": order["order_id"],
            "condition_type": CONDITION_INACTIVE,
            "check_date": when.isoformat(),
            "message": text,
            "factory_today": FACTORY_TODAY.isoformat(),
            "notify_channel": "local",
        }
        if not confirmed:
            record_event(
                event_type="action_proposal",
                tool=tool_name,
                inputs={**payload, "confirmed": False},
                result_ok=True,
                result_summary="watch proposed, not saved",
                confirmation_status="pending",
                execution_status="not_saved",
                target=order["order_id"],
            )
            return tool_json(
                {
                    "ok": True,
                    "tool": tool_name,
                    "data": {
                        "saved": False,
                        "needs_confirmation": True,
                        **payload,
                        "proposed_action": {
                            "type": "create_watch",
                            "order_id": order["order_id"],
                            "condition_type": CONDITION_INACTIVE,
                            "check_date": when.isoformat(),
                            "message": text,
                            "requires_confirmation": True,
                            "confirmed": False,
                        },
                        "limitations": [
                            "Watch is not saved until confirmed=true. "
                            "Python will evaluate ORDER_INACTIVE_BY_DATE later; "
                            "this tool does not decide if the condition is already true. "
                            "V1 records a local alert only (no SMTP)."
                        ],
                    },
                    "trace": {
                        "tool": tool_name,
                        "source_file": "orders.csv",
                        "filter": {"order_id": order["order_id"]},
                        "rows": [
                            {
                                "order_id": order["order_id"],
                                "status": order["status"],
                                "last_activity_date": order["last_activity_date"],
                            }
                        ],
                        "calculations": [
                            {
                                "name": "resolve_check_date",
                                "inputs": {"raw": check_date, "origin": FACTORY_TODAY.isoformat()},
                                "result": when.isoformat(),
                            }
                        ],
                        "basis": (
                            "Proposal only. Condition is not evaluated here. "
                            "Thursday from 2026-04-01 is 2026-04-02."
                        ),
                    },
                }
            )

        watch = create_watch_row(
            order_id=order["order_id"],
            condition_type=CONDITION_INACTIVE,
            check_date=when,
            message=text,
        )
        record_event(
            event_type="action_execution",
            tool=tool_name,
            inputs={**payload, "confirmed": True, "watch_id": watch["id"]},
            result_ok=True,
            result_summary=f"watch {watch['id']} saved locally",
            confirmation_status="confirmed",
            execution_status="saved_local",
            target=order["order_id"],
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "saved": True,
                    "watch_id": watch["id"],
                    "status": watch["status"],
                    **payload,
                    "storage": "copilot_state.db (local only)",
                    "limitations": [
                        "Saved locally. Evaluation runs when GET /api/watches "
                        "is called with a factory as_of date. No scheduler, no SMTP."
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "copilot_state.db",
                    "filter": {"order_id": order["order_id"], "watch_id": watch["id"]},
                    "rows": [{"watch_id": watch["id"], "status": watch["status"]}],
                    "calculations": [
                        {
                            "name": "resolve_check_date",
                            "inputs": {"raw": check_date, "origin": FACTORY_TODAY.isoformat()},
                            "result": when.isoformat(),
                        }
                    ],
                    "basis": (
                        "Watch persisted as ACTIVE. Python evaluates later; "
                        "the model did not decide whether the condition is met."
                    ),
                },
            }
        )
    except WatchError as exc:
        return tool_error(tool_name, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_watch failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


class ListWatchesInput(BaseModel):
    order_id: Optional[str] = Field(
        default=None,
        description="If set, only watches for this order id (e.g. ORD-005).",
    )


class CancelWatchInput(BaseModel):
    order_id: Optional[str] = Field(
        default=None,
        description="Order id such as ORD-005. Use when the manager names the order.",
    )
    watch_id: Optional[int] = Field(
        default=None,
        description="Exact watch id from list_watches. Use when several watches match.",
    )
    confirmed: bool = Field(
        default=False,
        description="Must be false unless the manager explicitly confirmed cancelling.",
    )


@tool(args_schema=ListWatchesInput)
def list_watches(order_id: Optional[str] = None) -> str:
    """List standing watches including CANCELLED history.

    Use when the manager asks what is being watched, whether a watch existed
    before, or before cancelling if the watch_id is unknown.
    Cancelled rows are kept for audit — they are not deleted. If status is
    CANCELLED, say the watch existed and was stopped; do not say there was none.
    """
    tool_name = "list_watches"
    try:
        oid = (order_id or "").strip() or None
        all_rows = [watch_summary(row) for row in load_watches(order_id=oid, user_id=get_current_user_id(required=False))]
        by_status = {"ACTIVE": [], "FIRED": [], "CANCELLED": []}
        for row in all_rows:
            by_status.setdefault(row["status"], []).append(row)
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "count": len(all_rows),
                    "active_count": len(by_status["ACTIVE"]),
                    "fired_count": len(by_status["FIRED"]),
                    "cancelled_count": len(by_status["CANCELLED"]),
                    "filter": {"order_id": oid} if oid else {},
                    "watches": all_rows,
                    "active": by_status["ACTIVE"],
                    "fired": by_status["FIRED"],
                    "cancelled": by_status["CANCELLED"],
                    "note": (
                        "Rows are never deleted. CANCELLED means the manager stopped "
                        "that watch; it is history. ACTIVE still evaluates. FIRED is "
                        "a local alert still on the board. cancel_watch only changes "
                        "status, it does not erase the row or watch_events."
                    ),
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "copilot_state.db",
                    "filter": {"order_id": oid},
                    "rows": all_rows,
                    "calculations": [],
                    "basis": (
                        "All standing watches in copilot_state.db, including CANCELLED."
                    ),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_watches failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=CancelWatchInput)
def cancel_watch(
    order_id: Optional[str] = None,
    watch_id: Optional[int] = None,
    confirmed: bool = False,
) -> str:
    """Propose or cancel a standing watch (ACTIVE or FIRED).

    Use when the manager wants to stop a watch or dismiss a triggered alert.
    Does not delete the audit/event history. Requires confirmation.
    Not for create_reminder calendar notes — those are a different tool.
    """
    tool_name = "cancel_watch"
    try:
        try:
            watch = resolve_watch_for_cancel(watch_id=watch_id, order_id=order_id)
        except WatchError as exc:
            extra = {}
            if exc.candidates:
                extra["candidates"] = exc.candidates
            return tool_error(tool_name, exc.code, exc.message, **extra)

        summary = watch_summary(watch)
        payload = {
            **summary,
            "previous_status": watch["status"],
        }
        if not confirmed:
            record_event(
                event_type="action_proposal",
                tool=tool_name,
                inputs={**payload, "confirmed": False},
                result_ok=True,
                result_summary="watch cancel proposed, not applied",
                confirmation_status="pending",
                execution_status="not_saved",
                target=watch["order_id"],
            )
            return tool_json(
                {
                    "ok": True,
                    "tool": tool_name,
                    "data": {
                        "cancelled": False,
                        "needs_confirmation": True,
                        **payload,
                        "proposed_action": {
                            "type": "cancel_watch",
                            "watch_id": watch["id"],
                            "order_id": watch["order_id"],
                            "requires_confirmation": True,
                            "confirmed": False,
                        },
                    },
                    "trace": {
                        "tool": tool_name,
                        "source_file": "copilot_state.db",
                        "filter": {"watch_id": watch["id"], "order_id": watch["order_id"]},
                        "rows": [summary],
                        "calculations": [],
                        "basis": "Cancel is not applied until confirmed=true.",
                    },
                }
            )

        cancelled = cancel_watch_row(int(watch["id"]))
        record_event(
            event_type="action_execution",
            tool=tool_name,
            inputs={
                **watch_summary(cancelled),
                "previous_status": cancelled.get("previous_status"),
                "confirmed": True,
            },
            result_ok=True,
            result_summary=f"watch {cancelled['id']} cancelled",
            confirmation_status="confirmed",
            execution_status="cancelled",
            target=cancelled["order_id"],
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "cancelled": True,
                    "watch_id": cancelled["id"],
                    "order_id": cancelled["order_id"],
                    "status": cancelled["status"],
                    "previous_status": cancelled.get("previous_status"),
                    "check_date": (cancelled.get("params") or {}).get("check_date"),
                    "note": (
                        "Watch is CANCELLED, not deleted. The row stays in "
                        "copilot_state.db with full history. list_watches still "
                        "returns it. It will not evaluate again and leaves the "
                        "active/fired sidebar lists."
                    ),
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "copilot_state.db",
                    "filter": {"watch_id": cancelled["id"]},
                    "rows": [watch_summary(cancelled)],
                    "calculations": [],
                    "basis": "Status set to CANCELLED. The watch row and watch_events are kept.",
                },
            }
        )
    except WatchError as exc:
        extra = {}
        if exc.candidates:
            extra["candidates"] = exc.candidates
        return tool_error(tool_name, exc.code, exc.message, **extra)
    except Exception as exc:  # noqa: BLE001
        logger.exception("cancel_watch failed")
        return tool_error(tool_name, "INTERNAL", str(exc))

