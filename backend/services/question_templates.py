"""Retrieve the closest development-set questions as answer-style templates.

Matching is TF-IDF cosine over question text (numpy only). A retrieval returns
three templates when both languages exist: the two closest questions in the
query's language, then one closest question in the other language. The other
language is chosen by the model, because Chinese and English tokens do not
overlap. Numbers in those templates are not ground truth for the live query —
the agent must still copy facts from this turn's tool JSON.
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
_SAME_LANGUAGE_K = 2
_TOKEN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)
_ORDER_ID = re.compile(r"ORD-\d+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for tok in _TOKEN.findall((text or "").lower()):
        if len(tok) > 1 and "\u4e00" <= tok[0] <= "\u9fff":
            tokens.extend(tok[i : i + 2] for i in range(len(tok) - 1))
        else:
            tokens.append(tok)
    return tokens


def _index() -> tuple[tuple[dict[str, str], ...], dict[str, int], np.ndarray, np.ndarray]:
    mtime = QUESTIONS_PATH.stat().st_mtime if QUESTIONS_PATH.is_file() else 0.0
    return _index_at(mtime)


@lru_cache(maxsize=1)
def _index_at(mtime: float) -> tuple[tuple[dict[str, str], ...], dict[str, int], np.ndarray, np.ndarray]:
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
                "relevant_tool": str(row.get("relevant_tool") or "").strip(),
                "category": str(row.get("category") or "").strip(),
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


def _query_scores(query: str) -> np.ndarray | None:
    items, vocab, matrix, idf = _index()
    if not items or not (query or "").strip() or not vocab:
        return None
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
    return matrix @ vec


def retrieve_answer_templates(query: str, k: int = DEFAULT_K) -> list[dict[str, Any]]:
    """Two closest questions in the query language, then one in the other language."""
    items, _, _, _ = _index()
    scores = _query_scores(query)
    if scores is None or not items:
        return []
    k = max(0, min(int(k), len(items)))
    if k == 0:
        return []
    same_limit = min(_SAME_LANGUAGE_K, k)
    hits = _language_hits(query, scores, items, same=True, limit=same_limit)
    if len(hits) < k:
        other = _other_language_hit(query)
        if other is not None and all(hit["id"] != other["id"] for hit in hits):
            hits.append(other)
    logger.info(
        "retrieved answer templates %s query=%r",
        [(h["id"], h["score"]) for h in hits],
        (query or "")[:120],
    )
    return hits[:k]


def _language_hits(
    query: str,
    scores: np.ndarray,
    items: tuple[dict[str, str], ...] | list[dict[str, str]],
    *,
    same: bool,
    limit: int,
) -> list[dict[str, Any]]:
    want_cjk = _has_cjk(query)
    ranked = sorted(
        (
            index
            for index, item in enumerate(items)
            if (_has_cjk(item["question"]) == want_cjk) is same
        ),
        key=lambda index: float(scores[index]),
        reverse=True,
    )
    hits: list[dict[str, Any]] = []
    for index in ranked:
        score = float(scores[index])
        if score <= 0:
            break
        hits.append({**items[index], "score": round(score, 4)})
        if len(hits) >= limit:
            break
    return hits


def _other_language_hit(query: str) -> dict[str, Any] | None:
    """One closest question in the other language. TF-IDF cannot cross scripts."""
    qid = _pick_other_language(query)
    if not qid:
        return None
    items, _, _, _ = _index()
    item = next((row for row in items if row["id"] == qid), None)
    if item is None or _has_cjk(item["question"]) == _has_cjk(query):
        return None
    return {**item, "score": 0.01}


def _pick_other_language(query: str) -> str:
    """Ask the model for one id in the language the query is not written in."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.agent.graph import build_model, llm_is_configured

    if not llm_is_configured():
        return ""
    items, _, _, _ = _index()
    want_cjk = not _has_cjk(query)
    pool = [item for item in items if _has_cjk(item["question"]) is want_cjk]
    if not pool:
        return ""
    listing = "\n".join(f"{row['id']}: {row['question'][:180]}" for row in pool)
    language = "Chinese" if want_cjk else "English"
    system = (
        f"Choose the one {language} question closest in meaning to the manager's question. "
        'Return JSON only: {"id":"<id>"}. Use only an id from the list.'
    )
    user = f"Question:\n{query[:400]}\n\n{language}:\n{listing}"
    try:
        # This call runs inside the answering turn. "nostream" keeps its JSON
        # id out of the manager's live answer.
        result = build_model().invoke(
            [SystemMessage(content=system), HumanMessage(content=user)],
            config={"tags": ["nostream"]},
        )
    except Exception:
        logger.exception("other-language template match failed")
        return ""
    text = getattr(result, "content", result)
    if isinstance(text, list):
        text = "\n".join(
            str(block.get("text") or "") if isinstance(block, dict) else str(block)
            for block in text
        )
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or ""), flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.info("other-language template match was not JSON")
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("id") or "").strip()


