# ⚖️ 出庭手续生成器

> Streamlit 本地应用 · 法务一键生成出庭 7 份材料

**v1.1.0** · 2026-08-17

---

## ✨ 核心功能

- 📋 **新建案件**：填写案号/案由/法院/开庭日期 → 一键生成 7 份出庭材料
- 🖨 **浏览器内 PDF 预览**：基于 PDF.js 全内联技术，可缩放/翻页/打印全部
- 📦 **完整 zip 包**：包含 DOCX 模板 + PDF 文件 + 合并 PDF
- 🏢 **公司/代理人管理**：左侧侧边栏管理委托单位、代理人信息
- 💾 **历史案件**：SQLite 持久化所有生成记录
- 🔌 **飞书集成**（预留接口）：MVP 阶段占位

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

### macOS / Linux（任意方式选一）

**方式 1：双击启动**（最简单）
```
双击 启动.command
```

**方式 2：命令行启动**
```bash
bash bin/start.sh
```

**方式 3：Python 直接启动**
```bash
python3 bin/start.py
```

启动成功后浏览器自动打开 http://localhost:18501

### Windows

**方式 1：双击 `bin\start.bat`**

**方式 2：命令行**
```cmd
bin\start.bat
```

### 首次启动检查

```bash
bash bin/status.sh    # macOS/Linux
bin\status.bat        # Windows
```

正常输出：
```
🔌 端口 18501: ✅ 已监听
📄 PID 文件: 12345
💚 健康检查: ✅ 通过
🎉 服务正常运行
```

---

## 📥 安装依赖

### 创建虚拟环境（推荐）
```bash
cd modules/court-doc-generator
python3 -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### 系统 Python 直接安装
```bash
pip install -r requirements.txt
```

### 依赖说明（详见 [requirements.txt](requirements.txt)）
- `streamlit ≥ 1.40` — Web 框架
- `python-docx ≥ 1.1` — Word 模板处理
- `reportlab ≥ 4.0` — DOCX → PDF（用内置 STSong-Light 中文字体）
- `pypdf ≥ 4.0` — PDF 合并
- `PyMuPDF ≥ 1.24` — 缩略图（v1.x 预留）
- `pytest ≥ 7.4` — 测试

---

## 🧪 运行测试

```bash
pytest tests/ -v
# 覆盖率
pytest tests/ --cov=. --cov-report=term-missing
```

---

## 📂 目录结构

```
court-doc-generator/
├── app.py                          # Streamlit 主入口
├── config.py                       # 路径常量 + JSON 配置
├── database.py                     # SQLite CRUD
├── generator.py                    # 占位符替换 + 文件生成
├── docx_to_pdf.py                  # DOCX → PDF（reportlab）
├── pdf_merger.py                   # PDF 合并（pypdf）
├── feishu_api.py                   # 飞书集成（stub）
├── pdf_viewer_component.py         # PDF.js 全内联浏览器预览
├── requirements.txt                # Python 依赖
├── module.yaml                     # 模块元数据
├── README.md                       # 本文件
├── bin/                            # 服务管理脚本
│   ├── start.{py,sh,bat}          # 启动
│   ├── stop.{py,sh,bat}           # 停止
│   ├── restart.{py,sh,bat}        # 重启
│   ├── status.{py,sh,bat}         # 状态查询
│   └── 启动.command                # macOS 双击入口（项目根）
├── tests/                          # 单元测试
├── data/                           # SQLite 数据库
├── outputs/                        # 生成的出庭手续（按案件分目录）
├── .run/                           # PID + 日志
├── templates/                      # Word 模板（含 README）
├── static/                         # 静态 PDF + PDF.js 库（含 README）
└── docs/                           # 设计与规格
    ├── README.md
    ├── REQUIREMENTS.md
    ├── SPEC.md
    └── PROMPTS.md
```

---

## ⚙️ 配置说明

### 端口

默认端口 **18501**。被占用时自动切换到 **19000**。

修改方法：编辑 `bin/start.py` 的 `DEFAULT_PORT` 常量。

### PDF.js 库（浏览器内预览）

需要在 `static/pdfjs/` 准备两个文件：
- `pdf.min.js`（约 320 KB）
- `pdf.worker.min.js`（约 1 MB）

下载方法见 [static/README.md](static/README.md)。库未就位时，浏览器内预览自动降级为"系统 Preview 打开"按钮。

---

## 🐛 常见问题

| 问题 | 排查 |
|------|------|
| 端口被占用 | `bash bin/stop.sh` 或手动释放 |
| Python 未找到 | 装 Python 3.10+ 并勾选 "Add to PATH"（Windows）|
| PDF.js 加载失败 | 下载 `pdf.min.js` + `pdf.worker.min.js` 到 `static/pdfjs/` |
| 合并 PDF 失败 | 检查 `outputs/<案件>/` 下是否生成 7 份 PDF |
| DOCX→PDF 字体丢失 | reportlab 内置 STSong-Light，无需额外字体 |
| 中文字段乱码 | STSong-Light 已内置，无需配置 |

---

## 📚 设计文档

- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — 需求基线（MoSCoW + 用户故事 + 验收标准）
- [docs/SPEC.md](docs/SPEC.md) — 技术规格（架构 + 关键决策 + 实施 Checklist）
- [docs/PROMPTS.md](docs/PROMPTS.md) — 项目提示词集

---

## 📜 版本

- **v1.1.0** (2026-08-17)：移除 PII 硬编码、修复 agents 唯一性 bug、接入 docx_to_pdf + pdf_merger、实现 PDF.js 全内联浏览器预览、跨平台启动脚本
- **v1.0.x** (历史)：MVP 初版

---

## 📄 许可证

内部使用 · 法务部专用