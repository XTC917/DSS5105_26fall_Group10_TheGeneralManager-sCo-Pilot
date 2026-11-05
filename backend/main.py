"""FastAPI entry point.

Run from the project root:

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import time
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from backend.config import PROJECT_ROOT, SEMANTIC_LAYER_PATH, using_factory_date
from backend.agent.graph import llm_is_configured, run_agent, set_checkpointer
from backend.logging_setup import setup_logging
from backend.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ActionOfferRequest,
    ActionOfferResponse,
    SuggestionRequest,
    SuggestionResponse,
)
from backend.services.audit import list_audit
from backend.services.auth import CurrentUser, get_current_user, get_optional_current_user, require_admin
from backend.services.briefing import build_morning_briefing
from backend.services.confirm_actions import ConfirmError, confirm_proposed_action, decline_proposed_action
from backend.services.checkpoint_store import postgres_checkpointer
from backend.services.conversation_history import (
    ActionDecisionError,
    ConversationNotFoundError,
    fail_chat_attempt,
    get_owned_conversation,
    attach_action_offer,
    record_clarification_choice,
    record_turn_action_decision,
    save_turn,
    start_chat_attempt,
    validate_turn_action,
)
from backend.services.database import get_db, init_db
from backend.services.factory_clock import load_factory_date, set_factory_date
from backend.services.request_context import set_current_user
from backend.services.action_offers import compose_action_offer
from backend.services.discovery import DEFAULT_LIMIT, MAX_LIMIT, discover_factory_issues
from backend.services.question_templates import compose_deep_dive_questions
from backend.routers.data_admin import (
    datasource_router,
    query_router,
    upload_router,
)
from backend.services.watches import evaluate_and_list
from backend.services.why import explain_why
from backend.tools.registry import MVP_TOOLS
from backend.routers.auth import router as auth_router, users_router
from backend.routers.conversations import router as conversations_router
from backend.routers.email import router as email_router

logger = logging.getLogger(__name__)
_CHAT_WORKERS: set[asyncio.Task] = set()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    if origins:
        return origins
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_db()
    try:
        with postgres_checkpointer() as checkpointer:
            set_checkpointer(checkpointer)
            logger.info("SweaterCo co-pilot API ready. LLM configured=%s", llm_is_configured())
            yield
    finally:
        set_checkpointer(None)


app = FastAPI(
    title="SweaterCo GM Co-Pilot",
    version="0.1.0",
    description="Track 1: grounded factory Q&A via inspectable tools.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Management (shares data/factory.db with the Co-Pilot tools).
app.include_router(upload_router)
app.include_router(datasource_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(conversations_router)
app.include_router(email_router)

_PROBLEM_ANSWER = "I couldn't finish that answer. Please try again."


@app.get("/api/health")
def health(user: CurrentUser | None = Depends(get_optional_current_user)) -> dict:
    questions_path = PROJECT_ROOT / "evaluation" / "questions.json"
    return {
        "ok": True,
        "factory_today": load_factory_date().isoformat(),
        "llm_configured": llm_is_configured(),
        "tools": [t.name for t in MVP_TOOLS],
        # Deploy integrity only — does not invoke the LLM or change agent behavior.
        "answer_templates_present": questions_path.is_file(),
        "semantic_layer_present": SEMANTIC_LAYER_PATH.is_file(),
    }


def _answer_text(response: ChatResponse) -> str:
    answer = (response.answer or "").strip()
    if response.clarification and not answer:
        answer = str((response.clarification or {}).get("prompt") or "Which of these did you mean?").strip()
    return answer or _PROBLEM_ANSWER


def _store_chat_turn(
    user: CurrentUser,
    request: ChatRequest,
    response: ChatResponse,
    *,
    attempt_id: int,
    duration_ms: int,
) -> ChatResponse:
    """Save this turn, including a refusal or a user-facing error."""
    response_json = response.model_dump(
        exclude={"answer", "conversation_id", "turn_id"},
        mode="json",
    )
    saved_turn = save_turn(
        user.id,
        request.conversation_id,
        question=request.message,
        answer=_answer_text(response),
        response_json=response_json,
        attempt_id=attempt_id,
        duration_ms=duration_ms,
    )
    response.turn_id = saved_turn["id"]
    response.proposed_actions = [
        {**action, "_turn_id": saved_turn["id"]}
        for action in response.proposed_actions
    ]
    return response


def _problem_response(
    request: ChatRequest,
    user: CurrentUser,
    *,
    attempt_id: int | None,
    duration_ms: int,
    answer: str,
) -> ChatResponse:
    response = ChatResponse(
        answer=answer,
        conversation_id=str(request.conversation_id),
        limitation="error",
    )
    if attempt_id is None:
        return response
    try:
        return _store_chat_turn(
            user,
            request,
            response,
            attempt_id=attempt_id,
            duration_ms=duration_ms,
        )
    except Exception:  # noqa: BLE001
        logger.exception("could not store the failed chat turn")
        return response


def _complete_chat(
    request: ChatRequest,
    user: CurrentUser,
    progress=None,
    on_token=None,
) -> ChatResponse:
    started_ns = time.perf_counter_ns()
    attempt_id: int | None = None
    public_conversation_id = str(request.conversation_id)

    def duration_ms() -> int:
        return max(0, (time.perf_counter_ns() - started_ns) // 1_000_000)

    def record_failure(code: str, message: str) -> None:
        if attempt_id is None:
            return
        try:
            fail_chat_attempt(
                user.id,
                attempt_id,
                duration_ms=duration_ms(),
                error_code=code,
                error_message=message,
            )
        except Exception:  # noqa: BLE001
            logger.exception("could not persist failed chat attempt")

    try:
        get_owned_conversation(user.id, request.conversation_id)
        attempt = start_chat_attempt(
            user.id,
            request.conversation_id,
            question=request.message,
            clarification_reply=request.clarification_reply,
        )
        attempt_id = int(attempt["id"])

        if not llm_is_configured():
            return _problem_response(
                request,
                user,
                attempt_id=attempt_id,
                duration_ms=duration_ms(),
                answer="Chat is not ready yet. Please try again later.",
            )

        if request.clarification_reply:
            record_clarification_choice(
                user.id,
                request.conversation_id,
                request.message,
            )

        thread_id = f"user:{user.id}:conversation:{public_conversation_id}"
        set_current_user(user)
        try:
            with using_factory_date(load_factory_date()):
                result = run_agent(
                    request.message,
                    public_conversation_id,
                    clarification_reply=request.clarification_reply,
                    original_question=request.original_question,
                    thread_id=thread_id,
                    progress=progress,
                    on_token=on_token,
                )
        finally:
            set_current_user(None)

        prepared = result.get("why")
        try:
            why = prepared if isinstance(prepared, dict) else explain_why(request.message, result)
        except Exception:  # noqa: BLE001
            logger.exception("why explanation failed")
            why = None
        response = ChatResponse(**{**result, "why": why})
        return _store_chat_turn(
            user,
            request,
            response,
            attempt_id=attempt_id,
            duration_ms=duration_ms(),
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat failed")
        if attempt_id is not None:
            return _problem_response(
                request,
                user,
                attempt_id=attempt_id,
                duration_ms=duration_ms(),
                answer=_PROBLEM_ANSWER,
            )
        record_failure("CHAT_SERVICE_UNAVAILABLE", _PROBLEM_ANSWER)
        raise HTTPException(status_code=503, detail=_PROBLEM_ANSWER) from exc


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    return _complete_chat(request, user)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, user: CurrentUser = Depends(get_current_user)):
    """Same chat turn as /api/chat, with live progress and answer text."""

    async def events():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def progress(text: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", {"message": text}))

        def on_token(piece) -> None:
            if isinstance(piece, dict) and piece.get("reset"):
                loop.call_soon_threadsafe(queue.put_nowait, ("token", {"reset": True}))
                return
            if piece:
                loop.call_soon_threadsafe(queue.put_nowait, ("token", {"text": piece}))

        async def produce() -> None:
            try:
                response = await asyncio.to_thread(
                    _complete_chat, request, user, progress, on_token
                )
                await queue.put(("done", response.model_dump(mode="json")))
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "Chat failed. Please try again."
                await queue.put(("error", {"message": detail}))
            except Exception:
                logger.exception("chat stream failed")
                await queue.put(("error", {"message": "Chat failed. Please try again."}))

        worker = asyncio.create_task(produce())
        _CHAT_WORKERS.add(worker)
        worker.add_done_callback(_CHAT_WORKERS.discard)
        try:
            yield 'event: progress\ndata: {"message":"Checking the question…"}\n\n'
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                if event in {"done", "error"}:
                    break
        finally:
            if not worker.done():
                worker.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/suggestions", response_model=SuggestionResponse)
def suggestions(
    request: SuggestionRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> SuggestionResponse:
    """Deep-dive questions. Called beside answer rendering, not inside the answer."""
    asked = [text.strip()[:400] for text in request.asked if str(text or "").strip()][-12:]
    return SuggestionResponse(
        suggestions=compose_deep_dive_questions(
            request.query.strip()[:400],
            asked=asked,
        )
    )


@app.post("/api/action-offers", response_model=ActionOfferResponse)
def action_offers(
    request: ActionOfferRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ActionOfferResponse:
    """One yes/no action after the answer. Not called while the answer is still running."""
    with using_factory_date(load_factory_date()):
        offer = compose_action_offer(
            request.question.strip()[:400],
            request.answer.strip()[:800],
            request.traces[:8],
            tools_used=request.tools_used[:12],
            proposed_actions=request.proposed_actions[:6],
        )
    if not offer:
        return ActionOfferResponse()
    return ActionOfferResponse(prompt=offer["prompt"], action=offer["action"])


@app.get("/api/briefing")
def briefing(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Structured morning briefing facts (no LLM)."""
    with using_factory_date(load_factory_date()):
        return build_morning_briefing(get_db())