def without_foreign_order_templates(
    query: str,
    hits: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Drop examples whose question names an order id the manager did not write.

    The answer text may still name orders the tool found. The question text may
    not point the model at a different order.
    """
    named = {match.group(0).upper() for match in _ORDER_ID.finditer(query or "")}
    kept: list[dict[str, Any]] = []
    for hit in hits or []:
        ids = {match.group(0).upper() for match in _ORDER_ID.finditer(str(hit.get("question") or ""))}
        foreign = ids - named
        if foreign:
            logger.info(
                "dropped answer template %s foreign order ids %s",
                hit.get("id"),
                sorted(foreign),
            )
            continue
        kept.append(hit)
    return kept


def supplement_templates_for_tools(
    query: str,
    hits: list[dict[str, Any]] | None,
    tools: list[str] | tuple[str, ...] | None,
) -> list[dict[str, Any]]:
    """If a called tool has no retrieved example, append its closest bank question."""
    merged: list[dict[str, Any]] = list(hits or [])
    seen_ids = {str(h.get("id") or "") for h in merged}
    covered = {str(h.get("relevant_tool") or "") for h in merged if h.get("relevant_tool")}
    needed: list[str] = []
    for name in tools or []:
        tool = str(name or "").strip()
        if not tool or tool in covered or tool in needed:
            continue
        needed.append(tool)
    if not needed:
        return merged
    items, _, _, _ = _index()
    scores = _query_scores(query)
    if scores is None or not items:
        return merged
    extras: list[tuple[str, str]] = []
    for tool in needed:
        best_idx = None
        best_score = -1.0
        for i, item in enumerate(items):
            if item.get("relevant_tool") != tool:
                continue
            if item["id"] in seen_ids:
                continue
            score = float(scores[i])
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is None:
            continue
        extra = {**items[best_idx], "score": round(best_score, 4)}
        merged.append(extra)
        seen_ids.add(extra["id"])
        covered.add(tool)
        extras.append((extra["id"], tool))
    if extras:
        logger.info("supplemented answer templates %s query=%r", extras, (query or "")[:120])
    return merged


_SKIP_CATEGORIES = frozenset(
    {
        "unsupported",
        "out_of_scope",
        "security",
        "empty_result",
        "not_found_lookup",
        "edge_case",
        "audit",
        "clarification",
    }
)
_DISPLAY_ONLY = frozenset({"draw", "render_table", "filter_rows", "summarize_rows"})
_ACTION_TOOLS = frozenset(
    {
        "create_reminder",
        "create_watch",
        "cancel_watch",
        "draft_chase_email",
        "send_email",
        "add_order_note",
    }
)
_BLOCK_PHRASES = ("dismiss this proposal", "test sprint")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_SPACE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACE.sub(" ", (text or "").strip().lower())


def _order_ids(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).upper() for match in _ORDER_ID.finditer(text or "")))


def _has_cjk(text: str) -> bool:
    return _CJK.search(text or "") is not None


def _registered_suggestion_tools() -> set[str]:
    from backend.tools.registry import MVP_TOOLS

    return {str(getattr(tool, "name", tool)) for tool in MVP_TOOLS} - _DISPLAY_ONLY


def _family(item: dict[str, str]) -> str:
    question = (item.get("question") or "").lower()
    tool = item.get("relevant_tool") or ""
    category = item.get("category") or ""
    if any(word in question for word in ("risk", "miss", "due date", "overdue", "stall", "priority", "resequence", "briefing")):
        return "risk"
    if category.startswith("anomaly") or tool in {"discover_factory_issues", "get_stage_output"}:
        return "anomaly"
    if category == "feasibility" or tool == "check_feasibility":
        return "feasibility"
    if category.startswith("action_") or tool in _ACTION_TOOLS:
        return "action"
    if category.startswith("risk") or category == "priority" or tool in {"get_orders_at_risk", "get_today_priority", "get_morning_briefing"}:
        return "risk"
    return "order"


def _skipped(item: dict[str, str], registered: set[str]) -> bool:
    if (item.get("category") or "") in _SKIP_CATEGORIES:
        return True
    tool = (item.get("relevant_tool") or "").strip()
    if not tool or tool in _DISPLAY_ONLY:
        return True
    names = [part.strip() for part in tool.split("+") if part.strip()]
    return any(name not in registered for name in names)


def _slot_fill(question: str, slot_id: str | None) -> str:
    ids = _order_ids(question)
    if slot_id and len(ids) == 1 and ids[0] != slot_id:
        return re.sub(re.escape(ids[0]), slot_id, question, flags=re.IGNORECASE)
    return question


def _ranked_followups(
    query: str,
    asked: list[str] | None = None,
    focus: str = "",
    pool: int = 6,
) -> list[dict[str, str]]:
    """Template questions for the next step, still in their original wording."""
    items, _, matrix, _ = _index()
    query = (query or "").strip()
    if not items or not query or matrix.size == 0:
        return []
    pool = max(0, min(int(pool), 8))
    if pool == 0:
        return []
    scores = _query_scores(query)
    if scores is None:
        return []
    asked_list = [text.strip() for text in (asked or []) if str(text or "").strip()][-12:]
    if query not in asked_list:
        asked_list.append(query)
    asked_norm = {_norm(text) for text in asked_list}
    asked_max = np.zeros(len(items), dtype=np.float64)
    for text in asked_list:
        row = _query_scores(text)
        if row is not None:
            asked_max = np.maximum(asked_max, row)
    best = int(np.argmax(scores))
    anchored = float(scores[best]) > 0.12
    current_family = _family(items[best]) if anchored else ""
    slot_id = (_order_ids(query) or _order_ids(focus) or [None])[0]
    registered = _registered_suggestion_tools()
    query_cjk = _has_cjk(query)
    ranked: list[tuple[tuple, int, str]] = []
    for index, item in enumerate(items):
        if _skipped(item, registered):
            continue
        if float(asked_max[index]) > 0.92:
            continue
        if _norm(item["question"]) in asked_norm:
            continue
        lowered = (item.get("question") or "").lower()
        if any(phrase in lowered for phrase in _BLOCK_PHRASES):
            continue
        same_family = bool(current_family) and _family(item) == current_family
        if float(scores[index]) <= 0.08 and not same_family:
            continue
        key = (
            0 if _has_cjk(item["question"]) == query_cjk else 1,
            0 if same_family else 1,
            -float(scores[index]),
        )
        ranked.append((key, index, item["question"]))
    ranked.sort(key=lambda row: row[0])
    picked: list[dict[str, str]] = []
    picked_index: list[int] = []
    for _, index, _text in ranked:
        question = items[index]["question"]
        if any(_norm(question) == _norm(previous["question"]) for previous in picked):
            continue
        if any(float(matrix[index] @ matrix[previous]) > 0.88 for previous in picked_index):
            continue
        picked.append(
            {
                "id": items[index]["id"],
                "question": question,
                "relevant_tool": items[index].get("relevant_tool") or "",
            }
        )
        picked_index.append(index)
        if len(picked) >= pool:
            break
    return picked


def suggest_followups(
    query: str,
    asked: list[str] | None = None,
    focus: str = "",
    k: int = 3,
) -> list[str]:
    """Deterministic template follow-ups. Prefer compose_deep_dive_questions for the product."""
    query = (query or "").strip()
    k = max(0, min(int(k), 3))
    slot_id = (_order_ids(query) or _order_ids(focus) or [None])[0]
    asked_norm = {_norm(text) for text in (asked or []) if str(text or "").strip()}
    asked_norm.add(_norm(query))
    picked: list[str] = []
    for item in _ranked_followups(query, asked=asked, focus=focus, pool=max(k, 1)):
        text = _slot_fill(item["question"], slot_id)
        if not text or _norm(text) in asked_norm or text in picked:
            continue
        picked.append(text)
        if len(picked) >= k:
            break
    return picked


_STAGES = ("knitting", "assembly", "washing", "packing")
_STAGE_RE = re.compile(r"\b(knitting|assembly|washing|packing)\b", re.IGNORECASE)


def _stages(text: str) -> list[str]:
    seen: list[str] = []
    for match in _STAGE_RE.finditer(text or ""):
        stage = match.group(1).capitalize()
        if stage.lower() not in {item.lower() for item in seen}:
            seen.append(stage)
    return seen


def _anchor_order_ids(questions: list[str]) -> list[str] | None:
    """The latest question's order id. Earlier questions do not choose the subject."""
    if not questions:
        return []
    latest = _order_ids(questions[-1])
    if len(latest) > 1:
        return None
    return latest


def _anchor_stage(questions: list[str]) -> str | None:
    """The latest question's stage. Earlier questions do not choose the subject."""
    if not questions:
        return ""
    latest = _stages(questions[-1])
    if len(latest) > 1:
        return None
    return latest[0] if latest else ""


def _entity_span(text: str) -> bool:
    span = (text or "").strip()
    if _ORDER_ID.fullmatch(span):
        return True
    if _STAGE_RE.fullmatch(span):
        return True
    if re.fullmatch(r"\d+", span):
        return True
    return any(char.isupper() for char in span)


def accept_grounded_rewrite(template: str, proposed: str, questions: list[str]) -> bool:
    """True when proposed is the template with entities taken from the manager's questions."""
    from difflib import SequenceMatcher

    corpus = "\n".join(questions)
    latest_ids = set(_order_ids(questions[-1])) if questions else set()
    proposed_ids = _order_ids(proposed)
    if any(order_id not in latest_ids for order_id in proposed_ids):
        return False
    template_ids = _order_ids(template)
    anchor = _anchor_order_ids(questions)
    if template_ids:
        if not anchor or len(anchor) != 1 or set(proposed_ids) != set(anchor):
            return False
    matcher = SequenceMatcher(None, template.lower(), (proposed or "").lower())
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = template[i1:i2].strip()
        new = proposed[j1:j2].strip()
        if not old or not new or new.lower() not in corpus.lower():
            return False
        if not _entity_span(old):
            return False
        if _ORDER_ID.fullmatch(old) and not _ORDER_ID.fullmatch(new):
            return False
        if _STAGE_RE.fullmatch(old) and not _STAGE_RE.fullmatch(new):
            return False
    return True


def _apply_grounded_edits(template: str, questions: list[str]) -> str | None:
    proposed = template
    template_ids = list(dict.fromkeys(_order_ids(template)))
    anchor = _anchor_order_ids(questions)
    if template_ids:
        if not anchor or len(anchor) != 1 or len(template_ids) != 1:
            return None
        if template_ids[0] != anchor[0]:
            proposed = re.sub(re.escape(template_ids[0]), anchor[0], proposed, flags=re.IGNORECASE)
    stage = _anchor_stage(questions)
    template_stages = list(dict.fromkeys(item.lower() for item in _stages(template)))
    if stage and len(template_stages) == 1 and template_stages != [stage.lower()]:
        proposed = re.sub(template_stages[0], stage, proposed, flags=re.IGNORECASE)
    if not accept_grounded_rewrite(template, proposed, questions):
        return None
    return proposed


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


def _draft_with_model(
    query: str,
    asked: list[str],
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Ask the model to rewrite the next disclosure step. Invalid output is discarded."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.agent.graph import build_model, llm_is_configured

    if not candidates or not llm_is_configured():
        return []
    catalog = "\n".join(f"- {item['id']}: {item['question']}" for item in candidates)
    history = "\n".join(f"- {text}" for text in asked[-6:])
    system = (
        "You choose the next progressive-disclosure questions for a factory manager. "
        "The subject is the latest question only. Earlier questions show what was already asked. "
        "If the latest question names an order, every rewritten question uses that order. "
        "Do not keep or insert an order from an earlier question. "
        "If the latest question names no order, do not insert one. "
        "Read the latest question and the screened templates. "
        "You decide which templates reveal the next useful detail. "
        "There is no fixed list of steps. "
        "Select at most 3 templates, then rewrite only those. "
        "Do not rephrase the latest question. "
        "Do not choose a template that asks the same kind of question. "
        "Swapping the order, stage, customer, product, or number is not a deeper question. Skip it. "
        "Do not pick three templates that ask the same thing. "
        "Change an order id, a stage (Knitting, Assembly, Washing, Packing), "
        "a customer or product name, or a number only when that value is in the latest question. "
        "Do not invent a question, an order id, or a name. "
        "If a template names one order and the latest question names a different one, replace it with the latest order. "
        "If the manager named several orders in the latest question, skip templates that need a single order. "
        'Return JSON only: {"questions":[{"source_id":"...","question":"..."}]}. '
        "Keep each template's language."
    )
    user = f"Latest question:\n{query}\n\nRecent questions:\n{history}\n\nTemplates:\n{catalog}"
    try:
        result = build_model().invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
    except Exception:
        logger.exception("deep-dive suggestion model failed")
        return []
    text = _message_text(result)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.info("deep-dive suggestion was not JSON")
        return []
    rows = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    drafted: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        drafted.append(
            {
                "source_id": str(row.get("source_id") or "").strip(),
                "question": str(row.get("question") or "").strip(),
            }
        )
    return drafted


def _kind_key(text: str) -> str:
    masked = (text or "").lower()
    masked = _ORDER_ID.sub(" {order} ", masked)
    masked = _STAGE_RE.sub(" {stage} ", masked)
    masked = re.sub(r"\d+", " {n} ", masked)
    return _SPACE.sub(" ", masked).strip()


def same_kind(left: str, right: str) -> bool:
    """True when the questions match once order, stage, and number swaps are ignored."""
    from difflib import SequenceMatcher

    kind_left = _kind_key(left)
    kind_right = _kind_key(right)
    if not kind_left or not kind_right:
        return False
    if kind_left == kind_right:
        return True
    return SequenceMatcher(None, kind_left, kind_right).ratio() >= 0.84


def _lateral_replacement(proposed: str, asked: list[str], accepted: list[str]) -> bool:
    return any(same_kind(proposed, previous) for previous in [*asked, *accepted])


def compose_deep_dive_questions(
    query: str,
    asked: list[str] | None = None,
    k: int = 3,
) -> list[str]:
    """Model rewrites template keywords. A question that is unclear or ungrounded is dropped."""
    query = (query or "").strip()
    if not query:
        return []
    asked_list = [text.strip() for text in (asked or []) if str(text or "").strip()][-12:]
    asked_list = [text for text in asked_list if text != query]
    asked_list.append(query)
    asked_norm = {_norm(text) for text in asked_list}
    k = max(0, min(int(k), 3))
    candidates = _ranked_followups(query, asked=asked_list, pool=8)
    if not candidates:
        return []
    by_id = {item["id"]: item["question"] for item in candidates}
    accepted: list[str] = []
    for row in _draft_with_model(query, asked_list, candidates):
        template = by_id.get(row.get("source_id") or "")
        proposed = row.get("question") or ""
        if not template or not proposed or _norm(proposed) in asked_norm:
            continue
        if not accept_grounded_rewrite(template, proposed, asked_list):
            logger.info("dropped ungrounded deep-dive suggestion %r", proposed[:160])
            continue
        if _lateral_replacement(proposed, asked_list, accepted):
            logger.info("dropped same-kind deep-dive suggestion %r", proposed[:160])
            continue
        if proposed not in accepted:
            accepted.append(proposed)
        if len(accepted) >= k:
            return accepted
    for item in candidates:
        fallback = _apply_grounded_edits(item["question"], asked_list)
        if not fallback or _norm(fallback) in asked_norm or fallback in accepted:
            continue
        if _lateral_replacement(fallback, asked_list, accepted):
            continue
        accepted.append(fallback)
        if len(accepted) >= k:
            break
    logger.info("deep-dive suggestions %s query=%r", accepted, query[:120])
    return accepted
