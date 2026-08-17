# Legal System — Agent 工作指南

> 本目录（legal/）为法务部工程化系统，所有 AI 在此目录下工作时须遵守本文档。

## 系统架构

- **架构模式**：模块化 Monorepo，每个功能模块独立运行、可单独嵌入主系统
- **模块管理**：通过 `modules/index.yaml` 统一注册
- **需求追踪**：`docs/requirements/backlog.md`，格式 AI 可解析

## 模块命名规范

**强制规则：目录名和代码符号只用 ASCII 英文。**

| 元素 | 正确 | 错误 |
|------|------|------|
| 模块目录 | `court-doc-generator` | `智能出庭文书` |
| 文件名 | `pdf_merger.py` | `PDF合并器.py` |
| 函数名 | `def merge_pdfs()` | `def 合并PDF()` |

中文内容放 README / SPEC.md 等文档中详细说明，代码和目录结构全部英文。

## 新功能开发流程

1. **提出需求** → 写入 `backlog.md`
2. **评审** → 确认优先级和模块归属
3. **开发** → 在对应 `modules/<name>/` 下实现
4. **注册** → 更新 `modules/index.yaml`
5. **上线** → 更新 `backlog.md` 状态 + `CHANGELOG.md`

## 目录规范

```
legal/               ← 根目录（英文）
├── docs/            ← 文档（英文）
├── modules/         ← 模块（英文目录名）
└── shared/          ← 共享（英文）
```

## 忽略文件规则

以下类型**不提交**到仓库：
- 临时文件：`.tmp`、`.log`、`.swp`
- 虚拟环境：`.venv/`、`.venv/`
- 运行产物：`outputs/`、`static/merged/`、`.run/`
- 构建产物：`dist/`、`build/`、`*.egg-info/`
- 系统文件：`.DS_Store`、`__pycache__/`

## 环境与依赖

- 依赖通过 `requirements.txt` 管理，不提交 `.venv/`
- 新模块需在 `module.yaml` 中声明依赖
