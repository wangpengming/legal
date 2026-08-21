# ⚖️ 出庭手续生成器

> React + FastAPI 全栈应用 · 法务一键生成出庭 7 份材料

**v2.0.0** · 2026-08-21

---

## ✨ 核心功能

- 📋 **案件管理**：新建/编辑/删除案件，二次确认防误操作
- 🏢 **公司/代理人管理**：委托单位、代理人信息维护，支持上传自定义 PDF
- 🚀 **一键生成**：7 份出庭材料自动生成（DOCX 模板填充 + DOCX→PDF 转换 + PDF 合并）
- 👁 **浏览器内 PDF 预览**：基于 PDF.js，支持缩放/翻页/打印
- 🖨 **在线打印**：浏览器打印预览 + 系统打印机直打
- 📸 **拍照扫描（OCR）**：上传起诉状/传票图片，Tesseract 识别后自动回填表单
- 👥 **多用户隔离**：注册/登录 + workspace 数据隔离（每人独立 DB + 文件）
- 📦 **ZIP 打包下载**：所有生成文件 + 合并 PDF 一键打包

---

## 📦 输出清单（按出庭顺序）

| #  | 文件 | 类型 | 来源 |
|----|------|------|------|
| 00 | `00_合并出庭手续_<案号>.pdf` | 合并 PDF | 7 份 PDF 自动合并 |
| 01 | `01_营业执照.pdf` | 静态 | `static/1.营业执照复印件.pdf` |
| 02 | `02_法定代表人证明_<案号>.{docx,pdf}` | 动态 | `templates/2.法定代表人证明.docx` |
| 03 | `03_法人身份证.pdf` | 静态 | `static/法人身份证.pdf` |
| 04 | `04_授权委托书_<案号>.{docx,pdf}` | 动态 | `templates/4.授权委托书.docx` |
| 05 | `05_推荐信_<案号>.{docx,pdf}` | 动态 | `templates/5.推荐信.docx` |
| 06 | `06_代理人劳动合同.pdf` | 静态 | `static/代理人劳动合同.pdf` |
| 07 | `07_代理人身份证.pdf` | 静态 | `static/代理人身份证.pdf` |

---

## 🚀 快速启动

### 前置条件

- **Python 3.10+**（推荐 3.12）
- **Node.js 18+**（推荐 20 LTS）
- **npm**（随 Node.js 安装）
- **Tesseract**（可选，仅 OCR 扫描需要）：`brew install tesseract tesseract-lang`

### 一键启动（推荐）

```bash
cd modules/court-doc-generator

# 1. 创建虚拟环境 + 安装依赖（首次）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r backend/requirements.txt

# 2. 安装前端依赖（首次）
cd frontend && npm install && cd ..

# 3. 一键启动
python3 bin/start.py
```

启动后：
- 前端界面：http://localhost:18502
- 后端 API 文档：http://localhost:8001/docs

### 单独启动

```bash
# 仅后端
python3 backend/bin/start.py

# 仅前端
python3 frontend/bin/start.py
```

### 服务管理

```bash
python3 bin/status.py      # 查看状态
python3 bin/stop.py        # 停止全部
python3 bin/restart.py     # 重启全部
```

---

## 🧪 运行测试

```bash
cd modules/court-doc-generator
source .venv/bin/activate
pytest tests/ -v
```

---

## 📂 目录结构

