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
│       └── backlog.md           # 待办需求（AI可解析格式）
├── modules/                    # 功能模块
│   ├── index.yaml              # 模块注册表
│   └── [module-name]/          # 模块目录
│       ├── src/                # 源代码
│       ├── tests/              # 测试
│       ├── docs/               # 模块文档
│       ├── module.yaml          # 模块规格（Qoder可读）
│       └── SPEC.md              # 模块规格
├── shared/                     # 跨模块共享
│   ├── common/                 # 公共代码
│   ├── templates/             # 共用模板
│   └── config/                # 共用配置
├── .qoder/                    # Qoder项目配置
│   └── projects/              # Qoder项目定义
├── tools/                     # 工程工具脚本
├── .gitignore
└── README.md
```

## 模块注册

查看所有可用模块：`cat modules/index.yaml`

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
4. 临时文件、构建产物、env文件不提交

## AI操作指南

**识别模块**：`cat modules/index.yaml`
**查看需求**：`cat docs/requirements/backlog.md`
**模块规格**：`cat modules/<name>/SPEC.md`
**全局配置**：`cat shared/config/`
