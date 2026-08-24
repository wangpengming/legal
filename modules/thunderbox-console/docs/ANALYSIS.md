# Thunderbox Console · 雷盒控制台 — 详细分析

> 版本：v0.1（分析稿）· 日期：2026-08-24 · 关联：[原始需求](../requirements/01-原始需求.md) · [SPEC](SPEC.md) · [原型](../prototype.html)

---

## 1. 定位

**一句话**：把公司内部 PaaS 部署平台 Thunderbox 的 MCP 管理能力，包装成一个网页版可视化控制台，让非技术人员无需任何命令行 / MCP / Docker 知识即可完成应用的创建、部署、监控、运维全流程。

- **是什么**：Thunderbox 的「可视化操作台」，等价于 Vercel Dashboard / Railway Console / Coolify UI 的角色，但面向法务部非技术用户，更进一步做到「小白零门槛」
- **不是什么**：不是 Coolify 的替代品（底层不动）；不做平台级管理（用户管理/实例编排）；不绕过 MCP 直接调 Coolify API（保持单一上游契约，MCP 是官方唯一管理通道）
- **位置**：legal monorepo 第五个模块，与 court-doc-generator / litigation-system / case-intelligence / portal 并列，未来可被 portal 门户集成

**命名**：`thunderbox-console`（雷盒控制台）——「Thunderbox」= 平台名（雷盒/雷霆盒），「Console」= 控制台，中文「雷盒控制台」直接达意：一看便知是 Thunderbox 的图形化管理台。

## 2. 背景与动机

| 事实 | 现状 | 问题 |
|------|------|------|
| Thunderbox 能力 | 13 个 MCP 工具（应用部署/监控/控制/数据库四层） | 只存在于 MCP 协议层，非技术用户不可见 |
| 使用门槛 | 需懂 MCP（JSON-RPC、session、tools/call） | 小白无法使用 |
| 现有路径 | AI 代理（Qoder/Hermes）写 MCP 调用 → 用户口述需求 | 每次操作依赖 AI，流程长、不可自助 |
| 潜在用户 | 法务部 3-5 位非技术同事 + 管理者 | 想部署内部工具（如法务小应用）但无法自助 |

**动机**：让「把代码/镜像变成线上应用」从 AI 专属能力变成人人可点的按钮；同时为法务部后续自建小应用（内部工具、数据分析页等）提供自助部署通道。

## 3. 用户画像与场景

### 3.1 用户画像

| 画像 | 特征 | 典型诉求 | 设计对策 |
|------|------|---------|---------|
| **小白业务用户**（主要） | 不懂命令行、不知 MCP、怕点错 | 把同事给我的 Git 地址变成能打开的网页 | 向导式流程、每个选项都有通俗解释、状态一目了然（成功/失败/进行中） |
| **管理者** | 关心系统可用性与资源 | 看哪些应用在跑、有几个挂了 | 总览 Dashboard：统计卡 + 状态分布 + 健康点 |
| **技术同事**（次要） | 懂 Git/Docker | 快速部署复杂应用（私有仓、自定义端口、数据库） | 高级选项可展开：git_token、volumes、build 命令覆盖 |

### 3.2 核心场景（用户故事）

- **US-1 创建**：作为小白，我粘贴一个 Git 仓库地址（或 Docker 镜像名），跟着向导点 4 步，就能创建一个应用，并自动获得 `xxx.tbox.ktvsky.com` 域名 —— 每一步的选项都有大白话解释
- **US-2 部署**：作为用户，我点「部署」按钮，能看到构建进度、日志、最终成功或失败原因；失败时给出「看构建日志」的明确入口
- **US-3 监控**：作为管理者，我打开首页就能看到：几个应用在跑、几个异常、最近谁部署了什么
- **US-4 回滚**：作为用户，新版本发布后发现有问题，我在部署历史里点「回滚」一键回到上一个正常版本
- **US-5 数据库**：作为用户，我给应用加一个数据库，然后在网页里执行 SQL 查数据（只读模式防误操作），或提交一段带名字的迁移脚本安全变更表结构
- **US-6 配置**：作为用户，我改一个环境变量、切换访问模式（内部人员才能看 / 公开 / 白名单邮箱），3 秒生效
- **US-7 排查**：应用起不来时，我在页面上直接看运行日志和构建日志，而不是找人帮忙

