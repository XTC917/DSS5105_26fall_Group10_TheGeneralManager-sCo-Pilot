# SweaterCo GM Co-Pilot（DSS5105 Track 1）

面向小型针织服装工厂总经理的 **AI 管理 Co-Pilot**。

本项目的核心是一个**基于 LangGraph、能够调用业务工具的 Agent（Tool-Using Agent）**，而不是一个通用聊天机器人。

当前仓库实现了一个**可运行的第一版 Co-Pilot**，包括：

* 可检查、可追溯的 Python 业务工具
* Chat API
* 基于 React 的管理端 UI
* 开发阶段评测集

> **数据集中的工厂业务日期：2026-04-01**
>
> 业务逻辑中的日期不使用计算机系统当前时间。

Track 1 要求系统具备五类工具能力：

**Retrieval / Judgement / Tracing / Discovery / Action**

同时还要求支持：

* 定时运营简报（Scheduled Briefing）
* 全天候问答（All-day Q&A）
* 持续监控（Standing Watches）
* 生产可行性估算（Feasibility Estimates）
* 经确认后的操作（Confirmed Actions）
* 完整的可追溯性（Full Traceability）

下面列出了目前已经实现的功能，以及仍待完成的课程要求。

---

## What Works Now｜当前已实现

### Data and API｜数据与 API

* 加载 `orders.csv`、`production_log.csv`、`workshops.csv` 至 SQLite
* `POST /api/chat` — 经过可检查的 Pre-router 后，将业务范围内的问题交给 LangGraph ReAct Agent
* 支持多轮对话，并且**每一轮都会重新调用工具获取最新数据**

  * 使用 `conversation_id` + `MemorySaver` 管理会话
* 对超出系统能力范围的问题（收入、销售价格、员工数量等）返回能力限制，**不会调用无关工具**
* 使用 `data/copilot_state.db` 进行轻量级审计

  * 即使重新加载 `factory.db` 中的 CSV 数据，审计记录仍会保留

### Tools｜工具

项目中的工具按照课程要求映射为五类：

| 类型        | 工具                                   | 功能                                                                |
| --------- | ------------------------------------ | ----------------------------------------------------------------- |
| Retrieval | `get_order_status`                   | 查询单个订单；如果存在多个匹配结果，会要求用户进一步提供订单 ID，例如 “the TrendCart order”        |
| Retrieval | `get_orders_at_risk`                 | 识别逾期、生产停滞、交期紧张的订单；风险公式由 Python 计算                                 |
| Judgement | `check_feasibility`                  | 对新订单进行产能可行性估算，并明确列出计算假设                                           |
| Tracing   | `trace_order`                        | 查看 `orders.csv` 中对应的原始数据行、计算字段以及风险标记                              |
| Discovery | `find_orders`                        | 根据客户、产品、生产阶段、状态等条件列出**所有匹配订单**（用户指定筛选）          |
| Discovery | `discover_factory_issues`            | 按已定义规则主动发现并排序 Top N 问题（订单风险 + 阶段产量偏低） |
| Briefing  | `get_morning_briefing`               | 生成结构化生产运营信息，包括风险订单、最近一天产量与 30 天中位数对比、暂停生产的车间等                     |
| Action    | `draft_chase_email`                  | 根据订单信息生成本地催单邮件草稿，不会发送                                             |
| Action    | `send_email`                         | Proposal → Confirm → **模拟执行**并写入审计记录；目前仍为 `sent: false`，没有真实 SMTP |
| Action    | `add_order_note` / `create_reminder` | Proposal → Confirm → 在本地持久化                                       |
| Audit     | `get_recent_actions`                 | 从 `copilot_state.db` 中读取最近的操作记录                                   |

> `production_log.csv` 是**整个工厂范围的数据**，粒度为 `date × stage`，并非单个订单的生产记录。
>
> 因此它主要用于生产早报和产能可行性分析，而不是作为独立的订单查询工具。

---

## Interface｜用户界面

当前 React 管理端提供：

* 对话式 Chat
* 侧边栏运营快照

  * Morning Briefing
  * Top Issues
  * Triggered alerts / Active watches
  * Recent Actions
* 回答及 **“Why?”** 追踪信息

  * 原始数据行
  * 计算过程
* 操作确认：消息上的 **Confirm / Dismiss**（聊天 “yes” 仍可用）

---

`evaluation/questions.json` 是 few-shot 答法模板库，不是评测 runner。

