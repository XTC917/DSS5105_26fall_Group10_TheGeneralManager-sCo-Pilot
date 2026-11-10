# SweaterCo GM Co-Pilot (DSS5105 Track 1)

AI co-pilot for the general manager of a small knitwear factory. The core is a
**tool-using LangGraph agent**, not a generic chatbot.

This repository is a **working first co-pilot**: inspectable Python tools, a
chat API, a laptop manager UI, and a development evaluation set. Factory date
in the dataset: **2026-04-01**. Do not use the computer clock for business logic.

The repository also contains a local PostgreSQL database and an experimental
PostgreSQL version of the standalone data-administration service. The data
administration UI is now present in the main application, but its main-system
data services still use SQLite until the PostgreSQL integration is completed.

Track 1 asks for five kinds of tool (retrieval / judgement / tracing /
discovery / action), a scheduled briefing, all-day Q&A, standing watches,
feasibility estimates, confirmed actions, and full traceability. What is
shipped vs still open is listed below.

## What works now

### Data and API

- Load `orders.csv`, `production_log.csv`, `workshops.csv` into SQLite
- Reproduce and validate the local PostgreSQL design under `postgresql_database/`
- Run the experimental PostgreSQL administration API under `SQL_related_app/`
- `POST /api/chat` — inspectable pre-router, then LangGraph ReAct for in-scope questions
- Authenticated multi-turn chat with **fresh tool calls each turn**, PostgreSQL
  conversation history, and PostgreSQL LangGraph checkpoints
- Unsupported questions (revenue, selling price, workers, …) return a limitation with **no tool call**
- Lightweight audit in `data/copilot_state.db` (survives CSV reload of `factory.db`)
- Field meanings for the agent come from `data/semantic_layer.yaml`

### Tools (mapped to the five course kinds)

| Kind | Tool | What it does |
|---|---|---|
| Retrieval | `get_order_status` | One order; asks for an id if several match (e.g. “the TrendCart order”) |
| Retrieval | `get_orders_at_risk` | Miss-due list from max(pieces / 30-day stage median, remaining stages). Overdue and stalled are separate flags |
| Judgement | `check_feasibility` | Capacity estimate for a new order, with stated assumptions |
| Tracing | `trace_order` | Source `orders.csv` row + computed fields + risk flags |
| Discovery (filter) | `find_orders` | List **all** matches by customer / product / stage / status. Does not rank “unusual” issues |
| Discovery (ranked) | `discover_factory_issues` | Top-N production_log stage issues + production snapshot. Python sorts |
| Priority | `get_today_priority` | Today's 1st/2nd/3rd order buckets + `days_left`. Python grouping |
| Briefing | `get_morning_briefing` | Structured ops facts (reuses at-risk rules, last-day output vs 30-day median, suspended workshops) |
| Action | `draft_chase_email` | Local draft from order fields. Never sent |
| Action | `send_email` | Proposal → confirm → **simulated** audit row. Still `sent: false` (no SMTP) |
| Action | `add_order_note` / `create_reminder` | Proposal → confirm → persist locally. Reminder is a calendar note; it does **not** auto-fire |
| Action | `create_watch` / `list_watches` / `cancel_watch` | Standing watch. Python evaluates on `GET /api/watches?as_of=`. Cancel requires confirmation |
| Audit | `get_recent_actions` | Read recent rows from `copilot_state.db` |

`production_log.csv` is factory-wide (`date × stage`), not per order. It is used
inside briefing and feasibility, not as a separate lookup tool.

### Interface

- React UI: chat + sidebar snapshot of briefing / **top issues** / **triggered alerts** / **active watches** / recent actions
- Answer + **“Why?”** traces (source rows and calculations; fired watches expand snapshot evidence)
- Confirmation is a **UI click** (Confirm / Dismiss on the proposal). Chat “yes” still works as a fallback.

### Standing watches (V1)

Active watches are evaluated whenever `GET /api/watches` is called, using the
supplied factory `as_of` date (default **2026-04-01**). This is **not**
real-time monitoring and **not** a scheduler.