## 4. 竞品参照系（学什么 / 避什么）

| 参照 | 优点 | 缺点 | 本模块取舍 |
|------|------|------|-----------|
| **Vercel Dashboard** | 极简、状态色清晰、引导文案好 | 面向开发者，术语多 | 术语全部中文化 + 通俗解释 |
| **Railway** | 一键模板、环境变量管理流畅 | 部署状态不直观 | 状态机可视化 + 日志联动 |
| **Coolify UI**（平台本身） | 功能全 | 面向开发者，复杂、深色参数化界面 | 只暴露 13 工具能力，砍掉平台级 |
| **Litestream/Dokploy** | 简洁 | 生态小 | 参考其部署状态时间线 |

**差异点（针对小白）**：
1. 全中文 + 术语解释气泡（「构建包是什么？」tooltip）
2. 向导式创建（默认值充分，直接可点「下一步」到底）
3. 状态机图形化（部署过程 = 进度条 + 阶段文案 + 日志流）
4. 有副作用操作一律二次确认（回滚/停止/改访问模式/清空环境变量）

## 5. 功能矩阵（MCP 13 工具 → 页面能力 → MoSCoW）

| MCP 工具 | 页面能力 | 优先级 |
|----------|---------|--------|
| thunderbox_query | 应用列表（卡片/表格）、详情、健康检查、运行日志 | Must |
| thunderbox_create | 创建应用向导（4 步：来源/构建/环境/域名权限） | Must |
| thunderbox_deploy | 详情页「部署」按钮 + 构建进度/日志流 | Must |
| thunderbox_rollback | 部署历史时间线 + 一键回滚（先列表后回滚） | Must |
| thunderbox_control | 启动/停止/取消构建按钮（状态上下文可用） | Must |
| thunderbox_config | 环境变量管理（新增/编辑/删除）、访问模式切换、白名单邮箱、协管员、ref | Must |
| thunderbox_check | 域名探测卡片 + 服务器资源面板 | Should |
| thunderbox_db_add | 应用详情「附加数据库」向导（sqlite/postgres 二选一） | Must |
| thunderbox_sql | SQL 工作台：ro/rw 切换、结果表格、行数上限提示 | Must |
| thunderbox_apply_migration | 迁移管理：新建迁移（名称+SQL）、历史列表、重放提示 | Should |
| thunderbox_describe_schema | Schema 查看器（表→列→主键树） | Should |
| thunderbox_list_tables | 表列表面板（Schema 查看器的轻量入口） | Should |
| thunderbox_db_remove | 「删除数据库」入口 → 说明页（MCP 禁用，引导管理后台） | Must（边界提示） |
| —（平台约定） | 删除应用 → 同样禁用提示 | Should |

**期望分层**：
- **MVP（P0）**：应用列表 + 创建向导 + 部署/日志 + 启停 + 回滚 + 环境变量 + 访问模式 + SQL 工作台（ro）+ db_add
- **P1**：SQL rw、迁移管理、schema 查看、域名探测、审计日志页
- **P2**：服务器资源面板、协管员管理、bypass_trusted_ips、portal 集成

## 6. 架构决策

### 6.1 三段式拓扑（核心决策）

```
┌─────────────┐   REST/JSON   ┌──────────────┐  MCP(HTTP)  ┌─────────────────┐
│  浏览器前端   │ ───────────→ │  FastAPI 网关  │ ──────────→ │ Thunderbox MCP  │
│ React+Vite  │ ←─────────── │  (持 token)   │ ←────────── │ api-box.tbox…  │
└─────────────┘  SSE/轮询    └──────────────┘   JSON-RPC   └─────────────────┘
```

**为什么前端不直连 MCP**：
1. **Token 安全**：Bearer token 只能存在后端，进前端 bundle = 泄露（任何人打开控制台源码就能拿走平台管理权）
2. **协议复杂度**：streamable HTTP 的 session 管理/SSE 解析放后端统一处理，前端只管业务
3. **可扩展**：后端可加审计、缓存、状态归一，前端不受 MCP 协议演进影响

