# Phase 4A — 云端部署准备与安全审计

> 状态：准备阶段，未创建任何云资源、未执行数据库迁移、未调用付费 LLM。
> 日期：2026-06-16

## 1. 推荐架构

优先组合：

| 层 | 推荐 | 原因 |
|---|---|---|
| 前端 | Vercel Hobby | 免费、Git 自动部署、`/api` rewrite 可做同源代理、HTTPS 自动 |
| 后端 | Render Free Web Service（Docker） | 支持 Python/FastAPI 长期进程、SSE、免费 HTTPS；代价是 15 分钟无流量休眠 |
| PostgreSQL | Neon Free | 1 GB/项目、100 CU-hours/项目/月、5 分钟无活动自动 scale-to-zero、无需信用卡 |

备选组合：

- 前端：Cloudflare Pages（免费构建 500 次/月、20,000 文件、单文件 25 MiB；静态带宽通常更宽松）。如果需要同源 `/api`，需要 Pages Function/Worker 代理，配置比 Vercel rewrite 多一步。
- 数据库：Supabase Free（500 MB、1 周无活动暂停、5 GB egress）。适合已经使用 Supabase Auth 的项目；本项目已有 JWT + auth schema，Neon 更贴近“纯 Postgres”。
- 后端：Fly.io / Koyeb 等容器平台可作为 Render 备选，但免费额度、休眠和信用卡要求需要重新核实。

## 2. 免费额度核对结果（2026-06 官方页面）

### Render Free

- Web Service：512 MB RAM，less than 1 CPU。
- 15 分钟没有入站流量会 spin down；下一次请求约 1 分钟冷启动。
- 每月 750 free instance hours；spun-down 期间不消耗。
- 文件系统 ephemeral：上传文件、日志、SQLite 在重启/重新部署/休眠后丢失。
- 免费 Postgres 30 天后过期，不建议用于本项目长期测试。
- 免费实例不建议用于生产；朋友测试可以，但需要接受冷启动。

### Neon Free

- 100 projects，100 CU-hours/project/月，1 GB storage/project。
- 5 分钟无活动自动 scale-to-zero；下次查询通常数百毫秒恢复。
- 无需信用卡；不会因为不活跃暂停项目。
- 超出 100 CU-hours 或 5 GB 网络传输后，项目 compute 暂停到下一个计费周期；数据不会删除。
- 免费计划是否允许创建额外 LOGIN 角色/Schema 权限需要人工在 Neon SQL Editor 验证；如果不允许，使用 Neon owner 角色并记录为 least-privilege 待办。

### Vercel Hobby

- 免费 Hobby，适合个人/非商业项目。
- 每月 1M CDN requests、100 GB Fast Data Transfer、1M Function invocations、4 小时 Fluid Active CPU。
- Hobby 不适合商业用途；课程/朋友测试可以使用，但需确认符合 Vercel 条款。
- 自动 HTTPS、Git 自动部署、rewrite/headers 配置简单。

### Cloudflare Pages Free

- 500 builds/月，20,000 files/站，单文件 25 MiB。
- 100 projects/account，100 custom domains/project。
- 静态资源 CDN 免费；Pages Functions 请求计入 Workers 配额。
- 如果使用 Cloudflare Pages，同源 API 需要 Pages Function 代理到 Render，或让前端直接调用 Render 并配置 CORS。

### Supabase Free

- 500 MB database，5 GB egress。
- 免费项目 1 周无活动后暂停。
- 2 个 active projects。
- 适合作为 Neon 备选；如果以后使用 Supabase Auth，需要替换现有 JWT/AuthContext。

## 3. 成本风险

- Render：免费 web service + 免费 instance hours。超出带宽/构建分钟可能产生补充费用；未添加支付方式时通常暂停免费服务。
- Neon：免费计划超出 compute/网络后暂停，不自动转付费；添加支付方式/升级付费计划前不会产生费用。
- Vercel：Hobby 有硬性免费额度；升级 Pro 或购买 add-on 才会收费。
- LLM：真正的不可控成本来源。必须限制为“仅管理员审核通过的测试账号”使用，并在 OpenAI 控制台设置项目预算/用量告警。
- 建议：所有云账户保持“无支付方式”或“免费计划 + 预算告警”，不要在 Phase 4B 前绑定自动扣费。

## 4. PostgreSQL 云端迁移规划

本地数据库：`factory_copilot_db`，Alembic 当前版本 `006_chat_attempts`，包含 `app`、`admin_meta`、`copilot`、`auth` schema。

### 迁移原则

1. 云端使用全新独立数据库，不修改本地数据库。
2. 不复制本地 `auth.users`、密码哈希、JWT、私人聊天记录、checkpoint 数据。
3. 只导入课程允许公开测试的演示业务数据（orders / production_log / workshops / snapshot）。
4. 保留表结构和必要权限。
5. 保留 LangGraph checkpoint 表结构，但清空 checkpoint 内容。
6. 用户重新注册，管理员审批后才可登录。

