# Phase 4A — 公网安全审计

> 范围：仅审计与部署相关的 HTTP、认证、数据库、上传、日志和成本风险。
> 未修改 Agent Routing / Answerability / Prompt / Tool Calling / Evaluation。

## P0 — 公网开放前必须完成

### P0-1 `/api/briefing` 与 `/api/discovery` 未要求认证

- 现象：两个读取接口直接 `get_db()` 返回业务数据，没有 `Depends(get_current_user)`。
- 风险：任何知道 URL 的人都能读取工厂订单风险/生产问题摘要。
- 最小修复：已加入 Bearer 认证依赖；前端 `fetchBriefing` / `fetchDiscovery` 本来就发送 `Authorization`，不会破坏正常前端。
- 验证：`tests/test_api.py` 增加未认证 401 用例。

### P0-2 CORS 白名单硬编码为 localhost

- 现象：`allow_origins` 只包含 `http://localhost:5173` / `127.0.0.1:5173`。
- 风险：生产域名无法访问；如果临时改成 `*` 且 `allow_credentials=True`，浏览器会拒绝或形成不安全配置。
- 最小修复：已改为 `CORS_ORIGINS` 逗号分隔环境变量；未设置时回退到本地开发来源。
- 要求：生产只填 Vercel 生产/预览域名，不要使用 `*`。

### P0-3 云端密钥与默认凭据必须全部替换

- `.env.example` 中保留了本地演示用的 `factory_admin/admin`、`factory_agent/agent` 示例。
- 风险：如果直接复制到云环境，数据库会被弱口令保护。
- 要求：
  - 云端数据库使用随机强密码；
  - `AUTH_SECRET_KEY` 至少 32 字符随机值；
  - `ADMIN_REGISTRATION_CODE` 使用独立随机值；
  - 不要把 `.env` 或填好的 `deploy/env.cloud.example` 提交到仓库；
  - Render/Vercel 只通过 Secret/Environment 面板注入。

### P0-4 不允许匿名使用 LLM

- 当前 `/api/chat` 和 `/api/chat/stream` 已经要求 `get_current_user`，匿名用户不能直接调用。
- 但仍需保证：
  - 注册后默认 `PENDING`，管理员审批后才可登录；
  - 不公开 `ADMIN_REGISTRATION_CODE`；
  - 只把网址发给受信任的测试同学。
- 如果未来开放匿名体验，必须先加限流和预算上限。

## P1 — 朋友测试前建议完成

### P1-1 登录/注册/聊天缺少频率限制

- `/api/auth/login`、`/api/auth/register`、`/api/chat*` 没有应用层 rate limit。
- 风险：暴力尝试密码、已授权账号刷 LLM 费用。
- 建议：
  - 在 Render/Cloudflare/Vercel 层加 IP/路径限流；
  - 在 FastAPI 里加简单内存限流（单实例免费 Render 可行）；
  - OpenAI 控制台设置项目预算和用量告警。

### P1-2 JWT 存储在 localStorage

- 前端 `authHeaders()` 从 `localStorage` 读取 token。
- 风险：一旦出现 XSS，token 可被读取。
- 现状：token TTL 默认 12 小时，没有 refresh/revocation。
- 建议 Phase 4B/4C：迁移到 httpOnly + Secure + SameSite cookie，或至少加 CSP 和短 TTL。

### P1-3 上传文件与日志不持久

- `backend/uploads` 和 `logs/app.log` 在 Render Free 上都是 ephemeral。
- 风险：重新部署/休眠后上传记录丢失；长期日志无法审计。
- 建议：
  - 上传改存 S3/R2/Supabase Storage；
  - 日志使用 Render log stream 或外部日志服务；
  - 免费阶段明确告知测试用户不要上传重要文件。

### P1-4 上传限制是“读入内存后检查”

- `_read_limited` 先 `await file.read()` 再判断 100 MB。
- 风险：免费 512 MB RAM 下，大文件可能造成内存压力。
- 建议：改为分块读取/流式写入，或把上限降到 10–20 MB。

### P1-5 免费实例冷启动影响 SSE 首字节

- Render Free 15 分钟无流量休眠，冷启动约 1 分钟。
- 风险：用户第一次打开聊天会等待较久；Vercel rewrite 代理可能增加超时/缓冲风险。
- 建议：Phase 4E 实测；必要时前端显示“服务正在唤醒”提示。

## P2 — 后续优化

- `/api/health` 暴露工具列表与 `llm_configured`，信息价值低；可考虑生产环境只返回 `ok`。
- 管理员 SQL 查询已限制单条 SELECT + read-only transaction，但仍建议记录审计日志。
- 错误日志可能包含问题文本/堆栈；不要记录 Authorization、密码、API Key、完整 DB URL。
- 免费数据库连接数有限；checkpoint pool 当前 `min_size=1,max_size=4`，朋友测试可接受，但需监控连接。
- 缺少自动化安全测试（401/403、CORS、上传大小、限流）。

## 已确认安全的正向点

- 管理员 API 使用 `require_admin`。
- Data Management 上传/查询/删除均要求 ADMIN。
- SQL 查询只允许单条 SELECT，并设置 read-only transaction、5 秒 statement timeout。
- 密码使用 Argon2id。
- 会话按 `user_id` owner 校验；`get_owned_conversation` 防止横向越权。
- proposed action 有 `_turn_id` 归属校验。
- `.gitignore` 已忽略 `.env`、`logs/`、`data/*.db`、`frontend/dist/`。
