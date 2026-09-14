"""Retrieve the closest development-set questions as answer-style templates.

Matching is TF-IDF cosine over question text (numpy only). Numbers in those
templates are not ground truth for the live query — the agent must still copy
facts from this turn's tool JSON.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

import numpy as np

from backend.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions.json"
DEFAULT_K = 3
_TOKEN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


@lru_cache(maxsize=1)
def _index() -> tuple[tuple[dict[str, str], ...], dict[str, int], np.ndarray, np.ndarray]:
    if not QUESTIONS_PATH.is_file():
        logger.warning("question bank missing: %s", QUESTIONS_PATH)
        empty = np.zeros((0, 0))
        return (), {}, empty, empty
    raw = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    items: list[dict[str, str]] = []
    for row in raw.get("questions") or []:
        qid = str(row.get("id") or "").strip()
        question = str(row.get("question") or "").strip()
        if not qid or not question:
            continue
        items.append(
            {
                "id": qid,
                "question": question,
                "expected_answer": str(row.get("expected_answer") or "").strip(),
            }
        )
    docs = [_tokens(item["question"]) for item in items]
    vocab: dict[str, int] = {}
    for tokens in docs:
        for tok in tokens:
            if tok not in vocab:
                vocab[tok] = len(vocab)
    n_docs = len(docs)
    n_terms = len(vocab)
    tf = np.zeros((n_docs, n_terms), dtype=np.float64)
    for i, tokens in enumerate(docs):
        if not tokens:
            continue
        counts: dict[int, int] = {}
        for tok in tokens:
            j = vocab[tok]
            counts[j] = counts.get(j, 0) + 1
        length = float(len(tokens))
        for j, count in counts.items():
            tf[i, j] = count / length
    df = (tf > 0).sum(axis=0)
    idf = np.log((n_docs + 1.0) / (df + 1.0)) + 1.0
    matrix = tf * idf
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return tuple(items), vocab, matrix / norms, idf


def retrieve_answer_templates(query: str, k: int = DEFAULT_K) -> list[dict[str, Any]]:
    """Return up to k bank questions most similar to the manager's query."""
    items, vocab, matrix, idf = _index()
    if not items or not (query or "").strip() or not vocab:
        return []
    q_tokens = _tokens(query)
    vec = np.zeros(len(vocab), dtype=np.float64)
    if q_tokens:
        counts: dict[int, int] = {}
        for tok in q_tokens:
            j = vocab.get(tok)
            if j is None:
                continue
            counts[j] = counts.get(j, 0) + 1
        length = float(len(q_tokens))
        for j, count in counts.items():
            vec[j] = count / length
        vec = vec * idf
        norm = np.linalg.norm(vec)
        if norm:
            vec = vec / norm
    scores = matrix @ vec
    k = max(0, min(int(k), len(items)))
    if k == 0:
        return []
    order = np.argsort(scores)[::-1][:k]
    hits: list[dict[str, Any]] = []
    for idx in order:
        score = float(scores[int(idx)])
        if score <= 0:
            continue
        item = items[int(idx)]
        hits.append({**item, "score": round(score, 4)})
    logger.info("retrieved answer templates %s", [h["id"] for h in hits])
    return hits