### 推荐执行顺序

1. 在 Neon 创建项目/数据库，记录 direct connection string。
2. 以 owner 身份连接，检查是否能创建角色：
   - `factory_admin`（migration/admin）
   - `factory_agent`（runtime read-only）
   - `factory_reader`（可选 group role）
3. 如果允许，执行角色创建（不要复用本地密码，使用新随机密码）。
4. 设置环境变量：`PGUSER=factory_admin`、`PGPASSWORD=...`，运行：
   ```powershell
   alembic upgrade head
   ```
   这会创建 `001` 到 `006` 的所有 schema、auth 表、conversation 表、checkpoint 表、chat_attempts 表。
5. 导入演示业务数据：
   - 参考 `postgresql_database/sql/03_import.sql`，把本地路径替换为云端可访问的 CSV 路径；
   - 或启动应用后用 Data Management 的导入功能导入 `postgresql_database/data/*.csv`；
   - 不要导入 `auth.users` / `copilot.conversations` / `copilot.checkpoint_*`。
6. 运行 `04_validate.sql` 做只读校验。
7. 执行权限收敛：确保 `factory_agent` 只有 `SELECT`，不能 DDL/DML。
8. 设置应用运行时 `DATABASE_URL` 为 `factory_agent` 的连接；`PG_ADMIN_*` 为 `factory_admin` 的连接。
9. 启动后端，确认 `/api/health` 正常；用管理员注册码创建第一个 ADMIN；再审批测试用户。

### 风险点

- `postgresql_database/sql/01_roles_and_database.sql` 不是幂等的，重复执行会因角色已存在失败。云端只执行一次，或先检查 `pg_roles`。
- `CREATE DATABASE`/`CREATE ROLE` 需要足够权限；Neon/Supabase 免费计划可能不提供 superuser，需人工验证。
- Alembic `005_checkpoint_memory` 会执行 LangGraph `PostgresSaver.MIGRATIONS`，需要 `copilot` schema 和建表权限。
- `checkpoint_store.py` 启动时检查 `checkpoint_migrations` 版本，缺失/过期会拒绝启动。
- 免费数据库连接数有限；当前 checkpointer pool `min_size=1,max_size=4`，朋友测试可接受，但不能高并发。
- 所有连接必须带 `sslmode=require`（Neon/Supabase 要求）。

## 5. 后端部署准备结果

已检查：

- 启动命令：`uvicorn backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips "*"`。
- Python：Dockerfile 使用 `python:3.12-slim`；本地 `.venv` 已能导入 `backend.main`。
- 环境变量：`backend.config` / `backend.pg_config` 从仓库根 `.env` 读取；云端无 `.env` 时直接读 Render 环境变量。
- 数据库：`DATABASE_URL` 用于普通 runtime；`PG_ADMIN_*` 用于 migration/admin/checkpointer。
- Checkpoint：Alembic 005 创建 `copilot.checkpoint_*`；应用启动时检查版本。
- 上传：`backend/uploads` 在免费 Render 上是 ephemeral；需要后续接 S3/R2/Supabase Storage。
- 日志：`logs/app.log` 也是 ephemeral；Render 控制台日志可用，长期日志需外部 log drain。
- SSE：已有 keep-alive（10s）和 `X-Accel-Buffering: no`；Render 支持流式响应，但 Vercel rewrite 代理是否无缓冲需要 Phase 4E 实测。
- CORS：已改为 `CORS_ORIGINS` 环境变量；未设置时只允许本地 5173。

已新增：

- `Dockerfile`
- `.dockerignore`
- `render.yaml`
- `deploy/env.cloud.example`

## 6. 前端部署准备结果

已检查：

- `npm run build` 成功。
- 前端请求全部使用相对 `/api`，本地由 Vite proxy 转发到 `127.0.0.1:8000`。
- 生产环境推荐 Vercel `rewrites` 把 `/api/*` 转发到 Render，实现同源请求，避免浏览器 CORS。
- SPA 路由由 Vercel fallback rewrite 到 `index.html`。
- 静态资源缓存、基础安全 headers 已加入 `frontend/vercel.json`。
- 未把 API Key 或数据库连接字符串写入前端。
- PWA 后续只需增加 manifest/service worker；当前 Vite 构建不阻塞。

已新增：

- `frontend/vercel.json`

注意：

- `vercel.json` 中的 `REPLACE-WITH-RENDER-SERVICE` 必须替换为实际 Render URL。
- 如果 Vercel rewrite 对 SSE 产生缓冲/超时，改用 Render 直连 + `CORS_ORIGINS` 白名单。

## 7. 公网安全问题清单

详见 `docs/phase4a_security_audit.md`。核心结论：

- P0 已修复：`/api/briefing`、`/api/discovery` 现在要求 Bearer 认证；CORS 改为环境变量白名单。
- P0 仍需人工执行：云端必须使用全新强密码/密钥；禁止使用 `.env.example` 中的示例密码；只允许审核通过的账号使用。
- P1：缺少登录/聊天限流；JWT 存在 localStorage；上传文件 ephemeral；日志可能包含请求细节；免费实例冷启动。
- P2：`/api/health` 暴露工具列表；错误日志长期存储；管理员 SQL 查询审计。

