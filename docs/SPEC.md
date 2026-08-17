# Legal System 系统规格 v1.0

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

每个模块必须在 `modules/index.yaml` 注册：

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
