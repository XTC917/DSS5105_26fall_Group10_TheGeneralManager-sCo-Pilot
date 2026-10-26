# 05 — Delivery Register（最终交付说明）

## 1. 交付内容

| 文件 | 内容 |
|---|---|
| `01_evaluation_test_set.json` | **主交付物**：142 个测试用例，完整字段，可直接被评测器读取 |
| `02_evaluation_test_set.csv` | 同上，扁平化，方便 Excel/人工审阅 |
| `03_risk_rule_register.csv` | 48 条风险/优先级相关用例的规则对照（当前代码定义 / 历史测试行为 / 分歧 / 需拍板项） |
| `04_evidence_gap_list.csv` | 11 条证据缺口（2 条阻塞 + 9 条题干需回看截图） |
| `05_delivery_register.md` | 本文件 |
| `scripts/build_final.py` | 从 phase 1 + phase 2 产物重建最终测试集 |
| `scripts/verify_final.py` | 27 项独立核对 |

**总覆盖**：177 条原始记录全部可追溯到至少 1 个测试用例；46 条 Bad 全部覆盖。

---

## 2. 最终状态分布（5 种，已简化）

| 状态 | 数量 | 含义 | 谁来动 |
|---|---|---|---|
| `READY` | **68** | 问题有效、标准客观、无规则分歧；**可直接跑评测** | 评测器 |
| `READY_DATA_CHECK` | **47** | 标准客观，但期望值含具体数字，跑一次数据库确认即可签字 | 评测器 + 数据库 |
| `PENDING_RULE_DECISION` | **15** | 涉及风险/优先级规则，等组长定口径（见 `03_risk_rule_register.csv`） | 组长 |
| `PENDING_TOOL_AVAILABILITY` | **11** | 用了当前代码里不存在的 `get_today_priority` 工具，需确认是否为待开发能力 | 组长 + 后端 |
| `EVIDENCE_GAP` | **1** | 原始记录不足以成为可执行用例（K39-B11） | JasT |
| 合计 | **142** | | |

> 重要：**没有 `PENDING_CONFIRMATION` 状态**。所有 Bad 问题都已给出客观验收标准，不再卡在"等测试者确认"；原始 Bad 评级与反馈一并保留，标准来源在 `standard_provenance` 字段（`PROPOSED_BY_THIS_CONSOLIDATION...`），**未经原测试者确认**，且 `reviewer_confirmed` 恒为 `false`。

---

## 3. Bad 问题的处理方式

46 条 Bad 全部进入测试集，按"可直接制定客观标准"的原则处理（见任务书 B 节）。例如：

- 小写订单号应正常识别 → `G_LOWERCASE_ORDER_ID`（K39-B06）
- 文字与表格必须一致 → `G_CUSTOMERS_MULTI_RISK`（K39-B10）
- 多轮追问必须正确继承上下文 → `G_TRENDCART_URGENT_FOLLOWUP`（K42-B02）
- 列表不能静默截断 → `G_LIST_COMPLETED`（K40-BQ14）
- 表格生成失败不能假装成功 → `G_OVERDUE_TABLE`（K40-BQ56）
- 查询无结果时应明确说明 → `G_EMPTY_RESULT_CHART`（K40-BQ15）
- 澄清后应回答用户选择的具体问题 → `G_CLARIFY_*`
- 不应插入与用户问题无关的内容 → `G_WORKSHOP_SUSPENDED`（K39-B18）
- 不应编造不存在的数据 → `G_REVENUE` / `G_SELLING_PRICE` / `G_OUTSOURCING_COST`

每条 Bad 的具体失败点、建议正确回答、编号化 Acceptance Criteria、修复类型/负责人、要问什么、证据可靠性、截图路径，都在 `phase2/02_bad_expected_answers_draft.xlsx`（Sheet `BadAnswers`）逐行可查。

**不能把 tester 希望拥有的新功能写成当前已支持的能力**：5 条标记为 `NEW_FEATURE_REQUIRED`（最早可交付日、what-if 产能、30 天波动率、准时率、客户整体概况卡片），验收标准写的是"必须明确说明不支持，或新增功能"，而不是"当前就能答"。`G_CLARIFY_CUSTOMER_OVERVIEW`（客户整体概况选项）的"overview 卡片"同样移入 notes 作为 proposed enhancement。

---

## 4. 风险判断问题的处理（Section C）

**没有自行选择 pace-based 或 stage-based 作为最终真值**。所有风险相关用例（48 条 register 行）按三类登记（`03_risk_rule_register.csv`）：

| 类别 | 行数 | 含义 | 例 |
|---|---|---|---|
| A. 当前代码已明确规定 | 23 | 按 `docs/tool_spec.md` + `backend/services/calculations.py` 验收 | OVERDUE（due < 2026-04-01）、STALLED（≥3 个工作日无活动） |
| B. 历史测试与当前代码存在差异 | 10 | 测试时行为与代码/文档不一致，需定稿 | TIGHT_DEADLINE（pace 法 vs 阶段数法）、默认 at-risk 名单（3 单 vs 全部 flagged） |
| C. 需要组长确定的规则 / 工具能力 | 15（4 规则 + 11 工具） | 规则本身没写清，或所用工具不在当前代码中 | "all" 的隐式时间窗、Morning Briefing 是否纳入、`get_today_priority` 是否为待开发能力 |

**具体冲突点（不选真值，只列出）**：
- **CF-04**：TIGHT_DEADLINE 是 `working_days_until_due_inclusive < remaining_stage_count`（代码/文档）还是"剩余工时 > 可用工作日"（pace 法，测试时行为）。两者对 ORD-103 给出相反结论。
- **CF-05**：默认 at-risk 名单是否包含已逾期订单（JasT 认为不该含，其余三人判 GOOD）。
- **CF-06**：不带时间窗的 "all" 是否等价于"今天至 +3 天"。
- **CF-12**：Morning Briefing 本轮是否纳入。

