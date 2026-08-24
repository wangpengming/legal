# Thunderbox Console · 雷盒控制台 — 方案设计（SPEC）

> 版本：v0.1（原型评估稿）· 日期：2026-08-24 · 状态：待用户评估
> 关联：[ANALYSIS](ANALYSIS.md) · [原始需求](../requirements/01-原始需求.md) · [原型](../prototype.html)
> 本文档为**方案设计级** SPEC；原型通过后另出实现级 SPEC（含组件树/TDD 清单）

---

## 1. 概述

**雷盒控制台**是 Thunderbox PaaS 平台的网页可视化管理系统：前端（React）→ 后端网关（FastAPI，持有 token）→ Thunderbox MCP（13 工具）三段式，把应用的创建/部署/回滚/启停、环境配置、数据库 SQL/迁移、日志查看、域名探测全部搬到页面上，面向非技术小白用户。

- 模块名：`thunderbox-console`（中文：雷盒控制台）
- 版本：0.0.1（planning）→ 1.0.0（MVP 上线）
- 端口：backend 8002 · frontend 18503（dev）/ 生产单端口由后端托管 dist

## 2. 设计目标

| 目标 | 说明 | 度量 |
|------|------|------|
| 小白可用 | 零命令行、零 MCP 知识；所有操作点鼠标完成 | 新用户不看文档可完成「创建→部署→查看」 |
| 全量覆盖 | 13 个 MCP 工具全部有对应可视化入口 | 工具覆盖度 13/13（含禁用项的引导页） |
| 安全围墙 | token 不出后端；写操作全审计；风险操作二次确认 | 前端 bundle 无 token；审计 100% 写操作 |
| 状态透明 | 部署/构建过程可视化，失败可自助排查 | 状态机 6 态全映射；失败页含构建日志入口 |
| 工程合规 | 遵循 AGENTS.md §10.4 模块基础设施 | bin 4件套 / /health / ports.yaml / 路由规范 |

## 3. 架构拓扑

```
┌────────────────┐  REST/JSON   ┌──────────────────┐  MCP streamable HTTP  ┌──────────────────┐
│  React 前端     │ ───────────→ │  FastAPI 网关      │ ───────────────────→ │  api-box.tbox…  │
│  Vite + TS     │ ←─────────── │  backend/app      │ ←─────────────────── │  thunderbox v0.2 │
│  状态机/轮询    │   JSON/SSE   │  ├─ mcp_client.py │    JSON-RPC/session  │                  │
└────────────────┘              │  ├─ api/apps.py   │                      └──────────────────┘
                                │  ├─ api/db.py     │
                                │  ├─ audit.py(SQLite)│
                                └──────────────────┘
```

**三层职责**：
- **前端**（React 18 + Vite + TS）：页面渲染、状态机、轮询、表单校验、二次确认；零敏感信息
- **网关**（FastAPI + httpx）：唯一 MCP 会话管理点；13 工具 → 20+ REST 端点；token 注入与遮罩；审计落库；状态归一化（原始状态 → 6 枚举）
- **上游**（Thunderbox MCP）：唯一事实源，本模块不做业务数据缓存

### 3.1 关键技术决策（决策记录）

| # | 决策 | 选择 | 备选 | 理由 |
|---|------|------|------|------|
| D1 | 前端直连 vs 网关代理 | **网关代理** | 前端直连 MCP | token 安全（红线）、SSE/session 复杂度收敛、可审计 |
| D2 | MCP 客户端实现 | **httpx 手写轻量 client（~150 行）** | 官方 mcp SDK | 协议简单（4 种消息）、依赖可控；SDK 若过重则弃用 |
| D3 | 后端框架 | **FastAPI** | Flask | 与 litigation-system / court-doc-generator 对齐；自动 OpenAPI |
| D4 | 前端框架 | **React 18 + Vite + TS** | 原生/静态 | 与现有两模块技术栈复用；组件生态（表格/表单） |
| D5 | 状态轮询 | **前端轮询 REST**（部署中 2-5s，稳定 30s） | WebSocket/SSE | 简单可靠；MCP 本身无推送 |
| D6 | 审计存储 | **SQLite（data/audit.db）** | 无/MCP 侧 | 写操作追溯必需；本地零依赖 |
| D7 | 生产形态 | **后端托管 frontend/dist + 单端口 8002** | dev 双端口 | 一键部署到 Thunderbox/dogfooding 场景 |
| D8 | 视觉风格 | **深色科技风（Vercel/Railway 系）** | portal 商务浅色 | 部署控制台气质差异 + 用户「高端大气」诉求 |

## 4. 核心领域模型

### 4.1 应用（App）—— 归一化视图

```yaml
App:
  id: string            # MCP 返回的 app_id
  name: string
  domain: string        # xxx.tbox.ktvsky.com（前端拼接展示）
  status: string        # 归一化 6 枚举（见 4.2）
  source: { type: git_repo|docker_image, url, ref }
  build_pack: dockerfile|nixpacks|static|spa
  port: int
  access_mode: public|internal|restricted
  db: { attached: bool, engine: sqlite|postgres|null }
  volumes: [string]
  created_at, updated_at: string
  deployment: { id, commit?, started_at?, duration?, logs_url? }
```

