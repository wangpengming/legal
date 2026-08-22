# 智能出庭文书 · Court Document Generator

> 出庭手续文档生成器 — 法务部一键生成出庭 7 份材料（React + FastAPI 全栈）

## 功能

7 份出庭材料一键生成：法定代表人证明、授权委托书、推荐信、营业执照、法人身份证、劳动合同、代理人身份证。

支持：Word模板填充 → DOCX → PDF → 合并PDF → ZIP打包 → 浏览器内预览打印 → 在线打印。

扩展能力：多代理人材料动态绑定、用户注册/登录与 workspace 数据隔离、拍照扫描（OCR）建档、案件搜索/筛选/预设库、操作日志、CSV 导出、表单草稿、开庭日期提醒、暗色模式。

## 技术栈

- **前端**：React 18 + TypeScript + Vite（dev 端口 18502）
- **后端**：FastAPI + Uvicorn（端口 8001，生产形态由后端统一托管前端产物，单端口访问）
- **Word处理**：python-docx
- **DOCX→PDF**：reportlab（多平台候选字体自适应 + FONT_DIR 兜底，见部署手册 §4.3）
- **PDF处理**：pypdf + PyMuPDF
- **数据库**：SQLite（data/，workspace 隔离）
- **PDF预览**：PDF.js
- **OCR**：Tesseract（可选，扫描建档）

## 目录结构

```
court-doc-generator/
├── bin/                  # 一键启动/停止/状态/重启（四件套）
├── backend/              # FastAPI 后端（app/main.py 入口 + /health）
│   ├── app/api/          # REST API 路由（/api/v1/*）
│   ├── app/core/         # config.py（Settings）+ database.py
│   ├── bin/              # 后端单服务四件套
│   └── .env.example      # 环境变量模板（cp 为 .env 后按需修改）
├── frontend/             # React + Vite 前端（npm run build 产物由后端托管）
├── generator.py          # 核心生成逻辑（共享）
├── docx_to_pdf.py        # DOCX → PDF 转换（共享）
├── pdf_merger.py         # PDF 合并（共享）
├── scan_service.py       # OCR 扫描服务（共享）
├── templates/            # Word 模板
├── static/               # 静态 PDF + PDF.js 库
├── data/                 # SQLite 数据库（不入 git）
├── outputs/              # 生成结果（不入 git）
├── .run/                 # PID + 日志（不入 git）
├── tests/                # 单元测试
└── docs/                 # README / REQUIREMENTS / SPEC / PROMPTS / DEPLOYMENT
```

## 运行

### 开发模式（前后端分离）

```bash
cd modules/court-doc-generator

# 首次：依赖安装
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r backend/requirements.txt
cd frontend && npm install && cd ..

# 启动（后端 8001 + 前端 18502）
python3 bin/start.py
python3 bin/status.py    # 状态
python3 bin/stop.py      # 停止
```

### 生产模式（后端托管前端，单端口 8001）

```bash
cd modules/court-doc-generator
python3 bin/start.py --prod     # 校验 frontend/dist 存在后启动
# 浏览器访问 http://localhost:8001
```

完整步骤（前端构建 → dist 携带/服务器构建 → .env → systemd 托管 → 日志/排障）见 **[docs/DEPLOYMENT.md](./DEPLOYMENT.md)**。

## 拍照扫描功能

**状态**：已上线（v2.2.x）

- 上传起诉状/传票图片（支持多图 + PDF 混合）→ 双 PSM OCR 识别
- 自动提取：案号 / 法院 / 案由 / 当事人 / 开庭时间 / 标的金额 → 一键回填表单
- 识别结果可手工修正后保存；形近字/案由词表随真实样本持续扩充