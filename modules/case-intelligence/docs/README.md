# case-intelligence 模块用户手册

> **版本**: 3.3.0 | **更新**: 2026-10-12
> **模块**: 案件智能分析系统

---

## 1. 模块简介

case-intelligence 是法务部工程化系统的案件智能分析模块，提供：

- **案件管理**：历史案件批量入库、查询、统计
- **结构化提取**：从案件材料中按 D1-D5 五维度提取结构化信息
- **模板管理**：答辩状/质证意见/当庭陈述/证据目录 4 类文书模板
- **Prompts 规则库**：AI 提示词统一管理，支持多引擎切换

---

## 2. 目录结构

```
modules/case-intelligence/
├── bin/
│   ├── extract.py          # CLI 入口（register/scan/search/report…）
│   ├── start|stop|restart|status.py     # 服务 4 件套（另有 .sh/.bat 跨平台壳层）
│   ├── start_ui|stop_ui|restart_ui|status_ui.py  # Streamlit UI 服务实现（被 4 件套委托）
│   └── health.py           # 健康探针（JSON，只读）
├── data/
│   └── case_registry.db    # SQLite 数据库
├── prompts/                 # AI 提示词规则库
│   ├── prompts.yaml        # 索引 + 使用指南
│   ├── 提取/              # D1-D5 提取提示词
│   ├── 匹配/               # 相似案件匹配
│   └── 生成/               # 文书生成提示词
├── output_templates/        # 固定文书模板
├── output/                 # 生成的文书
├── scripts/                 # 工具脚本
├── src/                     # 核心代码
│   ├── database.py         # 数据库操作
│   ├── scanner.py          # 目录扫描
│   ├── parser.py          # 文件解析
│   ├── extractor.py        # AI 提取
│   └── importer.py         # 数据导入
└── docs/                   # 文档
```

---

## 3. 快速开始

### 3.1 安装依赖

```bash
cd modules/case-intelligence
pip install -r requirements.txt
```

### 3.2 一键启停（Web UI · 服务 4 件套）

本模块的“服务”为 Streamlit Web UI（`:18503`）。`bin/` 提供跨平台 4 件套
（`.py` + `.sh` + `.bat`），`start|stop|restart|status.py` 直接控制该服务：

```bash
cd modules/case-intelligence
python bin/start.py          # 启动 UI（后台，写 PID/日志到 .run/）
python bin/status.py         # 端口 + PID + /_stcore/health + 日志尾部
python bin/restart.py        # 先停后启
python bin/stop.py           # 三重定位停止（PID / lsof·netstat / 兜底）
```

> macOS/Linux 用 `./bin/start.sh`；Windows 用 `bin\start.bat`。
> 纯 CLI 操作（register/scan/search…）仍走 `bin/extract.py`，与本服务控制相互独立。

### 3.3 查看帮助

```bash
python bin/extract.py --help
```

输出：

```
usage: extract.py [-h] {scan,register,extract,promote,complete,check,search,list,report} ...

案件智能分析 CLI

positional arguments:
  {scan,register,extract,promote,complete,check,search,list,report}
    scan       扫描目录，发现案件材料
    register   登记新案件
    extract    从案件材料提取 D1-D5 维度
    promote    将提取物提升为模板
    complete   标记案件为已完成
    check      查询案件详情
    search     搜索案件
    list       列出所有案件
    report     生成统计报告
```

---

## 4. CLI 命令详解

### 4.1 scan - 扫描目录

```bash
# 扫描目录，列出发现的案件材料（dry-run）
python bin/extract.py scan /path/to/case --dry-run

# 扫描 + AI 提取（需配置 AI 引擎）
python bin/extract.py scan /path/to/case --ai --engine basic

# 扫描 + 预览提取结果（不入库）
python bin/extract.py scan /path/to/case --ai --preview

# 扫描 + 入库
python bin/extract.py scan /path/to/case --ai --import
```

**参数说明**：

| 参数 | 说明 |
|------|------|
| `--dry-run` | 仅扫描不入库 |
| `--ai` | 启用 AI 提取 |
| `--engine` | AI 引擎（basic/ollama/openai） |
| `--preview` | 预览提取结果 |
| `--import` | 入库 |

### 4.2 register - 登记案件

```bash
# 登记新案件
python bin/extract.py register \
    --name '腾讯音乐诉北京雷石侵权纠纷案' \
    --case-number '2023京0491民初23751号' \
    --plaintiff '腾讯音乐' \
    --defendant '北京雷石' \
    --cause '著作权侵权'
```

### 4.3 extract - 提取 D1-D5

```bash
# 从案件材料提取 D1-D5 维度
python bin/extract.py extract \
    --case-id <case_id> \
    --type D1
```

**D1-D5 维度说明**：

