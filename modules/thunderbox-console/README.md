# thunderbox-console · 雷盒控制台

> **Thunderbox PaaS 部署平台的 MCP 可视化管理系统** — 把 13 个 MCP 工具全部搬到网页上，应用部署、数据库、日志、域名探测，纯点鼠标完成，零命令行、零 MCP 知识要求。

| 项 | 值 |
|----|----|
| 模块名 | thunderbox-console（中文：雷盒控制台） |
| 状态 | planning（原型评估阶段，2026-08-24） |
| 目标用户 | 法务部非技术同事（小白友好） |
| 上游 | Thunderbox MCP（`api-box.tbox.ktvsky.com/mcp`，v0.2.0） |
| 文档入口 | [docs/README.md](docs/README.md) |

## 为什么需要它

Thunderbox 所有管理能力目前只通过 MCP 协议暴露（13 个工具：创建/部署/回滚/启停应用、SQL/迁移、日志、域名探测），只有会写 MCP 调用的人（AI / 开发者）能用。雷盒控制台在中间加一层**可视化网关**：网页 → 后端 REST → MCP → Thunderbox，让小白也能完成"把代码变成线上应用"的全过程。

## 核心能力（四层）

| 层 | 页面能力 |
|----|---------|
| 🚀 应用部署 | 四步创建向导（Git 仓库 / Docker 镜像 → 构建方式 → 环境变量/数据库/卷 → 域名权限）；一键部署/回滚 |
| 📊 监控查询 | 总览 Dashboard、应用列表、详情、日志、健康检查、域名探测 |
| 🔧 生命周期 | 启动/停止/取消构建；环境变量、访问模式（公开/内部/白名单）、协管员管理 |
| 🗄️ 数据库 | SQL 工作台（只读/读写双模式）、表结构查看、版本化迁移 |

## 文档

- [requirements/01-原始需求.md](requirements/01-原始需求.md) — 用户诉求与 MCP 能力基线留档
- [docs/ANALYSIS.md](docs/ANALYSIS.md) — 详细分析（定位/画像/功能矩阵/架构决策/安全/演进）
- [docs/SPEC.md](docs/SPEC.md) — 方案设计（架构拓扑 / API / 状态机 / 页面结构 / 验收清单）
- [prototype.html](prototype.html) — 高保真交互原型（深色科技风）

## 开发流程（当前阶段）

```
分析 ✅ → SPEC ✅ → 原型图 ✅ → 【用户评估】← 你在这里
                                   ↓ 通过后
                    实现 SPEC + goal → backend / frontend / bin 4件套 / 测试
```