```
court-doc-generator/
├── bin/                    # 一键启动/停止/状态/重启
│   ├── start.py
│   ├── stop.py
│   ├── status.py
│   └── restart.py
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 入口 + /health
│   │   ├── api/            # REST API 路由
│   │   │   ├── auth.py     # 注册/登录
│   │   │   ├── companies.py
│   │   │   ├── agents.py
│   │   │   ├── cases.py
│   │   │   ├── generate.py # 材料生成
│   │   │   ├── history.py  # 生成历史
│   │   │   ├── files.py    # 文件预览
│   │   │   ├── scan.py     # OCR 扫描
│   │   │   └── print_api.py # 在线打印
│   │   └── core/
│   │       ├── config.py   # 配置
│   │       └── database.py # SQLite
│   ├── bin/                # 后端启动/停止/状态/重启
│   │   ├── start.py
│   │   ├── stop.py
│   │   ├── status.py
│   │   └── restart.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React + Vite 前端
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   │   ├── LoginPage.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── CasesPage.tsx
│   │   │   ├── CompaniesPage.tsx
│   │   │   ├── AgentsPage.tsx
│   │   │   ├── HistoryPage.tsx
│   │   │   └── ScanPage.tsx
│   │   └── components/     # 共享组件
│   │       ├── Layout.tsx
│   │       ├── PdfPreviewModal.tsx
│   │       ├── CaseDetailModal.tsx
│   │       └── ConfirmDialog.tsx
│   ├── bin/                # 前端启动/停止/状态/重启
│   │   ├── start.py
│   │   ├── stop.py
│   │   ├── status.py
│   │   └── restart.py
│   ├── package.json
│   └── vite.config.ts
├── generator.py            # 核心生成逻辑（共享）
├── docx_to_pdf.py          # DOCX → PDF 转换（共享）
├── pdf_merger.py           # PDF 合并（共享）
├── scan_service.py         # OCR 扫描服务（共享）
├── config.py               # 路径常量（共享）
├── requirements.txt        # 共享 Python 依赖
├── module.yaml             # 模块元数据
├── templates/              # Word 模板
├── static/                 # 静态 PDF + PDF.js 库
├── data/                   # SQLite 数据库（不入 git）
├── outputs/                # 生成结果（不入 git）
├── .run/                   # PID + 日志（不入 git）
├── tests/                  # 单元测试
└── docs/                   # 设计文档
    ├── README.md
    ├── REQUIREMENTS.md
    ├── SPEC.md
    └── PROMPTS.md
```

---

## ⚙️ 配置说明

### 端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8001 | FastAPI + Uvicorn |
| 前端界面 | 18502 | Vite dev server |

端口注册表：`shared/config/ports.yaml`

### 环境变量

复制 `.env.example` 为 `.env`（可选，默认值即可运行）：

```bash
cp backend/.env.example backend/.env
```

### OCR 扫描（可选）

拍照扫描需要系统安装 Tesseract：

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu/Debian
apt install tesseract-ocr tesseract-ocr-chi-sim
```

---

## 🐛 常见问题

| 问题 | 排查 |
|------|------|
| 端口被占用 | `python3 bin/stop.py` 或手动释放 |
| Python 未找到 | 安装 Python 3.10+ |
| npm 未找到 | 安装 Node.js 18+ |
| 前端白屏 | 确认后端已启动（`python3 bin/status.py`） |
| PDF.js 加载失败 | 下载 `pdf.min.js` + `pdf.worker.min.js` 到 `static/pdfjs/` |
| 合并 PDF 失败 | 检查 `outputs/<案件>/` 下是否生成 7 份 PDF |
| OCR 不工作 | 确认 Tesseract 已安装：`tesseract --list-langs` |

---

## 📚 设计文档

- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — 需求基线（MoSCoW + 用户故事 + 验收标准）
- [docs/SPEC.md](docs/SPEC.md) — 技术规格（架构 + 关键决策 + 实施 Checklist）
- [docs/PROMPTS.md](docs/PROMPTS.md) — 项目提示词集

---

## 📜 版本

- **v2.0.0** (2026-08-21)：React+FastAPI 全栈重构，Streamlit 遗骸清理
- **v1.3.0** (2026-08-20)：用户注册/登录 + workspace 数据隔离
- **v1.2.0** (2026-08-18)：多代理人材料动态绑定
- **v1.1.x** (2026-08-17)：PDF.js 预览、在线打印、跨平台脚本

---

## 📄 许可证

内部使用 · 法务部专用