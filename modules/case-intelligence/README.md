# case-intelligence — 案例智能分析模块

> **版本**: v3.4.1 | **状态**: active | **更新时间**: 2026-10-14
> **形态**: Python CLI + Streamlit Web UI（`:18503`）+ SQLite
> **部署**: thunderbox · [`legal-case.tbox.ktvsky.com`](https://legal-case.tbox.ktvsky.com)（internal，GitHub 源码）

---

## 模块定位

从案件材料中按 **D1-D5 五维度**（事实认定 / 法律依据 / 攻防策略 / 证据体系 / 赔偿裁量）提取结构化知识，沉淀为提取物知识库，并按固定模板（答辩状 / 质证意见 / 当庭陈述 / 证据目录）生成文书与分析。

**核心原则：提取物是燃料、维度固定内容随案由变化、Prompts 是系统大脑。**

## 核心能力

| 能力 | 说明 |
|------|------|
| 案源管理 | 注册 / 查询 / 画像标签，录入方式 CLI / UI / AI 三种 |
| **UI 上传录入（v3.4.1）** | 浏览器直接上传多文件或 ZIP（文件夹打包）→ 安全解压 → 自动提取 → 查重 → 导入 |
| **一键生成（v3.4.1）** | 导入成功后携带 case_id 直达文书生成页 |
| 五维度提取 | D1 事实 / D2 法律 / D3 攻防 / D4 证据 / D5 赔偿，mock/basic/ollama/openai/minimax 五引擎可切换 |
| 模板归纳 | 4 类固定文书模板，从提取物自动归档沉淀 |
| 文书生成 | MD + DOCX 双格式，三级降级（模板 → 模板+LLM → LLM → fallback） |
| 相似案件匹配 | `src/case_matcher.py` 规则打分（案由/年份/场景/D1-D5 覆盖） |
| 目录扫描 | 服务器路径扫描兜底（递归扫描 + 文件分类 + 元数据推断） |

## 快速上手

```bash
cd modules/case-intelligence

# 首次：创建虚拟环境 + 安装依赖
uv venv .venv --python 3.12
uv pip install -p .venv -r requirements.txt pytest

# 配置（复制后填写，勿提交真实值）
cp .env.example .env            # MINIMAX_API_KEY / AUTH_USERS
# 或直接导出环境变量（生产部署走 thunderbox env_vars 注入）
export MINIMAX_API_KEY=sk-xxx

# 启动 Web UI（后台，PID/日志在 .run/）
python3 bin/start.py
# → http://localhost:18503（登录账号见 AUTH_USERS 或默认 admin/admin123）

# 状态 / 停止 / 重启
python3 bin/status.py && python3 bin/stop.py && python3 bin/restart.py

# CLI（16 子命令）
python3 bin/extract.py --help

# 测试（TDD 全量）
.venv/bin/python -m pytest tests/ -v
```

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/README.md](docs/README.md) | 用户手册（目录结构/使用/运维） |
| [docs/SPEC.md](docs/SPEC.md) | 模块规格 v3.4.1（对象模型/数据库/流程/健康检查） |
| [docs/SPEC-ui-upload.md](docs/SPEC-ui-upload.md) | **UI 上传提取与生成链路增补规格（v3.4.1）** |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | 需求基线（MoSCoW + 用户故事） |
| [requirements/01-原始需求.md](requirements/01-原始需求.md) | v1 原始需求（归档基线） |
| [SPEC-UI.md](SPEC-UI.md) | Web UI 页面规格 |
| [reference_index.yaml](reference_index.yaml) | 外部数据源引用索引 |

## 安全红线（§6.2）

- `ai_engines.yaml` 中密钥一律 `env://MINIMAX_API_KEY` 引用，**不明文入库**
- `.env` 不提交；thunderbox 部署经 `env_vars` 注入 `MINIMAX_API_KEY` / `AUTH_USERS` / `DATA_DIR`
- 上传物落盘 `data/inbox/`（volume 内持久，已 gitignore）；ZIP 解压含路径穿越 / 符号链接 / 大小 / 文件数四重校验

## 目录结构（关键路径）

```
modules/case-intelligence/
├── app.py                    # Streamlit 多页入口
├── pages/                    # 7 页：登录/案件列表/详情/扫描录入/文书生成/模板管理/案件匹配/统计看板
├── src/                      # 内核：database / scanner / parser / extractor / importer /
│   │                         #      case_recognizer / case_matcher / document_generator /
│   │                         #      upload_ingest（v3.4.1 上传落盘）/ ai_engine / langchain_llm
├── bin/                      # 服务 4 件套 + extract CLI + health 探针
├── prompts/                  # AI 提示词规则库（系统大脑，不可随意修改）
├── data/                     # SQLite + inbox/ + 提取物（gitignore，部署挂卷 /data）
├── tests/                    # pytest 全量（135+ passed）
└── .streamlit/config.toml    # maxUploadSize=500MB（v3.4.1）
```

## 遗留与规划（详见 backlog）

- 飞书 Bot 主线（文件上传→提取→生成，`fb01`-`fb08`）——**整体后置**，见 `docs/requirements/backlog.md`
- 文件夹上传：当前以 ZIP 打包替代（浏览器限制），飞书云盘文件夹分享链路待调研