这些用例在测试集里**保留问题、工具、测试数据和验收标准框架**，但具体风险标签/订单集合标为 `PENDING_RULE_DECISION`，等组长定口径后再填具体订单集合。例如 `G_RISK_DEFAULT` 的 `expected_answer` 里只写 "the returned set must equal the rule-defined set after CF-04/05/06 are fixed; the 3-order observation (ORD-029/108/103) is the tested-build result, not a confirmed truth"。

---

## 5. 其他不确定问题

- **数据库才能确定具体数字**：`data_verification_status = DATA_VERIFICATION_REQUIRED`（64 条）；保留可验证的计算/查询标准（如 `get_orders_at_risk` + 对应 flag），标记为待数据库核对。`CROSS_CHECKED_BY_RECORDS`（50 条）指 ≥2 位测试者独立观察到相同数值，但仍需 DB 签字。
- **工具不支持的功能**：按三类明确区分（`capability_class` 字段）：
  - `SHOULD_ANSWER_BUT_BLOCKED`（4 条：B08 3 天+多阶段、B17 客户集中度、B23 进展对比、B05 文字/表格不一致）——应该正常回答却被错误拦截。
  - `LEGITIMATE_LIMITATION`（7 条）——当前确实没有该能力，应明确说明限制（收入/售价、外包成本、7 天产出、按客户件数、排班/设备数据）。
  - `NEW_FEATURE_REQUIRED`（5 条）——需要新增功能才能满足期望（最早交付日、what-if 产能、波动率、准时率、客户整体概况卡片）。
  - `CLARIFY_INSTEAD_OF_BLOCKING`（2 条）——语义矛盾应澄清而不是拦截。

---

## 6. 多轮与证据缺口

- **多轮上下文**：11 个测试用例保留了 `conversation_context` 与 `prerequisite_turns`（如 TrendCart 三轮、 clarify 选项、feasibility 二次追问）。证据缺口导致无法还原的，标 `EVIDENCE_GAP` 并进入 `04_evidence_gap_list.csv`。
- **证据缺口清单（11 条）**：
  - 2 条 **BLOCKED**：`K39-B11`（下一轮问题未被截图）、`K39-B15`（评语与截图不符，归属不确定）。
  - 9 条 **VERIFY_WORDING**：题干是根据评价者"测试说明"重建的（ZZJ 的 9 条），不是截图原句，但用例本身可执行（期望标准不依赖措辞）。
  - 全部保留与原始记录的关联（record_id / source_file / artifacts）。

---

## 7. 可追溯性保证

- 177 条原始记录**全部**可追溯到至少 1 个测试用例（`records_traceable = 177`）。
- 46 条 Bad 全部覆盖（`bad_records_covered = 46`）。
- 每条 Bad 的原始评级与反馈原文保留在 `source_records[].reviewer_feedback` 与 `original_ratings`。
- 没有伪造缺失的问题或回答：题干无法还原的 2 条记录进入 gap 清单，不进入可执行用例。
- 没有任何 `reviewer_confirmed = true` 或 `CONFIRMED` 状态：所有标准都标 `standard_provenance`（`CROSS_VALIDATED_BY_RECORDS` / `SINGLE_EVALUATOR_GOOD` / `STANDARD_PROPOSED_BY_THIS_CONSOLIDATION...`）。

---

## 8. 仍然需要组长拍板 / 开发者修复的事项

| 优先级 | 事项 | 负责人 | 影响 |
|---|---|---|---|
| P0 | CF-04：TIGHT_DEADLINE 规则（pace vs 阶段数） | 组长 + 后端 | 15 条 `PENDING_RULE_DECISION` + 12 条已收录的期望值 |
| P0 | CF-07 / CF-08：flag 计算双路径不一致 | 后端 | ETS-076 / ETS-079 的 flag 一致性 |
| P0 | CF-13：ORD-107 交期查库一行 | 后端 / 你 | ETS-078 / ETS-127 |
| P1 | CF-05 / CF-06：默认 at-risk 名单与 "all" 时间窗 | 组长 | ETS-110 / ETS-112 / ETS-133 |
| P1 | CF-09 / CF-10 / CF-11：澄清卡片 / 0 结果画图 / 双账号 fixture | 组长 + XJT/ZZJ | 产品规则定稿 |
| P1 | 11 条 `PENDING_TOOL_AVAILABILITY`：`get_today_priority` 是否为待开发能力 | 组长 + 后端 | 这 11 条用例能否跑 |
| P2 | JasT 的记录核对（`04_grouped_reviewer_messages.md` §1.0 清单） | 你 → JasT | 29 条 BAD 的归属 |
| P2 | ZZJ 重新上传报告 + 确认截图归属 | 你 → ZZJ | 审计完整性 |
| P2 | 47 条 `READY_DATA_CHECK` 的数据库复核 | 你 | 数字最终签字 |

---

## 9. 验证

- `verify_final.py` **27/27 PASS**（结构、追溯、覆盖、无伪造确认、phase 1 文件未动）。
- `verify.py`（phase 1）**20/20 PASS**（仍有效）。
- 所有产物在 `ProjectEvaluation/analysis_output/final/`；原始文件与 phase 1/phase 2 文件未被覆盖。

## 10. 复现

```bash
cd ProjectEvaluation
python analysis_output/final/scripts/build_final.py   # 重建 01/02/03/04 + stats
python analysis_output/final/scripts/verify_final.py  # 27/27 通过
```

`build_final.py` 只读取 phase 1 与 phase 2 的产物，**不重新 OCR、不写回 phase 1/phase 2 目录**。
