"""FastAPI entry point.

Run from the project root:

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.services.why import build_why

from backend.config import FACTORY_TODAY
from backend.agent.graph import llm_is_configured, run_agent
from backend.logging_setup import setup_logging
from backend.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
)
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

logger = logging.getLogger(__name__)
_CHAT_WORKERS: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_db()
    logger.info("SweaterCo co-pilot API ready. LLM configured=%s", llm_is_configured())
    yield


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


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "factory_today": "2026-04-01",
        "llm_configured": llm_is_configured(),
        "tools": [t.name for t in MVP_TOOLS],
    }


def _execute_chat(request: ChatRequest, user: CurrentUser, *, progress=None) -> ChatResponse:
    # Keep the existing in-memory conversation model. Namespace sessions by the
    # authenticated user so the new stream cannot share another user's context.
    session_id = f"user:{user.id}:conversation:{request.conversation_id}"
    if not llm_is_configured():
        raise HTTPException(status_code=503, detail="Chat is not configured.")
    set_current_user(user)
    try:
        progress_args = {"progress": progress} if progress else {}
        result = run_agent(request.message, session_id,
                           clarification_reply=request.clarification_reply, **progress_args)
        result["conversation_id"] = request.conversation_id
        result["why"] = build_why(request.message, result)
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.") from exc
    finally:
        set_current_user(None)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> ChatResponse:
    return _execute_chat(request, user)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, user: CurrentUser = Depends(get_current_user)):
    # Authentication is resolved before the first event or tool invocation.
    if not llm_is_configured():
        raise HTTPException(status_code=503, detail="Chat is not configured.")

    async def events():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def progress(text):
            # Worker callbacks never touch asyncio objects from their thread.
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", {"message": text}))

        async def produce():
            try:
                response = await asyncio.to_thread(_execute_chat, request, user, progress=progress)
                await queue.put(("done", response.model_dump(mode="json")))
            except HTTPException as exc:
                await queue.put(("error", {"message": exc.detail}))
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
            # Let in-flight generation finish without automatically retrying
            # tools when the client disconnects. No history store is used.
            if not worker.done():
                worker.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    try:
        result = confirm_proposed_action(request.action, current_user=user)
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
    try:
        result = decline_proposed_action(request.action, current_user=user)
    except ConfirmError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return ConfirmActionResponse(ok=True, type=result.get("type"), declined=True, summary="Dismissed. Nothing was saved.")
