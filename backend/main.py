"""FastAPI entry point.

Run from the project root:

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agent.graph import llm_is_configured, run_agent
from backend.logging_setup import setup_logging
from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.database import init_db
from backend.tools.registry import MVP_TOOLS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_db()
    logger.info("SweaterCo co-pilot API ready. LLM configured=%s", llm_is_configured())
    yield


app = FastAPI(
    title="SweaterCo GM Co-Pilot",
    version="0.1.0",
    description="Track 1 MVP: grounded factory Q&A via inspectable tools.",
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


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "factory_today": "2026-04-01",
        "llm_configured": llm_is_configured(),
        "tools": [t.name for t in MVP_TOOLS],
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not llm_is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "OPENAI_API_KEY is not set. Tools still work (run pytest). "
                "Copy .env.example to .env to enable the agent."
            ),
        )
    try:
        result = run_agent(request.message, request.conversation_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(**result)
