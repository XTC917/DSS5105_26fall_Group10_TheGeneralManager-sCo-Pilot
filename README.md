# SweaterCo GM Co-Pilot (DSS5105 Track 1)

AI co-pilot for the general manager of a small knitwear factory. The core is a **tool-using LangGraph agent**, not a generic chatbot.

This repository is the **first MVP**: data layer, four tools, a chat API, and a minimal React UI.

Factory date in the dataset: **2026-04-01**. Do not use the computer clock for business logic.

## What works now

- Load `orders.csv`, `production_log.csv`, `workshops.csv` into SQLite
- `get_order_status` — look up one order; ask for an id if several match
- `get_orders_at_risk` — overdue / stalled / tight-deadline (formulas in Python)
- `trace_order` — source row + calculations
- `check_feasibility` — inspectable capacity estimate for a new order
- `POST /api/chat` — pre-router, then LangGraph agent for in-scope questions
- Unsupported questions (revenue, workers, …) return a limitation with **no tool call**
- Minimal manager UI with answer + “Why?” traces
- `evaluation/` — development evaluation set + deterministic runner

## What is not built yet

Morning briefing, discovery engine, emails / notes / reminders, audit log, `assess_stage_performance`, and the full home-screen layout. Placeholder files exist so we can add them later without reshaping the project.

## Repository layout

```
backend/          FastAPI + LangGraph + tools + services
frontend/         React + Vite + Tailwind
data/             Track 1 CSVs + semantic_layer.yaml
docs/             architecture.md, tool_spec.md
evaluation/       Track 1 development evaluation set (not a held-out official score)
tests/            pytest — no LLM key required
```

Read `docs/architecture.md` and `docs/tool_spec.md` before changing rules.

## Semantic layer

Field meanings for the agent live in `data/semantic_layer.yaml` (also loaded into the system prompt):

- `data_definition` — every stored table/column, including descriptions
- `term_definition` — special vocabulary that is **not** a CSV column (e.g. factory today, selling price, OVERDUE)

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

`evaluation/questions.json` is used during development. Do not treat scores on
this file as an unbiased held-out evaluation. Scores are reported as two
dimensions: **data/tool accuracy** and **final-answer quality**. See
`evaluation/README.md`. A later held-out file can be passed with `--dataset`.

Division of labour:

- **Tools / Python** compute every number (status, risk flags, feasibility).
- **LLM** only selects an in-scope tool and explains the result.
- **Unsupported questions** must not fire unrelated tools.
- **Actions** (later) will require confirmation and an audit log.

## Try these questions (after the API key is set)

- How is ORD-120 doing?
- How is the TrendCart order doing?  ← should ask which order
- Which orders are at risk?
- Why is ORD-120 considered risky?
- Can we take 800 hoodies by August 25?
- What is the revenue from TrendCart?  ← should refuse (no price data)

## Rules for teammates

1. Do not invent columns or business facts that are not in `data/` + `data/semantic_layer.yaml` (and the short CSV overview in `data/data_dictionary.md`).
2. Do not put totals, day counts, or capacity math in the prompt — add a Python function.
3. If a design is not supported by the files, leave a `# TODO` instead of guessing.
4. Side-effecting actions (later) must never run without an explicit confirmation.

## Logging

API logs go to the console and `logs/app.log`.
