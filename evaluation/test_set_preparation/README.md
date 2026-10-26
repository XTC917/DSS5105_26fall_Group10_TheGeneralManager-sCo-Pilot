# Evaluation Test Set Preparation (Sprint 1)

Consolidated evaluation dataset for the SweaterCo GM Co-Pilot agent.

## Source

- 4 testers, 177 original test records (131 GOOD / 46 BAD).
- Records were cross-compared, de-duplicated and normalised into a unified test set.
- After consolidation: **142 test cases** (every case is traceable to at least one original record).

## Files

| File | Contents |
|---|---|
| `01_evaluation_test_set.json` | Canonical test set: 142 cases with `expected_behavior`, `acceptance_criteria`, `decision_status`, `rule_dependency`, `data_verification_status`, `source_records`, etc. |
| `02_evaluation_test_set.csv` | Flat view of the same test set for review in a spreadsheet. |
| `03_risk_rule_register.csv` | Rule register for the 48 risk / priority cases (current-code rule vs. historical test behaviour vs. open decisions). |
| `04_evidence_gap_list.csv` | 11 records that cannot become executable tests as-is (2 blocked, 9 with reconstructed question wording). |
| `05_delivery_register.md` | Delivery summary: status definitions, handling of BAD records, open decisions, and what still blocks final sign-off. |

## Status distribution

| Status | Count |
|---|---|
| `READY` | 68 |
| `READY_DATA_CHECK` | 47 |
| `PENDING_RULE_DECISION` | 15 |
| `PENDING_TOOL_AVAILABILITY` | 11 |
| `EVIDENCE_GAP` | 1 |
| **Total** | **142** |

## Notes

- All BAD records are kept and tracked; none were deleted or silently downgraded to notes.
- Expected behavior and acceptance criteria have been consolidated, but they have **not** been individually confirmed by every original tester. No expected answer is marked `CONFIRMED` (`reviewer_confirmed` is `false` for every case).
- `READY_DATA_CHECK` means the acceptance criteria are stable but the concrete numbers still need one pass against the database.
- `PENDING_RULE_DECISION` means the risk/priority rule itself is not settled yet (e.g. TIGHT_DEADLINE definition, default at-risk window). No pace-based or stage-based rule has been selected as ground truth.
- `PENDING_TOOL_AVAILABILITY` means the referenced tool (`get_today_priority`) is not registered in the current codebase and needs a decision on whether it is an upcoming capability.
- This is an **evaluation dataset** for development and review. It is not a held-out benchmark, and it does not claim that all expected answers have been verified.
- No credentials, API keys, personal data or test-account secrets are included.