---

# What Is Not Built Yet｜尚未完成

以下是 Track 1 中目前仍缺失或只完成了一部分的核心能力。

### 1. Scheduled Briefing｜定时运营简报

目前的 Briefing 只能：

* 用户主动在 Chat 中询问
* 或由侧边栏请求 `/api/briefing`

系统目前**不会按照时间自动生成 Briefing**。

此外，目前只有 Agent 在生成自然语言回答时才会产生 prose；侧边栏主要加载结构化 JSON 数据。

---

### 2. Standing Watches｜持续监控

目前 `create_reminder` 只能保存一条本地记录：

```text
notified: false
```

系统还没有真正持续检查：

> “ORD-058 到周四之前仍然没有任何进展。”

并在满足条件后主动提醒经理。

也就是说，目前有 **Reminder**，但还没有真正的 **Standing Watch / Monitoring Loop**。

---

### 3. Ranked Discovery｜主动发现并排序工厂问题

V1 已注册 `discover_factory_issues`。

* `find_orders` 仍只做用户指定的条件筛选
* `discover_factory_issues` 按已定义规则主动找出订单风险和阶段产量偏低，并由 Python 排序
* 不是万能异常检测器；不会用 LLM 写 SQL，也没有副作用

阶段产量规则仍是 briefing 里那条 `0.70 × 30 天中位数`，不是完整的 `assess_stage_performance`。

---

### 4. `assess_stage_performance`｜生产阶段绩效分析

目前还没有完整、可检查的：

> “这个生产阶段当前产量是否正常？”

工具。

Morning Briefing 中目前只有一个简单的：

```text
当前产量 < 0.70 × 过去 30 天中位数
```

的下降启发式判断。

---

### 5. Confirmation UI｜独立确认界面

Agent 只提出方案（`confirmed=false`）。消息上出现 **Confirm / Dismiss**：

* 点 **Confirm** → `POST /api/actions/confirm`，服务端以 `confirmed=true` 执行白名单工具（不经过 LLM）
* 点 **Dismiss** → 只记审计，不落库

这仍然满足课程要求的二次确认。聊天里回复 “yes” 仍可作为备用。

---

### 6. Held-out Evaluation｜独立测试集

目前还没有正式的 Held-out Evaluation 文件。

在对外声称正式准确率之前，需要添加一个独立 JSON 数据集，例如：

```json
{
  "meta": {
    "usage": "held-out"
  }
}
```

---

### 7. Course Write-ups｜课程交付材料

以下属于课程交付物，而非产品代码：

* `Evaluation.pdf`

  * 包括至少 10 个失败案例分析
* Sprint Decks
* `GroupX.zip`

---

## Out of Scope｜本 Track 不要求

以下功能不属于本 Track 的课程要求：

* 真实 SMTP 邮件发送
* 真实日历集成
* 真实 Push Notification
* Voice Input / Output
* YAML Business Ontology

---

# Repository Layout｜项目结构

```text
backend/          FastAPI + LangGraph + tools + services
frontend/         React + Vite + Tailwind
data/             Track 1 CSV 数据集（Source of Truth）
docs/             architecture.md、tool_spec.md
evaluation/       Track 1 开发阶段评测集（非正式 Held-out Score）
tests/            pytest 测试，无需 LLM API Key
```

修改业务规则前，请先阅读：

```text
docs/architecture.md
docs/tool_spec.md
```

`tool_spec.md` 记录了各工具的行为和限制。

课程最终 Evaluation Report 仍要求整理一张统一的工具表，至少包含：

| Name | Input | Output | Purpose | Non-goals | Failure Mode |
| ---- | ----- | ------ | ------- | --------- | ------------ |
| 工具名称 | 输入    | 输出     | 用途      | 不负责什么     | 失败情况         |

---

# Prerequisites｜运行环境

* Python 3.10+
* Node.js 18+
* OpenAI-compatible API Key

> API Key **仅在使用 Chat Agent 时需要**。
>
> `pytest` 测试和数据加载功能无需 API Key。

---

# Backend｜后端

在项目根目录使用 PowerShell：

```powershell
python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

copy .env.example .env

# 编辑 .env，设置 OPENAI_API_KEY
# 可选配置：OPENAI_BASE_URL、LLM_MODEL

uvicorn backend.main:app --reload --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

---

# Frontend｜前端

```powershell
cd frontend

npm install

