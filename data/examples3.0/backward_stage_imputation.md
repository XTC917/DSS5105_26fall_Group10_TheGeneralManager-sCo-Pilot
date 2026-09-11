# 订单日快照（v2）：2026-03-23 至 2026-04-01

从 4/1 的 `orders.csv` **倒推**每天结束时各单在哪一站。应用没有接线。

**快照专用约定：** 把 4/1 的 `last_activity_date`（L）读成 **进入 4/1 当前站的日期**。这与课设数据字典「最后一次记工」不同，只用于 `data/examples/`。

- 生成：仓库根目录运行 `.\.venv\Scripts\python.exe data/examples/build_as_of_snapshots.py`
- 每天一个文件夹：`orders.csv`、`production_log.csv`（截止昨天）、`workshops.csv`、`README.md`
- 阶段事件表（不含工厂）：[order_stage_summary.csv](order_stage_summary.csv) — `order_id, status, stage, last_activity_date`。`last_activity_date` 是该阶段开始日；查某天 D 取该单 `last_activity_date ≤ D` 的最后一行。
- 对比：[v1_vs_v2_comparison.md](v1_vs_v2_comparison.md)

### 新工序 `ORDERED`

已下单、但还没进入第一站（织）。**status 一律 `IN_PROGRESS`**（完工除外）：

- `status = IN_PROGRESS`
- `current_stage = ORDERED`
- `last_activity_date = order_date`（下单日）

开始织/缝/洗/包之后，`current_stage` 才是那四站之一。

### 产量 log

当天结束时还看不到当天产量。`production_log.csv` 含源文件中 `date ≤ 昨天` 的全部行。

### 车间 queue_days

其它列与 `data/workshops.csv` 相同。`current_queue_days`：4/1 用真值，往前每个工作日 50/50 为 0 或次日+1。周日抄周六。

---

## 倒退顺序

跳过 `order_date > D` 的单。然后：

1. **冻结** `completed_date ≤ D` → COMPLETE。
2. **已进当前站** `D ≥ L` 且未完工 → 停在 4/1 的站；`last_activity_date` 保持 L（进站日）。
3. **未进当前站** `D < L`：
   - 4/1 是 KNITTING → **ORDERED**（还没开始织），`last_activity_date` = 下单日。
   - 4/1 是后三站 → 在 L 之前最后一个工作日往回，填 **各前序站** 的加工日（件数/日产能，每站至少 1 天）；更早的工作日 = ORDERED。
4. 将完工但 `D` 还没到完成日：完成日当天结束才是 COMPLETE；之前按四站从完成日前一个工作日往回填，更早为 ORDERED。

周日：在制（含 ORDERED）抄周六。ORD-019 / ORD-054 源数据周日完工，当天写成 COMPLETE。

例：ORD-010，4/1 在 KNITTING，L = 3/30，下单 3/24。

| 日期 | status | current_stage | last_activity |
|---|---|---|---|
| 3/24–3/28 | IN_PROGRESS | ORDERED | 2026-03-24 |
| 3/29 日 | IN_PROGRESS | ORDERED | 2026-03-24 |
| 3/30–4/1 | IN_PROGRESS | KNITTING | 2026-03-30 |

---

## 阶段时长

`dwell_s = max(1, round(件数 / 该工序工作日产量中位数))`

只用于 **L 之前的各前序站**（当前站从 L 才开始，不往 L 前面占天数）。

中位数（77 个工作日）：织 882，缝 754，洗 715，包 667。

4/1 应对齐源 `orders.csv`，没有 ORDERED。
