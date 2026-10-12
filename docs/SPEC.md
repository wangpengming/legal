# Legal System 系统规格 v1.1

> 最后更新：2026-10-12

## 1. 系统架构

### 1.1 核心原则

- **模块独立**：每个模块可独立运行、测试、部署
- **松耦合**：模块间通过约定接口通信，不直接硬依赖
- **AI原生**：所有规范以AI可解析的格式编写（Markdown + YAML头部）
- **版本演进**：所有变更记录在CHANGELOG.md

### 1.2 目录规范

| 路径 | 用途 | 是否提交 |
|------|------|---------|
| `modules/` | 功能模块源码 | ✅ |
| `shared/config/` | 跨模块共享配置 | ✅ |
| `shared/common/`、`shared/templates/` | 跨模块共享代码/模板 | 🚧 规划中，待建 |
| `docs/` | 文档 | ✅ |
| `tools/` | 工程脚本 | 🚧 规划中，待建 |
| `.qoder/` | Qoder项目配置 | ✅（Qoder 生成并纳入版本管理） |
| `.git/` | Git仓库数据 | ⚠️（自动管理） |
| `*.tmp/*.log/*.zip` | 临时文件 | ❌ |
| `node_modules/.venv/` | 依赖包 | ❌ |
| `secrets.yaml/secrets.json/credentials.*` | 密钥类文件 | ❌（安全红线） |
| `.env` | 环境变量 | ✅（私有仓库；真实密钥勿写入） |

## 2. 模块规范

### 2.1 模块注册

每个模块必须在 `modules/index.yaml` 注册（含 `integrated` 字段记录并入日期）：

```yaml
modules:
  - name: contract-review
    path: modules/contract-review
    status: active          # active | planning | archived
    version: 1.0.0
    description: 合同审查模块
    entry: src/main.py
    deps: []                # 直接依赖的其他模块
```

### 2.2 模块结构

每个模块必须有：

```
modules/<name>/
├── src/                   # 源代码
├── tests/                 # 测试文件
├── docs/                  # 模块文档
│   ├── README.md
│   └── API.md
├── module.yaml            # 模块规格（Qoder可读）
├── SPEC.md                # 模块规格（详细）
└── requirements.txt       # 依赖列表
```

### 2.3 module.yaml 格式

```yaml
name: <module-name>
version: <semver>
status: active | planning | archived
description: 一句话描述
entry: src/main.py
port:                       # 端口（登记的注册表：shared/config/ports.yaml）
  app: <port>
domain:                     # 域名（登记的注册表：shared/config/domains.yaml）
  subdomain: legal-<name>   # 一模块一域名，legal-* 前缀
  fqdn: legal-<name>.tbox.ktvsky.com
  access_mode: internal     # 一律 internal（仅内网）
deps:
  - <module-name>
env:
  - VAR_NAME: description
```

> 注：
> - 并入模块允许保留子项目原始内部结构（如 litigation-system 的 backend/frontend 布局），仅要求补 module.yaml / docs/ / SPEC.md 登记文件
> - 原生开发模块（如 court-doc-generator）允许平铺布局（app.py 于模块根），不必强制 src/
> - module.yaml / docs/ / SPEC.md 为登记标配，`entry: none` 表示尚无代码（planning 阶段）。

### 2.4 当前已注册模块

以 `modules/index.yaml` 为准，当前 4 个模块：

| 模块 | 状态 | 版本 | 域名（thunderbox） | 职责 | 技术栈 | 并入日期 |
|------|------|------|--------------------|------|--------|----------|
| court-doc-generator | active | 2.2.5 | `legal-court` ⚠️待回收 | 出庭手续文档生成器（7 份材料一键生成 + OCR 扫描 + 多用户隔离） | FastAPI + React 18 + Vite + SQLite | 2026-08-17（原生开发） |
| litigation-system | active | 0.2.0 | `legal-litigation` | 法务诉讼业务平台（飞书历年案件天级同步 + 检索/统计/AI 双模式，基线 638 条） | FastAPI + SQLAlchemy + SQLite FTS5 / React 18 + Vite + ECharts | 2026-08-17（并入 modules/） |
| case-intelligence | active | 3.3.0 | `legal-case` | 案例智能分析模块（五维度提取 + 目录扫描 + AI 辅助录入，CLI） | Python CLI + SQLite | 2026-08-17（并入 modules/） |
| portal | planning | 0.1.0 | `legal-portal` | Legal 统一门户（注册表驱动子系统集成框架 + 健康监控总览） | 单文件 HTML/JS 原型 + nginx 同源反代（规划） | 2026-08-17（原生开发） |

## 3. 需求管理规范

### 3.1 需求格式

所有需求写入 `docs/requirements/backlog.md`，使用结构化格式：

```markdown
## YYYY-MM-DD 需求标题

**类型**: feature | fix | improvement
**模块**: <module-name> | cross-module | system
**状态**: proposed | in-progress | done | rejected
**优先级**: P0(紧急) | P1(重要) | P2(一般) | P3(低)

### 描述
需求详细描述...

### 验收标准
- [ ] 标准1
- [ ] 标准2
```

### 3.2 需求优先级定义

| 优先级 | 定义 | 处理时限 |
|--------|------|---------|
| P0 | 紧急，影响核心功能 | 24小时内 |
| P1 | 重要，功能必需 | 1周内 |
| P2 | 一般，有则更好 | 1个月内 |
| P3 | 低，可延后 | 待定 |

## 4. 模块间接口约定

### 4.1 事件总线（待实现）