npm run dev
```

打开：

```text
http://localhost:5173
```

Vite 会将 `/api` 请求代理至后端 `8000` 端口。

---

# Tests｜测试

```powershell
.\.venv\Scripts\Activate.ps1

pytest
```

测试包括：

* Schema
* 日期计算
* 风险标记
* Agent Routing
* Tool JSON

测试**不会调用 LLM**。

---

---

# Architecture Principle｜核心职责划分

项目明确区分 **Python Tools** 和 **LLM Agent** 的职责。

### Tools / Python

所有确定性的业务计算都由 Python 完成，包括：

* 订单状态
* 风险标记
* 日期计算
* 产能估算
* Morning Briefing
* 其他业务数字

### LLM

LLM 主要负责：

* 判断问题是否属于系统支持范围
* 选择合适的业务工具
* 根据工具返回结果组织和解释最终答案

### Unsupported Questions

对于系统不支持的问题：

> **不得调用无关工具。**

例如：

> “What is the revenue from TrendCart?”

由于当前数据没有价格 / 收入信息，Agent 应直接说明系统无法回答，而不是调用其他工具进行推测。

### Actions

所有具有副作用的操作遵循：

**Proposal → Confirmation → Persistence**

即：

1. Agent 首先提出操作方案
2. 用户在界面点击 Confirm（或聊天回复 yes）
3. 系统才在本地持久化

目前邮件功能**不会实际发送邮件**。

---

# Try These Questions｜示例问题

配置 API Key 后，可以尝试：

```text
How is ORD-120 doing?
```

查询 ORD-120 当前状态。

```text
How is the TrendCart order doing?
```

如果存在多个 TrendCart 订单，Agent 应要求用户进一步指定具体订单。

```text
Which orders are at risk?
```

查询当前存在风险的订单。

```text
Why is ORD-120 considered risky?
```

解释 ORD-120 为什么被判断为风险订单。

```text
Can we take 800 hoodies by August 25?
```

检查新增 800 件 Hoodie 订单的生产可行性。

```text
Give me this morning's briefing
```

生成当天的生产运营简报。

```text
List the TrendCart orders
```

列出所有 TrendCart 相关订单。

```text
Draft a chase-up email for ORD-120
```

生成 ORD-120 的催单邮件草稿。

```text
Create a reminder to check ORD-005 tomorrow
```

创建本地 Reminder Proposal；不会向外部系统发送通知。

```text
What is the revenue from TrendCart?
```

应该拒绝回答，因为当前数据没有价格 / 收入数据。

---

# Next｜下一阶段开发计划

为了优先满足 Track 1 的核心要求，建议按照以下顺序继续开发：

### 1. Standing Watches

基于工厂日历进行到期检查，并将触发结果写入 UI / Audit。

> 暂时仍不需要真实 Push Notification。

### 2. Stage Performance

完整的 `assess_stage_performance` 仍未实现。Discovery V1 只复用 briefing 的 0.70 × 中位数启发式。

### 3. Scheduled Briefing

实现真正的：

> Scheduled Briefing

或者至少支持：

> 打开应用 → 自动展示今天的 Briefing

而不只是侧边栏中的结构化 JSON。

### 4. Held-out Evaluation

添加独立 Held-out Evaluation 数据集，并为 `Evaluation.pdf` 准备失败案例分析。

---

# Rules for Teammates｜协作开发规则

### 1. 不得编造数据字段或业务事实

只能使用：

```text
data/
data/data_dictionary.md
```

中明确存在的数据和业务定义。

### 2. 不要把业务计算写进 Prompt

例如：

* 总数量
* 天数
* 剩余天数
* 产能
* 风险计算

等业务逻辑都必须由 **Python Function** 完成。

不要把计算公式写死在 Prompt 中。

### 3. 不确定的设计不要猜

如果现有数据无法支持某项设计：

```python
# TODO
```

而不是自行假设业务规则。

### 4. 副作用操作必须经过明确确认

任何具有副作用的操作：

* 必须经过用户明确确认
* 不得在确认之前执行
* 不得声称已经发送外部邮件

---

# Logging｜日志

API 日志输出至：

```text
console
logs/app.log
```

查询、工具调用以及 Action Trace 写入：

```text
data/copilot_state.db
```

该数据库已加入 `.gitignore`。

它独立于 `factory.db`，因此即使重新加载 CSV 数据，也会保留 Co-Pilot 的操作与审计记录。
