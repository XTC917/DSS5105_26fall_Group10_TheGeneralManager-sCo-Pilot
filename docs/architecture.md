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
 Inspectable router  ── unsupported ──► answer, no tools
        │
        ▼
 LangGraph ReAct agent
        │
        ├── get_order_status      (retrieval)
        ├── get_orders_at_risk    (retrieval)
        ├── get_morning_briefing  (structured briefing)
        ├── find_orders           (user-directed discovery)
        ├── discover_factory_issues (production_log issues)
        ├── get_today_priority     (1st/2nd/3rd order buckets)
        ├── trace_order           (tracing)
        ├── check_feasibility     (judgement)
        ├── draft_chase_email / send_email / add_order_note / create_reminder
        ├── create_watch / list_watches / cancel_watch
        └── get_recent_actions    (audit read)
                │
                ▼
 backend/services/database.py + calculations
                │
                ▼
 PostgreSQL (app, copilot, auth, admin_meta)
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
| Data | PostgreSQL + `data/` | Runtime records and app state in PostgreSQL; CSVs are seed/import sources | Treat CSVs or SQLite as the runtime store |

## Dataset clock

The demo starts at **2026-04-01**. Signed-in users can advance their saved factory
date one calendar day at a time from the sidebar. The watch board, briefing,
discovery, and chat calculations use that date. Advancing changes the date
used to evaluate existing records. The factory is still closed on Sundays
for working-day calculations.

## PostgreSQL runtime and migration history

An early local prototype used SQLite and rebuilt its tables from CSV files.
The final application no longer uses SQLite at runtime. Operational records,
authentication, conversation history, checkpoints, and action state are stored
in PostgreSQL. `backend/services/database.py` connects through psycopg, while
Alembic manages application-schema migrations. CSV files remain seed and
controlled-import sources rather than the live runtime store.

## Agent

`langgraph.prebuilt.create_react_agent` uses the registered tools, while
PostgreSQL-backed conversation history and checkpoints allow one
`conversation_id` to keep multi-turn context (e.g. "the first one").
The API reports **only the tools used after the latest user message**. A
feasibility answer must not list retrieval tools left over from earlier
questions in the same chat.

If `OPENAI_API_KEY` is missing, tools, the pre-router, and pytest still work;
`/api/chat` for in-scope questions returns 503. Unsupported questions are
answered without an API key because they never reach the LLM.

Any OpenAI-compatible endpoint works (`OPENAI_BASE_URL` + `LLM_MODEL`).

`evaluation/questions.json` is the few-shot answer-template bank (not an eval runner).

Side-effecting actions follow: propose → UI Confirm click → controlled execute → audit log.
The agent only proposes (`confirmed=false`). `POST /api/actions/confirm` runs the
whitelisted tool with `confirmed=true` and does **not** call the LLM. Dismiss
(`POST /api/actions/decline`) records the decision without applying the proposed
side effect. Email remains simulated by default; the separate delivery path can
send through Resend only when delivery is explicitly enabled and configured.
Notes, reminders, standing watches, and audit records persist in PostgreSQL.

**Reminders vs standing watches:** `create_reminder` stores a calendar note
(`remind_on` + free-text message). Python does **not** evaluate that message.
`create_watch` stores a typed condition (`ORDER_INACTIVE_BY_DATE`). Python
evaluates it on the signed-in account's saved factory date when the sidebar
refreshes through `GET /api/watches`. `cancel_watch` sets `status=CANCELLED` after
confirmation — the row is **not deleted**, so `list_watches` can still answer
"was there a watch?". ACTIVE stops evaluating; FIRED leaves the live alerts
list and appears under cancelled history. A
`WatchNotifier` protocol delivers alerts after the watch is already `FIRED`;
V1 only has `LocalWatchNotifier`. Email would plug in later without changing
the condition.

**Ranked vs filtered discovery:** `find_orders` only applies the manager's
filters. `discover_factory_issues` walks production_log stage-below-baseline
rules and returns Top N plus the `production` snapshot. `get_today_priority`
returns the 1st/2nd/3rd order buckets. Both are read-only and not general
anomaly detectors. `GET /api/discovery?limit=5` exposes the same service as
`discover_factory_issues`.

## What is intentionally missing

- `assess_stage_performance` (beyond the briefing/discovery last-day vs median check)
- External calendar and push integrations
- A background scheduler (watches evaluate when `/api/watches` is called)
- Email delivery is optional and disabled by default unless Resend is configured

## Adding a new tool (later)

1. Put arithmetic in `backend/services/`.
2. Wrap it in `backend/tools/<category>.py` with `@tool`.
3. Return `{ok, tool, data, trace}` or `{ok: false, error}`.
4. Register it in `backend/tools/registry.py`.
5. Add a pytest that does not need an LLM.
6. Document the formula in `docs/tool_spec.md`.