模块间通过事件通信：
- Topic格式：`module.<event>`
- Payload：JSON

### 4.2 共享数据

共享数据通过 `shared/common/` 下的公共模块：
- 数据模型定义
- 常量定义
- 工具函数

### 4.3 模块间数据流

当前无模块间硬依赖（不导入对方代码），仅存在业务与数据层面的弱衔接：

```
飞书多维表格（案件主数据，638 条）
        │ 天级同步
        ▼
┌─────────────────────┐        ┌──────────────────────┐        ┌───────────────────────┐
│ litigation-system    │        │ court-doc-generator  │        │ case-intelligence      │
│ 结构化案件数据平台    │        │ 出庭手续材料生成      │        │ 卷宗文档检索与规则系统  │
│ 同步/检索/统计/AI    │        │ 7 份材料 + PDF 合并   │        │ OCR/全文检索/检查清单   │
└──────────┬──────────┘        └──────────────────────┘        └───────────┬───────────┘
           │ 远期：详情页链接跳转（案件级互通）                                │ 远期：按案号回填案件↔文档强关联
           └───────────────────────────────┴────────────────────────────────┘
```

- **现状**：三模块各自独立运行；litigation-system 从飞书同步案件主数据，case-intelligence 已落地 v3.3.0（SQLite 轻量 CLI + Streamlit UI），court-doc-generator 离线生成材料
- **远期**：模块间数据流按「案件主数据 → 卷宗文档/审核规则」组织，详见各模块 SPEC 演化路线

## 5. Qoder项目配置

每个模块在 `.qoder/projects/` 下有独立项目配置：

```yaml
project:
  name: legal.<module-name>
  root: modules/<module-name>
  type: python | node | web
```

## 6. 环境变量规范

本仓库为私有仓库：`.env` 及其变体（`.env.example` / `.env.local` 等）允许提交并纳入版本管理；
密钥类文件（`secrets.yaml` / `secrets.json` / `credentials.*`）为安全红线，一律不提交。
含真实密钥的环境变量请使用 `.local` 后缀随用随清，避免写入版本库。

## 7. 版本约定

- 模块版本：语义化版本 `major.minor.patch`（如 court-doc-generator v1.1.4）
- 系统版本：语义化版本，记录于 `docs/requirements/CHANGELOG.md`，与模块版本演进保持同步

## 8. 模块演进说明

- 模块状态机：`planning`（方案设计）→ `active`（运行使用）→ `archived`（下线归档），状态由 `modules/index.yaml` 与各模块 `module.yaml` 声明
- 并入策略：外部子项目（如 tmp/dev 下的成型项目）以**原样迁入**为原则，仅补登记文件（module.yaml / docs/ / SPEC.md），不重构其内部代码；源码层面改动走独立演进
- 演进记录：所有模块变更登记于 `docs/requirements/CHANGELOG.md`，需求条目记录于 `backlog.md`

## 9. 部署与域名规范

生产部署统一走雷石内部平台 **thunderbox（雷石盒子）**。完整手册见 [`docs/deployment-thunderbox.md`](./deployment-thunderbox.md)。

### 9.1 平台信息

| 项 | 值 |
|----|----|
| 控制台 | `https://box.tbox.ktvsky.com/` |
| MCP 端点 | `https://api-box.tbox.ktvsky.com/mcp`（HTTP transport） |
| 域名规范 | `<subdomain>.tbox.ktvsky.com` |
| 代码来源 | **仅支持 GitHub** —— 部署代码须先迁移到 GitHub 仓库 |
| 访问模式 | 一律 `internal`（仅内网） |
| Token | 控制台创建；**严禁写入仓库**（项目 scope 会被提交） |

### 9.2 域名规则：一模块一域名 🔴

> 强制规则详见 `AGENTS.md §10.4.5`。

1. **一模块一域名**：每个模块在 thunderbox 上有且仅有一个域名，域名为应用创建时绑定，不得为同一模块另建域名。
2. **禁止随意创建**：新建域名前必须先在域名注册表登记并走查重。
3. **命名空间**：统一 `legal-*` 前缀（kebab-case）。
4. **双登记一致**：`module.yaml` 的 `domain` 字段必须与 `shared/config/domains.yaml` 一致。
5. **注册表**：[`shared/config/domains.yaml`](../shared/config/domains.yaml)（与端口注册表 `ports.yaml` 并列）。

### 9.3 域名分配

| 模块 | 域名 | access_mode | 状态 |
|------|------|-------------|------|
| court-doc-generator | `legal-court.tbox.ktvsky.com` | internal | ⚠️ 待回收（遗留占用；回退候选 `legal-court-generator` / `legal-courtdocs`） |
| litigation-system | `legal-litigation.tbox.ktvsky.com` | internal | 待申请 |
| case-intelligence | `legal-case.tbox.ktvsky.com` | internal | 待申请 |
| portal | `legal-portal.tbox.ktvsky.com` | internal | 待申请 |

### 9.4 部署形态（各模块生产运行方式）

| 模块 | 生产形态 | 健康端点 |
|------|---------|---------|
| court-doc-generator | FastAPI 单端口（8001）托管前端 `dist/`；systemd 可选 | `/health` |
| litigation-system | Docker Compose（api:8000 + nginx:8080） | `/healthz` |
| case-intelligence | Streamlit UI（18503）+ SQLite CLI（Docker 方案已收敛为轻量形态） | `/_stcore/health` |
| portal | 规划：nginx 同源反代 + 静态页面（`legal-portal`） | 待定义 |
