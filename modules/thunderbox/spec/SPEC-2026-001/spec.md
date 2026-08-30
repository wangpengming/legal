# Thunderbox Console · SPEC-2026-001 — 雷盒控制台 MVP

> **Spec ID**：SPEC-2026-001
> **版本**：1.0.0
> **状态**：Draft
> **来源**：prototype.html + PLAN-A.md + ANALYSIS.md + MCP-CAPABILITY-SPEC.md
> **关联**：spec/context.md · docs/PLAN-A.md · docs/ANALYSIS.md · prototype.html
> **不访问**：Confluence / Jira（Phase 4 Jira 同步跳过）

---

## 1. Outcomes（可观测结果）

| # | Outcome | 验证方式 |
|---|---------|---------|
| O1 | 用户在浏览器打开 `http://localhost:18502` 能看到应用列表（来自真实 MCP） | 浏览器访问 /health 200 |
| O2 | 用户完成 4 步向导后成功创建一个 `legal-thunderbox-test-*` 应用 | `thunderbox_query` 返回新 app |
| O3 | 用户点击「部署」后能看到状态推进（building → running） | 日志端点返回非空 |
| O4 | 用户点击「回滚」后应用回到上一版本 | 部署历史返回非空 |
| O5 | 用户可在 SQL 工作台执行 `SELECT` 并看到结果 | 返回 rows/columns |
| O6 | bin/start.py 启动后 /health 8 秒内返回 200 | `curl localhost:18502/health` |
| O7 | Docker 镜像在 Thunderbox 部署后外部可访问 `legal-thunderbox.tbox.ktvsky.com` | `curl https://legal-thunderbox.tbox.ktvsky.com/health` |

---

## 2. Scope

### In Scope

- FastAPI 后端（现有 18 端点补测试 + 新增审计端点）
- MCP 封装层（现有 thunderbox_mcp.py 补 characterization test）
- 前端 HTML（从 prototype.html 演进，直接 FastAPI 静态托管）
- bin 4 件套（start / stop / restart / status）
- Dockerfile（单容器，Thunderbox 部署）
- 本地开发 + Thunderbox 部署到 `legal-thunderbox.tbox.ktvsky.com`
- 测试覆盖：后端 MCP 层 ≥ 70%，REST 端点 ≥ 80%，关键路径（创建→部署→回滚）≥ 90%

### Out of Scope

- 删除应用（`thunderbox_db_remove` 禁用引导已有，不做真实删除）
- 域名探测/资源探测 UI（`thunderbox_check` MCP 已有）
- 模板库、通知中心、⌘K 命令面板
- Portal 集成、用户认证
- React 前端（v1 用 HTML 原型演进，省前端构建步）

---

## 3. Constraints（约束）

| 类别 | 约束 |
|------|------|
| **技术栈** | Python 3.11 + FastAPI + http.client（MCP）+ HTML（原型演进） |
| **部署** | 单 Docker 镜像（nginx:alpine 静态托管 + uvicorn）；参考 court-doc-generator 部署经验 |
| **安全** | Bearer token 仅 `.env`（不写入代码）；审计 100% 写操作；日志遮罩 token |
| **测试隔离** | 所有 pytest 只操作 `legal-thunderbox-test-*` app；`legal-thunderbox.tbox.ktvsky.com` 仅读操作 |
| **Dockerfile** | PyPI 清华镜像（`pypi.tuna.tsinghua.edu.cn`）；apt 默认源；端口一致 EXPOSE/CMD/thunderbox_create |
| **Volumes** | `data/`（SQLite 审计）必须挂载（ephemeral 容器数据不丢） |
| **代码规范** | 遵循 AGENTS.md §5 命名规范（英文文件名/函数名）；中文仅 UI 文案/文档 |
| **TDD** | 纯新增代码 RED-GREEN-REFACTOR；已有代码 characterization test 锁定行为 |
| **Git** | 本地开发：`modules/thunderbox/`；Thunderbox 部署源：`/Users/pengming/code/work/me/legal-thunderbox/`（开发完成后同步） |

---

