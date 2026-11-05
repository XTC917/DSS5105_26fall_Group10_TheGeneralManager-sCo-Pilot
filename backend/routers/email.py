"""Email preview and explicit delivery for drafts from an owned chat turn."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import re
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from backend.pg_config import COPILOT_SCHEMA
from backend.services.auth import CurrentUser, get_current_user
from backend.services.pg_database import connect

router = APIRouter(prefix="/api/email")
DRAFTS = f"{COPILOT_SCHEMA}.email_drafts"
ATTEMPTS = f"{COPILOT_SCHEMA}.email_send_attempts"
MAILBOX = re.compile(r"[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+")


class DraftEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    recipient_email: str = Field(default="", max_length=254)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=100_000)


class SendConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def _delivery_config():
    sender = os.getenv("EMAIL_FROM", "").strip()
    recipient = os.getenv("EMAIL_TEST_RECIPIENT", "").strip()
    key = os.getenv("RESEND_API_KEY", "").strip()
    enabled = os.getenv("EMAIL_DELIVERY_ENABLED", "").lower() == "true"
    return sender, recipient, key, bool(enabled and sender and key and MAILBOX.fullmatch(recipient))


def _payload(sender, recipient, subject, body):
    return {"from": sender, "to": [recipient], "subject": subject, "text": body}


def _digest(payload):
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _source(conn, user_id, turn_id, index):
    turn = conn.execute(
        f"""SELECT t.conversation_id, t.response_json
            FROM {COPILOT_SCHEMA}.chat_turns t
            JOIN {COPILOT_SCHEMA}.conversations c ON c.id = t.conversation_id
            WHERE t.id = %s AND c.user_id = %s
            FOR KEY SHARE OF t, c""",
        (turn_id, user_id),
    ).fetchone()
    drafts = turn["response_json"].get("email_drafts", []) if turn else []
    if not 0 <= index < len(drafts):
        raise HTTPException(404, "Email draft not found.")
    draft_id = uuid5(NAMESPACE_URL, f"sweaterco/email/{user_id}/{turn_id}/{index}")
    return draft_id, turn["conversation_id"], drafts[index]


def _view(row):
    sender, recipient, _, enabled = _delivery_config()
    status = row["status"]
    # A process can stop after committing the attempt but before recording the
    # provider response. Surface the uncertainty and keep the send locked.
    if status == "SENDING" and row["updated_at"] < datetime.now(timezone.utc) - timedelta(minutes=2):
        status = "UNKNOWN"
    return {
        "id": row["id"], "version": row["version"], "status": status,
        "recipient_email": row["recipient_email"], "from_address": row["from_address"],
        "subject": row["subject"], "body": row["body"], "content_hash": row["content_hash"],
        "can_send": bool(enabled and row["status"] == "DRAFT" and row["content_hash"]
                         and row["from_address"] == sender
                         and (row["recipient_email"] or "").casefold() == recipient.casefold()),
    }


@router.get("/turns/{turn_id}/drafts/{index}")
def get_email_draft(turn_id: int, index: int, user: CurrentUser = Depends(get_current_user)):
    with connect(admin=True) as conn:
        draft_id, _, source = _source(conn, user.id, turn_id, index)
        row = conn.execute(f"SELECT * FROM {DRAFTS} WHERE id = %s AND user_id = %s",
                           (draft_id, user.id)).fetchone()
    if row is None:
        row = {**source, "id": draft_id, "version": 0, "status": "DRAFT",
               "recipient_email": None, "from_address": None, "content_hash": None}
    return _view(row)


@router.put("/turns/{turn_id}/drafts/{index}")
def save_email_draft(turn_id: int, index: int, edit: DraftEdit,
                     user: CurrentUser = Depends(get_current_user)):
    recipient = edit.recipient_email or None
    if recipient and not MAILBOX.fullmatch(recipient):
        raise HTTPException(422, "Enter a single valid recipient email address.")
    if "\r" in edit.subject or "\n" in edit.subject or any(
        "\0" in value for value in (edit.subject, edit.body, edit.recipient_email)
    ):
        raise HTTPException(422, "The draft contains invalid characters.")
    sender, _, _, _ = _delivery_config()
    digest = _digest(_payload(sender, recipient, edit.subject, edit.body)) if sender and recipient else None
    fields = (recipient, sender or None, edit.subject, edit.body, digest)
    with connect(admin=True) as conn:
        draft_id, conversation_id, source = _source(conn, user.id, turn_id, index)
        if edit.version == 0:
            row = conn.execute(
                f"""INSERT INTO {DRAFTS}
                    (id, user_id, conversation_id, order_id, recipient_name, language, audience,
                     template_id, recipient_email, from_address, subject, body, content_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING RETURNING *""",
                (draft_id, user.id, conversation_id, source["order_id"], source.get("recipient_name"),
                 source["language"], source["audience"], source.get("template_id"), *fields),
            ).fetchone()
        else:
            row = conn.execute(
                f"""UPDATE {DRAFTS}
                    SET recipient_email = %s, from_address = %s, subject = %s, body = %s,
                        content_hash = %s, version = version + 1, status = 'DRAFT',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s AND version = %s
                      AND status IN ('DRAFT', 'FAILED')
                    RETURNING *""",
                (*fields, draft_id, user.id, edit.version),
            ).fetchone()
        if row is None:
            raise HTTPException(409, "The draft changed. Reload it before editing or confirming.")
    return _view(row)


def _submit(payload, attempt_id, api_key):
    try:
        response = httpx.post(
            "https://api.resend.com/emails", json=payload, timeout=15,
            headers={"Authorization": f"Bearer {api_key}", "Idempotency-Key": str(attempt_id)},
        )
    except httpx.RequestError:
        return "UNKNOWN", None, None
    if response.is_success:
        try:
            result = response.json()
            message_id = result.get("id") if isinstance(result, dict) else None
        except ValueError:
            message_id = None
        if isinstance(message_id, str) and message_id.strip():
            return "SUBMITTED", message_id, response.status_code
    # A timeout, conflict, or server error can leave the provider's result uncertain.
    if response.status_code in {400, 401, 403, 404, 422, 429}:
        return "FAILED", None, response.status_code
    return "UNKNOWN", None, response.status_code


@router.post("/drafts/{draft_id}/send")
def send_confirmed_email(draft_id: UUID, confirmation: SendConfirmation,
                         user: CurrentUser = Depends(get_current_user)):
    sender, allowed_recipient, api_key, enabled = _delivery_config()
    with connect(admin=True) as conn:
        row = conn.execute(f"SELECT * FROM {DRAFTS} WHERE id = %s AND user_id = %s FOR UPDATE",
                           (draft_id, user.id)).fetchone()
        if row is None:
            raise HTTPException(404, "Email draft not found.")
        if row["version"] != confirmation.version or row["content_hash"] != confirmation.content_hash:
            raise HTTPException(409, "The draft changed. Save and review the new version.")
        if row["status"] in {"SENDING", "SUBMITTED", "UNKNOWN", "FAILED"}:
            return _view(row)
        if row["status"] != "DRAFT":
            raise HTTPException(409, "This draft cannot be sent.")
        if not enabled:
            raise HTTPException(503, "Email delivery is not configured.")
        recipient = row["recipient_email"] or ""
        if not MAILBOX.fullmatch(recipient) or recipient.casefold() != allowed_recipient.casefold():
            raise HTTPException(422, "Use the configured test recipient.")
        payload = _payload(row["from_address"], recipient, row["subject"], row["body"])
        if row["from_address"] != sender or _digest(payload) != confirmation.content_hash:
            raise HTTPException(409, "The sending details changed. Save and review again.")
        attempt_id = uuid4()
        conn.execute(
            f"""INSERT INTO {ATTEMPTS}
                (id, draft_id, draft_version, confirmed_by, content_hash, payload_snapshot,
                 idempotency_key, request_count, first_requested_at, last_requested_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (attempt_id, draft_id, row["version"], user.id, row["content_hash"],
             Jsonb(payload), str(attempt_id)),
        )
        conn.execute(f"""UPDATE {DRAFTS} SET status = 'SENDING', updated_at = CURRENT_TIMESTAMP
                         WHERE id = %s""", (draft_id,))

    status, message_id, http_status = _submit(payload, attempt_id, api_key)

    with connect(admin=True) as conn:
        conn.execute(
            f"""UPDATE {ATTEMPTS}
                SET status = %s, provider_email_id = %s, last_http_status = %s,
                    submitted_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                    error_code = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s""",
            (status, message_id, http_status, status == "SUBMITTED",
             None if status == "SUBMITTED" else status, attempt_id),
        )
        row = conn.execute(
            f"""UPDATE {DRAFTS} SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s RETURNING *""", (status, draft_id),
        ).fetchone()
    return _view(row)
