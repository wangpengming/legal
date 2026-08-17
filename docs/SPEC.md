# Legal System 系统规格 v1.1

> 最后更新：2026-08-17

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
| `shared/` | 跨模块共享代码 | ✅ |
| `docs/` | 文档 | ✅ |
| `tools/` | 工程脚本 | ✅ |
| `.qoder/` | Qoder项目配置 | ✅ |
| `.git/` | Git仓库数据 | ⚠️（自动管理） |
| `*.tmp/*.log/*.zip` | 临时文件 | ❌ |
| `node_modules/.venv/` | 依赖包 | ❌ |
| `.env` | 环境变量 | ❌ |

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
deps:
  - <module-name>
env:
  - VAR_NAME: description
```

> 注：并入模块允许保留子项目原始内部结构（如 litigation-system 的 backend/frontend 布局），
> module.yaml / docs/ / SPEC.md 为登记标配，`entry: none` 表示尚无代码（planning 阶段）。

### 2.4 当前已注册模块

以 `modules/index.yaml` 为准，当前 3 个模块：

| 模块 | 状态 | 版本 | 职责 | 技术栈 | 并入日期 |
|------|------|------|------|--------|----------|
| court-doc-generator | active | 1.0.0 | 出庭手续文档生成器（7 份材料一键生成 + PDF 合并预览） | Streamlit + python-docx + reportlab（PDF.js 内联预览） | 2026-08-17（原生开发） |
| litigation-system | active | 0.2.0 | 法务诉讼业务平台（飞书历年案件天级同步 + 检索/统计/AI 双模式，基线 638 条） | FastAPI + SQLAlchemy + SQLite FTS5 / React 18 + Vite + ECharts | 2026-08-17（并入 modules/） |
| case-intelligence | planning | 3.0.0 | 同质化案件文档检索与规则系统（三对象模型，不做 AI，只做检索） | NocoDB + Paperless-ngx + Docker Compose（7 容器） | 2026-08-17（并入 modules/） |

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

- **现状**：三模块各自独立运行；litigation-system 从飞书同步案件主数据，case-intelligence 于规划阶段（`entry: none`），court-doc-generator 离线生成材料
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

环境变量写在 `.env.example`（可提交），实际 `.env` 不提交。

## 7. 版本约定

- 模块版本：语义化版本 `major.minor.patch`
- 系统版本：日期版本 `YYYY.MM.DD`

## 8. 模块演进说明

- 模块状态机：`planning`（方案设计）→ `active`（运行使用）→ `archived`（下线归档），状态由 `modules/index.yaml` 与各模块 `module.yaml` 声明
- 并入策略：外部子项目（如 tmp/dev 下的成型项目）以**原样迁入**为原则，仅补登记文件（module.yaml / docs/ / SPEC.md），不重构其内部代码；源码层面改动走独立演进
- 演进记录：所有模块变更登记于 `docs/requirements/CHANGELOG.md`，需求条目记录于 `backlog.md`
