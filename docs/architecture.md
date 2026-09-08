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
        ├── discover_factory_issues (ranked discovery)
        ├── trace_order           (tracing)
        ├── check_feasibility     (judgement)
        ├── draft_chase_email / send_email / add_order_note / create_reminder
        ├── create_watch / list_watches / cancel_watch
        └── get_recent_actions    (audit read)
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
| Data | `data/` | Source CSVs | — |

## Dataset clock

Business logic uses **`FACTORY_TODAY = 2026-04-01`**, not the computer's date.
The factory is closed on Sundays.

## Why SQLite, not DuckDB

Three small clean tables. SQLite is in the Python standard library, and teammates
can open `data/factory.db` in any viewer. Rebuilt from CSV on every API startup.

## Agent

`langgraph.prebuilt.create_react_agent` with the registered tools and a `MemorySaver`
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

Side-effecting actions follow: propose → UI Confirm click → local execute → audit log.
The agent only proposes (`confirmed=false`). `POST /api/actions/confirm` runs the
whitelisted tool with `confirmed=true` and does **not** call the LLM. Dismiss
(`POST /api/actions/decline`) writes an audit row and saves nothing. Chat “yes”
still works as a fallback. There is no SMTP. Confirmed "send email" writes a
**simulated** audit row and still reports `sent: false`. Notes, reminders, and
standing watches persist in `copilot_state.db`, which is separate from
`factory.db` so CSV reload does not wipe them.

**Reminders vs standing watches:** `create_reminder` stores a calendar note
(`remind_on` + free-text message). Python does **not** evaluate that message.
`create_watch` stores a typed condition (`ORDER_INACTIVE_BY_DATE`). Python
evaluates it when `GET /api/watches?as_of=YYYY-MM-DD` runs. There is no
scheduler and no `date.today()` — callers pass a factory `as_of` date
(default `FACTORY_TODAY`). `cancel_watch` sets `status=CANCELLED` after
confirmation — the row is **not deleted**, so `list_watches` can still answer
"was there a watch?". ACTIVE stops evaluating; FIRED leaves the live alerts
list and appears under cancelled history. A
`WatchNotifier` protocol delivers alerts after the watch is already `FIRED`;
V1 only has `LocalWatchNotifier`. Email would plug in later without changing
the condition.

**Ranked vs filtered discovery:** `find_orders` only applies the manager's
filters. `discover_factory_issues` walks defined Python rules (order risk +
stage-below-baseline), assigns priority, and returns Top N. It is read-only
and is not a general anomaly detector. `GET /api/discovery?limit=5` exposes
the same service as the tool.

## What is intentionally missing

- `assess_stage_performance` (beyond the briefing/discovery last-day vs median check)
- Real email / calendar / push integrations (watches fire as local alerts)
- A background scheduler (watches evaluate when `/api/watches` is called)
- Semantic layer / YAML ontology

## Adding a new tool (later)

1. Put arithmetic in `backend/services/`.
2. Wrap it in `backend/tools/<category>.py` with `@tool`.
3. Return `{ok, tool, data, trace}` or `{ok: false, error}`.
4. Register it in `backend/tools/registry.py`.
5. Add a pytest that does not need an LLM.
6. Document the formula in `docs/tool_spec.md`.
