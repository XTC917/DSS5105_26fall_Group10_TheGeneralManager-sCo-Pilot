---
name: summary-evaluation
description: Score a SweaterCo manager answer on the L0–L3 ladder and the A+/A/A-/B+/C summary grades. Use when judging summary accuracy for the baseline, exclude-exact, or full few-shot evaluation. The tool-data comparison is already done in code; this skill scores only the written answer.
---

# Summary evaluation

Score one written answer. Do not call tools. Do not rewrite the answer. Return one JSON object and nothing else.

## Ladder

Use these definitions in this order. Do not paraphrase them when you explain a score.

L1 — Basic Correctness：核心事实和结论正确，没有关键性错误。
L2 — Analytical Completeness：满足 L1，并提供必要的数据依据、风险解释或业务逻辑。
L3 — Decision-Ready Answer：满足 L1、L2，同时提供符合问题目的的深入判断、关联分析或可执行建议。
只有满足 L1 才能获得 L2，只有满足 L1 和 L2 才能获得 L3。如果连 L1 都未达到，则判为 L0 — Fail。

## Slide grades

Summary Accuracy = (A+ + A) / Total Evaluation Cases

| Grade | Definition | Counted |
| --- | --- | --- |
| A+ | Fully accurate | Yes |
| A | Semantically accurate | Yes |
| A- | Basic correctness only | No |
| B+ | Invalid / unavailable | No |
| C | Factually inaccurate | No |

Map the ladder onto those grades:

- L3 → A+. Counted yes. Fully accurate and decision-ready.
- L2 → A. Counted yes. Semantically accurate, with the data, risk, or business logic the question needs, but without the deeper judgement or action L3 requires.
- L1 only → A-. Counted no. Core facts are right, and the answer is not factually inaccurate, but it does not meet Analytical Completeness.
- L0 because the reply is empty, the unfinished-answer sentence, or otherwise unavailable → B+. Counted no.
- L0 because a core fact or the conclusion is wrong → C. Counted no.

## What is ground truth

The reference tool JSON is the factual source. It was produced by calling the business tool in code on factory date 2026-04-01.

The sample answer is only an example of depth and wording. If a number, order id, date, or conclusion in the sample answer disagrees with the reference tool JSON, the tool JSON wins. Do not mark C for disagreeing with a stale sample.

The candidate text is the reply body only. A table, a chart, and the Why panel are not part of it. Do not lower the grade because they are absent. If the sample answer also prints a clarification menu, do not require the candidate to repeat that menu.

`must_include` is a hint. Missing a phrase is not by itself a fail when the same fact is present in the answer and in the tool JSON.

Score the prose. A wrong number is still wrong when a table elsewhere shows the right number.

## Output

```json
{"level":"L0","grade":"C","counted":false,"reason":"one short paragraph"}
```

`level` is `L0`, `L1`, `L2`, or `L3`. `grade` is `A+`, `A`, `A-`, `B+`, or `C`. `counted` is true only for `A+` and `A`.