### 4.2 状态机（归一化）

```
unknown ─┬─ 创建成功 → idle（未部署）
         └─ 部署 → building → deploying → running ✅
                                          └→ build_failed ❌（+ 构建日志入口）
running ──stop──→ stopped ──start──→ running
building/deploying ──cancel──→ cancelled
```

| 原始状态（MCP） | 归一化 | 前端展示 |
|----------------|--------|---------|
| building / deploying | building / deploying | 进度条 + 阶段文案 + 日志流 |
| running | running | 绿色 ✅ + 访问链接 |
| build_failed | build_failed | 红色 ❌ + 「查看构建日志」 |
| stopped / cancelled | stopped / cancelled | 灰色 |
| 未知/缺失 | unknown | 灰色问号 |

### 4.3 审计事件

```yaml
AuditEvent: { id, ts, action, app_id, app_name, operator(可选), detail(json), result: ok|error, msg }
# 写操作全记录：create / deploy / rollback / start / stop / cancel / config(env/access/volume) / db_add / sql_rw / migrate
```

## 5. API 契约（网关 → 前端）

### 5.1 REST 端点（20+）

| 方法 | 路径 | 对应 MCP | 说明 |
|------|------|---------|------|
| GET | /health | — | `{"status":"ok","version":"0.1.0"}`（§10.4.4） |
| GET | /api/thunderbox/v1/apps | query | 列表（list_scope=mine 默认；支持 ?scope=） |
| GET | /api/thunderbox/v1/apps/{id} | query | 详情（含状态、部署信息） |
| POST | /api/thunderbox/v1/apps | create | 创建（不部署）；body=AppCreate |
| POST | /api/thunderbox/v1/apps/{id}/deploy | deploy | body 可选 {ref}；返回 estimated_seconds/poll_interval |
| POST | /api/thunderbox/v1/apps/{id}/rollback | rollback | body 可选 {target}；无 target 返回历史列表 |
| GET | /api/thunderbox/v1/apps/{id}/history | rollback(列表) | 部署历史（回滚目标选择器数据源） |
| POST | /api/thunderbox/v1/apps/{id}/control | control | body {action: start\|stop\|cancel} |
| PATCH | /api/thunderbox/v1/apps/{id}/config | config | body 见 5.2；env 增量合并/删除/访问模式/白名单/协管/ref/卷 |
| GET | /api/thunderbox/v1/apps/{id}/logs | query | ?build=true\|false&since=；返回日志文本 |
| GET | /api/thunderbox/v1/apps/{id}/health | query | 健康检查（health=true） |
| GET | /api/thunderbox/v1/apps/{id}/db/tables | list_tables | 表名列表 |
| GET | /api/thunderbox/v1/apps/{id}/db/schema | describe_schema | 完整表结构 |
| POST | /api/thunderbox/v1/apps/{id}/db/add | db_add | {engine: sqlite\|postgres, sqlite_path?} |
| POST | /api/thunderbox/v1/apps/{id}/db/sql | sql | {sql, mode: ro\|rw} → {rows,rowCount,columns,truncated} |
| POST | /api/thunderbox/v1/apps/{id}/db/migrate | apply_migration | {name, sql} → {applied, reason?} |
| GET | /api/thunderbox/v1/apps/{id}/db/migrations | — | 迁移历史（本地审计补充或 MCP 查询） |
| GET | /api/thunderbox/v1/check/domain | check | ?name=xxx → {available, owner?} |
| GET | /api/thunderbox/v1/check/resources | check | 服务器资源概览 |
| GET | /api/thunderbox/v1/audit | — | 审计日志列表（分页） |
| DELETE | /api/thunderbox/v1/apps/{id} | — | **不实现**：403 + 指引（对应 MCP 禁用，引导管理后台） |

### 5.2 AppCreate / Config 参数映射（前端表单 → MCP 直通）

```yaml
AppCreate:
  name / subdomain: string            # 向导第1步校验子域可用性（check）
  source_type: git_repo | docker_image
  source_url: string                  # HTTPS Git URL / Docker 镜像名
  ref?: string
  git_token?: string                  # 仅私有仓；不透传到审计
  build_pack?: dockerfile|nixpacks|static|spa   # 默认 nixpacks
  port?: number                       # 默认按 build_pack（nginx=80/node=3000/python=5000/go=8080）
  install_command? / build_command? / start_command? / publish_directory?  # 高级覆盖
  volumes?: [string]                  # "source:target[:ro]"
  database?: false|true|{type: sqlite|postgres, sqlite_path?}
Config:
  env_vars / remove_env: object|list  # 增量合并
  access_mode: public|internal|restricted
  add_emails / remove_emails: [email]
  manager_action + manager_email
  ref?: string
  volumes?: [string]                  # 破坏性替换 → 前端强确认
  bypass_trusted_ips?: bool
```

## 6. 页面结构（信息架构）