## 4. Decisions（技术决策）

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| D1 | MCP 客户端 | `http.client.HTTPSConnection` 手写（已有代码） | 协议简单，依赖可控 |
| D2 | 前端技术 | HTML（原型演进）+ FastAPI 静态托管 | 跳过 React 构建步，快速交付；原型已验证 UI |
| D3 | 后端部署端口 | 18502（避开 8501 默认 / 8000-8001 已占用） | §10.4.2 端口规范 |
| D4 | 审计存储 | SQLite（`data/audit.db`） | 本模块写操作全记录；无外部依赖 |
| D5 | 生产形态 | 后端托管 `frontend/` 单目录 + 单端口 | 与 court-doc-generator 对齐 |
| D6 | 破坏性操作 | 回滚 ✅ / 停止 ✅ / 改 public ✅ / 删除 ❌ | 参照竞品安全边界 |
| D7 | SQL 安全 | 默认 `mode=ro`；rw 需前端显式切换 + 确认 | 参照 ANALYSIS §7 |
| D8 | 测试用 MCP | 真实 MCP（非 mock） | 验证 MCP 契约 + session 管理正确性 |
| D9 | 代码同步策略 | 开发完 `rsync` 到 `legal-thunderbox/` → push GitHub | Thunderbox 只能从 GitHub 拉源码 |
| D10 | Volumes 命名 | `legal-thunderbox-data` | 与 app 名一致，生命周期绑定 |

---

## 5. Epic

### Epic-1: Thunderbox Console MVP — 雷盒控制台完整交付

- **概述**：把 Thunderbox MCP 能力包装成可视化网页，让非技术人员无需 MCP 知识即可完成应用创建、部署、回滚、配置、数据库运维全流程；同步支持 AI Agent 通过 REST API 调用相同 MCP 能力。
- **Outcomes**：
  - 浏览器打开控制台看到真实应用列表
  - 走完创建向导后 Thunderbox 侧新增应用
  - 部署后状态从 building 推进到 running
  - 回滚后应用回到上一版本
  - SQL 工作台可执行只读查询
  - bin/start.py 启动 /health 8 秒内 200
  - Docker 镜像在 Thunderbox 部署后外部可访问

---

## 6. Stories

---

### Story-1: 后端基础设施与测试体系

- **Estimate**：8 SP
- **AC-1**: Given 开发者执行 `cd modules/thunderbox && pytest backend/tests/ -v` When 测试套件运行 Then 所有测试通过（≥ 15 个用例，覆盖 MCP 层 + REST 端点）
- **AC-2**: Given 开发者执行 `python bin/start.py` When 服务启动 Then `/health` 返回 `{"status":"ok","version":"1.0.0"}`，PID 写入 `.run/thunderbox.pid`，日志写入 `.run/thunderbox.log`
- **AC-3**: Given 服务运行中 When 开发者执行 `python bin/stop.py` Then 进程被停止，PID 文件被删除
- **AC-4**: Given 服务运行中 When 开发者执行 `python bin/status.py` Then 显示端口状态、PID、健康检查结果，退出码 0
- **Dependencies**：None

#### Subtask-1.1: MCP 层 characterization test

- **Files**：
  - Create `backend/tests/test_thunderbox_mcp.py`
- **Test**：`backend/tests/test_thunderbox_mcp.py`
- **Technical Notes**：
  - 用 `responses` library mock HTTP（不 mock MCP 层内部），验证 `ThunderboxMCP.list_apps()` 发送正确的 JSON-RPC 请求、解析 SSE body、返回 `list[App]`
  - 用 characterization test 锁定现有行为（已有代码行为即为正确行为）
  - 覆盖：`list_apps`、`get_app`、`check_domain`、`get_app_logs`、`get_build_logs`
  - conftest.py 中 `THUNDERBOX_TOKEN` 从 env 读取，mock 响应包含 `legal-thunderbox.tbox.ktvsky.com` app（只读，无破坏）

#### Subtask-1.2: REST 端点 characterization test

- **Files**：
  - Create `backend/tests/test_api.py`
