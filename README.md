# SweaterCo GM Co-Pilot (DSS5105 Track 1)

## Introduction

<!-- Write the project introduction here. -->



---

## Start here (new users)

This repo is an **AI co-pilot for a knitwear factory general manager**.  
It is **not** a generic chatbot: the model calls **inspectable Python business tools**, and those tools own the numbers.

**Factory date in the dataset: `2026-04-01`.**  
Business logic uses that date, not your laptop clock.

### One-minute mental model

```text
Manager question (UI)
        │
        ▼
FastAPI  /api/chat
        │
        ▼
LangGraph agent  ──selects tool──►  Python tools (orders, risk, feasibility, …)
        │                                      │
        ▼                                      ▼
Natural-language answer  ◄──────── tool JSON + Why traces
```

| Layer | Responsibility |
| --- | --- |
| **Python tools / services** | Status, risk flags, medians, feasibility, briefing, watches |
| **LLM** | Pick an in-scope tool and explain the tool result |
| **UI** | Chat, Overview, Confirm/Dismiss for side effects, Why panel |

If the data cannot support a question (e.g. revenue / selling price), the system should **refuse** instead of guessing.

---

## What you get in this repo

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI app, LangGraph agent, tools, services |
| `frontend/` | React + Vite manager UI |
| `data/` | Source CSVs, `semantic_layer.yaml`, as-of snapshots |
| `docs/` | Architecture, tool behaviour, deploy, email |
| `evaluation/` | Question bank, annotation packs, scoring SOP, 3-condition runner |
| `tests/` | pytest (no LLM key required) |
| `postgresql_database/` | Postgres schema / seed / validation notes |
| `SQL_related_app/` | Standalone data-admin experiment |
| `deploy/` | Cloud env example |
| `Dockerfile`, `render.yaml` | Backend deploy (Render) |
| `frontend/vercel.json` | Frontend deploy (Vercel) |

Deployed shape: **frontend on Vercel**, **API on Render (Docker)**, **email via Resend** (optional; off by default).

---

## Prerequisites

- Python **3.10+**
- Node.js **18+**
- Local **PostgreSQL** (chat history / auth / checkpoints)
- An OpenAI-compatible API key **only if you want the chat agent**  
  (`pytest` and data loading work without a key)

---

## Run locally

### 1. Backend

From the repo root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

- `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`, `LLM_MODEL`)
- Postgres roles/passwords (`PGUSER` / `PGPASSWORD`, admin pair for migrations)
- `AUTH_SECRET_KEY` (≥ 32 chars) and `ADMIN_REGISTRATION_CODE`

Apply migrations, then start the API:

```powershell
alembic -c alembic.ini upgrade head
uvicorn backend.main:app --reload --port 8000
```

Health check: http://127.0.0.1:8000/api/health

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  
Vite proxies `/api` to port `8000`.

### 3. Tests

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

These tests cover schemas, dates, risk flags, routing, and tool JSON. They do **not** call an LLM.

---

## How the product works (short)

### Data

- Source of truth for factory facts: `data/orders.csv`, `production_log.csv`, `workshops.csv`
- Field meanings for the agent: `data/semantic_layer.yaml`
- `production_log` is factory-wide (`date × stage`), **not** per order

### Tools (course kinds)

| Kind | Examples |
| --- | --- |
| Retrieval | `get_order_status`, `get_orders_at_risk`, `find_orders` |
| Judgement | `check_feasibility` |
| Tracing | `trace_order` |
| Discovery | `discover_factory_issues`, `get_today_priority`, `get_morning_briefing` |
| Action | notes, reminders, watches, email draft / simulated send |

Side-effecting actions **propose first**; they persist only after **Confirm** in the UI.  
Default email path is local / simulated unless Resend delivery is explicitly enabled — see `docs/email_delivery.md`.

### Try these after the API key works

- How is ORD-120 doing?
- Which orders are at risk?
- Can we take 800 hoodies by August 25?
- Give me this morning's briefing
- Draft a chase-up email for ORD-120
- What is the revenue from TrendCart? ← should refuse

---

## Evaluation (dev harness)

- `evaluation/questions.json` — few-shot bank + development question set
- `evaluation/run_conditions.py` — three conditions: baseline / exclude_exact / full
- `evaluation/人工评分SOP.md` — how humans grade summary answers
- Annotation packs: `evaluation/annotation_sets.json`

This is a **development** harness, not a held-out official score.

Env switches used by the harness (unset = live product behaviour):

- `EVAL_SEMANTIC_LAYER`
- `EVAL_RESPONSE_TEMPLATES`
- `EVAL_FEW_SHOT` (`full` | `exclude_exact` | `off`)
- `EVAL_CAPTURE_TOOL_ARGS=1` — attach tool args for scoring

---

## Where to read next

1. `docs/architecture.md` — request path and system shape  
2. `docs/tool_spec.md` — tool behaviour and limits  
3. `Factory_Primer.md` — factory domain background  
4. `docs/phase4a_deployment_plan.md` / `docs/email_delivery.md` — deploy & mail  
5. `postgresql_database/README.md` — local Postgres setup

---

## Rules for contributors

1. Do not invent columns or business facts that are not in `data/` + `semantic_layer.yaml`.
2. Do not put totals / day counts / capacity math in the prompt — put them in Python.
3. If the files do not support a design, leave a `# TODO` instead of guessing.
4. Side-effecting actions need explicit confirmation; never claim an external email was sent unless delivery is really enabled.