**备选方案对比**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 前端直连 MCP | 无后端 | token 泄露、CORS、SSE 复杂 | ❌ |
| 后端封装 MCP（本方案） | token 安全、可审计、前端简单 | 多一层开发 | ✅ |
| 直接调 Coolify API | 能力更全 | 非官方通道、绕过 MCP 契约、token 权限模型不同 | ❌（保持唯一契约） |

### 6.2 MCP 客户端实现

- Python `httpx` 手写轻量客户端（initialize → notifications/initialized → tools/call，管理 `Mcp-Session-Id`）或官方 `mcp` SDK（`mcp.client.streamable_http`）；选型：优先官方 SDK，若依赖过重则 httpx 手写（协议简单，~150 行）
- 每个 REST 请求 → 新建/复用 MCP 会话 → tools/call → 结果归一为统一 JSON 返回前端
- 超时/重试：MCP 调用 30s 超时；部署类长任务返回 `estimated_seconds`+`poll_interval_seconds`，由前端轮询

### 6.3 REST API 设计（草案）

```
GET    /health                                    # 健康检查（§10.4.4：{"status":"ok","version":"x.y.z"}）
GET    /api/thunderbox/v1/apps                    # 应用列表（query list_scope=mine 默认）
GET    /api/thunderbox/v1/apps/{app_id}           # 应用详情
POST   /api/thunderbox/v1/apps                    # 创建应用（create）
POST   /api/thunderbox/v1/apps/{app_id}/deploy    # 部署（可选 ref）
POST   /api/thunderbox/v1/apps/{app_id}/rollback  # 回滚（可选 target → 列表）
POST   /api/thunderbox/v1/apps/{app_id}/control   # start/stop/cancel
PATCH  /api/thunderbox/v1/apps/{app_id}/config    # env/access_mode/白名单/协管/ref/volumes
GET    /api/thunderbox/v1/apps/{app_id}/logs      # 运行日志（?build=true 构建日志）
GET    /api/thunderbox/v1/apps/{app_id}/health    # 健康检查
GET    /api/thunderbox/v1/apps/{app_id}/db/tables
GET    /api/thunderbox/v1/apps/{app_id}/db/schema
POST   /api/thunderbox/v1/apps/{app_id}/db/add    # 附加数据库
POST   /api/thunderbox/v1/apps/{app_id}/db/sql    # {sql, mode} → {rows,rowCount,columns,truncated}
POST   /api/thunderbox/v1/apps/{app_id}/db/migrate {name, sql}
GET    /api/thunderbox/v1/check/domain?name=xxx   # 域名探测
GET    /api/thunderbox/v1/check/resources         # 服务器资源
GET    /api/thunderbox/v1/audit                   # 审计日志（本模块 SQLite）
```

### 6.4 状态机（前端核心模型）

```
                    ┌────────────┐
      deploy ─────→ │  building  │ ──→ deploying ──→ running ✅
      (创建后)       └────────────┘                       │
                                             build_failed ❌ → 查构建日志
  running ──stop──→ stopped ──start──→ running
  building ──cancel──→ cancelled
```

- 归一化：MCP 返回的原始状态 → 前端统一枚举（running/stopped/building/deploying/build_failed/cancelled/unknown）
- 轮询策略：部署中 2-5s（按 poll_interval_seconds）；稳定态 30s 后台静默刷新
- 日志联动：building/failed 时详情页自动展开「构建日志」面板并 auto-scroll

### 6.5 数据存储

- 审计日志：SQLite（本模块 `data/audit.db`，含 .gitignore 规范中的 data/ 忽略）：action/app_id/operator/result/time
- 不做业务数据缓存（MCP 是唯一事实源）；列表页可做 30s 内存缓存降载

### 6.6 端口与基础设施（§10.4 合规）