- **Test**：`backend/tests/test_api.py`
- **Technical Notes**：
  - 用 `TestClient`（FastAPI）+ `responses` mock MCP HTTP，验证 18 个端点返回结构正确
  - 覆盖：/health、/api/apps（GET/POST）、/api/apps/{id}、/api/apps/{id}/logs、/api/apps/{id}/build-logs、/api/apps/{id}/health、/api/apps/{id}/rollback-history、/api/apps/{id}/config（GET/PATCH）、/api/apps/{id}/deploy、/api/apps/{id}/control、/api/apps/{id}/rollback、/api/domains/check、/api/apps/{id}/database（POST/DELETE）、/api/apps/{id}/tables、/api/apps/{id}/schema、/api/apps/{id}/sql、/api/apps/{id}/migrations
  - 不 mock 的端点（/health）用真实调用

#### Subtask-1.3: bin 4 件套

- **Files**：
  - Create `backend/bin/start.py`
  - Create `backend/bin/stop.py`
  - Create `backend/bin/restart.py`
  - Create `backend/bin/status.py`
  - Create `backend/bin/start.sh`
  - Create `backend/bin/stop.sh`
  - Create `backend/bin/restart.sh`
  - Create `backend/bin/status.sh`
  - Create `backend/bin/start.bat`
  - Create `backend/bin/stop.bat`
  - Create `backend/bin/restart.bat`
  - Create `backend/bin/status.bat`
- **Test**：`backend/tests/test_bin.py`
- **Technical Notes**：
  - start.py：端口 18502 检测 → 启动 uvicorn → 等待 8s → GET /health 验证 → 写 PID
  - stop.py：三重定位（PID 文件 → lsof 端口 → pgrep 进程名）
  - status.py：端口 + PID + /health + 日志尾部，退出码 0/1/2
  - .sh 内 `exec python3 "$0.py" "$@"`（bash 3.2 兼容）
  - .bat 内 `python "%~dpn0.py" %*`
  - PID：`modules/thunderbox/.run/thunderbox.pid`（已 gitignore）

#### Subtask-1.4: conftest.py 与测试隔离

- **Files**：
  - Create `backend/tests/__init__.py`
  - Create `backend/tests/conftest.py`
  - Modify `backend/tests/test_thunderbox_mcp.py`（导入 conftest fixture）
- **Test**：`backend/tests/test_thunderbox_mcp.py` + `backend/tests/test_api.py`
- **Technical Notes**：
  - 全局 `DATA_DIR` fixture 指向 `.pytest-data`（模块根，已 gitignore）
  - `THUNDERBOX_TOKEN` fixture 从 `os.environ["THUNDERBOX_TOKEN"]` 读取（真实 token 不入代码）
  - `APP_NAME_PREFIX = "legal-thunderbox-test-"` 常量，所有 app 创建/操作动态拼接唯一后缀（timestamp/random）
  - mock HTTP fixture：返回固定结构的 `responses` 响应，禁止返回真实 MCP 调用

#### Subtask-1.5: .env.example + Dockerfile

- **Files**：
  - Create `backend/.env.example`
  - Create `Dockerfile`
- **Technical Notes**：
  - `.env.example`：`THUNDERBOX_TOKEN=your_token_here` + `# Thunderbox Bearer Token`
  - Dockerfile：基于 `python:3.11-slim`；`apt-get install procps`（lsof）；`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`；WORKDIR `/app`；EXPOSE 18502；CMD `["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "18502"]`
  - 参考 court-doc-generator 教训（惰性初始化已合规，PyPI 镜像必加，procps 用于 lsof）

---

### Story-2: 应用生命周期管理（创建→部署→回滚→启停）

- **Estimate**：13 SP
- **AC-1**: Given 用户在应用列表页 When 点击「创建应用」Then 4 步向导出现，S1 选择来源（S2 显示构建配置，S3 显示环境与数据，S4 显示域名与权限），完成后 `thunderbox_create` 被调用，列表页显示新应用
- **AC-2**: Given 用户在应用详情页 When 点击「部署」Then `thunderbox_deploy` 被调用，状态推进到 building → deploying → running（或 build_failed + 构建日志入口）
- **AC-3**: Given 用户在应用详情页 When 点击「回滚」Then `thunderbox_rollback(history=true)` 返回历史列表，用户选择目标后 `thunderbox_rollback(target=N)` 执行
- **AC-4**: Given 用户在应用详情页 When 点击「停止」Then `thunderbox_control(action=stop)` 被调用，状态变为 stopped；点击「启动」则 `start`
- **AC-5**: Given 部署进行中 When 用户点击「取消」Then `thunderbox_control(action=cancel)` 被调用，状态变为 cancelled
- **Dependencies**：Story-1

