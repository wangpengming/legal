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
│   └── requirements/           # 需求池
│       ├── backlog.md           # 待办需求（AI可解析格式）
│       └── CHANGELOG.md         # 变更记录
├── modules/                    # 功能模块
│   ├── index.yaml              # 模块注册表
│   ├── court-doc-generator/    # 出庭手续文档生成器（Streamlit）
│   ├── litigation-system/      # 法务诉讼业务平台（FastAPI + React）
│   ├── case-intelligence/      # 同质化案件文档检索与规则系统（NocoDB + Paperless，规划中）
│   ├── portal/                 # 统一门户（注册表驱动集成框架 + 健康监控总览，原型已交付）
│   └── [module-name]/          # 通用模块目录
│       ├── src/                # 源代码
│       ├── tests/              # 测试
│       ├── docs/               # 模块文档
│       ├── module.yaml          # 模块规格（Qoder可读）
│       └── SPEC.md              # 模块规格
├── shared/                     # 跨模块共享（暂仅 config/；common/、templates/ 规划中）
├── .qoder/                    # Qoder项目配置（Qoder 生成并纳入版本管理）
├── tools/                     # 工程工具脚本（规划中，待建）
├── .gitignore
└── README.md
```

## 模块注册

查看所有可用模块：`cat modules/index.yaml`

当前已注册模块：

| 模块 | 状态 | 版本 | 一句话 |
|------|------|------|--------|
| court-doc-generator | active | 1.1.4 | 出庭手续文档生成器（7份材料一键生成 + PDF合并预览） |
| litigation-system | active | 0.2.0 | 法务诉讼业务平台（飞书历年案件天级同步 + 检索/统计/AI 双模式） |
| case-intelligence | planning | 3.0.0 | 同质化案件文档检索与规则系统（NocoDB + Paperless-ngx，不做 AI） |
| portal | planning | 0.1.0 | 法务统一门户（注册表驱动集成框架 + 健康监控总览，单文件原型已交付） |

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

## 快速开始

```bash
# 查看需求池
cat docs/requirements/backlog.md

# 查看系统规格
cat docs/SPEC.md

# 查看模块列表
cat modules/index.yaml
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
**全局配置**：`cat shared/config/`
