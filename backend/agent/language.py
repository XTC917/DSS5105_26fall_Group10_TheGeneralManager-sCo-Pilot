"""Keep user-visible model text in Chinese or English.

A third language replaces the whole string. The replacement follows the
manager's question: Chinese if they wrote Han characters, otherwise English.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from backend.agent.answerability import reply_language

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[A-Za-zÀ-ÿ]+")
_HAN = re.compile(r"[\u4e00-\u9fff]")

# Ordinary English, including the factory words that show up on buttons.
_ENGLISH = frozenset(
    """
    a an the of and or to for in on at by is are was were be been being this these
    those which what how only about from with their your you mean did do not no
    status order orders risk risks today priority factory problem problems
    production output capacity workshop due date dates morning report snapshot
    progress stage against recent pace may miss missed whether new fits all every
    one doing done answer answers way more than can should would will still
    currently inprogress complete overdue assembly knitting washing packing
    """.split()
)

# Closed-class words that do not appear as English in these answers.
_OTHER_WORDS = frozenset(
    {
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "einer",
        "einem",
        "einen",
        "den",
        "dem",
        "des",
        "nicht",
        "für",
        "und",
        "ist",
        "auf",
        "mit",
        "erfordert",
        "aktuellen",
        "spezifischen",
        "bestellung",
        "frage",
        "los",
        "las",
        "que",
        "por",
        "para",
        "como",
        "una",
        "está",
        "pedido",
        "les",
        "des",
        "une",
        "est",
        "dans",
        "avec",
        "cette",
        "commande",
    }
)


def has_other_language(text: str) -> bool:
    """True when the text is not only Chinese and English."""
    if not (text or "").strip():
        return False
    for char in text:
        if char.isascii() or char.isspace() or char.isdigit():
            continue
        if _HAN.match(char):
            continue
        if unicodedata.category(char).startswith(("P", "S", "Z")):
            continue
        if unicodedata.category(char).startswith("L"):
            return True
    words = [token.lower() for token in _WORD.findall(text)]
    if not words:
        return False
    english = [word for word in words if word in _ENGLISH]
    if len(words) <= 8 and not english and not _HAN.search(text):
        return True
    hits = set(words) & _OTHER_WORDS
    return len(hits) >= 2


def _rewrite(text: str, question: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.agent.graph import build_model

    target = "Chinese" if reply_language(question) == "zh" else "English"
    system = (
        f"Rewrite the entire text into {target}. "
        "Keep order ids, numbers, dates, and names that were already there. "
        "Do not add facts. Return only the rewritten text."
    )
    result = build_model().invoke(
        [SystemMessage(content=system), HumanMessage(content=text)]
    )
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        content = "\n".join(parts)
    rewritten = str(content or "").strip()
    return rewritten or text


def align_visible_text(text: str, question: str) -> str:
    """Replace a non-Chinese, non-English answer with the question's language."""
    if not has_other_language(text):
        return text
    try:
        rewritten = _rewrite(text, question)
    except Exception:  # noqa: BLE001 — a failed rewrite must not drop the answer
        logger.exception("language rewrite failed")
        return text
    logger.info("rewrote non zh/en text into %s", reply_language(question))
    return rewritten


def align_visible_payload(parsed: dict, question: str) -> dict:
    """Replace non-Chinese, non-English user-visible text with the question's language."""
    cache: dict[str, str] = {}

    def once(text: str) -> str:
        if text not in cache:
            cache[text] = align_visible_text(text, question)
        return cache[text]

    parsed["answer"] = once(parsed.get("answer") or "")
    for trace in parsed.get("traces") or []:
        if isinstance(trace, dict) and trace.get("basis"):
            trace["basis"] = once(str(trace["basis"]))
    card = parsed.get("clarification")
    if isinstance(card, dict):
        if card.get("prompt"):
            card["prompt"] = once(str(card["prompt"]))
        for option in card.get("options") or []:
            if not isinstance(option, dict):
                continue
            if option.get("label"):
                option["label"] = once(str(option["label"]))
            if option.get("message"):
                option["message"] = once(str(option["message"]))
    return parsed
