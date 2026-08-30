# SPEC-2026-001 · Context — 雷盒控制台 SDD

> **关联**：spec/spec.md · SPEC-2026-001

---

## 1. PRD 来源

| 来源 | 文件 | 内容摘要 |
|------|------|---------|
| 原型图 | `prototype.html`（2172 行，8 页） | 总览/应用列表/创建向导/应用详情/日志/配置/数据库/审计 |
| 方案文档 | `docs/PLAN-A.md`（305 行） | 方案 A：FastAPI + MCP 适配层架构 + 13 工具映射 |
| 方案分析 | `docs/ANALYSIS.md`（210 行） | 用户画像 / MoSCoW 优先级 / 状态机 / 安全分析 |
| MCP 能力对齐 | `docs/MCP-CAPABILITY-SPEC.md`（119 行） | 13 个 MCP 工具与原型逐项对照，P0/P1/P2 优先级 |
| 现有后端代码 | `backend/main.py`（357 行） | FastAPI 入口，18 个 REST 端点 |
| 现有 MCP 层 | `backend/thunderbox_mcp.py`（547 行） | ThunderboxMCP 类，21 个确定性方法 |
| 部署经验 | `docs/DEPLOYMENT-THUNDERBOX.md`（341 行） | court-doc-generator 部署教训（惰性初始化/镜像/PyPI/volumes） |

---

## 2. 原型功能矩阵

### 8 个页面

| 页面 | 核心功能 | MCP 来源 |
|------|---------|---------|
| ① 总览 Dashboard | 统计卡/状态分布/最近部署/资源/域名探测 | `thunderbox_query` + `thunderbox_check` |
| ② 应用列表 | 卡片/表格视图/搜索/筛选/状态徽章 | `thunderbox_query` |
| ③ 创建向导 | 4 步：来源→构建→环境→权限 | `thunderbox_create` + `thunderbox_check` |
| ④ 应用详情 | 状态机/主操作/4 Tabs | `thunderbox_query` + `thunderbox_deploy` + `thunderbox_control` + `thunderbox_rollback` |
| ⑤ 日志 | 构建日志/运行日志/终端风格 | `thunderbox_query(logs/build_logs)` |
| ⑥ 配置 | 环境变量/访问模式/白名单/协管员/ref/volumes | `thunderbox_config` |
| ⑦ 数据库 | 表列表/schema/SQL工作台/迁移 | `thunderbox_db_add` + `thunderbox_sql` + `thunderbox_apply_migration` + `thunderbox_describe_schema` |
| ⑧ 审计日志 | 写操作全记录/风险操作二次确认 | SQLite 本地审计 |

### 关键交互

- 状态机可视化：building → deploying → running / build_failed
- 有副作用操作：二次确认弹窗（回滚/停止/取消/改 public/替换 volumes）
- SQL 工作台：ro/rw 切换 + 确认文案
- 向导默认值：nixpacks / 自动端口推导 / 无需填 git_token

---

## 3. 现有代码分析

### 已有（可直接复用）

| 文件 | 行数 | 状态 | 说明 |
|------|------|------|------|
| `backend/thunderbox_mcp.py` | 547 | 已实现，缺测试 | ThunderboxMCP 封装，21 个方法 |
| `backend/main.py` | 357 | 已实现，缺测试 | 18 个 REST 端点，FastAPI |
| `requirements.txt` | 4 | 已实现 | fastapi/uvicorn/pydantic |

### 待新增（按优先级）

| 文件/目录 | 说明 | TDD 要求 |
|----------|------|---------|
| `backend/bin/` | 4 件套：start/stop/restart/status × .py/.sh/.bat | TDD（纯新增） |
| `backend/tests/` | pytest 单元测试 | TDD（纯新增） |
| `frontend/src/` | 从 prototype.html 演进（HTML → Vite 托管） | characterization → TDD |
| `Dockerfile` | 容器镜像（参考 court 教训） | characterization（参考 court） |
| `.env.example` | 环境变量模板 | 直接创建 |
| `backend/tests/conftest.py` | 全局 fixture：MCP 隔离 | TDD |
| `backend/routers/` | 路由拆分（可按需） | TDD（可选重构） |

### 关键部署经验（court-doc-generator 教训）

1. **惰性初始化**：`thunderbox_mcp.py` 的 `_TESSERACT`/`_LANG` 问题在当前代码中不存在（MCP 层无外部二进制依赖），但未来扩展需注意
2. **PyPI 镜像**：Dockerfile 必须用清华镜像（`pypi.tuna.tsinghua.edu.cn`）
3. **系统依赖**：当前代码无 C 扩展依赖，但 `python-multipart`/`pydantic` 已在 requirements.txt
4. **Volumes 挂载**：部署时必须声明 volumes（`data/` 审计 SQLite 必须持久化）
5. **端口一致性**：Dockerfile EXPOSE / CMD / thunderbox_create `port` 三者必须一致

---

## 4. 测试隔离策略

| 操作类型 | 测试目标 | 原因 |
|---------|---------|------|
| 读操作（list_apps、get_app、check_domain、get_logs） | `legal-thunderbox.tbox.ktvsky.com` 真实应用 | 安全，只读不破坏 |
| 破坏性操作（deploy、start、stop、config、db） | 本地测试：`legal-thunderbox-test-*` 隔离沙盒 app | 隔离，不影响线上 |
| 端到端冒烟 | 本地 docker-compose 完整验证 | 真实 Thunderbox 环境 |

**域名约束**：
- Thunderbox 项目名：`legal-thunderbox`
- 部署目标：`legal-thunderbox.tbox.ktvsky.com`
- 测试用沙盒：`legal-thunderbox-test-*`（`legal-thunderbox-test-deploy` / `legal-thunderbox-test-db` 等）
- 所有 pytest 测试只操作以 `legal-thunderbox-test-` 开头的 app
- 测试 fixture 命名禁止硬编码真实 app ID，动态生成

---

## 5. Scope 边界

### In Scope（本期）

- 应用列表/详情（读操作，真实 MCP）
- 创建应用向导（git_repo / docker_image）
- 部署/回滚/启停/取消（测试 app 操作）
- 环境变量管理（增删改）
- 访问模式切换（public/internal/restricted）
- 邮箱白名单（restricted 模式）
- 协管员管理（add/remove）
- 数据库附加（sqlite/postgres）
- SQL 工作台（ro/rw，含 1000 行限制）
- 迁移管理（幂等 apply）
- 日志查看（运行/构建）
- 审计日志（SQLite，本模块内）
- bin 4 件套
- Dockerfile
- 本地开发 + Thunderbox 部署

### Out of Scope（明确排除）

- **删除应用**（MCP `thunderbox_db_remove` 禁用引导已实现，不做真实删除操作）
- **协管员完整管理**（add/remove 已有，列表/权限级暂不实现）
- **域名探测/资源探测**（`thunderbox_check` MCP 能力已分析，UI 暂不实现）
- **模板库**（创建向导的快捷预填）
- **通知中心**（部署状态推送）
- **⌘K 命令面板**（快捷操作面板）
- **Portal 集成**（远期）
- **用户认证**（v1 无登录，内网工具定位）