#### Subtask-2.1: 前端 — 应用列表页 + 总览 Dashboard

- **Files**：
  - Create `frontend/index.html`（从 `prototype.html` 的应用列表页提取）
  - Modify `backend/main.py`（静态文件托管）
- **Test**：`frontend/tests/test_app_list.js`（Playwright e2e）
- **Technical Notes**：
  - index.html 包含侧边导航（8 个页面入口）、总览 Dashboard（统计卡 + 应用列表）
  - JS 调用 `GET /api/apps` 渲染列表
  - 状态徽章映射（MCP 原始状态 → 6 枚举归一化）
  - prototype.html 中非本期 scope 的页面（域名探测/资源/审计/设置）暂时保留链接但提示"功能开发中"

#### Subtask-2.2: 前端 — 创建应用向导

- **Files**：
  - Create `frontend/wizard.html`（从 prototype.html 的创建向导页提取）
- **Test**：`frontend/tests/test_wizard.js`（Playwright e2e）
- **Technical Notes**：
  - 4 步状态机：S1（来源）→ S2（构建）→ S3（环境与数据）→ S4（域名与权限）
  - Step 1：`source_type` 单选卡片（git_repo / docker_image）+ URL 输入 + git_token 可选
  - Step 2：`build_pack` 四选一（dockerfile / nixpacks / spa / static）+ 高级选项（build_command / install_command / start_command / publish_directory）
  - Step 3：环境变量键值对列表（增删）+ 数据库类型单选 + volumes 摘要
  - Step 4：子域预填（来自 Step 1 name）+ 访问模式三选一（public/internal/restricted）+ 白名单邮箱（restricted 时显示）
  - 最终提交 `POST /api/apps`

#### Subtask-2.3: 前端 — 应用详情页 + 状态机

- **Files**：
  - Create `frontend/detail.html`（从 prototype.html 的应用详情页提取）
- **Test**：`frontend/tests/test_detail.js`（Playwright e2e）
- **Technical Notes**：
  - Header：状态徽章 + 域名链接 + 主操作按钮组（部署/停止-启动/取消/回滚）
  - 部署进度条（building → deploying → running / build_failed）
  - Tab 切换：概览 / 日志 / 配置 / 数据库
  - 部署后自动轮询状态（每 5s），成功后停止

#### Subtask-2.4: 前端 — 状态机 + 轮询逻辑

- **Files**：
  - Modify `frontend/detail.html`（JS 部分）
- **Technical Notes**：
  - 状态归一化函数：`normalizeStatus(raw)` → running/stopped/building/deploying/build_failed/cancelled/unknown
  - 轮询策略：building/deploying 状态每 5s 轮询 `GET /api/apps/{id}`；running/stopped 停止轮询
  - build_failed 时：详情页自动展开「构建日志」Tab 并提示"查看构建日志"
  - 失败重试：`estimated_seconds` 字段（如果有）指导超时判断

#### Subtask-2.5: 回滚功能（含历史列表）

- **Files**：
  - Modify `frontend/detail.html`（回滚 Tab 部分）
  - Create `backend/tests/test_rollback_flow.py`
- **Test**：`backend/tests/test_rollback_flow.py`（TDD：创建 test app → 部署 → 回滚）
- **Technical Notes**：
  - 回滚按钮：先 GET `/api/apps/{id}/rollback-history` → 渲染历史列表（commit / 时间 / 状态）→ 用户选择目标 → POST `/api/apps/{id}/rollback`（body: `{target: N}`）
  - 无目标时：显示历史列表供选择
  - 二次确认弹窗："回滚到 [commit]？此操作将替换当前版本"

---

### Story-3: 配置管理与环境变量

