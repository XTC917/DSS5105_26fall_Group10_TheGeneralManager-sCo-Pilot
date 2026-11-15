"""Pick the clarification option that matches the standard answer, then continue.

The text sent back is the same text a click sends: the question prompt, then the
option label. A standard answer that stops at the menu is left on the card.
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)
_OPTION_LINE = re.compile(r"^(?:I['’]ll|I will|我会|我将)", re.IGNORECASE)
_PROMPTS = (
    "which of these did you mean?",
    "what should count as",
    "who should this email",
    "answer every question below",
    "您想采用哪一种",
    "请回答下面每一个问题",
    "这封邮件是写给",
    "什么算",
)
_MENU_ONLY = {"other", "其他"}


def reply_body(parsed: dict[str, Any]) -> str:
    """The manager-facing prose. Tables, charts, and Why stay out of this text."""
    text = _strip_markdown_tables(str(parsed.get("answer") or ""))
    return _strip_why_heading(text).strip()


def card_body(card: dict[str, Any]) -> str:
    """The clarification the manager sees, without a table or a Why panel."""
    parts: list[str] = []
    prompt = str(card.get("prompt") or "").strip()
    if prompt:
        parts.append(prompt)
    for group in _groups(card):
        group_prompt = str(group.get("prompt") or "").strip()
        if group_prompt and group_prompt not in parts:
            parts.append(group_prompt)
        for option in group.get("options") or []:
            label = str(option.get("label") or "").strip()
            if label:
                parts.append(label)
    return "\n\n".join(parts).strip()


def stops_at_card(case: dict[str, Any]) -> bool:
    """True when the standard answer is the menu itself, not the answer after a choice."""
    return follow_target(case) is None and _opens_as_menu(str(case.get("expected_answer") or ""))


def follow_target(case: dict[str, Any]) -> str | None:
    """The part of the standard answer that comes after the menu. None when there is none."""
    expected = str(case.get("expected_answer") or "")
    if not _opens_as_menu(expected):
        return expected
    kept = []
    for line in expected.splitlines():
        text = line.strip()
        if not text or text.casefold() in _MENU_ONLY:
            continue
        if any(prompt in text.casefold() for prompt in _PROMPTS):
            continue
        if _OPTION_LINE.match(text):
            continue
        kept.append(text)
    body = "\n".join(kept).strip()
    return body or None


def choose_clarification(card: dict[str, Any], case: dict[str, Any]) -> dict[str, Any] | None:
    """Return the click text for the option closest to the standard answer."""
    target = follow_target(case) or str(case.get("expected_answer") or "")
    gold = [str(item).strip() for item in ((case.get("clarification") or {}).get("options") or []) if str(item).strip()]
    lines = []
    picked = []
    for group in _groups(card):
        options = [option for option in group.get("options") or [] if str(option.get("label") or "").strip()]
        if not options:
            continue
        label, score = _best_label(options, gold, target)
        lines.append(_reply_text(str(group.get("prompt") or card.get("prompt") or ""), label))
        picked.append({"prompt": group.get("prompt") or "", "label": label, "score": round(score, 3)})
    if not lines:
        return None
    return {"text": "\n\n".join(lines), "picked": picked}


def _best_label(options: list[dict[str, Any]], gold: list[str], target: str) -> tuple[str, float]:
    scored = []
    for option in options:
        label = str(option.get("label") or "").strip()
        gold_score = max((_overlap(label, item) for item in gold), default=0.0)
        answer_score = _overlap(label, target)
        scored.append((gold_score + answer_score, label))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


def _groups(card: dict[str, Any]) -> list[dict[str, Any]]:
    questions = card.get("questions")
    if isinstance(questions, list) and questions:
        return [item for item in questions if isinstance(item, dict)]
    return [{"prompt": card.get("prompt") or "", "options": card.get("options") or []}]


def _reply_text(prompt: str, label: str) -> str:
    question = prompt.strip()
    chosen = label.strip()
    if not question or question == chosen:
        return chosen
    return f"{question}\n{chosen}"


def _opens_as_menu(expected: str) -> bool:
    first = ""
    for line in expected.splitlines():
        if line.strip():
            first = line.strip().casefold()
            break
    return any(prompt in first for prompt in _PROMPTS)


def _overlap(label: str, target: str) -> float:
    left = set(_TOKEN.findall(label.casefold()))
    right = set(_TOKEN.findall(target.casefold()))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def _strip_markdown_tables(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            continue
        kept.append(line)
    return "\n".join(kept)


def _strip_why_heading(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.fullmatch(r"#{0,3}\s*(Why|原因)\s*", line.strip(), flags=re.IGNORECASE):
            return "\n".join(lines[:index])
    return text