@app.get("/api/discovery")
def discovery(limit: int = DEFAULT_LIMIT, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Production-log issues from defined Python rules (no LLM)."""
    if limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be an integer from 1 to {MAX_LIMIT}.",
        )
    with using_factory_date(load_factory_date()):
        return discover_factory_issues(get_db(), limit=limit)


@app.get("/api/audit")
def audit(limit: int = 15, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Recent audit rows for the authenticated user. Not a compliance archive."""
    cap = max(1, min(limit, 50))
    set_current_user(user)
    try:
        return {"items": list_audit(limit=cap, user_id=user.id), "limit": cap}
    finally:
        set_current_user(None)


class SetFactoryDateRequest(BaseModel):
    factory_date: date


@app.post("/api/factory-date")
def choose_factory_date(
    request: SetFactoryDateRequest,
    _admin: CurrentUser = Depends(require_admin),
) -> dict:
    """Set the one factory date every account treats as today."""
    try:
        day = set_factory_date(request.factory_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"factory_today": day.isoformat()}


@app.get("/api/watches")
def watches(as_of: str | None = None, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Evaluate only the authenticated user's watches on the shared factory date."""
    day = load_factory_date()
    if as_of is not None:
        try:
            requested = date.fromisoformat(as_of)
            if requested.isoformat() != as_of:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="as_of must be YYYY-MM-DD.") from exc
        if requested != day:
            raise HTTPException(status_code=409, detail="as_of must match your saved factory date.")
    get_db()
    set_current_user(user)
    try:
        with using_factory_date(day):
            return evaluate_and_list(day)
    finally:
        set_current_user(None)


class StoredActionOffer(BaseModel):
    prompt: str
    action: dict


@app.post("/api/turns/{turn_id}/action-offer")
def store_action_offer(
    turn_id: int,
    request: StoredActionOffer,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Keep the automatic watch or email suggestion on this turn."""
    try:
        attach_action_offer(
            user.id,
            turn_id,
            {"prompt": request.prompt, "action": request.action},
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat turn not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/actions/confirm", response_model=ConfirmActionResponse)
def confirm_action(request: ConfirmActionRequest, user: CurrentUser = Depends(get_current_user)) -> ConfirmActionResponse:
    """Persist a proposed action after a UI click. Does not call the LLM."""
    get_db()
    turn_id = request.action.get("_turn_id")
    try:
        if isinstance(turn_id, int) and turn_id >= 1:
            validate_turn_action(user.id, turn_id, action=request.action)
        with using_factory_date(load_factory_date()):
            result = confirm_proposed_action(request.action, current_user=user)
        if isinstance(turn_id, int) and turn_id >= 1 and result.get("ok"):
            record_turn_action_decision(
                user.id,
                turn_id,
                action=request.action,
                status="confirmed",
                summary=result.get("summary") or "Action confirmed.",
            )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat turn not found") from exc
    except ActionDecisionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConfirmError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    if not result.get("ok"):
        err = result.get("error") or {}
        raise HTTPException(
            status_code=400,
            detail=err.get("message") or "Confirmation failed.",
        )
    return ConfirmActionResponse(**result)


@app.post("/api/actions/decline", response_model=ConfirmActionResponse)
def decline_action(request: ConfirmActionRequest, user: CurrentUser = Depends(get_current_user)) -> ConfirmActionResponse:
    """Record that the manager dismissed a proposal. Nothing is persisted."""
    get_db()
    turn_id = request.action.get("_turn_id")
    summary = "Dismissed. Nothing was saved."
    try:
        if isinstance(turn_id, int) and turn_id >= 1:
            validate_turn_action(user.id, turn_id, action=request.action)
        with using_factory_date(load_factory_date()):
            result = decline_proposed_action(request.action, current_user=user)
        if isinstance(turn_id, int) and turn_id >= 1:
            record_turn_action_decision(
                user.id,
                turn_id,
                action=request.action,
                status="dismissed",
                summary=summary,
            )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat turn not found") from exc
    except ActionDecisionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConfirmError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return ConfirmActionResponse(ok=True, type=result.get("type"), declined=True, summary=summary)
