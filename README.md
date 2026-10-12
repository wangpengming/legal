# Legal System - 法务部工程化系统

> AI原生驱动 · 模块化架构 · 持续演进

## 项目概述

法务部工程化系统，采用模块化monorepo架构，每个功能模块独立运行，可按需嵌入主系统。

## 目录结构

```
legal/
├── docs/                       # 系统文档
│   ├── README.md               # 文档索引
│   ├── SPEC.md                 # 系统规格
│   ├── deployment-thunderbox.md # thunderbox 部署手册
│   └── requirements/           # 需求池
│       ├── backlog.md           # 待办需求（AI可解析格式）
│       └── CHANGELOG.md         # 变更记录
├── modules/                    # 功能模块
│   ├── index.yaml              # 模块注册表
│   ├── court-doc-generator/    # 出庭手续文档生成器（React + FastAPI）
│   ├── litigation-system/      # 法务诉讼业务平台（FastAPI + React）
│   ├── case-intelligence/      # 案例智能分析模块（CLI，五维度提取 + 目录扫描）
│   ├── portal/                 # 统一门户（注册表驱动集成框架 + 健康监控总览，原型已交付）
│   └── [module-name]/          # 通用模块目录
│       ├── src/                # 源代码
│       ├── tests/              # 测试
│       ├── docs/               # 模块文档
│       ├── module.yaml          # 模块规格（Qoder可读）
│       └── SPEC.md              # 模块规格
├── shared/                     # 跨模块共享（config/：ports.yaml + domains.yaml；common/、templates/ 规划中）
├── .qoder/                    # Qoder项目配置（Qoder 生成并纳入版本管理）
├── tools/                     # 工程工具脚本（规划中，待建）
├── .gitignore
└── README.md
```

## 模块注册

查看所有可用模块：`cat modules/index.yaml`

当前已注册模块：

| 模块 | 状态 | 版本 | 域名（thunderbox） | 一句话 |
|------|------|------|--------------------|--------|
| court-doc-generator | active | 2.2.5 | `legal-court` ⚠️待回收 | 出庭手续文档生成器（React+FastAPI，7份材料一键生成 + OCR扫描 + 多用户隔离） |
| litigation-system | active | 0.2.0 | `legal-litigation` | 法务诉讼业务平台（飞书历年案件天级同步 + 检索/统计/AI 双模式） |
| case-intelligence | active | 3.3.0 | `legal-case` | 案例智能分析模块（CLI，五维度提取 + 目录扫描 + AI 辅助录入） |
| portal | planning | 0.1.0 | `legal-portal` | 法务统一门户（注册表驱动集成框架 + 健康监控总览，单文件原型已交付） |

> **域名规则**：每个模块在 thunderbox 上**有且仅有一个域名**（`legal-*` 前缀，仅内网），统一登记 `shared/config/domains.yaml`，**禁止随意创建**（详见 `AGENTS.md §10.4.5`）。

## 模块间关系

```
                    ┌─────────────────────┐
                    │   litigation-system  │ 飞书结构化案件数据：同步/检索/统计/AI
                    └──────────┬──────────┘
                               │ 案件互通（远期）
┌─────────────────┐  ┌────────▼──────────────┐
│ court-doc-generator│ │  case-intelligence     │ 卷宗文档/审核规则：OCR/全文检索/清单
└─────────────────┘  └───────────────────────┘
 出庭手续材料生成          新案件受理/审核工作流入口
```

三角布局：**文书生成 · 诉讼数据平台 · 卷宗检索规则**，三者独立演进、按需集成。

**portal 统一门户**（第 4 模块，规划中）：通过同源反代（nginx）+ apps.yaml 注册表汇聚三个子系统为单一入口 `https://legal.internal/`，并提供系统健康监控总览；原型见 `modules/portal/prototype.html`。

## 部署（thunderbox / 雷石盒子）

生产部署统一走雷石内部平台 **thunderbox**：

- **平台**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`
- **代码来源**：**仅支持 GitHub** —— 部署前须先把代码迁移到 GitHub 仓库
- **域名**：`<subdomain>.tbox.ktvsky.com`，**一模块一域名**（`legal-*` 前缀，`access_mode=internal`），见下表与 `shared/config/domains.yaml`
- **Token**：控制台创建，**严禁写入仓库**（项目 scope 会被提交）

📖 完整部署手册（GitHub 通道 / MCP 工具 / 域名申请 / 排障）：[docs/deployment-thunderbox.md](docs/deployment-thunderbox.md)

## 快速开始

```bash
# 查看需求池
cat docs/requirements/backlog.md

# 查看系统规格
cat docs/SPEC.md

# 查看模块列表
cat modules/index.yaml

# 查看端口 / 域名注册表
cat shared/config/ports.yaml
cat shared/config/domains.yaml
```

## 开发规范

1. 每个模块必须有 `module.yaml` 和 `SPEC.md`
2. 所有需求写入 `docs/requirements/backlog.md`
3. 模块间通过约定接口通信，禁止直接硬依赖
4. 临时文件、构建产物、密钥类文件（secrets/credentials）不提交；隐藏文件与项目规则（.qoder/）及 .env 允许提交（私有仓库）

## AI操作指南

**识别模块**：`cat modules/index.yaml`
**查看需求**：`cat docs/requirements/backlog.md`
**模块规格**：`cat modules/<name>/SPEC.md` 或 `cat modules/<name>/module.yaml`
**全局配置**：`cat shared/config/`（端口注册表 `ports.yaml` · 域名注册表 `domains.yaml`）
**部署手册**：`cat docs/deployment-thunderbox.md`
