"""Local action tools. There is no SMTP or push-notification integration.

Pattern: propose (confirmed=false, default) → manager confirms → persist locally
and write an audit row. Email is never actually sent.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import FACTORY_TODAY
from backend.services.audit import add_note, add_reminder, list_audit, record_event
from backend.services.calculations import assess_order_risk, parse_iso_date
from backend.services.database import get_db
from backend.services.request_context import get_current_user_id
from backend.tools.common import tool_error, tool_json

logger = logging.getLogger(__name__)

NO_SMTP = (
    "There is no email or calendar integration. Nothing was sent to a customer "
    "or workshop. The payload is a local draft / audit record only."
)


class DraftEmailInput(BaseModel):
    order_id: str = Field(..., description="Exact order id such as ORD-120.")


class SendEmailInput(BaseModel):
    order_id: str = Field(..., description="Exact order id such as ORD-120.")
    confirmed: bool = Field(
        default=False,
        description="Must be false unless the manager explicitly confirmed sending.",
    )


class AddNoteInput(BaseModel):
    order_id: str = Field(..., description="Exact order id such as ORD-107.")
    note: str = Field(..., description="Short operational note in the manager's words.")
    confirmed: bool = Field(
        default=False,
        description="Must be false unless the manager explicitly confirmed saving the note.",
    )


class CreateReminderInput(BaseModel):
    order_id: str = Field(..., description="Exact order id such as ORD-005.")
    remind_on: str = Field(
        ...,
        description="Factory-calendar date YYYY-MM-DD. Tomorrow from 2026-04-01 is 2026-04-02.",
    )
    message: str = Field(..., description="What to check on that date.")
    confirmed: bool = Field(
        default=False,
        description="Must be false unless the manager explicitly confirmed creating the reminder.",
    )


class RecentActionsInput(BaseModel):
    limit: int = Field(default=15, description="How many recent audit rows to return (max 50).")


def _lookup_order(order_id: str) -> dict | None:
    return get_db().get_order_by_id(order_id)


def _compose_chase_email(order: dict) -> dict:
    risk = assess_order_risk(order)
    flags = ", ".join(risk["flags"]) if risk["flags"] else "none recorded"
    return {
        "to": (
            f"{order['customer']} — customer email is not in orders.csv; "
            "do not invent an address"
        ),
        "subject": f"SweaterCo order {order['order_id']} ({order['product']}) needs attention",
        "body": (
            f"Order {order['order_id']} for {order['customer']}: "
            f"{order['pieces']} {order['product']}, status {order['status']}, "
            f"stage {order['current_stage']}, due {order['due_date']}, "
            f"last activity {order['last_activity_date']}. "
            f"Risk flags from factory rules: {flags}."
        ),
        "order_id": order["order_id"],
        "customer": order["customer"],
        "risk_flags": risk["flags"],
    }


@tool(args_schema=DraftEmailInput)
def draft_chase_email(order_id: str) -> str:
    """Prepare a chase-up email draft from order fields. Does not send anything.

    Use when the manager asks to draft or write an email about an order.
    Always say the draft was not sent. There is no SMTP.
    """
    tool_name = "draft_chase_email"
    try:
        order = _lookup_order(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        draft = _compose_chase_email(order)
        record_event(
            event_type="action_proposal",
            tool=tool_name,
            inputs={"order_id": order["order_id"]},
            result_ok=True,
            result_summary="email draft prepared, not sent",
            confirmation_status="not_required_for_draft",
            execution_status="not_sent",
            target=order["order_id"],
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "sent": False,
                    "channel": "local_draft_only",
                    "draft": draft,
                    "proposed_action": {
                        "type": "send_email",
                        "order_id": order["order_id"],
                        "requires_confirmation": True,
                        "confirmed": False,
                    },
                    "limitations": [NO_SMTP],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [{"order_id": order["order_id"], "customer": order["customer"]}],
                    "calculations": [],
                    "basis": NO_SMTP,
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("draft_chase_email failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=SendEmailInput)
def send_email(order_id: str, confirmed: bool = False) -> str:
    """Record a simulated send. Never claims a real email left the system.

    Call only after draft_chase_email, and only with confirmed=true after the
    manager explicitly agrees. Even then, execution_status is SIMULATED.
    """
    tool_name = "send_email"
    try:
        order = _lookup_order(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        draft = _compose_chase_email(order)
        if not confirmed:
            record_event(
                event_type="action_proposal",
                tool=tool_name,
                inputs={"order_id": order["order_id"], "confirmed": False},
                result_ok=True,
                result_summary="send proposed, awaiting confirmation",
                confirmation_status="pending",
                execution_status="not_sent",
                target=order["order_id"],
            )
            return tool_json(
                {
                    "ok": True,
                    "tool": tool_name,
                    "data": {
                        "sent": False,
                        "needs_confirmation": True,
                        "draft": draft,
                        "proposed_action": {
                            "type": "send_email",
                            "order_id": order["order_id"],
                            "requires_confirmation": True,
                            "confirmed": False,
                        },
                        "limitations": [NO_SMTP],
                    },
                    "trace": {
                        "tool": tool_name,
                        "source_file": "orders.csv",
                        "filter": {"order_id": order["order_id"]},
                        "rows": [],
                        "calculations": [],
                        "basis": "Confirmation required. " + NO_SMTP,
                    },
                }
            )
        record_event(
            event_type="action_execution",
            tool=tool_name,
            inputs={"order_id": order["order_id"], "confirmed": True},
            result_ok=True,
            result_summary="simulated local record only; no SMTP",
            confirmation_status="confirmed",
            execution_status="SIMULATED",
            target=order["order_id"],
        )
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "sent": False,
                    "needs_confirmation": False,
                    "execution_status": "SIMULATED",
                    "draft": draft,
                    "limitations": [NO_SMTP],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [],
                    "calculations": [],
                    "basis": "Manager confirmed a local record. " + NO_SMTP,
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("send_email failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=AddNoteInput)
def add_order_note(order_id: str, note: str, confirmed: bool = False) -> str:
    """Propose or locally save an order note. Requires confirmation to persist."""
    tool_name = "add_order_note"
    try:
        text = (note or "").strip()
        if not text:
            return tool_error(tool_name, "INVALID_INPUT", "note must be non-empty.")
        order = _lookup_order(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        if not confirmed:
            record_event(
                event_type="action_proposal",
                tool=tool_name,
                inputs={"order_id": order["order_id"], "note": text, "confirmed": False},
                result_ok=True,
                result_summary="note proposed, not saved",
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
                        "order_id": order["order_id"],
                        "note": text,
                        "proposed_action": {
                            "type": "add_order_note",
                            "order_id": order["order_id"],
                            "note": text,
                            "requires_confirmation": True,
                            "confirmed": False,
                        },
                    },
                    "trace": {
                        "tool": tool_name,
                        "source_file": "copilot_state.db",
                        "filter": {"order_id": order["order_id"]},
                        "rows": [],
                        "calculations": [],
                        "basis": "Note is not saved until confirmed=true.",
                    },
                }
            )
        note_id = add_note(user_id=get_current_user_id(required=False), order_id=order["order_id"], note=text)
        record_event(
            event_type="action_execution",
            tool=tool_name,
            inputs={"order_id": order["order_id"], "note": text, "confirmed": True},
            result_ok=True,
            result_summary=f"note {note_id} saved locally",
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
                    "note_id": note_id,
                    "order_id": order["order_id"],
                    "note": text,
                    "storage": "copilot_state.db (local only)",
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "copilot_state.db",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [{"note_id": note_id}],
                    "calculations": [],
                    "basis": "Saved locally after confirmation. Not written to orders.csv.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("add_order_note failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=CreateReminderInput)
def create_reminder(
    order_id: str,
    remind_on: str,
    message: str,
    confirmed: bool = False,
) -> str:
    """Propose or locally save a reminder. No push notification is sent."""
    tool_name = "create_reminder"
    try:
        text = (message or "").strip()
        if not text:
            return tool_error(tool_name, "INVALID_INPUT", "message must be non-empty.")
        try:
            when = parse_iso_date(remind_on)
        except ValueError:
            when = None
        if when is None:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "remind_on must be YYYY-MM-DD (factory calendar).",
            )
        order = _lookup_order(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        payload = {
            "order_id": order["order_id"],
            "remind_on": when.isoformat(),
            "message": text,
            "factory_today": FACTORY_TODAY.isoformat(),
        }
        if not confirmed:
            record_event(
                event_type="action_proposal",
                tool=tool_name,
                inputs={**payload, "confirmed": False},
                result_ok=True,
                result_summary="reminder proposed, not saved",
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
                            "type": "create_reminder",
                            "order_id": order["order_id"],
                            "remind_on": when.isoformat(),
                            "message": text,
                            "requires_confirmation": True,
                            "confirmed": False,
                        },
                        "limitations": [
                            "No notification service. The reminder is local only after confirmation."
                        ],
                    },
                    "trace": {
                        "tool": tool_name,
                        "source_file": "copilot_state.db",
                        "filter": {"order_id": order["order_id"]},
                        "rows": [],
                        "calculations": [],
                        "basis": "Reminder is not saved until confirmed=true.",
                    },
                }
            )
        reminder_id = add_reminder(user_id=get_current_user_id(required=False), order_id=order["order_id"], remind_on=when.isoformat(), message=text)
        record_event(
            event_type="action_execution",
            tool=tool_name,
            inputs={**payload, "confirmed": True},
            result_ok=True,
            result_summary=f"reminder {reminder_id} saved locally",
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
                    "reminder_id": reminder_id,
                    **payload,
                    "storage": "copilot_state.db (local only)",
                    "notified": False,
                    "limitations": [
                        "Saved locally. No email, SMS, or calendar notification was sent."
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "copilot_state.db",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [{"reminder_id": reminder_id}],
                    "calculations": [],
                    "basis": "Local reminder after confirmation. No external notify.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_reminder failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=RecentActionsInput)
def get_recent_actions(limit: int = 15) -> str:
    """Return recent audit rows (queries, tools, proposed and recorded actions)."""
    tool_name = "get_recent_actions"
    try:
        cap = max(1, min(int(limit or 15), 50))
        items = list_audit(limit=cap, user_id=get_current_user_id(required=False))
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "count": len(items),
                    "items": items,
                    "limitations": [
                        "Local audit in copilot_state.db. Not a full compliance system."
                    ],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "copilot_state.db",
                    "filter": {"limit": cap},
                    "rows": [{"id": item.get("id"), "tool": item.get("tool")} for item in items],
                    "calculations": [],
                    "basis": "Newest audit rows first.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_recent_actions failed")
        return tool_error(tool_name, "INTERNAL", str(exc))