| 维度 | 名称 | 说明 |
|------|------|------|
| D1 | 事实认定 | 当事人/背景/争议焦点/关键事实/权利基础/行为定性 |
| D2 | 法律依据 | 适用法条/法律关系定性/权利基础/抗辩可行性 |
| D3 | 攻防策略 | 原告诉请/被告抗辩排序/论证结构/主战场决策 |
| D4 | 证据体系 | 双方证据清单/质证要点/举证责任分配 |
| D5 | 赔偿裁量 | 赔偿请求/抗辩理由/计算方式/裁量因素/预估区间 |

### 4.4 list - 案件列表

```bash
# 列出所有案件
python bin/extract.py list

# 按年度筛选
python bin/extract.py list --year 2024

# 按质量筛选
python bin/extract.py list --quality A
```

### 4.5 search - 搜索案件

```bash
# 关键词搜索
python bin/extract.py search "腾讯"

# 搜索原告
python bin/extract.py search --plaintiff "腾讯"

# 搜索案由
python bin/extract.py search --cause "著作权"
```

### 4.6 report - 统计报告

```bash
# 生成统计报告
python bin/extract.py report
```

输出示例：

```
============================================================
案件智能分析统计报告
============================================================

📊 总体统计
  总案件数：88
  已完成：85
  进行中：3

📅 年度分布
  2024：40
  2025：40
  2026：8

🏷️ 质量分布
  A级（完整）：51
  B级（良好）：34
  C级（一般）：3
```

---

## 5. 批量工具脚本

### 5.1 历史案件批量入库

```bash
# 将 99 个历史案例批量入库
python scripts/batch_import.py
```

### 5.2 OCR 批量提取

```bash
# 从 PDF 中 OCR 提取缺失信息
python scripts/ocr_extract.py
```

### 5.3 批量审查

```bash
# 审查所有案例的提取质量
python scripts/review_all_cases_final.py
```

---

## 6. Prompts 规则库

### 6.1 目录结构

```
prompts/
├── prompts.yaml              # 索引
├── 提取/
│   ├── 1_新案材料提取_D1-D5.md    # 5维度提取
│   ├── 2_跨案归纳_Artifact汇聚.md   # 跨案归纳
│   └── 3_质量检查_提取物审核.md     # 质量审核
├── 匹配/
│   └── 4_新案匹配_相似案源检索.md  # 相似案件匹配
└── 生成/
    ├── 5_答辩状生成.md
    ├── 6_质证意见生成.md
    ├── 7_当庭陈述生成.md
    └── 8_证据目录生成.md
```

### 6.2 使用方法

1. 复制提示词文件内容
2. 粘贴到 AI 对话窗口
3. 补充案件材料
4. AI 输出结构化结果
5. 人工审核后入库

---

## 7. 固定模板库

### 7.1 模板类型

| 类型 | 说明 | 数量 |
|------|------|------|
| 答辩状 | 四层递进/主观无过错等 | 2+ |
| 质证意见 | 四性分别表述等 | 1+ |
| 当庭陈述 | 四段式结构等 | 2+ |
| 证据目录 | 三级分类清单等 | 1+ |

### 7.2 使用方法

1. 选择文书类型
2. 查看模板列表
3. 选择适用的模板
4. 填充案件信息
5. 生成文书

---

## 8. 常见问题

### Q1: 如何配置 AI 引擎？

创建 `ai_engines.yaml`：

```yaml
engines:
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    model: "qwen2.5:14b"
```

### Q2: OCR 提取失败怎么办？

1. 检查 PDF 是否为扫描件
2. 确认 Tesseract 已安装：`tesseract --version`
3. 安装中文语言包：`brew install tesseract/tesseract/tesseract-lang`

### Q3: 如何备份数据库？

```bash
cp data/case_registry.db data/case_registry.db.bak
```

---

## 9. 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 3.3.0 | 2026-10-12 | Streamlit Web UI + 目录扫描录入 + AI 引擎配置 + LangChain 文书生成 + prompts 固化 v1.2 + 飞书 Bot |
| 3.2.0 | 2026-09-27 | 历史案件88个入库，OCR批量提取 |
| 3.1.0 | 2026-09-22 | CLI框架、数据库、Prompts初始化 |
| 3.0.0 | 2026-08-17 | 初始版本 |

---

## 10. 部署与域名（thunderbox / 雷石盒子）

- **本模块域名（唯一）**：`legal-case.tbox.ktvsky.com`（`access_mode=internal`）
- **部署通道**：**GitHub（唯一）** → thunderbox 从 GitHub 构建
- **平台信息**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`
- **生产形态**：Python CLI + SQLite（`bin/extract.py`）+ Streamlit UI（`:18503`）

> 🔴 一模块一域名，禁止随意创建；域名统一登记 `shared/config/domains.yaml`（`AGENTS.md §10.4.5`）。
> 📖 系统级手册：[`docs/deployment-thunderbox.md`](../../../docs/deployment-thunderbox.md)
>
> **健康检查**：UI 运行时 `GET /_stcore/health`（200 ok，Streamlit 内置）；轻量 JSON 探针 `python bin/health.py`（版本 + UI + DB 统计，退出码 0/1）；状态检查 `python bin/status.py`（= `status_ui.py`，服务 4 件套）。
