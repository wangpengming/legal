# 同质化案件文档检索与规则系统 — 技术方案

> 版本: v3.0（文档检索 + 规则化知识库）
> 日期: 2026-08-12
> 目标服务器: `pengming@10.10.11.37`（Ubuntu 22.04 / 62GB RAM / 无需 GPU）

---

## 核心结论

| 维度 | 决策 |
|------|------|
| 核心方向 | 结构化案件数据库 + 文档全文检索 + 规则/检查清单，**不做 AI/LLM** |
| 案件管理 | NocoDB（开源 Airtable，42K+ Stars） |
| 文档管理 | Paperless-ngx（开源，44K+ Stars） |
| 部署 | Docker Compose，7 个容器 |
| 服务器 | 10.10.11.37（已有 Docker 环境） |
| 资源新增 | ~2GB RAM / ~10GB 磁盘 / **无需 GPU** |
| 用户门槛 | 极低（像 Excel 操作表格 + 拖拽上传 + 搜索关键词） |

**核心原则：搜得到、看得懂、用得上。不做 AI，只做检索。**

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [requirements/01-原始需求.md](requirements/01-原始需求.md) | v1 原始需求（归档基线） |
| [spec/01-方案设计v3.md](spec/01-方案设计v3.md) | **v3 方案设计**（架构/表结构/操作流程/部署/运维） |
| requirements/02-需求v3.md | v3 需求文档（**待补**：尚未产出，规划中） |
| research/01-文档检索与规则化方案调研.md | v3 技术调研（**待补**：尚未产出，规划中） |

---

## 架构概览

```
                        用户浏览器
                  ┌───────┴───────┐
                  │               │
         http://10.10.11.37:8090  http://10.10.11.37:8091
         (NocoDB 案件+规则)       (Paperless-ngx 文档)
                  │               │
         ┌────────▼────────┐  ┌───▼──────────────────┐
         │    NocoDB       │  │   Paperless-ngx       │
         │  • 案件表        │  │  • 文档上传/OCR       │
         │  • 检查清单表    │  │  • 全文检索           │
         │  • 审核记录表    │  │  • 标签分类           │
         │  • 经验规则表    │  │                       │
         └─────────────────┘  └───────────────────────┘
```

---

## 版本历史

| 版本 | 日期 | 方向 |
|------|------|------|
| v1 | - | AI 辅助分析（LangChain + PyMuPDF + FAISS） |
| v2 | 2026-08-10 | MaxKB + Ollama + Qwen3 8B RAG 方案 |
| **v3** | **2026-08-12** | **结构化案件数据库 + 文档检索 + 规则/检查清单** |

---

## 部署与域名（thunderbox / 雷石盒子）

> 本 README 为 v3 方案（NocoDB + Paperless 多容器）归档；模块现状已收敛为 **Python CLI + SQLite 轻量形态**（v3.3，`bin/extract.py` + Streamlit UI `:18503`）。

云平台部署统一走雷石 **thunderbox**：

- **本模块域名（唯一）**：`legal-case.tbox.ktvsky.com` · `access_mode=internal`
- **代码来源**：**仅支持 GitHub** —— 部署前须先把代码迁移到 GitHub 仓库
- **平台信息**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`

> 🔴 **域名规则**：每个模块**有且仅有一个域名**，不得随意创建；域名统一登记 `shared/config/domains.yaml`（详见 `AGENTS.md §10.4.5`）。
> 📖 系统级部署手册：[docs/deployment-thunderbox.md](../../docs/deployment-thunderbox.md)