- **Estimate**：5 SP
- **AC-1**: Given 用户在配置 Tab When 增删改环境变量 Then `thunderbox_config` 被调用，页面刷新后显示最新值
- **AC-2**: Given 用户切换访问模式（public / internal / restricted）When 点击确认 Then `thunderbox_config(access_mode=)` 被调用；切换到 public 时显示红色警告"互联网可访问"
- **AC-3**: Given restricted 模式下 When 用户增删邮箱白名单 Then `thunderbox_config(add_emails/remove_emails=)` 被调用
- **AC-4**: Given 用户在协管员区域 When 输入邮箱 + 点击添加/移除 Then `thunderbox_config(manager_action, manager_email)` 被调用
- **Dependencies**：Story-2

#### Subtask-3.1: 配置 Tab 前端实现

- **Files**：
  - Modify `frontend/detail.html`（配置 Tab 部分）
- **Technical Notes**：
  - 环境变量表：键值对列表 + 「新增」按钮 + 删除按钮（行内红×）
  - 访问模式：三个单选按钮（public 红色警告 / internal / restricted）
  - restricted 模式：邮箱白名单输入框 + 已有邮箱列表（可逐个移除）
  - 协管员：邮箱输入框 + 添加/移除按钮
  - 每次修改后：PATCH `/api/apps/{id}/config`，成功后 toast 提示

#### Subtask-3.2: 配置相关 API 端点测试

- **Files**：
  - Create `backend/tests/test_config_api.py`
- **Test**：`backend/tests/test_config_api.py`
- **Technical Notes**：
  - TDD：先写测试（env_vars 增量合并、access_mode 枚举校验、白名单格式校验、协管员邮箱格式）
  - 覆盖：GET /api/apps/{id}/config、 PATCH /api/apps/{id}/config（所有字段组合）
  - 破坏性操作（volumes 替换）需前端二次确认，此处只验证 API 层

---

### Story-4: 数据库与日志

- **Estimate**：8 SP
- **AC-1**: Given 用户在数据库 Tab When 点击「附加数据库」Then 选择类型（sqlite/postgres）后 `thunderbox_db_add` 被调用，页面刷新后显示数据库类型
- **AC-2**: Given 用户在 SQL 工作台 When 输入 `SELECT` 并点击执行 Then `thunderbox_sql(mode=ro)` 返回 rows/columns；输入非 SELECT 则拒绝（前端校验）
- **AC-3**: Given 用户切换到 rw 模式 When 输入 SQL 并点击执行 Then 显示红色警告提示"可修改数据库数据"，确认后 `thunderbox_sql(mode=rw)`
- **AC-4**: Given 用户执行迁移 When 输入名称 + SQL 并点击提交 Then `thunderbox_apply_migration` 被调用，显示 applied=true
- **AC-5**: Given 用户在日志 Tab When 选择「运行日志」或「构建日志」Then 分别调用 `thunderbox_query(logs=true)` 和 `thunderbox_query(build_logs=true)` 并渲染终端风格文本
- **Dependencies**：Story-2

#### Subtask-4.1: 数据库 Tab 前端实现

- **Files**：
  - Modify `frontend/detail.html`（数据库 Tab 部分）
- **Technical Notes**：
  - 未附加：显示「附加数据库」按钮（sqlite / postgres 单选）
  - 已附加：显示数据库类型 + 表列表（GET `/api/apps/{id}/tables`）+ schema 按钮
  - SQL 工作台：textarea（代码风格高亮可用 highlight.js CDN）+ ro/rw 切换按钮 + 执行按钮 + 结果表格
  - 1000 行上限提示（UI 提示）
  - 迁移面板：历史列表 + 新建表单（name + sql textarea）

#### Subtask-4.2: 数据库 API 测试

- **Files**：
  - Create `backend/tests/test_database_api.py`
- **Test**：`backend/tests/test_database_api.py`
- **Technical Notes**：
  - TDD：先写测试（db_add / list_tables / describe_schema / execute_sql ro+rw / apply_migration 幂等）
  - SQL 校验测试：非 SELECT 语句在 ro 模式下被拒绝（前端已校验，后端双重保障）
  - 所有测试操作 `legal-thunderbox-test-db-*` app

#### Subtask-4.3: 日志 Tab 前端实现

- **Files**：
  - Modify `frontend/detail.html`（日志 Tab 部分）
- **Technical Notes**：
  - 「运行日志」/「构建日志」切换按钮
  - `<pre>` 终端风格渲染（font-family: monospace，背景 #1e1e1e）
  - auto-scroll（`scrollTop = scrollHeight`）
  - 清空按钮（清空 textarea 内容）
  - 无日志时显示空状态提示