- 端口申请：`backend: 8002`（8000/8001 已占用）、`frontend: 18503`（18502 已占用）→ 登记 `shared/config/ports.yaml`
- bin/ 4 件套（start/stop/restart/status × .py/.sh/.bat）、PID+日志 `.run/`、`/health` 8s 内可探测
- 生产形态：后端托管 `frontend/dist/` 单端口访问（对齐 court-doc-generator §6 方案）

## 7. 安全分析

| 风险 | 等级 | 对策 |
|------|------|------|
| Token 泄露（前端 bundle/日志） | 🔴 高 | token 仅后端 .env；前端零 token；后端日志遮罩（`Bear***`）；.env 入 gitignore |
| 误操作（回滚/停服/改配置） | 🟠 中 | 全部二次确认弹窗；审计日志可追溯 |
| SQL 误写 | 🟠 中 | 默认 `mode=ro`；rw 需显式切换 + 确认；SQL 工作台只读默认文案 |
| 白名单/访问模式误配导致应用公开 | 🟠 中 | 切换 public 时明确警示「互联网可访问」+ 确认 |
| MCP 会话劫持 | 🟡 低 | token 与 MCP session 均后端持有；REST 仅监听 127.0.0.1（内网部署时自行收紧） |
| 前端 XSS（日志/描述渲染） | 🟡 低 | 日志/文本一律 textContent 渲染，禁 HTML 注入 |
| 私有仓库 git_token 误传 | 🟢 低 | 仅创建时输入；后端不透传该值到日志/审计（MCP 侧也不落库） |

## 8. 关键交互设计原则（小白友好）

1. **默认值合理**：向导每步都有安全默认（如 nixpacks、端口按 build_pack 自动推导），用户可直接一路「下一步」
2. **术语解释**：每个技术词旁带 ⓘ tooltip（「构建包：决定怎么把你的代码变成可运行的应用」）
3. **状态可感知**：一切异步操作都有进度（部署进度条/轮询倒计时/日志流）；失败永远给「为什么 + 怎么办」
4. **大胆但不危险**：主操作按钮大而清晰；破坏性操作（回滚/停止/删除类）红色 + 确认 + 说明影响范围
5. **零模型要求**：不出现 MCP/Coolify/JSON-RPC 字样（内部名词如「构建包」保留但解释）；所有 URL/端口等由系统拼接

## 9. 风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| MCP 协议演进（v0.2.0 变动） | 低 | 网关层单一封装点；MCP 变更只改 client 适配层 |
| 平台侧无应用时演示效果差 | 确定 | 原型内置模拟数据 + 状态机演示模式；实现版空状态引导页 |
| 访问模式/白名单语义理解偏差 | 中 | SPEC 逐字段标注 MCP 原始参数映射；验收时用真实环境验证 |
| 部署长任务（构建 10min+） | 中 | 前端轮询 + 「离开页面通知」；部署不依赖页面停留（后端无状态，轮询可恢复） |
| 小白创建后不会用 | 中 | 创建成功页给「访问链接」「首次部署指南」引导 |

## 10. 演进路线

| 阶段 | 内容 | 状态 |
|------|------|------|
| **M0 立项** | 分析 + SPEC + 原型图（本轮） | 🔄 进行中（待评估） |
| **M1 MVP** | backend 网关（13 工具全覆盖 API）+ frontend（列表/创建向导/详情/日志/SQL ro）+ bin 4件套 + 测试 | 待立项 |
| **M2** | 迁移管理 UI、schema 查看、域名/资源探测、审计日志页、SQL rw | 待立项 |
| **M3** | portal 门户集成（注册表 + 健康点）、协管员/白名单深度管理、部署模板库 | 远期 |

## 11. 待用户确认

1. **模块名**：thunderbox-console（雷盒控制台）是否 OK？（备选：tbox-console / deploy-dashboard）
2. **认证**：v0.1 无登录（本地/内网工具）？还是需要 PIN/账号？（建议无登录，与 portal 对齐，统一认证远期再说）
3. **部署目标**：本控制台将来是否也部署到 Thunderbox（dogfooding）？（建议是：`console.tbox.ktvsky.com`，spa + nixpacks）
4. **语言**：全中文界面？（建议全中文 + 术语 tooltip）