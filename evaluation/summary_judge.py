"""Build the summary packet for a Grok subagent, then apply its grade.

The judge is a Cursor subagent on a Grok model. This module does not call an
external Grok API. `settle` turns the subagent JSON into A+ / A / A- / B+ / C.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.config import PROJECT_ROOT

SKILL_PATH = PROJECT_ROOT / ".cursor" / "skills" / "summary-evaluation" / "SKILL.md"
_FAILURE = {
    "en": "I couldn't finish that answer. Please try again.",
    "zh": "这次没能完成回答。请再试一次。",
}


def load_skill_text(path: Path = SKILL_PATH) -> str:
    raw = path.read_text(encoding="utf-8")
    return re.sub(r"^---\n.*?\n---\n", "", raw, count=1, flags=re.DOTALL).strip()


def judge_packet(
    *,
    question: str,
    answer: str,
    reference_data: Any,
    sample_answer: str,
    must_include: list[str],
) -> dict[str, Any]:
    """The packet a Grok subagent scores. Code grades an unavailable answer itself."""
    if _unavailable(answer):
        return {
            "needs_judge": False,
            "summary": {
                "level": "L0",
                "grade": "B+",
                "counted": False,
                "reason": "The answer is empty or is the unfinished-answer sentence.",
                "source": "code",
            },
        }
    return {
        "needs_judge": True,
        "skill": load_skill_text(),
        "question": question,
        "answer": answer,
        "reference_tool_json": reference_data,
        "sample_answer": sample_answer,
        "must_include": must_include,
    }


def settle(payload: dict[str, Any]) -> dict[str, Any]:
    level = str(payload.get("level") or "L0").upper()
    if level not in {"L0", "L1", "L2", "L3"}:
        level = "L0"
    reason = str(payload.get("reason") or "").strip()
    if level == "L3":
        grade, counted = "A+", True
    elif level == "L2":
        grade, counted = "A", True
    elif level == "L1":
        grade, counted = "A-", False
    else:
        grade = "B+" if str(payload.get("grade") or "").upper() == "B+" else "C"
        counted = False
    return {
        "level": level,
        "grade": grade,
        "counted": counted,
        "reason": reason,
        "source": "grok",
    }


def _unavailable(answer: str) -> bool:
    text = (answer or "").strip()
    return not text or text in _FAILURE.values()
