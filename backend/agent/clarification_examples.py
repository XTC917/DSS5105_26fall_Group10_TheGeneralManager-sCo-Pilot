"""Pinned clarification cards, matched by cosine similarity.

Add another object under examples in data/clarification_few_shots.json.
Delete this module, that file, and the call in assess_answerability to remove it.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import numpy as np

from backend.config import PROJECT_ROOT
from backend.services.question_templates import _tokens

logger = logging.getLogger(__name__)

EXAMPLES_PATH = PROJECT_ROOT / "data" / "clarification_few_shots.json"
# Close wording of a pinned question. A different question stays on the model.
MATCH_THRESHOLD = 0.85


def _vector(tokens: list[str], vocab: dict[str, int]) -> np.ndarray:
    vec = np.zeros(len(vocab), dtype=np.float64)
    for token in tokens:
        index = vocab.get(token)
        if index is not None:
            vec[index] += 1.0
    norm = np.linalg.norm(vec)
    if norm:
        vec /= norm
    return vec


@lru_cache(maxsize=1)
def _load(mtime: float) -> tuple[dict, ...]:
    if not EXAMPLES_PATH.is_file():
        return ()
    raw = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
    examples = []
    for row in raw.get("examples") or []:
        question = str(row.get("question") or "").strip()
        options = row.get("options") or []
        if question and len(options) >= 2:
            examples.append(row)
    return tuple(examples)


def match_clarification(question: str) -> tuple[dict, float] | None:
    """Return the closest pinned card and its cosine, or None below the threshold."""
    text = (question or "").strip()
    if not text:
        return None
    mtime = EXAMPLES_PATH.stat().st_mtime if EXAMPLES_PATH.is_file() else 0.0
    examples = _load(mtime)
    if not examples:
        return None
    query_tokens = _tokens(text)
    best: tuple[dict, float] | None = None
    for example in examples:
        example_tokens = _tokens(str(example.get("question") or ""))
        vocab: dict[str, int] = {}
        for token in example_tokens + query_tokens:
            if token not in vocab:
                vocab[token] = len(vocab)
        if not vocab:
            continue
        score = float(_vector(query_tokens, vocab) @ _vector(example_tokens, vocab))
        if best is None or score > best[1]:
            best = (example, score)
    if best is None or best[1] < MATCH_THRESHOLD:
        logger.info(
            "clarification few-shot miss score=%s",
            None if best is None else round(best[1], 4),
        )
        return None
    logger.info(
        "clarification few-shot hit score=%s question=%r",
        round(best[1], 4),
        str(best[0].get("question") or "")[:80],
    )
    return best
