# 2026-04-01 当天订单说明

对照 4/1 的 `orders.csv`。倒推规则：L 为进入 4/1 当前站的日期，见 [backward_stage_imputation.md](../backward_stage_imputation.md)。

本日共 **120** 单。

## 当天进度（结束时）

| 状态 | 单数 |
|---|---|
| COMPLETE / COMPLETE | 86 |
| IN_PROGRESS / ASSEMBLY | 10 |
| IN_PROGRESS / KNITTING | 12 |
| IN_PROGRESS / PACKING | 2 |
| IN_PROGRESS / WASHING | 10 |

## 未完工订单：4/1 真实工序 → 本日（含 ORDERED）

`last_activity_date`（L）= 进入 4/1 那一站的日期。`D ≥ L` 停在该站；尚未进织则 `status=IN_PROGRESS`、`current_stage=ORDERED`，`last_activity_date` = 下单日。

| order_id | 4/1 真实工序 | 本日 | 说明 |
|---|---|---|---|
| ORD-002 | WASHING | WASHING | 已于 2026-03-23 进入 WASHING |
| ORD-005 | KNITTING | KNITTING | 已于 2026-03-24 进入 KNITTING |
| ORD-008 | KNITTING | KNITTING | 已于 2026-03-31 进入 KNITTING |
| ORD-010 | KNITTING | KNITTING | 已于 2026-03-30 进入 KNITTING |
| ORD-015 | ASSEMBLY | ASSEMBLY | 已于 2026-03-30 进入 ASSEMBLY |
| ORD-017 | KNITTING | KNITTING | 已于 2026-04-01 进入 KNITTING |
| ORD-020 | WASHING | WASHING | 已于 2026-03-30 进入 WASHING |
| ORD-024 | ASSEMBLY | ASSEMBLY | 已于 2026-04-01 进入 ASSEMBLY |
| ORD-029 | WASHING | WASHING | 已于 2026-04-01 进入 WASHING |
| ORD-035 | KNITTING | KNITTING | 已于 2026-04-01 进入 KNITTING |
| ORD-036 | KNITTING | KNITTING | 已于 2026-03-31 进入 KNITTING |
| ORD-040 | KNITTING | KNITTING | 已于 2026-04-01 进入 KNITTING |
| ORD-041 | WASHING | WASHING | 已于 2026-04-01 进入 WASHING |
| ORD-045 | WASHING | WASHING | 已于 2026-03-30 进入 WASHING |
| ORD-053 | ASSEMBLY | ASSEMBLY | 已于 2026-03-31 进入 ASSEMBLY |
| ORD-055 | ASSEMBLY | ASSEMBLY | 已于 2026-04-01 进入 ASSEMBLY |
| ORD-061 | WASHING | WASHING | 已于 2026-03-30 进入 WASHING |
| ORD-062 | KNITTING | KNITTING | 已于 2026-03-31 进入 KNITTING |
| ORD-063 | KNITTING | KNITTING | 已于 2026-03-30 进入 KNITTING |
| ORD-066 | ASSEMBLY | ASSEMBLY | 已于 2026-03-30 进入 ASSEMBLY |
| ORD-073 | ASSEMBLY | ASSEMBLY | 已于 2026-03-31 进入 ASSEMBLY |
| ORD-081 | ASSEMBLY | ASSEMBLY | 已于 2026-03-30 进入 ASSEMBLY |
| ORD-082 | KNITTING | KNITTING | 已于 2026-03-30 进入 KNITTING |
| ORD-083 | WASHING | WASHING | 已于 2026-03-30 进入 WASHING |
| ORD-093 | WASHING | WASHING | 已于 2026-04-01 进入 WASHING |
| ORD-095 | KNITTING | KNITTING | 已于 2026-04-01 进入 KNITTING |
| ORD-096 | KNITTING | KNITTING | 已于 2026-04-01 进入 KNITTING |
| ORD-099 | WASHING | WASHING | 已于 2026-03-31 进入 WASHING |
| ORD-103 | ASSEMBLY | ASSEMBLY | 已于 2026-03-30 进入 ASSEMBLY |
| ORD-107 | PACKING | PACKING | 已于 2026-04-01 进入 PACKING |
| ORD-108 | ASSEMBLY | ASSEMBLY | 已于 2026-03-31 进入 ASSEMBLY |
| ORD-109 | WASHING | WASHING | 已于 2026-03-30 进入 WASHING |
| ORD-114 | PACKING | PACKING | 已于 2026-03-30 进入 PACKING |
| ORD-120 | ASSEMBLY | ASSEMBLY | 已于 2026-03-30 进入 ASSEMBLY |

产量 log **看不到当天**：截止 2026-03-31（含）。

## 外发车间 current_queue_days（马尔可夫假定）

与本厂订单无关。4/1 为真值；往前每一工作日：要么是 **当天新单进来前队列为 0**，要么是 **同一堆积压再多 1 天**。周日抄周六。

| workshop_id | 本日 queue_days | 4/1 真值 |
|---|---|---|
| W1 | 4 | 4 |
| W2 | 2.5 | 2.5 |
| W3 | 5 | 5 |
| W4 | 0.5 | 0.5 |
| W5 | 3 | 3 |
| W6 | 1 | 1 |
| W7 | 0 | 0 |
| W8 | 0 | 0 |
