# SweaterCo GM Co-Pilot (DSS5105 Track 1)

AI co-pilot for the general manager of a small knitwear factory. The core is a
**tool-using LangGraph agent**, not a generic chatbot.

This repository is a **working first co-pilot**: inspectable Python tools, a
chat API, a laptop manager UI, and a development evaluation set. Factory date
in the dataset: **2026-04-01**. Do not use the computer clock for business logic.

Track 1 asks for five kinds of tool (retrieval / judgement / tracing /
discovery / action), a scheduled briefing, all-day Q&A, standing watches,
feasibility estimates, confirmed actions, and full traceability. What is
shipped vs still open is listed below.

## What works now

### Data and API

- Load `orders.csv`, `production_log.csv`, `workshops.csv` into SQLite
- `POST /api/chat` — inspectable pre-router, then LangGraph ReAct for in-scope questions
- Multi-turn chat with **fresh tool calls each turn** (`conversation_id` + MemorySaver)
- Unsupported questions (revenue, selling price, workers, …) return a limitation with **no tool call**
- Lightweight audit in `data/copilot_state.db` (survives CSV reload of `factory.db`)

### Tools (mapped to the five course kinds)

| Kind | Tool | What it does |
|---|---|---|
| Retrieval | `get_order_status` | One order; asks for an id if several match (e.g. “the TrendCart order”) |
| Retrieval | `get_orders_at_risk` | Overdue / stalled / tight-deadline. Formulas in Python |
| Judgement | `check_feasibility` | Capacity estimate for a new order, with stated assumptions |
| Tracing | `trace_order` | Source `orders.csv` row + computed fields + risk flags |
| Discovery (filter) | `find_orders` | List **all** matches by customer / product / stage / status. Does not rank “unusual” issues |
| Discovery (ranked) | `discover_factory_issues` | Top-N issues from defined order-risk + stage-below-baseline rules. Python sorts |
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

### Evaluation (development set)

`evaluation/questions.json` has **43** questions (course minimum 30):

- **11** ambiguous / unanswerable / hallucination-bait (minimum 5)
- **7** feasibility or action requests (minimum 5)

Gold answers are recomputed from the CSVs and Python services. This file is a
**development** set. Do not present scores on it as a held-out official result.

## What is not built yet (course gaps first)

These are Track 1 core capabilities that are still missing or only half-done:

- **Scheduled briefing** — current briefing is on-demand (ask in chat, or the sidebar loads `/api/briefing`). Nothing generates it on a clock. Prose appears only when the agent writes it.
- **Watch types beyond `ORDER_INACTIVE_BY_DATE`** — no stage-still-in, overdue-as-of, or factory-wide packing-behind watches yet. No scheduler; evaluate by calling the API with `as_of`.
- **`assess_stage_performance`** — full inspectable “is this stage output normal?” tool. Discovery/briefing only reuse the 0.70 × 30-day-median drop heuristic.
- **Held-out evaluation file** — add a separate JSON (`meta.usage = "held-out"`) before claiming official accuracy.
- **Course write-ups** — `Evaluation.pdf` (including ≥10 analysed failure cases), Sprint decks, `GroupX.zip`. Not product code.

Out of scope for this track (not a course requirement): real SMTP / calendar /
push, voice in/out, a YAML business ontology.

## Repository layout

```
backend/          FastAPI + LangGraph + tools + services
frontend/         React + Vite + Tailwind
data/             Track 1 CSVs (source of truth)
docs/             architecture.md, tool_spec.md
evaluation/       Track 1 development evaluation set (not a held-out official score)
tests/            pytest — no LLM key required
```

Read `docs/architecture.md` and `docs/tool_spec.md` before changing rules.
`tool_spec.md` documents behaviour and limits; the course still wants a single
table of name / input / output / purpose / non-goals / failure mode for the
final evaluation report.

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

uvicorn backend.main:app --reload --port 8000
```

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

## Evaluation

```powershell
python -m evaluation.run_evaluation --validate
python -m evaluation.run_evaluation --mode tools
```

`--mode tools` does not need an API key. `--mode agent` does.

Scores are two dimensions: **data/tool accuracy** and **final-answer quality**.
See `evaluation/README.md`. Pass a later held-out file with `--dataset`.

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

1. Do not invent columns or business facts that are not in `data/` + `data/data_dictionary.md`.
2. Do not put totals, day counts, or capacity math in the prompt — add a Python function.
3. If a design is not supported by the files, leave a `# TODO` instead of guessing.
4. Side-effecting actions must never run without an explicit confirmation, and must never claim an external email was sent.

## Logging

API logs go to the console and `logs/app.log`. Query/tool/action traces also go
to `data/copilot_state.db` (gitignored; survives CSV reload of `factory.db`).
