# 2026-03-23 当天订单说明

对照 4/1 的 `orders.csv`。倒推规则：L 为进入 4/1 当前站的日期，见 [backward_stage_imputation.md](../backward_stage_imputation.md)。

本日共 **113** 单。 还没下单、不在表里：ORD-010, ORD-024, ORD-035, ORD-040, ORD-063, ORD-082, ORD-095。

## 当天进度（结束时）

| 状态 | 单数 |
|---|---|
| COMPLETE / COMPLETE | 76 |
| IN_PROGRESS / ASSEMBLY | 4 |
| IN_PROGRESS / KNITTING | 2 |
| IN_PROGRESS / ORDERED | 29 |
| IN_PROGRESS / PACKING | 1 |
| IN_PROGRESS / WASHING | 1 |

## 未完工订单：4/1 真实工序 → 本日（含 ORDERED）

`last_activity_date`（L）= 进入 4/1 那一站的日期。`D ≥ L` 停在该站；尚未进织则 `status=IN_PROGRESS`、`current_stage=ORDERED`，`last_activity_date` = 下单日。

| order_id | 4/1 真实工序 | 本日 | 说明 |
|---|---|---|---|
| ORD-002 | WASHING | WASHING | 已于 2026-03-23 进入 WASHING |
| ORD-005 | KNITTING | ORDERED | 已下单未开工（4/1 的 KNITTING 从 2026-03-24 才开始；L=下单日） |
| ORD-008 | KNITTING | ORDERED | 已下单未开工（4/1 的 KNITTING 从 2026-03-31 才开始；L=下单日） |
| ORD-015 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-30 才开始；L=下单日） |
| ORD-017 | KNITTING | ORDERED | 已下单未开工（4/1 的 KNITTING 从 2026-04-01 才开始；L=下单日） |
| ORD-019 | COMPLETE | ORDERED | 已下单未开工（4/1 的 COMPLETE 从 2026-03-29 才开始；L=下单日） |
| ORD-020 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-03-30 才开始；L=下单日） |
| ORD-029 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-04-01 才开始；L=下单日） |
| ORD-030 | COMPLETE | ORDERED | 已下单未开工（4/1 的 COMPLETE 从 2026-03-28 才开始；L=下单日） |
| ORD-031 | COMPLETE | ASSEMBLY | 倒推上一站（尚未到 4/1 那一站） |
| ORD-036 | KNITTING | ORDERED | 已下单未开工（4/1 的 KNITTING 从 2026-03-31 才开始；L=下单日） |
| ORD-041 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-04-01 才开始；L=下单日） |
| ORD-044 | COMPLETE | ASSEMBLY | 倒推上一站（尚未到 4/1 那一站） |
| ORD-045 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-03-30 才开始；L=下单日） |
| ORD-053 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-31 才开始；L=下单日） |
| ORD-054 | COMPLETE | ORDERED | 已下单未开工（4/1 的 COMPLETE 从 2026-03-29 才开始；L=下单日） |
| ORD-055 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-04-01 才开始；L=下单日） |
| ORD-060 | COMPLETE | KNITTING | 倒推上一站（尚未到 4/1 那一站） |
| ORD-061 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-03-30 才开始；L=下单日） |
| ORD-062 | KNITTING | ORDERED | 已下单未开工（4/1 的 KNITTING 从 2026-03-31 才开始；L=下单日） |
| ORD-066 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-30 才开始；L=下单日） |
| ORD-069 | COMPLETE | ORDERED | 已下单未开工（4/1 的 COMPLETE 从 2026-03-30 才开始；L=下单日） |
| ORD-073 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-31 才开始；L=下单日） |
| ORD-081 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-30 才开始；L=下单日） |
| ORD-083 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-03-30 才开始；L=下单日） |
| ORD-084 | COMPLETE | ORDERED | 已下单未开工（4/1 的 COMPLETE 从 2026-03-28 才开始；L=下单日） |
| ORD-093 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-04-01 才开始；L=下单日） |
| ORD-096 | KNITTING | ORDERED | 已下单未开工（4/1 的 KNITTING 从 2026-04-01 才开始；L=下单日） |
| ORD-099 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-03-31 才开始；L=下单日） |
| ORD-103 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-30 才开始；L=下单日） |
| ORD-107 | PACKING | KNITTING | 倒推上一站（尚未到 4/1 那一站） |
| ORD-108 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-31 才开始；L=下单日） |
| ORD-109 | WASHING | ORDERED | 已下单未开工（4/1 的 WASHING 从 2026-03-30 才开始；L=下单日） |
| ORD-112 | COMPLETE | PACKING | 倒推上一站（尚未到 4/1 那一站） |
| ORD-113 | COMPLETE | ASSEMBLY | 倒推上一站（尚未到 4/1 那一站） |
| ORD-114 | PACKING | ASSEMBLY | 倒推上一站（尚未到 4/1 那一站） |
| ORD-120 | ASSEMBLY | ORDERED | 已下单未开工（4/1 的 ASSEMBLY 从 2026-03-30 才开始；L=下单日） |

产量 log **看不到当天**：截止 2026-03-22（含）。

## 外发车间 current_queue_days（马尔可夫假定）

与本厂订单无关。4/1 为真值；往前每一工作日：要么是 **当天新单进来前队列为 0**，要么是 **同一堆积压再多 1 天**。周日抄周六。

| workshop_id | 本日 queue_days | 4/1 真值 |
|---|---|---|
| W1 | 12 | 4 |
| W2 | 5 | 2.5 |
| W3 | 0 | 5 |
| W4 | 0 | 0.5 |
| W5 | 2 | 3 |
| W6 | 3 | 1 |
| W7 | 0 | 0 |
| W8 | 6 | 0 |