```
雷盒控制台（深色科技风）
├── ① 总览 Dashboard
│    统计卡（应用总数/运行中/停止/构建失败）· 状态分布条 · 最近部署活动 · 平台资源卡 · 域名快速探测
├── ② 应用列表
│    卡片/表格双视图切换 · 搜索（名称/域名/来源）· 状态筛选 · 行操作（详情/部署/启停/访问）
├── ③ 创建应用向导（4 步）
│    S1 来源：Git 仓库 / Docker 镜像（单选卡片）；URL + （私有仓开关 → Token 输入 + 说明）
│    S2 构建：build_pack 四种模式卡片（各带通俗说明 + 默认端口）→ 高级选项（命令覆盖/端口/发布目录/卷）
│    S3 环境与数据：环境变量键值列表（可增删）+ 数据库（无/SQLite/Postgres）+ 卷摘要
│    S4 域名与权限：子域预填（自动名称）+ 可用性实时探测 + 访问模式三选一 + 最终确认 → 创建
├── ④ 应用详情
│    Header：状态徽章 + 域名链接 + 主操作（部署/停止-启动/取消构建/回滚）
│    Tabs：概览（来源/构建/端口/卷/访问模式摘要 + 部署历史时间线）
│         │ 日志（构建日志/运行日志 切换，终端风格 auto-scroll）
│         │ 配置（环境变量表 CRUD + 访问模式 + 白名单邮箱 + 协管员 + ref + 卷（破坏性警告））
│         └ 数据库（未附加 → 「附加数据库」引导；已附加 → 表列表 / Schema / SQL 工作台 / 迁移）
├── ⑤ 数据库工作台（详情页内嵌 or 独立页）
│    SQL 编辑器（浅色代码主题、ro/rw 切换 + 确认）· 结果表格（列自适应 + 1000 行上限提示）·
│    迁移面板（历史列表 + 新建迁移表单 {name, sql}）
├── ⑥ 工具：域名探测 / 资源监控（thunderbox_check 可视化）
├── ⑦ 审计日志
└── ⑧ 关于/设置（MCP 连接状态、版本、帮助）
```

**全局**：侧边导航（图标+中文名）· 顶部搜索 · 操作 Toast · ConfirmDialog（危险操作红色）· ⓘ 术语 tooltip

## 7. 安全设计（实现约束）

1. token 仅 `backend/.env`（`THUNDERBOX_API_URL` / `THUNDERBOX_TOKEN`），.gitignore 屏蔽；前端无任何凭证
2. 网关日志/审计遮罩：`Authorization` 一律 `Bear***`；git_token 不入审计 detail
3. SQL 默认 `mode=ro`；rw 需前端显式切换 + 确认文案「可修改数据库数据」
4. 破坏性操作确认矩阵：回滚 / 停止 / 取消构建 / 切换 public / 替换 volumes / 删除 env → ConfirmDialog
5. 渲染安全：日志、SQL 结果、描述全部 `textContent` 渲染（防 XSS）
6. 监听范围：默认 127.0.0.1；部署到服务器时由部署者收紧（内网 + 可选反代认证）
7. 审计：写操作 100% 落库（含结果 ok/error）；审计页仅限本机/内网访问

## 8. 原型验收清单（本轮）

- [ ] prototype.html 单文件自包含，浏览器打开零报错、零外部依赖（离线可用）
- [ ] 深色科技风、中文界面、所有操作可视化
- [ ] 覆盖 7 大页面：总览/列表/创建向导/详情/日志/数据库工作台/审计
- [ ] 状态机演示：building → deploying → running / build_failed 切换
- [ ] 模拟数据支撑：3-4 个模拟应用（不同状态）、部署历史、日志流、SQL 结果
- [ ] 交互可用：向导可走完 4 步、Tab 切换、SQL 可执行（模拟）、确认弹窗触发
- [ ] 术语 tooltip、空状态（无应用）、禁用项引导（删除数据库 → 指引页）

## 9. 里程碑与交付物

| 里程碑 | 交付物 | 退出条件 |
|--------|--------|---------|
| M0 立项（本轮） | ANALYSIS / SPEC / prototype.html / 模块注册 | **用户评估通过** |
| M1 MVP | backend（mcp_client + 20+ REST + audit + /health）、frontend（7 页面）、bin 4件套、.env.example、pytest ≥ 15、文档 | 真实 Thunderbox 端到端：创建→部署→查询→回滚 |
| M2 增强 | 迁移管理、schema 查看、资源探测、审计页、SQL rw | 验收清单全绿 |
| M3 运营 | 部署到 Thunderbox（dogfooding）、portal 集成、模板库 | 生产可用 |

## 10. 风险与缓释（补充 ANALYSIS §9）

| 风险 | 缓释 |
|------|------|
| MCP 返回状态字段与文档不符 | mcp_client 做宽松解析 + 归一化兜底 unknown；联调期以真实响应校准 |
| 部署长任务轮询中断 | 前端恢复轮询（按 app_id 继续）；提供「刷新」手动入口 |
| 模拟数据误导原型评估 | 原型每页标注「⚠ 原型模拟数据」；实现版以网关真实数据替换 |
| 端口 8002 冲突 | start.py 端口检测（§10.4.2）；冲突时提示而非自行换端口 |