## 8. 后续实施路线图

### Phase 4B：创建云端 PostgreSQL

- 账户：Neon（或 Supabase）。
- 步骤：创建项目 → 保存 direct connection string → 创建角色/schema → `alembic upgrade head` → 导入演示数据 → 验证权限。
- 环境变量：`DATABASE_URL`、`PG_ADMIN_*`、schemas。
- 人工操作：是（创建数据库、设置密码）。
- 验收：`SELECT` 业务表成功；`factory_agent` 不能建表/写入；checkpoint 版本匹配。
- 费用：免费；超出额度会暂停，不自动扣费。
- 回滚：删除 Neon 项目或回滚到 branch/snapshot。

### Phase 4C：部署 FastAPI + LangGraph

- 账户：Render。
- 步骤：连接 GitHub → 选择 Dockerfile → 设置环境变量 → 部署 → 健康检查。
- 环境变量：`DATABASE_URL`、`PG_ADMIN_*`、`AUTH_SECRET_KEY`、`ADMIN_REGISTRATION_CODE`、`OPENAI_API_KEY`、`CORS_ORIGINS`。
- 人工操作：是（创建服务、填 secret）。
- 验收：`/api/health` 200；登录/注册/审批/聊天可用；SSE 正常。
- 费用：免费；注意冷启动和 750 小时。
- 回滚：Render rollback 到上一个 deploy。

### Phase 4D：部署 React Web

- 账户：Vercel。
- 步骤：导入仓库 → root directory `frontend` → build `npm run build` → output `dist` → 修改 `vercel.json` 的 Render URL → 部署。
- 环境变量：无（同源 `/api` rewrite）。
- 人工操作：是（首次导入、替换 URL）。
- 验收：HTTPS 页面可打开；登录、流式聊天、图表、移动端正常。
- 费用：Hobby 免费额度内。
- 回滚：Vercel instant rollback。

### Phase 4E：PC / Android / iPhone 浏览器测试

- 步骤：Chrome/Edge、Android Chrome、iPhone Safari 分别测试登录、切换会话、SSE、软键盘、横竖屏。
- 人工操作：是。
- 验收：无横向溢出；Composer 固定；SSE 不中断；刷新后恢复会话。
- 费用：0。
- 回滚：无代码回滚，必要时回退前端 deployment。

### Phase 5A：PWA

- 增加 manifest、图标、service worker、离线壳。
- 需要确认 API 缓存策略不缓存敏感响应。
- 验收：添加到主屏幕、离线显示壳、在线时正常。

### Phase 5B：Android APK

- 方案：Trusted Web Activity / Capacitor。
- 需要签名密钥、应用图标、隐私说明。
- 验收：安装后可登录并使用同一后端。
- 费用：Google Play 一次性注册费（如发布到商店）；内部测试可免费。

## 9. 明确回答

### A. 现在距离获得公网网址还差哪些步骤？

1. 创建 Neon 数据库并完成迁移/导入。
2. 在 Render 创建 Web Service 并配置环境变量。
3. 在 Vercel 导入前端并替换 `vercel.json` 的 Render URL。
4. 设置 `CORS_ORIGINS`（如果使用同源 rewrite 可只保留本地开发来源）。
5. 用管理员注册码创建第一个 ADMIN，审批测试用户。
6. 完成 Phase 4E 三端实测。

### B. 是否可以在不花钱的情况下完成？

可以，按推荐组合：

- Vercel Hobby 免费
- Render Free 512 MB
- Neon Free 1 GB
- LLM 由现有 API Key 付费/免费额度承担

注意：Render 冷启动约 1 分钟；Neon 超额度会暂停；LLM 成本仍需自行控制。

### C. 当前有哪些问题会阻止公网部署？

- 已修复：briefing/discovery 未认证；CORS 硬编码。
- 仍需人工：必须替换所有默认/示例密钥；必须创建云端数据库并迁移；必须配置 Render/Vercel。
- 需要实测：SSE 经 Vercel rewrite 是否保持流式；Render 免费实例冷启动对 SSE 首字节的影响。
- 需要接受：上传文件和日志在免费 Render 上不持久。

### D. 哪些工作可以在不修改 Agent 逻辑的情况下完成？

- 云端数据库、Alembic 迁移、演示数据导入。
- Render/Vercel 部署、环境变量、CORS、HTTPS。
- 登录/注册/审批、会话历史、Settings、主题。
- 安全 headers、限流（后续）、日志、备份策略。
- PWA/APK 外壳。

### E. 下一步最应该做什么？

先做 Phase 4B：创建 Neon 免费数据库，执行 `alembic upgrade head`，导入演示业务数据，验证 `factory_agent` 只读权限。数据库稳定后再部署 Render，最后接 Vercel。