- Condition: `ORDER_INACTIVE_BY_DATE` — still `IN_PROGRESS` and `last_activity_date` before `check_date`
- “Hasn't moved” uses `orders.last_activity_date` only. `production_log` is not per-order.
- Thursday from factory Wednesday 2026-04-01 is **2026-04-02** (Python, not the LLM)
- On fire: `watch_events` + `audit_log` + sidebar **Triggered alerts**. Same watch never fires twice
- Cancel: `cancel_watch` after confirmation. The row is **kept** as `CANCELLED` (not deleted). ACTIVE will not evaluate; FIRED leaves the live alert list and stays in watch history
- `WatchNotifier` is the future email hook. V1 is `LocalWatchNotifier` only (no SMTP)
- `create_reminder` is unchanged: a local calendar note, not a watch

`evaluation/questions.json` is a few-shot wording bank for the agent, not a scoring harness.


## Repository layout

```
backend/          FastAPI + LangGraph + tools + services
frontend/         React + Vite + Tailwind
data/             Track 1 CSVs + semantic_layer.yaml + examples3.0 as-of snapshots
docs/             architecture.md, tool_spec.md
evaluation/       Track 1 development evaluation set (not a held-out official score)
tests/            pytest — no LLM key required
postgresql_database/  PostgreSQL schema, seed data, validation, and permission tests
SQL_related_app/      Standalone data-administration app and PostgreSQL experiment
```

Read `docs/architecture.md` and `docs/tool_spec.md` before changing rules.
`tool_spec.md` documents behaviour and limits; the course still wants a single
table of name / input / output / purpose / non-goals / failure mode for the
final evaluation report.

## Semantic layer

Field meanings for the agent live in `data/semantic_layer.yaml` (also loaded into the system prompt):

- `data_definition` — every stored table/column, including descriptions
- `term_definition` — special vocabulary that is **not** a stored column (e.g. factory today, selling price, OVERDUE)

Do not put formulas in that file. Arithmetic stays in `backend/services/`. After editing the YAML, restart the backend.

## Prerequisites

- Python 3.10+
- Node.js 18+
- An OpenAI-compatible API key **only if you want the chat agent**
  (pytest and data loading work without a key)

## Backend

From the project root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set OPENAI_API_KEY (and optionally OPENAI_BASE_URL, LLM_MODEL)
# Set the PostgreSQL application/admin credentials, then apply schema migrations.
# For Alembic, temporarily set PGUSER/PGPASSWORD to the factory_admin credentials.
alembic -c alembic.ini upgrade head

uvicorn backend.main:app --reload --port 8000
```

FastAPI startup opens the checkpoint connection pool and verifies the migrated
checkpoint version. It does not create tables or run migrations.

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to port 8000.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

These tests check schemas, date arithmetic, risk flags, routing, and tool JSON. They do not call an LLM.

Division of labour:

- **Tools / Python** compute every number (status, risk flags, feasibility, briefing).
- **LLM** only selects an in-scope tool and explains the result.
- **Unsupported questions** must not fire unrelated tools.
- **Actions** propose first; persist locally only after confirmation. Email is never actually sent.

## Try these questions (after the API key is set)

- How is ORD-120 doing?
- How is the TrendCart order doing?  ← should ask which order
- Which orders are at risk?
- Why is ORD-120 considered risky?
- Can we take 800 hoodies by August 25?
- Give me this morning's briefing
- What should I be concerned about right now?  ← ranked discovery (not find_orders)
- List the TrendCart orders
- Draft a chase-up email for ORD-120
- Create a reminder to check ORD-005 tomorrow  ← local calendar note; does not auto-fire
- Tell me if ORD-005 hasn't moved by Thursday  ← standing watch; confirm, then `GET /api/watches?as_of=2026-04-02`
- Cancel the watch on ORD-005  ← confirm; ACTIVE stops evaluating, FIRED leaves the alert list
- What is the revenue from TrendCart?  ← should refuse (no price data)

## Next (remaining product work)

Suggested order so the core Track 1 bar is covered before polish:

1. Scheduled or “open the app → today’s briefing” prose, not only JSON in the sidebar
2. Optional: `EmailWatchNotifier` behind the existing `WatchNotifier` protocol (condition logic stays in Python)
3. Held-out evaluation file + failure-case notes for `Evaluation.pdf`

## Rules for teammates

1. Do not invent columns or business facts that are not in `data/` + `data/semantic_layer.yaml` (and the short table overview in `data/data_dictionary.md`).
2. Do not put totals, day counts, or capacity math in the prompt — add a Python function.
3. If a design is not supported by the files, leave a `# TODO` instead of guessing.
4. Side-effecting actions must never run without an explicit confirmation, and must never claim an external email was sent.

