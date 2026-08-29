# Architecture — SweaterCo GM Co-Pilot (MVP)

This document is for teammates who are new to the stack. Read it before editing code.

## What we are building

A **tool-using agent**, not a chatbot and not a dashboard.

The manager asks a question in natural language. A small **inspectable pre-router**
(`backend/agent/routing.py`) first checks whether the requested field exists in
the Track 1 tables. If it does not (revenue, selling price, worker names, …) the
system answers with a limitation and **does not call a tool**.

In-scope questions go to the LangGraph ReAct agent. The LLM only selects a
registered tool and explains the tool result. Deterministic Python tools do all
arithmetic.

```
Manager (React UI)
        │
        ▼
 FastAPI  /api/chat
        │
        ▼
 Inspectable router  ── unsupported / action-not-implemented ──► answer, no tools
        │
        ▼
 LangGraph ReAct agent
        │
        ├── get_order_status      (retrieval)
        ├── get_orders_at_risk    (retrieval)
        ├── trace_order           (tracing)
        └── check_feasibility     (judgement)
                │
                ▼
         services/  (SQLite + calculations)
                │
                ▼
         data/*.csv
```

## Layers (do not mix them)

| Layer | Folder | Allowed to do | Must not do |
|---|---|---|---|
| UI | `frontend/` | Display answers, traces, later confirmations | Business rules, SQL, arithmetic |
| API | `backend/main.py` | HTTP, CORS, health | Judgement logic |
| Agent | `backend/agent/` | Choose tools, write the reply | Invent numbers or data |
| Tools | `backend/tools/` | Call services, return JSON + trace | Hide rules in the prompt |
| Services | `backend/services/` | SQL, date math, risk, feasibility | Call the LLM |
| Semantic | `data/semantic_layer.yaml` | `data_definition` (columns + descriptions) + `term_definition` (jargon) | Arithmetic, invented columns |
| Data | `data/` | Source CSVs | — |

## Dataset clock

Business logic uses **`FACTORY_TODAY = 2026-04-01`**, not the computer's date.
The factory is closed on Sundays.

## Why SQLite, not DuckDB

Three small clean tables. SQLite is in the Python standard library, and teammates
can open `data/factory.db` in any viewer. Rebuilt from CSV on every API startup.

## Agent

`langgraph.prebuilt.create_react_agent` with four tools and a `MemorySaver`
so one `conversation_id` keeps multi-turn context (e.g. "the first one").
The API reports **only the tools used after the latest user message**. A
feasibility answer must not list retrieval tools left over from earlier
questions in the same chat.

If `OPENAI_API_KEY` is missing, tools, the pre-router, and pytest still work;
`/api/chat` for in-scope questions returns 503. Unsupported questions are
answered without an API key because they never reach the LLM.

Any OpenAI-compatible endpoint works (`OPENAI_BASE_URL` + `LLM_MODEL`).

## Evaluation vs unit tests

| | `tests/` (pytest) | `evaluation/` |
|---|---|---|
| Purpose | Regression for tools, routing, API | Formal Track 1 case set |
| Needs API key | No | Only `--mode agent` |
| Current file | — | `questions.json` is a **development** set |

Do not present scores on `evaluation/questions.json` as a held-out official
accuracy number. The runner reports **data/tool accuracy** and **final-answer
quality** separately. See `evaluation/README.md`.

Side-effecting actions (email, notes, reminders) are not implemented. When they
are added they must follow: propose → confirm → execute → audit log.

## What is intentionally missing (MVP)

Placeholders only — do not implement until we agree the next slice:

- Morning briefing / `discover_factory_issues`
- Email, notes, reminders, audit log
- `assess_stage_performance`
- Confirmation UI for side-effecting actions

## Adding a new tool (later)

1. Put arithmetic in `backend/services/`.
2. Wrap it in `backend/tools/<category>.py` with `@tool`.
3. Return `{ok, tool, data, trace}` or `{ok: false, error}`.
4. Register it in `backend/tools/registry.py`.
5. Add a pytest that does not need an LLM.
6. Document the formula in `docs/tool_spec.md`.
