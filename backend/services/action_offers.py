"""Yes/no offers after an answer. The payload is fixed before the model chooses.

A new tool joins by adding one builder. The model only picks an id from the
builders that already have every required field. It cannot invent an action.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from backend.config import factory_date
from backend.services.confirm_actions import ALLOWED_ACTIONS
from backend.services.watches import CONDITION_INACTIVE

logger = logging.getLogger(__name__)

_ORDER_ID = re.compile(r"ORD-\d+", re.IGNORECASE)
Lookup = Callable[[str], dict[str, Any] | None]


def _orders_in_traces(traces: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Every order the tools already returned, with whatever fields those rows carried."""
    found: dict[str, dict[str, Any]] = {}
    for trace in traces or []:
        for row in trace.get("rows") or []:
            if not isinstance(row, dict):
                continue
            order_id = str(row.get("order_id") or "").strip().upper()
            if not _ORDER_ID.fullmatch(order_id):
                continue
            slot = found.setdefault(order_id, {})
            for key in ("status", "due_date", "customer", "current_stage", "flags"):
                if row.get(key) not in (None, "", []):
                    slot[key] = row[key]
    return found


def _check_date(order: dict[str, Any]) -> str:
    due = str(order.get("due_date") or "").strip()
    today = factory_date().isoformat()
    if due >= today:
        return due
    return today


def _watch_offer(order: dict[str, Any]) -> dict[str, Any] | None:
    if order.get("status") != "IN_PROGRESS":
        return None
    if "create_watch" not in ALLOWED_ACTIONS:
        return None
    order_id = str(order["order_id"]).upper()
    check_date = _check_date(order)
    return {
        "id": f"create_watch:{order_id}",
        "prompt": (
            f"Need me to watch {order_id} and tell you if it hasn't moved by {check_date}?"
        ),
        "action": {
            "type": "create_watch",
            "order_id": order_id,
            "condition_type": CONDITION_INACTIVE,
            "check_date": check_date,
            "message": f"Tell me if {order_id} hasn't moved by {check_date}.",
            "requires_confirmation": True,
            "confirmed": False,
        },
    }


# Add a builder here when a future tool should be offerable. The UI stays the same.
# Chase-email offers stay off: a question that already asks for an email gets the
# draft in the answer, and a second "record a chase email?" card repeats it.
OFFER_BUILDERS = (_watch_offer,)


def _same_card(action: dict[str, Any], proposed_actions: list[dict[str, Any]] | None) -> bool:
    order_id = str(action.get("order_id") or "").upper()
    kind = str(action.get("type") or "")
    for item in proposed_actions or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") != kind:
            continue
        if str(item.get("order_id") or "").strip().upper() == order_id:
            return True
    return False


def _fact_line(order: dict[str, Any], row: dict[str, Any]) -> str:
    bits = [f"status {order.get('status') or row.get('status') or 'unknown'}"]
    due = order.get("due_date") or row.get("due_date")
    if due:
        bits.append(f"due {due}")
    stage = order.get("current_stage") or row.get("current_stage")
    if stage:
        bits.append(f"stage {stage}")
    if row.get("flags"):
        bits.append(f"flags {row['flags']}")
    return ", ".join(str(bit) for bit in bits)


def candidate_offers(
    traces: list[dict[str, Any]] | None,
    tools_used: list[str] | None = None,
    proposed_actions: list[dict[str, Any]] | None = None,
    lookup: Lookup | None = None,
) -> list[dict[str, Any]]:
    """One prepared action per order the tools already returned.

    A series of orders stays in the list. The only drop is a card this answer
    already shows for that same order and action.
    """
    del tools_used  # the answer's own confirm card is the duplicate check
    rows = _orders_in_traces(traces)
    resolve = lookup or _lookup_order
    offers: list[dict[str, Any]] = []
    for order_id, row in list(rows.items())[:16]:
        order = resolve(order_id)
        if not order:
            continue
        order = {**row, **order, "order_id": order_id}
        for build in OFFER_BUILDERS:
            offer = build(order)
            if not offer or _same_card(offer["action"], proposed_actions):
                continue
            offer["facts"] = _fact_line(order, row)
            offers.append(offer)
    return offers


def _lookup_order(order_id: str) -> dict[str, Any] | None:
    from backend.services.database import get_db

    return get_db().get_order_by_id(order_id)


def _message_text(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        content = "\n".join(parts)
    return str(content or "").strip()


def _choose_with_model(
    question: str,
    answer: str,
    offers: list[dict[str, Any]],
) -> str | None:
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.agent.graph import build_model, llm_is_configured

    if not offers or not llm_is_configured():
        return None
    catalog = "\n".join(
        f"- {item['id']}: {item['prompt']} ({item.get('facts') or 'no extra facts'})"
        for item in offers
    )
    system = (
        "You decide whether to offer one follow-up action after a factory answer. "
        "Choose at most one id from the list. The list may contain several orders "
        "from the same answer. Offer a watch for the single order the answer treats "
        "as late, stalled, or at risk, even when the other orders are fine. "
        "Offer the chase email when the answer is about contacting that one customer. "
        "If the answer does not single out one order, return a null id. "
        "Do not invent an id. "
        'Return JSON only: {"offer_id": "create_watch:ORD-120"} or {"offer_id": null}.'
    )
    user = (
        f"Question:\n{question[:400]}\n\nAnswer:\n{answer[:800]}\n\nOffers:\n{catalog}"
    )
    try:
        result = build_model().invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
    except Exception:
        logger.exception("action offer model failed")
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", _message_text(result), flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.info("action offer was not JSON")
        return None
    if not isinstance(payload, dict):
        return None
    offer_id = payload.get("offer_id")
    if offer_id is None:
        return None
    return str(offer_id).strip() or None


def compose_action_offer(
    question: str,
    answer: str,
    traces: list[dict[str, Any]] | None,
    tools_used: list[str] | None = None,
    proposed_actions: list[dict[str, Any]] | None = None,
    lookup: Lookup | None = None,
) -> dict[str, Any] | None:
    """One yes/no offer, or nothing. The chosen action is taken only from the candidates."""
    offers = candidate_offers(traces, tools_used, proposed_actions, lookup)
    if not offers:
        return None
    chosen = _choose_with_model(question, answer, offers)
    allowed = {item["id"] for item in offers}
    if chosen not in allowed:
        if chosen:
            logger.info("dropped action offer %r", chosen)
        return None
    offer = next(item for item in offers if item["id"] == chosen)
    return {"prompt": offer["prompt"], "action": offer["action"]}