## Logging

API logs go to the console and `logs/app.log`. Query/tool/action traces also go
to `data/copilot_state.db` (gitignored; survives CSV reload of `factory.db`).

## Phase 5D — mobile, Weekly state, Alert Finish, email delivery

This round fixed real-use issues on top of `main` (`0f0634a`) without changing
the Soft Intelligence UI, the seven themes, the agent prompt/routing/tools, or
the deployed environment.

### iPhone Safari (P0)

Root causes and fixes:

- **Input auto-zoom.** iOS Safari zooms any focused `input` / `textarea` /
  `select` whose computed font-size is below 16px. The composer, search, login,
  email and clarification fields were 12–14px. `src/index.css` now sets form
  controls to 16px on screens `< 768px` (mobile only; desktop type is unchanged).
- **Keyboard / address bar height.** The shell used `h-dvh`, which iOS does not
  reliably shrink when the keyboard opens. `src/main.jsx` syncs `--app-height`
  to `visualViewport.height`; the `Home` shell uses
  `height: var(--app-height, 100dvh)`, so the composer and bottom nav stay above
  the keyboard.
- **Horizontal overflow / safe area.** `html, body` are `overflow-x: hidden`
  with `max-width: 100%`; the viewport now uses `viewport-fit=cover` so
  `env(safe-area-inset-bottom)` works on notched iPhones. The bottom nav already
  pads with the safe-area inset. User zoom is **not** disabled (no
  `maximum-scale` / `user-scalable=no`).
- **Modals** cap at `92dvh`, scroll internally, and respect the bottom safe area.

Manual check sizes: 375 / 390 / 393 / 430 px. Real iPhone Safari / WebKit
verification is still a manual step (not run automatically here).

### Weekly briefing keeps its tab (P1)

`Morning` / `Weekly` is now owned by `Home` (`briefingPanel`) and persisted to
`sessionStorage` (`sweaterco:briefing-panel`). Switching Overview → Ask AI →
Overview (or refreshing data) keeps the choice for the browser session. Default
is still Morning. `Sidebar` and `MorningBriefingModal` accept an optional
controlled `panel` / `onPanelChange`, so the fullscreen briefing tabs stay in
sync too.

Weekly backend range (read-only review): `previous_working_week()` returns the
Monday–Saturday before the week containing the factory date. **Edge case:** if
the factory date is a Sunday, it returns the *prior* week, skipping the
Monday–Saturday that just finished; the week chart includes that just-finished
week. This is reported, not changed, per the no-backend-rules rule.

### Alert Finish (P0)

Frontend: `POST /api/watches/{id}/finish`. Backend: the same route exists in
`backend/main.py` and returns status `DONE` for a `FIRED` watch. The **deployed
Render** `/openapi.json` does not list the route (only `/api/watches`), so the
live 404 is a **stale backend release**, not a contract mismatch. Redeploy the
backend from current `main` (`0f0634a`; the route entered in `0d5da2f`). The
frontend now explains a 404 as “not available on the deployed API yet”. Finish
is never faked through Cancel.

### Email delivery (P1)

- Draft / edit endpoints are registered on Render; the send endpoint exists at
  `POST /api/email/drafts/{draft_id}/send`.
- Delivery is gated by `_delivery_config()`: enabled only when
  `EMAIL_DELIVERY_ENABLED=true` **and** `EMAIL_FROM` **and** `RESEND_API_KEY` are
  set. The UI only shows “Confirm and send” when `can_send` is true.
- The documented production setting `EMAIL_DELIVERY_ENABLED=false` makes the
  send endpoint return `503 Email delivery is not configured.` — the most likely
  reason real mail cannot be sent today.
- `render.yaml` does not declare email variables; add them manually and redeploy.
- **Safety:** `EMAIL_TEST_RECIPIENT` is read but no longer enforced; when enabled
  the app emails the single valid address entered on the draft. See
  `docs/email_delivery.md`.

Never enable delivery, send real mail, or finish/cancel a production watch as
part of verification without explicit human approval.