---

### Story-5: 审计日志与收尾

- **Estimate**：3 SP
- **AC-1**: Given 用户在审计日志页 When 查看列表 Then 所有写操作（create/deploy/rollback/start/stop/config/env/db/sql）均已记录，显示操作类型/app 名/时间/结果
- **AC-2**: Given 用户执行写操作 Then 网关层自动写入 `data/audit.db`，记录 action/app_id/operator/detail/result/ts
- **AC-3**: Given 开发者完成本地开发 When 执行 rsync 同步到 `legal-thunderbox/` Then 所有源码、测试、Dockerfile 同步完成，可 push GitHub
- **Dependencies**：Story-1、Story-2、Story-3、Story-4

#### Subtask-5.1: 审计中间件

- **Files**：
  - Create `backend/audit.py`
  - Modify `backend/main.py`（注册中间件）
- **Test**：`backend/tests/test_audit.py`
- **Technical Notes**：
  - FastAPI 中间件，拦截所有写操作端点（POST/PATCH/DELETE）
  - SQLite 表：`audit_events(id, ts, action, app_id, app_name, operator, detail_json, result, message)`
  - `detail_json` 存入参（不含 git_token）和响应摘要（不含敏感数据）
  - API 端点：GET `/api/audit`（分页，默认 50 条）

#### Subtask-5.2: 审计日志页 + 文档

- **Files**：
  - Create `frontend/audit.html`
  - Create `docs/SPEC.md`（模块三件套）
  - Create `docs/REQUIREMENTS.md`
  - Create `README.md`
- **Technical Notes**：
  - audit.html：表格展示（操作类型/app/时间/结果）+ 分页 + 筛选
  - README.md：模块说明 + 快速启动 + 环境变量说明
  - REQUIREMENTS.md：MoSCoW + 用户故事 + AC
  - SPEC.md：技术规格（本文档简化版）

#### Subtask-5.3: 代码同步脚本

- **Files**：
  - Create `sync-to-github.sh`
- **Technical Notes**：
  - `rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='.run' --exclude='data' --exclude='outputs' modules/thunderbox/ /Users/pengming/code/work/me/legal-thunderbox/`
  - 同步后提示用户确认并手动 push
  - 脚本本身放在 `modules/thunderbox/` 内

---

## 7. Verification（整体验证标准）

- [ ] 所有 AC 的 Given-When-Then 均有对应测试
- [ ] 端到端流程可走通（创建→部署→查询→回滚）
- [ ] 安全约束满足（token 不硬编码、审计全写操作）
- [ ] bin/start.py 启动 /health 8 秒内返回 200
- [ ] pytest 全部通过（≥ 15 个用例）
- [ ] Docker 镜像在 Thunderbox 部署后 `https://legal-thunderbox.tbox.ktvsky.com/health` 返回 200
- [ ] 所有 pytest 只操作 `legal-thunderbox-test-*` app（破坏性操作）
- [ ] `legal-thunderbox.tbox.ktvsky.com` 仅用于读操作（list_apps、get_app、get_logs）
- [ ] 代码同步到 `/Users/pengming/code/work/me/legal-thunderbox/` 后可 push GitHub

---

## 8. References

- PRD 原型：`modules/thunderbox/prototype.html`
- 方案 A：`modules/thunderbox/docs/PLAN-A.md`
- 方案分析：`modules/thunderbox/docs/ANALYSIS.md`
- MCP 能力：`modules/thunderbox/docs/MCP-CAPABILITY-SPEC.md`
- 部署教训：`docs/DEPLOYMENT-THUNDERBOX.md`
- SDD 规范：`/Users/pengming/code/work/projects/oem_ai_agent/flow/09-SDD落地实施方案-SpecKit+Superpowers.md`
- TDD 规范：`/Users/pengming/code/work/projects/oem_ai_agent/flow/08-TDD落地实施方案.md`
- AGENTS.md：`/Users/pengming/code/me/legal/AGENTS.md`（§5 命名规范 / §7 测试隔离 / §10.4 模块基础设施 / §10.5 Thunderbox 部署红线）
