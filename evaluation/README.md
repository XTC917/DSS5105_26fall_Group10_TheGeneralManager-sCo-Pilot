# Track 1 evaluation

This folder is the start of the **formal course evaluation set**. It is not a
replacement for `pytest`.

`questions.json` is a **development set**. It is used while we build routing,
tools, and the runner. Do **not** later present scores on this file as an
unbiased held-out evaluation. Point `--dataset` at a separate JSON file when
you have a held-out set (`meta.usage` = `"held-out"`).

Factory today remains **2026-04-01** (from `data/data_dictionary.md`).

## Two score dimensions

Do not collapse these into one official number.

### 1. Data / Tool Accuracy

Did the system use the right tool (or no tool), with the right parameters, and
did the Python tool return the gold facts?

`--mode tools` runs this against CSVs + `backend.services` and does **not**
need an LLM key (except that unsupported questions go through the pre-router).

Checks include:

- correct tool result (order row, risk set, feasibility verdict, trace)
- no unrelated tools on unsupported questions
- tool selection when `--mode agent` is used

### 2. Final Answer / Summary Quality

Did the natural-language reply actually say the facts the tool returned?

This catches: wrong counts (“8 orders at risk” when the tool found 10),
dropped flags, omitted order ids, invented revenue numbers, missing “this is a
heuristic” on feasibility.

Matching is deterministic (not LLM-as-judge):

- `must_contain` — facts, case-insensitive, `1,500` = `1500`
- `must_indicate` — synonym groups (`overdue`, `clarification`, `limitation`, …)
- `must_not_contain` — forbidden claims
- `must_include_ids` — every listed `ORD-…` must appear

Criteria are taken from optional `answer_criteria` on the question, or derived
from the existing `expected_result` so `questions.json` did not have to be
rewritten.

### 3. Development vs held-out

| File | `meta.usage` | What scores mean |
|---|---|---|
| `evaluation/questions.json` | `development` | Used while building. **Not** unbiased. |
| a future file, e.g. `evaluation/held_out.json` | `held-out` | Use this for the course write-up |

Same schema. Switch with `--dataset path`.

## Layout

| File | Role |
|---|---|
| `questions.json` | Development cases (unchanged gold questions) |
| `schema.py` | Required fields, optional `answer_criteria` keys |
| `verify.py` | Data/tool gold checks |
| `answer_quality.py` | Final-answer checks |
| `scoring.py` | Separate dimension totals |
| `run_evaluation.py` | CLI |

## Commands

```powershell
python -m evaluation.run_evaluation --validate
python -m evaluation.run_evaluation --mode tools
python -m evaluation.run_evaluation --mode agent --ids Q001,Q002,Q003,Q004,Q005
python -m evaluation.run_evaluation --dataset evaluation/held_out.json --mode tools
```

`--mode tools` is what CI / teammates should run without an API key.

Example tools-mode excerpt:

```
Deterministic tool checks: 32/32 passed

=== Evaluation scores (separate dimensions) ===
Set usage: development  — not an unbiased held-out official score.

1. Data / Tool Accuracy
   Factual tool result:     32/32 (100.0%)
   Tool selection:          10/10 (100.0%)
   Unsupported / no-tool:   10/10 (100.0%)

2. Final Answer / Summary Quality
   Answer pass:             10/10 (100.0%)
   ...
```

In tools mode, final-answer scoring applies to **router/canned** replies
(unsupported, hallucination bait, actions). Lookup/feasibility wording is
scored in `--mode agent`.

## Categories

`normal_lookup`, `risk_retrieval`, `judgement`, `traceability`, `ambiguous`,
`unanswerable`, `hallucination_bait`, `feasibility`, `action`.

Course minimums (development file only):

- at least 30 questions
- at least 5 ambiguous / unanswerable / hallucination-bait
- at least 5 feasibility / action

## Ground truth

Tool gold is recomputed from the CSVs and Python services. The LLM is never
asked to invent expected numbers. We do not tune the product just to raise
the score on this file.
