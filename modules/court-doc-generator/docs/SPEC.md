# 出庭手续生成器 · 技术规格（SPEC）

> **文档版本**：v1.0
> **最后更新**：2026-08-17
> **模块名**：court-doc-generator
> **对应需求**：见 [REQUIREMENTS.md](./REQUIREMENTS.md)
> **配套索引**：`docs/SPEC.md`（系统级）→ 本文件（模块级）

---

## 目录

- [0. 文档目的与读者](#0-文档目的与读者)
- [1. 系统概述](#1-系统概述)
- [2. 架构设计](#2-架构设计)
- [3. 技术选型与决策矩阵](#3-技术选型与决策矩阵)
- [4. 目录结构](#4-目录结构)
- [5. 数据模型与存储](#5-数据模型与存储)
- [6. Word 模板与占位符规范](#6-word-模板与占位符规范)
- [7. DOCX → PDF 转换方案](#7-docx--pdf-转换方案)
- [8. PDF 合并方案](#8-pdf-合并方案)
- [9. 浏览器内 PDF 预览方案](#9-浏览器内-pdf-预览方案)
- [10. ZIP 打包与下载](#10-zip-打包与下载)
- [11. UI 设计规范](#11-ui-设计规范)
- [12. 服务管理与部署](#12-服务管理与部署)
- [13. 跨平台分发策略](#13-跨平台分发策略)
- [14. 安全模型](#14-安全模型)
- [15. 性能基线](#15-性能基线)
- [16. 测试策略](#16-测试策略)
- [17. 演进路线（v1.x → v2.x）](#17-演进路线v1x--v2x)
- [18. 实施 Checklist（重新实现指南）](#18-实施-checklist重新实现指南)
- [19. 变更日志](#19-变更日志)

---

## 0. 文档目的与读者

### 0.1 目的

本 SPEC 定义"出庭手续生成器"模块的**可实施技术方案**，作为：

- 从零开发 / 二次开发 / 跨项目借鉴的实现蓝图
- 关键技术决策的论证档案（含评分矩阵）
- 新成员快速 onboarding 的速查手册

### 0.2 目标读者

| 读者 | 关注点 |
|------|--------|
| 主开发（pengming） | 实施清单 §18 |
| 二次开发者 | 技术选型 §3 + 架构 §2 |
| IT 运维 | 服务管理 §12 + 跨平台 §13 |
| Code Reviewer | 决策矩阵 §3 + 安全模型 §14 |

### 0.3 范围与基线

- **基线 Python**：3.10+（兼容 3.9）
- **基线平台**：macOS 11+ / Windows 10+ / Linux Ubuntu 20.04+
- **基线 Streamlit**：≥ 1.40（`use_container_width` 替换 `use_column_width`）
- **基线浏览器**：Chrome 110+ / Safari 16+ / Edge 110+

---

## 1. 系统概述

### 1.1 一句话定义

> **一个本地一键启动的 Streamlit 应用，让法务小白在 5 分钟内独立完成 7 份出庭材料的生成、合并、在线预览与打印，数据全留本机。**

### 1.2 关键能力图

```
┌─────────────────────────────────────────────────────────────┐
│              出庭手续生成器（CGD）                            │
├─────────────────────────────────────────────────────────────┤
│  输入层            │  处理层                  │  输出层      │
│  ──────────        │  ──────────             │  ────────── │
│  • 案件表单       │  • 模板占位符替换       │  • 3 份 DOCX│
│  • 公司/代理人    │  • DOCX → PDF           │  • 4 份 PDF │
│                   │  • PDF 合并              │  • 1 份 ZIP │
│                   │  • ZIP 打包              │  • 1 份合并│
│                   │                          │  • PDF +    │
│                   │                          │    在线预览 │
├─────────────────────────────────────────────────────────────┤
│  数据层：SQLite（公司/代理人/案件/历史）                        │
│  部署层：Streamlit 端口 18501                                  │
│  分发层：本地优先 + 可选 Cloudflare Tunnel                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 不做什么（Anti-Goals）

- ❌ 不做云端 SaaS 化（隐私 + 合规）
- ❌ 不做多用户协同编辑（Streamlit 单进程不适合）
- ❌ 不做 OCR 识别（拍照扫描待需求澄清）
- ❌ 不做 Word 模板的复杂样式保留（仅替换占位符，不重排版）

---

## 2. 架构设计

### 2.1 前后端分层

```
┌─────────────────────────────── 浏览器层 ───────────────────────────────┐
│                                                                          │
│   ┌────────────────────┐    ┌────────────────────┐   ┌────────────────┐ │
│   │ Streamlit 渲染层    │    │ components.html   │   │ PDF.js 全内联  │ │
│   │ (app.py)           │    │ (iframe)          │   │ (base64)       │ │
│   │                    │    │                    │   │                │ │
│   │ • 表单             │    │ • 浏览器内 PDF     │   │ • pdf.min.js   │ │
│   │ • 侧边栏           │    │ • 工具栏           │   │ • pdf.worker   │ │
│   │ • Tab 切换         │    │ • 打印按钮         │   │ • PDF 文件     │ │
│   └────────────────────┘    └────────────────────┘   └────────────────┘ │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ base64 data URI（绕过 SPA 路由）
                                    ▼
┌─────────────────────────────── 服务层（localhost:18501）────────────────┐
│                                                                          │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│   │ app.py      │  │ database.py  │  │ generator.py │  │ docx_to_pdf  │ │
│   │             │  │              │  │              │  │ + pdf_merger │ │
│   │ • UI 控制   │  │ • SQLite     │  │ • 模板替换   │  │ • PDF 转换   │ │
│   │ • 表单事件  │  │ • CRUD       │  │ • ZIP 打包   │  │ • PDF 合并   │ │
│   │ • 状态管理  │  │              │  │              │  │              │ │
│   └─────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│         │                                                                │
│         ▼                                                                │
│   ┌─────────────────────────────┐                                       │
│   │ config.py（路径/常量/JSON） │                                       │
│   │ feishu_api.py（Stub 占位）  │                                       │
│   └─────────────────────────────┘                                       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    ▼
┌─────────────────────────────── 数据 & 资源层 ────────────────────────────┐
│                                                                          │
│   data/court_matters.db  templates/*.docx  static/*.pdf                  │
│   outputs/YYYY-MM-DD_<案号>/  .run/streamlit.{log,pid}                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块边界

| 模块 | 职责 | 不应做 |
|------|------|--------|
| `config.py` | 路径常量、JSON 配置读写 | 业务逻辑 |
| `database.py` | SQLite 连接、CRUD、上下文管理器 | 业务编排 |
| `generator.py` | 模板替换、ZIP 打包、Finder 打开 | UI 交互 |
| `docx_to_pdf.py` | DOCX 解析 + reportlab 重渲染 | 模板替换 |
| `pdf_merger.py` | pypdf 合并 | 文件命名 |
| `feishu_api.py` | 飞书 OpenAPI Stub | 业务决策 |
| `app.py` | Streamlit UI + 编排 | 业务规则 |

### 2.3 状态管理

- **客户端状态**：Streamlit `session_state`（案号、表单临时值）
- **服务端状态**：SQLite 文件（持久化）
- **运行时状态**：`.run/streamlit.pid` + 端口 18501
- **输出状态**：`outputs/<日期>_<案号>/` 目录

### 2.4 错误处理策略

| 层级 | 策略 |
|------|------|
| UI 层 | `st.error()` + 友好提示 + 折叠 traceback |
| 服务层 | try/except → 抛出带上下文的异常 |
| 数据层 | SQLite 完整性约束由 DB 抛出 → 上层捕获 |
| 文件层 | 缺失文件 → 优雅降级（不阻塞其他文件） |

---

## 3. 技术选型与决策矩阵

### 3.1 选型总览

| 层 | 选型 | 版本基线 | 决策依据 |
|----|------|---------|---------|
| 前端框架 | **Streamlit** | ≥ 1.40 | 法务小白能改 + 内置组件够用 |
| 前端增强 | **components.html + PDF.js** | pdfjs-dist 4.x | 浏览器内 PDF 预览 |
| Word 处理 | **python-docx** | ≥ 1.1.0 | 模板填充标准库 |
| PDF 生成 | **reportlab** | ≥ 4.0 | 内置 STSong-Light 中文字体，零外部依赖 |
| PDF 合并 | **pypdf** | ≥ 4.0 | 维护活跃，API 清晰 |
| PDF 缩略图 | **PyMuPDF (pymupdf)** | ≥ 1.24 | 速度快，质量高 |
| 数据库 | **SQLite (stdlib)** | Python 3.10+ 内置 | 零安装，文件即数据库 |
| 进程管理 | **nohup + PID 文件** | - | macOS/Linux 原生 |
| 健康检查 | **curl /_stcore/health** | - | Streamlit 内置 |

### 3.2 关键决策评分（量化对比）

#### D-001：前端框架 Streamlit vs Flask/FastAPI + HTML

| 维度 | Streamlit | Flask + HTML | 权重 | Streamlit 得分 | Flask 得分 |
|------|-----------|--------------|------|---------------|------------|
| 法务小白可改 | ⭐⭐⭐⭐⭐ | ⭐⭐ | 5 | 25 | 10 |
| 表单/状态组件 | ⭐⭐⭐⭐⭐ | ⭐⭐ | 4 | 20 | 8 |
| 内置 data UI | ⭐⭐⭐⭐⭐ | ⭐ | 3 | 15 | 3 |
| 内置文件上传/下载 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 3 | 15 | 9 |
| PDF 内嵌 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 2 | 6 | 10 |
| 总分 | - | - | - | **81** | 40 |

**结论**：选 Streamlit。PDF 内嵌通过 components.html + PDF.js 全内联补齐。

#### D-002：DOCX → PDF 转换方案

| 方案 | 中文支持 | 跨平台 | 外部依赖 | 样式保真 | 评分 |
|------|---------|--------|---------|---------|------|
| A. reportlab 自渲染 | ⭐⭐⭐⭐⭐（STSong-Light） | ⭐⭐⭐⭐⭐（纯 Python） | 0 | ⭐⭐⭐（只保留文本） | 22 |
| B. libreoffice CLI | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 需装 LibreOffice | ⭐⭐⭐⭐⭐ | 22 |
| C. docx2pdf | ⭐⭐⭐⭐ | ⭐⭐（Win/Mac） | 需装 Office | ⭐⭐⭐⭐⭐ | 16 |
| D. docx2pdf + mammoth | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 0 | ⭐⭐⭐ | 18 |

**结论**：本期选 **A（reportlab 自渲染）**。理由：
1. 零外部依赖（法务小白无需装 LibreOffice）
2. STSong-Light 中文显示完美
3. 样式保真需求低（出庭材料格式固定，重渲染可控）
4. B/C 可作为未来升级路径（保留切换点）

> 注：当前源码 `docx_to_pdf.py` 已实现 reportlab 方案但**未被调用**（这是 P0 bug，需修复）。

#### D-003：PDF 浏览器预览方案

| 方案 | 跨平台 | 跨 SPA | 离线可用 | 中文 | 评分 |
|------|--------|--------|---------|------|------|
| A. PDF.js + /static/ HTTP | ⭐⭐⭐ | ❌ 被拦截 | ⭐ | ⭐⭐⭐⭐ | 12 |
| B. PDF.js + CDN | ⭐⭐⭐ | ❌ sandbox 拦截 | ⭐ | ⭐⭐⭐⭐ | 10 |
| C. PDF.js 全内联 base64 | ⭐⭐⭐⭐⭐ | ✅ 绕过 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **24** |
| D. 系统 Preview（subprocess.open） | ⭐⭐（仅 Mac） | ✅ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 16 |

**结论**：**C 为主，D 为降级**。

- 主方案：PDF.js 全内联 base64 data URI
- 关键陷阱：`new Function()` 不能泄漏 `var pdfjsLib`，**必须 `<script>eval(atob(mainB64))</script>`**
- Worker 通过 Blob URL 注入
- macOS 平台额外提供 D 降级按钮（永不删除）

#### D-004：占位符替换策略

| 方案 | 复杂度 | 顺序保证 | 样式保留 | 评分 |
|------|--------|---------|---------|------|
| A. 段落内按位置 | ⭐⭐ | ✅ 文档顺序 | ⭐⭐⭐⭐ | **18** |
| B. 命名占位符 `{{name}}` | ⭐⭐⭐⭐ | ❌ 需命名空间 | ⭐⭐⭐⭐ | 14 |
| C. Jinja2 模板 | ⭐⭐⭐⭐⭐ | ✅ | ⭐⭐⭐ | 12 |

**结论**：**A（中文全角【】按文档顺序）**。理由：
1. 已有 Word 模板使用【】，法务熟悉
2. 实现简单（`re.sub` 从后往前）
3. 顺序保证（从后往前替换防位置偏移）
4. python-docx 自动合并 runs，无需手动处理

#### D-005：服务端口

| 端口 | 选择理由 | 评分 |
|------|---------|------|
| 8501 | Streamlit 默认，**高冲突** | ❌ |
| 8080 | 通用 Web 服务端口 | ❌ |
| 18501 | **避开所有常用端口**，固定 | ✅ |

**结论**：**18501**。在启动脚本中检测冲突时明确报错，**不允许自动换端口**（避免找不到）。

---

## 4. 目录结构

### 4.1 重新实现的目录树

```
court-doc-generator/
├── 启动.command                    # macOS 双击启动入口
├── 启动.bat                        # Windows 双击启动入口（→ bin/start.py）
├── README.md                       # 模块说明
├── REQUIREMENTS.md                 # 本文档（已生成）
├── SPEC.md                         # 技术规格（本文件）
├── module.yaml                      # 模块注册元数据
├── requirements.txt                # 依赖锁版本
│
├── app.py                          # Streamlit 主入口
├── config.py                       # 路径常量 + JSON 配置
├── database.py                     # SQLite 模型
├── generator.py                    # 模板替换 + ZIP 打包
├── docx_to_pdf.py                  # DOCX → PDF（reportlab）
├── pdf_merger.py                   # PDF 合并（pypdf）
├── feishu_api.py                   # 飞书 API（Stub）
├── pdf_viewer_component.py         # PDF.js 全内联预览组件 🆕
│
├── templates/                      # Word 模板（用户后续添加）
│   ├── 2.法定代表人证明.docx
│   ├── 4.授权委托书.docx
│   └── 5.推荐信.docx
│
├── static/                          # 静态 PDF + PDF.js 资源
│   ├── 1.营业执照复印件.pdf        # 用户自行准备
│   ├── 法人身份证.pdf
│   ├── 代理人劳动合同.pdf
│   ├── 代理人身份证.pdf
│   └── pdfjs/                      # 🆕 PDF.js 库（pdf.min.js + worker）
│       ├── pdf.min.js
│       └── pdf.worker.min.js
│
├── bin/                            # 服务管理脚本
│   ├── manage.sh                   # 统一入口
│   ├── manage.bat                  # Windows 统一入口
│   ├── start.sh
│   ├── start.bat                   # 调用 start.py
│   ├── start.py                    # 纯 Python 跨平台启动 🆕
│   ├── stop.sh
│   ├── stop.bat
│   ├── restart.sh
│   ├── restart.bat
│   ├── status.sh
│   └── status.bat
│
├── outputs/                        # 生成结果（不入 git）
│   └── 2026-08-17_（2026）京0101民初1234号/
│       ├── 01_营业执照.pdf
│       ├── 02_法定代表人证明_<案号>.docx
│       ├── 03_法人身份证.pdf
│       ├── 04_授权委托书_<案号>.docx
│       ├── 05_推荐信_<案号>.docx
│       ├── 06_代理人劳动合同.pdf
│       ├── 07_代理人身份证.pdf
│       ├── 00_合并出庭手续_<案号>.pdf  🆕
│       └── 出庭手续全套_<案号>.zip
│
├── data/                           # SQLite 数据库（不入 git）
│   └── court_matters.db
│
├── .run/                           # 运行时（不入 git）
│   ├── streamlit.pid
│   └── streamlit.log
│
└── tests/                          # 单元测试
    ├── test_placeholder.py
    ├── test_database.py
    ├── test_generator.py
    └── test_pdf_merger.py
```

### 4.2 与 SPEC.md（系统级）的关系

- 系统 SPEC 规定每个模块应有 `src/`，但**本期采用顶层平铺**（与原代码现状一致）
- `src/` 的好处是清晰的包边界，缺点是文件层级深；顶层平铺符合"法务小白能改"原则
- 已在 README 顶部注明此差异

---

## 5. 数据模型与存储

### 5.1 ER 图

```
┌──────────────┐         ┌──────────────┐
│  companies   │ 1     * │   agents     │
│              │◄────────│              │
│ id (PK)      │         │ id (PK)      │
│ name (UQ)    │         │ name         │
│ credit_code  │         │ gender       │
│ legal_rep_*  │         │ id_card      │
│ address      │         │ position     │
│ phone        │         │ phone        │
│ is_default   │         │ company_id FK│
└──────────────┘         │ is_default   │
                         └──────────────┘
                                  ▲
                                  │ *
                          ┌───────┴──────┐
                          │    cases     │
                          │              │
                          │ id (PK)      │
                          │ case_number  │
                          │ case_cause   │
                          │ court        │
                          │ hearing_date │
                          │ opposing_*   │
                          │ our_role     │
                          │ authority   │
                          │ company_id FK│
                          │ agent_id FK │
                          │ notes       │
                          └──────────────┘
                                  ▲
                                  │ *
                       ┌──────────┴───────────┐
                       │ generation_history  │
                       │                      │
                       │ id (PK)              │
                       │ case_id FK           │
                       │ case_number          │
                       │ output_dir           │
                       │ file_count           │
                       │ generated_at         │
                       └──────────────────────┘
```

### 5.2 Schema 定义（database.py）

```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    credit_code TEXT,
    legal_rep_name TEXT NOT NULL,
    legal_rep_position TEXT,
    legal_rep_id_card TEXT,
    address TEXT,
    phone TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT,
    id_card TEXT,
    position TEXT,
    phone TEXT,
    company_id INTEGER,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE (name, company_id)              -- 修复：旧版用 (name, id_card) 有 bug
);

CREATE TABLE cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT NOT NULL,
    case_cause TEXT NOT NULL,
    court TEXT NOT NULL,
    hearing_date TEXT,
    opposing_party TEXT,
    our_role TEXT NOT NULL,
    authority_type TEXT DEFAULT '特别授权',
    company_id INTEGER,
    agent_id INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE generation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    case_number TEXT,
    output_dir TEXT,
    file_count INTEGER,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(id)
);
```

### 5.3 关键修复点

| 旧版问题 | 修复 |
|---------|------|
| `agents.UNIQUE(name, id_card)` 当 id_card 为空时不同人变同一人 | 改为 `UNIQUE(name, company_id)` |
| `ensure_default_*` 模块级副作用 | 移入 `main()` 或 `initialize()` |
| `is_default` 隐式管理无 UI | 增加 `set_default_company/agent` UI 按钮 |
| 没有 UPSERT 唯一性文档 | 增加 schema 注释说明 |

---

## 6. Word 模板与占位符规范

### 6.1 占位符格式

**使用中文全角【】**（U+3010 U+3011），区别于英文 `[]`。

### 6.2 替换顺序规则

> **按【】在文档中的物理出现顺序（从左到右、从上到下）依次消费 values 列表。**

```
模板段落："【】年【】月【】日"
values: ["2026", "8", "17"]
结果：   "2026年8月17日"
```

### 6.3 关键实现细节

```python
PLACEHOLDER_PATTERN = re.compile(r"【】")

def replace_placeholders_by_position(paragraph, values):
    # 1. 合并段落所有 runs（python-docx 自动）
    full_text = "".join(run.text for run in paragraph.runs)
    
    # 2. 找出所有【】位置
    matches = list(PLACEHOLDER_PATTERN.finditer(full_text))
    
    # 3. 不足的值填空串
    if len(values) < len(matches):
        values = list(values) + [""] * (len(matches) - len(values))
    
    # 4. 从后往前替换（避免位置偏移！）
    for i in range(len(matches) - 1, -1, -1):
        match = matches[i]
        value = str(values[i]) if values[i] is not None else ""
        new_text = new_text[:match.start()] + value + new_text[match.end():]
    
    # 5. 写回 paragraph.runs[0]，其余清空
    if new_text != full_text:
        paragraph.runs[0].text = new_text
        for run in paragraph.runs[1:]:
            run.text = ""
    
    return len(matches)
```

### 6.4 各模板占位符清单

| 模板 | 数量 | 替换内容（按顺序） |
|------|------|-------------------|
| 法定代表人证明 | 3 | 年、月、日 |
| 授权委托书 | 5 | 案由描述、案号、年、月、日 |
| 推荐信 | 6 | 法院、案由描述、案号、年、月、日 |

---

## 7. DOCX → PDF 转换方案

### 7.1 决策

**采用 reportlab 自渲染方案（方案 A，详见 §3.2 D-002）**。

### 7.2 字体处理

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 仅 STSong-Light 可用，其他中文字体会 KeyError
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
```

### 7.3 段落样式映射

| DOCX 特征 | reportlab 样式 |
|-----------|---------------|
| 字号 ≥ 16 | ChineseTitle（18pt 居中） |
| 居中对齐 + 文字 ≤ 25 字 | ChineseTitle |
| 居中对齐 + 文字 > 25 字 | ChineseNoIndent |
| 右对齐 | ChineseRight |
| 默认 | ChineseBody（12pt，首行缩进 2 字符） |

### 7.4 表格处理

- 简单表格：reportlab `Table` + `TableStyle`
- 边框：灰色 0.5pt
- 字体：STSong-Light 10pt
- 垂直对齐：MIDDLE

### 7.5 集成点

```python
# generator.py 中
from docx_to_pdf import docx_to_pdf

# 替换【】 → 生成 DOCX → 转 PDF
for template_key, output_name in [("legal_rep_cert", "02_..."), ...]:
    docx_path = output_dir / f"{output_name}.docx"
    pdf_path = output_dir / f"{output_name.replace('.docx', '.pdf')}"
    generate_dynamic_docx(template_key, values, docx_path)  # 已有
    docx_to_pdf(docx_path, pdf_path)  # 🆕 新增调用
```

> 注：当前源码 `docx_to_pdf` 函数已实现但未被调用（已记入 §18 Checklist）。

---

## 8. PDF 合并方案

### 8.1 合并顺序（出庭提交顺序）

```
01_营业执照.pdf
02_法定代表人证明_<案号>.pdf
03_法人身份证.pdf
04_授权委托书_<案号>.pdf
05_推荐信_<案号>.pdf
06_代理人劳动合同.pdf
07_代理人身份证.pdf
        ↓ 合并为
00_合并出庭手续_<案号>.pdf  🆕
```

### 8.2 实现

```python
from pypdf import PdfWriter
from pathlib import Path

def merge_pdfs(pdf_paths: list[Path], output_path: Path) -> Path:
    writer = PdfWriter()
    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            continue  # 优雅降级
        writer.append(str(pdf_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path
```

### 8.3 集成点

`generator.py:generate_court_matters()` 末尾：

```python
# 🆕 合并 7 份 PDF
merged_pdf = output_dir / f"00_合并出庭手续_{safe_case}.pdf"
merge_pdfs(
    sorted(output_dir.glob("0?_*.pdf")),  # 匹配 01-07
    merged_pdf,
)

# ZIP 也包含合并 PDF
zip_path = output_dir / f"出庭手续全套_{safe_case}.zip"
```

---

## 9. 浏览器内 PDF 预览方案

### 9.1 关键技术决策：PDF.js 全内联 base64

**为什么必须全内联**（Streamlit SPA 路由拦截，详见 common_pitfalls）：

| 路径 | 行为 | 结果 |
|------|------|------|
| `/static/pdfjs/pdf.min.js` | Streamlit SPA 返回 HTML | ❌ MIME 错误 |
| `/static/merged/xxx.pdf` | Streamlit SPA 返回 HTML | ❌ 同上 |
| CDN URL | sandboxed iframe 拦截 | ❌ CSP 跨域 |
| **base64 内联** | 绕过所有拦截 | ✅ |

### 9.2 组件接口

```python
# pdf_viewer_component.py
import base64
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

@st.cache_resource
def _load_pdfjs_libs():
    """一次性加载 PDF.js 主库 + worker（base64 缓存）"""
    pdfjs_dir = Path(__file__).parent / "static" / "pdfjs"
    main_b64 = base64.b64encode((pdfjs_dir / "pdf.min.js").read_bytes()).decode()
    worker_b64 = base64.b64encode((pdfjs_dir / "pdf.worker.min.js").read_bytes()).decode()
    return main_b64, worker_b64

def render_pdf_viewer(pdf_path: Path, height: int = 800):
    """在 Streamlit 中渲染 PDF 预览组件。"""
    main_b64, worker_b64 = _load_pdfjs_libs()
    pdf_b64 = base64.b64encode(Path(pdf_path).read_bytes()).decode()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {{ margin: 0; font-family: -apple-system, sans-serif; }}
        #toolbar {{
          padding: 8px; background: #f5f5f5;
          display: flex; gap: 8px; align-items: center;
        }}
        button {{
          padding: 4px 12px; border: 1px solid #ddd;
          background: white; border-radius: 4px; cursor: pointer;
        }}
        button:hover {{ background: #f0f0f0; }}
        #pdf-container {{ overflow: auto; height: {height}px; }}
        .page {{ margin: 8px auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        @media print {{
          #toolbar {{ display: none; }}
          .page {{ page-break-after: always; box-shadow: none; }}
        }}
      </style>
    </head>
    <body>
      <div id="toolbar">
        <button onclick="zoom(-0.1)">➖</button>
        <button onclick="zoom(0.1)">➕</button>
        <button onclick="prevPage()">◀</button>
        <span id="page-info">1 / 1</span>
        <button onclick="nextPage()">▶</button>
        <button onclick="printAll()" style="margin-left:auto;">🖨 打印全部</button>
      </div>
      <div id="pdf-container"></div>
      
      <script>
        // 🆕 Worker Blob URL 注入
        const workerBlob = new Blob(
          [Uint8Array.from(atob('{worker_b64}'), c => c.charCodeAt(0))],
          {{ type: 'application/javascript' }}
        );
        pdfjsLib.GlobalWorkerOptions.workerSrc = 
          URL.createObjectURL(workerBlob);
      </script>
      <script>eval(atob('{main_b64}'))</script>  <!-- 🆕 必须 eval，不能 new Function -->
      <script>
        // 🆕 PDF 数据通过 atob 传入，不用 URL
        pdfjsLib.getDocument({{ data: atob('{pdf_b64}') }}).promise.then(pdf => {{
          renderAllPages(pdf);
        }});
      </script>
    </body>
    </html>
    """
    components.html(html, height=height + 80)
```

### 9.3 关键陷阱（必须遵守）

> ⚠️ **绝对不能使用 `new Function(mainCode)`**：`var pdfjsLib` 不会从 Function 作用域泄漏到外层。
>
> ✅ **必须使用 inline `<script>eval(atob(mainB64))</script>`**：让 `var` 暴露到当前作用域。

### 9.4 降级方案：系统 Preview 按钮

```python
import subprocess

def open_in_preview(pdf_path: Path):
    """macOS: 用系统 Preview 打开"""
    subprocess.Popen(["open", str(pdf_path)])

def open_in_default(pdf_path: Path):
    """跨平台: 调用默认 PDF 阅读器（使用列表参数，避免 shell 注入）"""
    import platform, subprocess
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", str(pdf_path)])
    elif system == "Windows":
        # Windows 用 os.startfile 直接走 ShellExecute，避开 shell 解析
        os.startfile(str(pdf_path))  # noqa: S606  # 安全：Path 是内部可控
    else:
        subprocess.Popen(["xdg-open", str(pdf_path)])
```

> macOS 必须保留 `subprocess.Popen(["open", ...])` 降级按钮，永不删除。

---

## 10. ZIP 打包与下载

### 10.1 打包顺序

```python
import zipfile

def zip_outputs(output_dir: Path, case_number: str) -> Path:
    safe_case = sanitize_filename(case_number)
    zip_path = output_dir / f"出庭手续全套_{safe_case}.zip"
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 🆕 先放合并 PDF（最显眼）
        merged = output_dir / f"00_合并出庭手续_{safe_case}.pdf"
        if merged.exists():
            zf.write(merged, arcname=merged.name)
        
        # 然后按 01-07 顺序
        for file in sorted(output_dir.glob("0?_*.pdf")):
            zf.write(file, arcname=file.name)
        
        for file in sorted(output_dir.glob("*.docx")):
            zf.write(file, arcname=file.name)
    
    return zip_path
```

### 10.2 中文文件名编码

ZIP 标准（PKZIP）默认文件名用 CP437。中文文件名必须：

```python
# 方法 1：使用 UTF-8 标志位
zf.write(file, arcname=file.name)  # Python 3 默认用 UTF-8 编码 arcname

# 方法 2：手动编码
arcname_utf8 = file.name.encode('utf-8').decode('utf-8')  # 显式 UTF-8
```

> 注：现代 macOS / Windows 解压器都识别 UTF-8 flag，不需要 cp936 转换。

---

## 11. UI 设计规范

### 11.1 设计风格：Vercel/Linear 风

| 维度 | 规范 |
|------|------|
| 主色 | `#0a0a0a`（接近黑） |
| 成功色 | `#10b981` |
| 警告色 | `#f59e0b` |
| 错误色 | `#ef4444` |
| 字体 | Inter（西文）+ PingFang SC（中文） |
| 圆角 | 8px - 12px |
| 微动画 | hover 抬升 + transition 0.15s |
| 渐变 | 克制（仅 logo / 主按钮） |
| 字间距 | -0.005em |

### 11.2 Streamlit 主题定制

```python
# .streamlit/config.toml
[theme]
primaryColor = "#0a0a0a"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f5f5f5"
textColor = "#1a1a1a"
font = "sans serif"

[server]
headless = true
port = 18501
```

### 11.3 页面布局

```
┌──────────────────────────────────────────────────────────┐
│  Sidebar (1/4)        │  Main Area (3/4)                  │
│                       │                                  │
│  ⚖️ 出庭手续生成器     │  📋 生成出庭手续                  │
│  ──────────────       │  ──────────────                  │
│  🏢 委托单位           │  ┌─ 当前: 北京雷石 × 张洋 ─┐    │
│  [公司选择 ▼]         │  │                          │    │
│  [+ 添加/编辑]         │  │  Tab: [🆕新建] [📜历史] │   │
│  ──────────────       │  │                          │    │
│  👤 代理人             │  │  案号: ...              │    │
│  [代理人选择 ▼]        │  │  案由: ...              │    │
│  [+ 添加/编辑]         │  │  ...                    │    │
│  ──────────────       │  └──────────────────────────┘    │
│  📡 飞书集成           │                                  │
│  ✅ 飞书集成已启用      │  [🚀 生成出庭手续 (7 份文件)]    │
└──────────────────────────────────────────────────────────┘
```

### 11.4 关键 UI 约束

| 元素 | 约束 |
|------|------|
| 必填字段 | 标注 `*` + 缺失时按钮置灰 |
| 主操作按钮 | 文案明确（如 "🚀 生成出庭手续（7 份文件）"） |
| 错误提示 | `st.error()` + 折叠 traceback |
| 成功提示 | `st.success()` + 自动跳转 |
| 历史列表 | 每条带"🔄 重新生成"按钮 |
| 身份证号 | UI 默认遮罩，点 👁 切换显示 |

---

## 12. 服务管理与部署

### 12.1 bin/manage.sh 接口

```bash
bash bin/manage.sh {start|stop|restart|status}
```

### 12.2 三重进程定位

> **必须三重验证**，避免 PID 文件残留导致误操作。

```bash
is_service_running() {
    local pid_file="$2"
    local port="$3"
    local service_name="$4"
    
    # 1. PID 文件存在且进程存在
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0  # 进程活着
        fi
    fi
    
    # 2. 端口被占用（lsof）
    if lsof -ti :"$port" >/dev/null 2>&1; then
        return 0
    fi
    
    # 3. 进程名匹配（ps）
    if pgrep -f "$service_name" >/dev/null 2>&1; then
        return 0
    fi
    
    return 1
}
```

### 12.3 健康检查

```bash
health_check() {
    local url="http://localhost:${SERVICE_PORT}/_stcore/health"
    local retries=10
    for i in $(seq 1 $retries); do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo "✅ 健康检查通过"
            return 0
        fi
        sleep 1
    done
    echo "❌ 健康检查失败"
    return 1
}
```

### 12.4 macOS bash 3.2 兼容

```bash
# ❌ 错误（bash 4 数组语法）
pids+=($pid)

# ✅ 正确（字符串拼接）
pids="$pids $pid"

# 去重输出
echo "$pids" | tr ' ' '\n' | grep -v '^$' | sort -u
```

### 12.5 .command 窗口保持

```bash
#!/bin/bash
# 启动.command
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXIT_CODE=0
"$SCRIPT_DIR/bin/manage.sh" start || EXIT_CODE=$?
echo ""
echo "服务已启动，访问 http://localhost:18501"
echo "关闭窗口请按 Ctrl+C"
read -p "按回车键关闭此窗口..." _
exit $EXIT_CODE
```

### 12.6 Windows 启动（bin/start.py + 启动.bat）

```python
# bin/start.py（纯 Python，零外部命令依赖）
import subprocess, sys, time, webbrowser, os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SERVICE_PORT = 18501

def find_python():
    """按优先级查找 Python"""
    candidates = [
        SCRIPT_DIR / ".venv" / "Scripts" / "python.exe",  # 1. 项目虚拟环境
    ]
    # 2. PATH 中的 python / python3
    for name in ["python", "python3"]:
        r = subprocess.run(["where", name], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip().split("\n")[0]
    # 3. 都没找到 → 打开下载页
    webbrowser.open("https://www.python.org/downloads/")
    sys.exit(1)

def health_check():
    import socket
    for _ in range(15):
        with socket.socket() as s:
            if s.connect_ex(("localhost", SERVICE_PORT)) == 0:
                return True
        time.sleep(1)
    return False

if __name__ == "__main__":
    python = find_python()
    # 启动 streamlit
    subprocess.Popen([python, "-m", "streamlit", "run", "app.py",
                       "--server.port", str(SERVICE_PORT),
                       "--server.headless", "true"],
                      cwd=SCRIPT_DIR)
    if health_check():
        webbrowser.open(f"http://localhost:{SERVICE_PORT}")
    input("按回车键关闭窗口...")
```

```batch
@echo off
:: 启动.bat（仅做 Python 探测）
chcp 65001 >nul
cd /d "%~dp0"
python bin\start.py
if errorlevel 1 (
  echo 未检测到 Python，请访问 https://www.python.org/downloads/ 安装
  pause
)
```

> **关键约束**：不要用 `py` 命令！Windows 10/11 自带 Python Launcher，没装 Python 时会触发 Microsoft Store 引导。

### 12.7 端口配置

固定 **18501**，避开：80, 443, 3000, 5000, 8000, 8080, 8501, 8888。

冲突时不自动换端口，启动脚本明确报错：

```bash
if lsof -ti :"$SERVICE_PORT" >/dev/null 2>&1; then
    echo "❌ 端口 $SERVICE_PORT 被占用："
    lsof -i :"$SERVICE_PORT"
    echo "请关闭占用进程或修改 SERVICE_PORT"
    exit 1
fi
```

---

## 13. 跨平台分发策略

### 13.1 本地优先原则

> **本地优先**：分发整个文件夹（zip），用户解压后双击启动。
> 严禁直接给 localhost 地址或内网 IP 让对方远程访问。

### 13.2 打包排除目录

```
.venv/        虚拟环境
outputs/      历史生成文件
.run/        PID +日志
__pycache__/  编译缓存
static/merged/ 静态资源缓存
data/         SQLite 数据库
```

### 13.3 临时公网分享（可选，**仅限演示**）

```bash
# bin/share-public.sh
brew install cloudflared
cloudflared tunnel --url http://localhost:18501
```

> 临时性：每次重启 URL 变；需保持终端开；**禁止生产环境使用**。

### 13.4 局域网共享

```bash
# .streamlit/config.toml
[server]
headless = true        # 启用局域网访问
```

启动后日志会显示 Network URL：`http://192.168.x.x:18501`。

---

## 14. 安全模型

### 14.1 数据隔离

| 数据 | 存储位置 | 是否上传 |
|------|---------|---------|
| 案件信息 | 本地 SQLite | ❌ |
| 公司/代理人 | 本地 SQLite | ❌ |
| 身份证号 | 本地 SQLite | ❌ |
| 生成 PDF | 本地 outputs/ | ❌ |
| 飞书凭证 | 本地 .env | ❌ |

### 14.2 PII 防护（**关键**）

> ❌ **严禁硬编码真实 PII 到源码**

旧版问题（app.py:54-75）：
```python
default_agent = {
    "id_card": "230230198609092143",  # ← 真实身份证号
    "phone": "18810282639",           # ← 真实手机号
}
```

**新版方案**：
```python
def ensure_default_company_and_agent():
    """首次启动时，仅创建空记录，UI 引导用户填写"""
    if not db.list_companies():
        # 仅创建空记录，UI 引导填真实信息
        db.upsert_company({
            "name": "",  # 用户必须填
            "legal_rep_name": "",
            # ...
        })
        # UI 显示：⚠️ 请在左侧填写委托单位信息
```

### 14.3 .gitignore 必须屏蔽

```
data/          # SQLite（含敏感数据）
outputs/
.run/
.venv/
__pycache__/
.env
*.zip
```

### 14.4 UI 字段遮罩

```python
def mask_id_card(id_card: str) -> str:
    if not id_card or len(id_card) < 8:
        return ""
    return id_card[:4] + "*" * (len(id_card) - 8) + id_card[-4:]
# 输出：2302********2143
```

### 14.5 飞书凭证

> 飞书 app_id / app_secret 走 `.env` 文件（不入 git），调飞书 API 时不回显凭证。

---

## 15. 性能基线

### 15.1 性能指标

| 场景 | 指标 |
|------|------|
| 单案件端到端生成 | ≤ 30s |
| DOCX → PDF 转换（单文件） | ≤ 3s |
| 7 份 PDF 合并 | ≤ 2s |
| ZIP 打包 | ≤ 1s |
| PDF 浏览器内首屏 | ≤ 3s（5MB PDF） |
| UI 表单响应 | ≤ 200ms |

### 15.2 性能优化要点

- `@st.cache_resource` 缓存 PDF.js base64（避免每次重编码）
- PDF 文件按需编码（每个 PDF 单独 base64 一次）
- 缩略图用 PyMuPDF，控制单张 ≤ 50KB

---

## 17. 演进路线（v1.x → v2.x）

### 17.1 v1.0（MVP 已恢复）

- ✅ 7 份材料生成 + DOCX → PDF
- ✅ PDF 合并
- ✅ ZIP 打包
- ✅ 浏览器内 PDF 预览 + 一键打印
- ✅ macOS / Windows 启动脚本

### 17.2 v1.1（短期内）

- 飞书多维表格案件同步（用 lark-mcp）
- 飞书云盘文件上传
- 飞书 IM 通知

### 17.3 v1.2

- PDF 缩略图网格（多页概览）
- 案件模板（预填常用案由）
- 历史案件导出 CSV

### 17.4 v2.0（需求澄清后）

- 拍照扫描功能
- OCR 识别内容
- 法院案件查询接口对接

---

## 18. 实施 Checklist（重新实现指南）

> 本节是从零 / 修复源码的**逐步可执行清单**，每条对应一个可验证的产物。

### Phase 0：基础设施（半天）

- [ ] **C-001**：恢复 `src/` 或确认顶层平铺（统一所有 import）
- [ ] **C-002**：补 `.gitignore`（屏蔽 `data/`、`outputs/`、`.run/`、`.env`、`.venv/`）
- [ ] **C-003**：写 `requirements.txt`（streamlit>=1.40, python-docx>=1.1.0, pypdf>=4.0, pymupdf>=1.24, reportlab>=4.0）
- [ ] **C-004**：写 `module.yaml`（对齐 SPEC 字段）
- [ ] **C-005**：创建 `templates/`、`static/`、`data/`、`outputs/`、`.run/`、`bin/`、`tests/` 目录

### Phase 1：核心逻辑（半天）

- [ ] **C-101**：实现 `config.py`（路径常量 + JSON 配置）
- [ ] **C-102**：实现 `database.py`（Schema + CRUD + 上下文管理器）
- [ ] **C-103**：修复 `agents` 唯一性 bug（`UNIQUE(name, company_id)`）
- [ ] **C-104**：实现 `generator.py:replace_placeholders_by_position`（从后往前替换）
- [ ] **C-105**：实现 `generator.py:generate_court_matters`（含 PDF 转换/合并调用）
- [ ] **C-106**：修复 `ensure_default_*` 不写死 PII

### Phase 2：PDF 处理（半天）

- [ ] **C-201**：实现 `docx_to_pdf.py`（reportlab + STSong-Light）
- [ ] **C-202**：在 generator.py 中调用 docx_to_pdf
- [ ] **C-203**：实现 `pdf_merger.py`（pypdf）
- [ ] **C-204**：在 generator.py 中调用 merge_pdfs
- [ ] **C-205**：输出目录增加 `00_合并出庭手续_<案号>.pdf`

### Phase 3：浏览器内 PDF 预览（半天）

- [ ] **C-301**：下载 PDF.js 到 `static/pdfjs/`（pdf.min.js + pdf.worker.min.js）
- [ ] **C-302**：实现 `pdf_viewer_component.py:render_pdf_viewer`
- [ ] **C-303**：使用 `<script>eval(atob(mainB64))</script>`（不要 new Function）
- [ ] **C-304**：Worker 通过 Blob URL 注入
- [ ] **C-305**：PDF 数据用 `atob` 传入（不通过 URL）
- [ ] **C-306**：工具栏：缩放/翻页/打印全部
- [ ] **C-307**：@media print 隐藏工具栏
- [ ] **C-308**：保留 macOS Preview 降级按钮

### Phase 4：UI（半天）

- [ ] **C-401**：实现 `app.py` 侧边栏（公司/代理人/飞书状态）
- [ ] **C-402**：实现 `app.py` 主区域（新建/历史 Tab）
- [ ] **C-403**：表单字段：必填标 * + 实时校验
- [ ] **C-404**：案由描述预览实时刷新
- [ ] **C-405**：UI 视觉对齐 Vercel/Linear 风格
- [ ] **C-406**：身份证号字段 UI 遮罩

### Phase 5：服务管理 + 跨平台（半天）

- [ ] **C-501**：写 `bin/manage.sh`（start/stop/restart/status 统一入口）
- [ ] **C-502**：写 `bin/start.sh` / `stop.sh` / `restart.sh` / `status.sh`
- [ ] **C-503**：写 `bin/manage.bat` / `start.bat` / `start.py`
- [ ] **C-504**：三重进程定位（PID + 端口 + 进程名）
- [ ] **C-505**：健康检查 `curl /_stcore/health`
- [ ] **C-506**：macOS bash 3.2 兼容（字符串拼接代替数组 +=）
- [ ] **C-507**：写 `启动.command`（含 read 等待）
- [ ] **C-508**：写 `启动.bat`（Windows 双击入口）
- [ ] **C-509**：端口固定 18501，冲突明确报错

### Phase 6：测试 + 文档（半天）

- [ ] **C-601**：写 `tests/test_placeholder.py`（覆盖 §10.2 单元测试）
- [ ] **C-602**：写 `tests/test_database.py`
- [ ] **C-603**：写 `tests/test_generator.py`
- [ ] **C-604**：写 `tests/test_pdf_merger.py`
- [ ] **C-605**：在 `README.md` 给出 macOS / Windows / Linux 启动指引
- [ ] **C-606**：在 `backlog.md` 标记本期需求为 done
- [ ] **C-607**：在 `CHANGELOG.md` 记录 v1.0 变更

### Phase 7：飞书 Stub（半天，可选）

- [ ] **C-701**：实现 `feishu_api.py` 占位函数（明确标注 stub）
- [ ] **C-702**：UI 显示飞书状态（已启用/未启用）

---

## 19. 变更日志

| 日期 | 版本 | 变更摘要 |
|------|------|---------|
| 2026-08-17 | v1.0 | 首次从 docs/ + qoder-raw 全量反推整合，确立技术规格 |