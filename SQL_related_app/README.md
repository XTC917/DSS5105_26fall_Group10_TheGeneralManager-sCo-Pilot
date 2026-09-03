# 工厂数据管理后台（SQL_related_app）

一个独立的小工具：把 `orders`、`production_log`、`workshops` 三份 CSV/Excel 通过网页上传进 SQLite，并提供查询接口。

**目前和主系统是分开的**，没有任何互相调用。主系统照常读 `data/*.csv`，这个文件夹自己维护一个数据库文件。想接通的话看下面「和主系统怎么连」。

> 文件夹为什么叫 `SQL_related_app`：Windows 不区分大小写，`SQL_related` 会和已有的 `SQL_Related` 指向同一个目录，只能换名字。

## 做了什么

一个上传后台，三件事：

1. **上传** — 网页上拖入 CSV/Excel，先预览前 10 行确认没传错，再确认导入。
2. **管理** — 列出三个数据源的行数和状态，可以翻页查看表里的数据。
3. **查询** — 给外部（比如 Agent）提供两个接口：拿表结构、跑只读 SQL。

安全和正确性上做了这些约束：

- 只认 `orders`、`production_log`、`workshops` 三张表，其他表名一律拒绝，表名不会被拼进 SQL。
- 上传的文件用随机名保存，原始文件名不参与路径拼接。
- 导入前按预期列校验，列对不上直接失败，不会污染已有数据。
- 重复导入同一份文件是幂等的，行数不会翻倍。
- 对外的 SQL 接口只能 SELECT，且只能读那三张表，`sqlite_master` 和上传记录表都读不到。
- 「删除」数据源只是标记停用，不会删表。

## 怎么跑

后端：

```powershell
cd SQL_related_app\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python init_db.py --force   # 建库，只需第一次
.\.venv\Scripts\python main.py
```

前端（另开一个终端）：

```powershell
cd SQL_related_app\frontend
npm install
npm run dev
```

界面 http://localhost:3000，接口文档 http://127.0.0.1:8000/docs。

数据库文件在 `backend/data/factory_data.db`，不进 git。

## 接口清单

给主系统或 Agent 调用的，主要是后两个：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/query/schema` | 返回一段文字版表结构（含列名、行数、样例、业务规则），可直接塞进 prompt |
| POST | `/api/query/execute` | body `{"sql": "SELECT ..."}`，只读，最多返回 100 行 |
| GET | `/api/admin/datasources/` | 三个数据源的行数和状态 |
| GET | `/api/admin/datasources/{id}/data?limit=&offset=` | 分页读某张表 |
| POST | `/api/admin/upload/preview` | 上传文件预览，不落库 |
| POST | `/api/admin/upload/import` | 导入，必须带 `table_name` |
| GET | `/api/admin/upload/status/{upload_id}` | 查导入进度 |

## 和主系统怎么连

先说清楚现状。主系统的 `backend/services/database.py` 里，`FactoryDB.initialize()` **每次启动都会删掉 `data/factory.db` 再从 `data/*.csv` 重建**。所以不能简单地让主系统去读这边的数据库文件——要么被覆盖，要么两边数据对不上。

两条路，选一条：

### 方案 A：这边导出 CSV，主系统照常重建（推荐）

经理在网页上传 → 这边写回 `data/orders.csv` 等三个文件 → 主系统重启（或再调一次 `init_db()`）就拿到新数据。

主系统一行代码都不用改，`FactoryDB` 的重建逻辑本来就是干这个的。

**还需要做的**：这边加一个导出步骤，导入成功后把表写回 `data/` 下的 CSV。现在没有这个功能。

### 方案 B：主系统直接连这边的数据库

改主系统的 `DB_PATH` 指向 `SQL_related_app/backend/data/factory_data.db`，并且**跳过 `initialize()`**，否则文件会被删掉重建。

三张表的表名和列名与主系统完全一致，`FactoryDB` 的那些 `SELECT * FROM orders` 之类的查询可以直接跑。两点差异要注意：

- 这边的表多一列 `created_at`（导入时间戳），`SELECT *` 会带出来。
- 主系统还有 `upload_history` 等几张后台自己用的表，Agent 不该读到，`/api/query/execute` 已经挡住了，但直连数据库没有这层保护。

### 只想让 Agent 查数

不用改数据库，直接调 `GET /api/query/schema` 拿表结构、`POST /api/query/execute` 跑 SQL 就行。这条路不需要两边共享文件。

## 目录

```
backend/
  config.py           表白名单、列定义、路径
  db.py               SQLite 连接和通用查询
  init_db.py          建表脚本
  file_importer.py    读文件、清洗、写库
  schema_service.py   表结构文本 + 只读 SQL 校验
  routers/            upload / datasource / query 三组接口
frontend/
  src/components/     DataUpload（上传）、DataSourceList（数据源）
```
