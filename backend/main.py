"""FastAPI entry point.

Run from the project root:

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg import Error as DatabaseError

from backend.config import FACTORY_TODAY
from backend.agent.graph import llm_is_configured, run_agent, set_checkpointer
from backend.logging_setup import setup_logging
from backend.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
)
from backend.services.checkpoint_store import postgres_checkpointer
from backend.services.audit import list_audit
from backend.services.auth import CurrentUser, get_current_user
from backend.services.briefing import build_morning_briefing
from backend.services.calculations import parse_iso_date
from backend.services.confirm_actions import ConfirmError, confirm_proposed_action, decline_proposed_action
from backend.services.database import get_db, init_db
from backend.services.request_context import set_current_user
from backend.services.discovery import DEFAULT_LIMIT, MAX_LIMIT, discover_factory_issues
from backend.routers.data_admin import (
    datasource_router,
    query_router,
    upload_router,
)
from backend.services.watches import evaluate_and_list
from backend.tools.registry import MVP_TOOLS
from backend.routers.auth import router as auth_router, users_router
from backend.routers.conversations import router as conversations_router
from backend.services.conversation_history import (
    ActionDecisionError,
    ConversationNotFoundError,
    get_owned_conversation,
    record_turn_action_decision,
    save_turn,
    validate_turn_action,
)

logger = logging.getLogger(__name__)


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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "factory_today": "2026-04-01",
        "llm_configured": llm_is_configured(),
        "tools": [t.name for t in MVP_TOOLS],
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> ChatResponse:
    public_conversation_id = str(request.conversation_id)
    try:
        get_owned_conversation(user.id, request.conversation_id)
        if not llm_is_configured():
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM key is not set. For Gemini set GOOGLE_API_KEY "
                    "(LLM_PROVIDER=gemini); for GPT set OPENAI_API_KEY. "
                    "Tools still work (run pytest). Copy .env.example to .env "
                    "to enable the agent."
                ),
            )
        thread_id = f"user:{user.id}:conversation:{public_conversation_id}"
        set_current_user(user)
        try:
            result = run_agent(
                request.message,
                public_conversation_id,
                clarification_reply=request.clarification_reply,
                thread_id=thread_id,
            )
            # Validate the agent's public contract before storing a successful turn.
            response = ChatResponse(**result)
            result = response.model_dump(mode="json")
            response_json = {
                key: value
                for key, value in result.items()
                if key not in ("answer", "conversation_id")
            }
            saved_turn = save_turn(
                user.id,
                request.conversation_id,
                question=request.message,
                answer=result["answer"],
                response_json=response_json,
            )
            result["proposed_actions"] = [
                {**action, "_turn_id": saved_turn["id"]}
                for action in result.get("proposed_actions") or []
            ]
        finally:
            set_current_user(None)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.exception("chat persistence unavailable")
        raise HTTPException(status_code=503, detail="Conversation history is unavailable. Please try again.") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.") from exc
    return ChatResponse(**result)


@app.get("/api/briefing")
def briefing() -> dict:
    """Structured morning briefing facts (no LLM)."""
    return build_morning_briefing(get_db())


@app.get("/api/discovery")
def discovery(limit: int = DEFAULT_LIMIT) -> dict:
    """Production-log issues from defined Python rules (no LLM)."""
    if limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be an integer from 1 to {MAX_LIMIT}.",
        )
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


@app.get("/api/watches")
def watches(as_of: str | None = None, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Evaluate active watches at factory `as_of`, then return fired + active.

    Default as_of is FACTORY_TODAY (2026-04-01), not the computer clock.
    There is no scheduler; calling this endpoint is the evaluation trigger.
    Only the authenticated user's watches are evaluated and returned.
    """
    if as_of:
        try:
            day = parse_iso_date(as_of)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="as_of must be YYYY-MM-DD.") from exc
        if day is None:
            raise HTTPException(status_code=400, detail="as_of must be YYYY-MM-DD.")
    else:
        day = FACTORY_TODAY
    get_db()
    set_current_user(user)
    try:
        return evaluate_and_list(day)
    finally:
        set_current_user(None)


@app.post("/api/actions/confirm", response_model=ConfirmActionResponse)
def confirm_action(request: ConfirmActionRequest, user: CurrentUser = Depends(get_current_user)) -> ConfirmActionResponse:
    """Persist a proposed action after a UI click. Does not call the LLM."""
    get_db()
    turn_id = request.action.get("_turn_id")
    try:
        if isinstance(turn_id, int) and turn_id >= 1:
            validate_turn_action(user.id, turn_id, action=request.action)
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
