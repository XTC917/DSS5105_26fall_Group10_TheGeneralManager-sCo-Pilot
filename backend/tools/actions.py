"""Local action tools. There is no SMTP or push-notification integration.

Pattern: propose (confirmed=false, default) → manager confirms → persist locally
and write an audit row. Real delivery is handled separately by the email API.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.config import factory_date
from backend.services.audit import add_note, add_reminder, list_audit, record_event
from backend.services.calculations import assess_order_risk, parse_iso_date
from backend.services.pace import flags_with_pace_tight, pace_fields, stage_medians
from backend.services.database import get_db
from backend.services.request_context import get_current_user_id
from backend.services.email_templates import EmailAudience, EmailLanguage, compose_email, email_language
from backend.tools.common import manager_text, tool_error, tool_json

logger = logging.getLogger(__name__)

NO_SMTP = (
    "Nothing was sent to a customer or workshop. The payload is a draft or "
    "simulation record. Real delivery requires the dedicated email preview."
)


class DraftEmailInput(BaseModel):
    order_id: str | None = Field(default=None, description="Order id the manager wrote; omit only for overdue_customers scope.")
    language: EmailLanguage = Field(default="auto", description="Use zh/en for an explicit email language request; auto follows this turn.")
    audience: EmailAudience = Field(default="unspecified", description="customer/internal only when specified by the manager; never infer an address.")
    scope: Literal["single", "overdue_customers"] = Field(default="single", description="overdue_customers: draft one email per overdue order for all customers, without choosing arbitrary ids.")


class SendEmailInput(BaseModel):
    order_id: str = Field(..., description="Order id the manager wrote.")
    language: EmailLanguage = "auto"
    audience: EmailAudience = "unspecified"
    confirmed: bool = Field(default=False, description="True only after explicit manager confirmation. Simulation only.")


class AddNoteInput(BaseModel):
    order_id: str = Field(..., description="Order id the manager wrote.")
    note: str = Field(..., description="Short operational note in the manager's words.")
    confirmed: bool = Field(
        default=False,
        description="Must be false unless the manager explicitly confirmed saving the note.",
    )


class CreateReminderInput(BaseModel):
    order_id: str = Field(..., description="Order id the manager wrote.")
    remind_on: str = Field(
        ...,
        description="Factory-calendar date YYYY-MM-DD. Use the active factory date to resolve relative dates.",
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


def _compose_chase_email(order: dict, language: EmailLanguage = "auto",
                         audience: EmailAudience = "unspecified") -> dict:
    risk = assess_order_risk(order)
    pace = pace_fields(order, stage_medians(get_db()))
    flags = flags_with_pace_tight(list(risk["flags"]), pace)
    return compose_email(order, flags, language=email_language(language, manager_text()), audience=audience)


@tool(args_schema=DraftEmailInput)
def draft_chase_email(order_id: str | None = None, language: EmailLanguage = "auto",
                      audience: EmailAudience = "unspecified",
                      scope: Literal["single", "overdue_customers"] = "single") -> str:
    """Prepare a chase-up email draft from order fields. Does not send anything.

    Use when the manager asks to draft or write an email about an order.
    Always say the draft was not sent. There is no SMTP.
    """
    tool_name = "draft_chase_email"
    try:
        if scope == "overdue_customers":
            if order_id or audience == "internal":
                return tool_error(tool_name, "INVALID_INPUT", "overdue_customers cannot be combined with order_id or internal audience.")
            orders = [row for row in get_db().in_progress_orders()
                      if "OVERDUE" in assess_order_risk(row)["flags"]]
            drafts = [_compose_chase_email(row, language, "customer") for row in orders]
            record_event(event_type="action_proposal", tool=tool_name,
                         inputs={"scope": scope, "language": language}, result_ok=True,
                         result_summary=f"{len(drafts)} customer drafts prepared, not sent",
                         confirmation_status="not_required_for_draft", execution_status="not_sent")
            return tool_json({"ok": True, "tool": tool_name,
                              "data": {"sent": False, "channel": "local_draft_only",
                                       "needs_confirmation": False, "draft_only": True,
                                       "drafts": drafts, "count": len(drafts),
                                       "grouping": "one_draft_per_order", "limitations": [NO_SMTP]},
                              "trace": {"tool": tool_name, "source_file": "orders.csv",
                                        "filter": {"scope": scope}, "rows": orders,
                                        "calculations": [], "basis": "Existing OVERDUE rule; one draft per order; nothing sent."}})
        if not order_id or not order_id.strip():
            return tool_error(tool_name, "INVALID_INPUT", "order_id is required for a single-order draft.")
        order = _lookup_order(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        draft = _compose_chase_email(order, language, audience)
        record_event(
            event_type="action_proposal",
            tool=tool_name,
            inputs={"order_id": order["order_id"], "language": draft["language"], "audience": audience},
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
                    "needs_confirmation": False,
                    "draft_only": True,
                    "limitations": [NO_SMTP],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": "orders.csv",
                    "filter": {"order_id": order["order_id"]},
                    "rows": [order],
                    "calculations": [],
                    "basis": NO_SMTP,
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("draft_chase_email failed")
        return tool_error(tool_name, "INTERNAL", str(exc))


@tool(args_schema=SendEmailInput)
def send_email(order_id: str, confirmed: bool = False, language: EmailLanguage = "auto",
               audience: EmailAudience = "unspecified") -> str:
    """Record a simulated send. Never claims a real email left the system.

    Call only after draft_chase_email, and only with confirmed=true after the
    manager explicitly agrees. Even then, execution_status is SIMULATED.
    """
    tool_name = "send_email"
    try:
        order = _lookup_order(order_id)
        if not order:
            return tool_error(tool_name, "NOT_FOUND", "No order with that id in orders.csv.")
        draft = _compose_chase_email(order, language, audience)
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
                            "language": draft["language"],
                            "audience": audience,
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
            "factory_today": factory_date().isoformat(),
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
