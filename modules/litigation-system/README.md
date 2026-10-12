# 法务诉讼业务平台（litigation-system）

前后端分离 monorepo。数据真值以 **638 条基线** 为准（`requirements/01`），设计验收
2026-08-13 签核通过（79 项 77✓ + 2 豁免）后进入开发，按 `docs/05` 与 SPEC §9 路线图
逐 Phase 交付可运行版本 + 验收记录。

## 仓库结构

```
litigation-system/
  frontend/          # Vite + React 18 + TS：src/{api,components,features,pages,stores,lib,theme}
  backend/           # FastAPI：app/{api,models,schemas,services,sync,clean,stats,ai,core}, tests/
  data/              # SQLite(WAL) 数据文件（.gitignore，卷外持久化）
  docker-compose.yml # api(uvicorn) + web(Nginx)；调度器并入 api 进程
  README.md
```

## 快速启动

### 本地开发（后端）

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

- API：<http://localhost:8000>（OpenAPI 文档 <http://localhost:8000/docs>）
- 健康检查：`GET /healthz`

### Docker（联调期）

```bash
cp .env.example .env   # 填入飞书凭证 / APP_TOKEN（决策 D2：凭证仅环境变量）
docker compose up --build
```

- 后端 `:8000` · 前端 `:8080`（Nginx 托管 SPA 并反代 `/api`）
- SQLite 库持久化在 `./data/app.db`（WAL 模式）

### 前端（Phase 1 起）

```bash
cd frontend
npm ci && npm run dev   # Vite dev server :5173，代理 /api → :8000
```

## 环境变量（仅 `.env`，不提交）

| 变量 | 说明 |
|------|------|
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书应用凭证（docs/01，App Secret 不落库） |
| `FEISHU_APP_TOKEN` | Base App Token |
| `FEISHU_TABLE_CASES` / `FEISHU_TABLE_SONGS` | 案件表 / 歌曲表 table_id |
| `APP_TOKEN` | 单用户 API 认证 Token（可选；未设置不开启鉴权） |
| `DATABASE_URL` | 数据库地址（默认 `sqlite:///<repo>/data/app.db`） |

未配置飞书凭证时应用照常启动（健康检查/字典/指标可用），同步引擎处于离线状态。

## 数据与种子

- 首次启动自动建表（决策 D1：`create_all`，不上 alembic）并注入种子：字典基座
  （11-dicts 页）、首版清洗规则 R01~R06、8 项指标口径 v1.0。
- 上线数据走同步引擎：`POST /api/v1/sync/run`（full | incremental | record），
  或等待 APScheduler 每日 03:00 增量 / 03:40 指标重算 / 周一 22:00 案例库快照（Phase 2 接入）。

## 测试

```bash
cd backend
pytest                      # 全量：同步幂等 / 清洗规则 / 指标口径 / API 契约
pytest tests -k clean       # 按域过滤
```

测试使用独立临时 SQLite，永不触碰 `data/app.db`。

## 验证基线（Phase 0 交付断言）

| 项 | 断言 |
|----|------|
| 案件总数 | 638 |
| 音集协占比 | 312 / 48.9% |
| 在办件数 | 42 |
| 判赔累计 | ¥1,284,600 |
| 胜诉率 A/B | 78.2% / 71.2% |
| 支持率 / 判赔率 | 6.4% / 31.2% |
| 单曲判赔 | ¥870 |
| 结案周期 | 186 天 |
| 脏标记 | 47 处 |

## 部署（thunderbox / 雷石盒子）

云平台部署统一走雷石 **thunderbox**：

- **本模块域名（唯一）**：`legal-litigation.tbox.ktvsky.com` · `access_mode=internal`
- **生产形态**：Docker Compose（api `:8000` + nginx web `:8080`）
- **代码来源**：**仅支持 GitHub** —— 部署前须先把代码迁移到 GitHub 仓库
- **平台信息**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`

> 🔴 **域名规则**：每个模块**有且仅有一个域名**，不得随意创建；域名统一登记 `shared/config/domains.yaml`（详见 `AGENTS.md §10.4.5`）。
> 📖 系统级部署手册：[docs/deployment-thunderbox.md](../../docs/deployment-thunderbox.md)

## 相关文档

- `requirements/01` 需求规格 · `spec/SPEC.md` 系统规格 · `docs/03` 后端详细设计
- `docs/05-设计验收清单.md` 验收记录（2026-08-13 签核放行）· `docs/04-交付物索引.md`
- 实现计划：`诉讼平台开发实现计划_task-8f4.md`（Task 会话缓存，非仓库文件）