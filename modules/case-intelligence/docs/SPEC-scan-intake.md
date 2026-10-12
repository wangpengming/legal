# case-intelligence 目录扫描与 AI 辅助录入规范

> **版本**: v1.0 | **日期**: 2026-09-26 | **状态**: proposed
> **目标**: 实现"提供目录 → AI 辅助扫描录入"的全流程自动化

---

## 1. 背景与目标

### 1.1 当前痛点

| 痛点 | 影响 |
|------|------|
| 每次需手动 `register` | 无法批量处理历史案件 |
| 需人工复制 prompts 到 AI 窗口 | 操作繁琐，容易出错 |
| 提取结果格式不统一 | 信息散乱，难以检索 |
| 无文件解析能力 | docx/pdf 需人工复制内容 |

### 1.2 目标

**用户操作**：提供案件目录路径 → 系统自动扫描 → AI 辅助提取 → 结构化入库

**系统能力**：
1. **目录扫描**：自动发现目录中的案件材料文件
2. **文件解析**：支持 docx/pdf/txt/md 等格式
3. **AI 辅助提取**：调用 LLM 按 D1-D5 维度提取结构化信息
4. **规范入库**：格式统一、内容准确、方便检索

---

## 2. 功能规格

### 2.1 核心流程

```
用户提供目录路径
       ↓
┌─────────────────────────────────────────────┐
│  1. 目录扫描（Scanner）                     │
│     - 递归扫描目录                          │
│     - 识别文件类型（docx/pdf/txt/md）       │
│     - 过滤非案件材料（目录名/日期/图片等）   │
│     - 生成文件清单                          │
└─────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────┐
│  2. 文件解析（Parser）                      │
│     - docx: python-docx 读取正文           │
│     - pdf: pdfplumber/pymupdf 提取文本      │
│     - txt/md: 直接读取                      │
│     - 输出统一格式：纯文本 + 元数据          │
└─────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────┐
│  3. AI 辅助提取（Extractor）                │
│     - 调用 LLM（本地 Ollama / 飞书 AI）     │
│     - 按 D1-D5 维度提取结构化信息           │
│     - 生成结构化 JSON + Markdown            │
│     - 人工复核确认                          │
└─────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────┐
│  4. 规范入库（Importer）                    │
│     - 案件基本信息入库（cases 表）          │
│     - 5 维度提取物入库（artifacts 表）      │
│     - 生成规范化报告                        │
└─────────────────────────────────────────────┘
```

### 2.2 CLI 命令

```bash
# 扫描目录，列出发现的案件材料
python bin/extract.py scan /path/to/case --dry-run

# 扫描 + AI 提取 + 入库（交互式确认）
python bin/extract.py scan /path/to/case --ai --import

# 扫描 + 预览提取结果（不入库）
python bin/extract.py scan /path/to/case --ai --preview

# 指定 AI 引擎
python bin/extract.py scan /path/to/case --ai --engine ollama
python bin/extract.py scan /path/to/case --ai --engine feishu
```

### 2.3 目录扫描规则

#### 2.3.1 文件类型识别

| 扩展名 | 类型 | 优先级 | 说明 |
|--------|------|--------|------|
| .docx | Word | P1 | 起诉状、答辩状、证据清单等 |
| .pdf | PDF | P1 | 扫描件、公证书等 |
| .txt | 文本 | P2 | 纯文本材料 |
| .md | Markdown | P2 | 分析笔记等 |
| .png/.jpg | 图片 | P3 | 截图等（暂不处理） |

#### 2.3.2 文件分类规则

基于文件名关键词自动分类：

| 关键词 | 类型 | 模板字段 |
|--------|------|---------|
| 起诉状 / 诉状 | PLIFFING_STATEMENT | 原告主张 |
| 答辩状 | DEFENSE_STATEMENT | 被告抗辩 |
| 证据 / 清单 / 目录 | EVIDENCE_LIST | 证据材料 |
| 合同 / 协议 / 授权 | CONTRACT | 授权链 |
| 判决 / 裁定 / 裁决 | JUDGMENT | 裁判结果 |
| 传票 / 通知 | SUMMONS | 程序文书 |
| 质证 | CROSS_EXAM | 质证意见 |
| 其他 | OTHER | 其他材料 |

#### 2.3.3 案件识别规则

从目录名/文件名推断案件基本信息：

```
# 目录结构示例
/Users/zhangyang/Desktop/案件/腾讯音乐诉北京雷石侵权纠纷案/
├── 01-起诉状.docx
├── 02-证据清单.pdf
├── 03-答辩状.docx
└── 04-授权书.pdf

# 提取结果
case_name: 腾讯音乐诉北京雷石侵权纠纷案
plaintiff: 腾讯音乐
defendant: 北京雷石
cause: 侵权纠纷（推断）
```

---

## 3. 数据模型

### 3.1 扫描结果结构

```python
@dataclass
class ScanResult:
    """目录扫描结果"""
    case_name: str                    # 案件名称（从目录名提取）
    root_path: Path                  # 根目录路径
    files: List[FileInfo]            # 文件清单
    inferred_metadata: CaseMetadata   # 推断的案件信息
    confidence: float                # 推断置信度


@dataclass
class FileInfo:
    """文件信息"""
    path: Path                       # 文件路径
    type: FileType                   # 文件类型
    category: FileCategory           # 分类
    size: int                        # 文件大小
    modified: datetime               # 修改时间
    content_preview: str             # 内容预览（前500字）


@dataclass
class CaseMetadata:
    """推断的案件元数据"""
    case_name: Optional[str] = None
    case_number: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    cause: Optional[str] = None
    court: Optional[str] = None
```

### 3.2 AI 提取结果结构

```python
@dataclass
class ExtractedCase:
    """AI 提取的结构化案件信息"""
    # 基本信息
    case_number: Optional[str]       # 案号
    case_name: str                   # 案件名称
    court: Optional[str]             # 法院
    cause: str                       # 案由
    filing_date: Optional[str]       # 立案日期
    
    # 当事人
    plaintiffs: List[Party]          # 原告列表
    defendants: List[Party]          # 被告列表
    
    # D1-D5 维度
    d1_facts: DFacts                 # 事实认定
    d2_legal: DLegal                 # 法律依据
    d3_strategy: DStrategy           # 攻防策略
    d4_evidence: DEvidence           # 证据体系
    d5_damages: DDamages             # 赔偿裁量
    
    # 原始引用
    raw_citations: List[Citation]    # 原文引用
    confidence: float                # 提取置信度


@dataclass
class Party:
    """当事人"""
    name: str
    role: str                        # 原告/被告/第三人
    id_type: Optional[str]           # 证件类型
    id_number: Optional[str]         # 证件号码（脱敏）
    auth_level: Optional[str]        # 授权层级（针对原告）
    company: Optional[str]           # 公司名称


@dataclass
class DFacts:
    """D1: 事实认定"""
    background: str                  # 案件背景
    dispute_points: List[str]        # 争议焦点
    key_facts: List[KeyFact]         # 关键事实
    rights_basis: str                # 权利基础
    behavior定性: str                # 行为定性


@dataclass
class KeyFact:
    """关键事实"""
    description: str                 # 事实描述
    source: str                     # 来源（文件名+段落）
    status: str                      # 已证/待核/推论
```

---

## 4. AI 提取规范

### 4.1 提取维度（D1-D5）

| 维度 | 名称 | 必须提取 | 格式 |
|------|------|---------|------|
| D1 | 事实认定 | ✅ | 表格+段落 |
| D2 | 法律依据 | ✅ | 法条列表 |
| D3 | 攻防策略 | ✅ | 抗辩排序表 |
| D4 | 证据体系 | ✅ | 证据清单表 |
| D5 | 赔偿裁量 | ✅ | 计算表+区间 |

### 4.2 提取质量标准

| 标准 | 要求 |
|------|------|
| 完整性 | 5 个维度必须全部覆盖 |
| 准确性 | 关键事实必须有原文引用 |
| 一致性 | 各维度之间逻辑自洽 |
| 可追溯性 | 每条信息标注来源文件 |

### 4.3 AI 引擎支持

| 引擎 | 配置键 | 说明 |
|------|--------|------|
| ollama | `--engine ollama` | 本地 qwen2.5/llama3 |
| feishu | `--engine feishu` | 飞书 AI |
| openai | `--engine openai` | OpenAI API |
| mock | `--engine mock` | 测试用，返回模拟数据 |

---

## 5. 用户交互

### 5.1 交互式确认流程

```
$ python bin/extract.py scan /path/to/case --ai --import

📁 扫描目录: /path/to/case
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 发现案件: 腾讯音乐诉北京雷石侵权纠纷案
   置信度: 95%

📄 发现文件 (5 个):
   ├── 01-起诉状.docx         [起诉状]     245 KB
   ├── 02-证据清单.pdf       [证据清单]   1.2 MB
   ├── 03-答辩状.docx        [答辩状]     89 KB
   └── 04-授权书.pdf         [授权书]     567 KB

🔍 推断信息:
   原告: 腾讯音乐娱乐（珠海）有限公司
   被告: 北京雷石天地电子技术有限公司
   案由: 侵害作品信息网络传播权纠纷
   案号: 2023京0491民初23751号（待确认）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  确认以下信息:
   [y] 信息正确，开始 AI 提取
   [n] 信息有误，退出
   [e] 编辑案件信息

>
```

### 5.2 AI 提取进度

```
🤖 AI 提取中... (0/5)

   ✓ D1 事实认定     ████████████ 100%
   ○ D2 法律依据     ░░░░░░░░░░░░  0%
   ○ D3 攻防策略     ░░░░░░░░░░░░  0%
   ○ D4 证据体系     ░░░░░░░░░░░░  0%
   ○ D5 赔偿裁量     ░░░░░░░░░░░░  0%
```

### 5.3 入库确认

```
✅ AI 提取完成

📊 提取摘要:
   D1: 6 条关键事实，3 条已证，2 条待核
   D2: 5 条适用法条
   D3: 3 项抗辩（主力1/辅助1/备用1）
   D4: 12 份证据
   D5: 赔偿区间 50-80 万

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  确认入库:
   [y] 确认入库
   [n] 仅保存草稿，稍后确认
   [r] 重新提取
   [e] 编辑提取结果

>
```

---

## 6. 目录结构

```
modules/case-intelligence/
├── src/
│   ├── __init__.py
│   ├── database.py              # 现有：SQLite 操作
│   ├── artifact_store.py        # 现有：提取物存储
│   ├── template_store.py        # 现有：模板存储
│   ├── case_recognizer.py      # 现有：案件识别
│   ├── scanner.py               # 新增：目录扫描器
│   ├── parser.py                # 新增：文件解析器
│   ├── extractor.py             # 新增：AI 提取器
│   └── importer.py              # 新增：数据导入器
├── prompts/                     # 现有：提示词规则库
├── bin/
│   └── extract.py              # 扩展：新增 scan 命令
└── tests/
    ├── test_scanner.py         # 新增
    ├── test_parser.py           # 新增
    └── test_extractor.py        # 新增
```

---

## 7. 验收标准

### 7.1 功能验收

| # | 标准 | 测试方式 |
|---|------|---------|
| 1 | 扫描目录能发现所有 docx/pdf/txt/md 文件 | 单元测试 |
| 2 | 文件分类正确（起诉状/答辩状/证据等） | 单元测试 |
| 3 | 从目录名推断案件名称 | 单元测试 |
| 4 | 从文件内容提取案号/当事人/案由 | 单元测试 |
| 5 | AI 提取 D1-D5 维度完整 | e2e 测试 |
| 6 | 提取结果格式规范（JSON + Markdown） | e2e 测试 |
| 7 | 入库后可通过 CLI 检索 | 集成测试 |

### 7.2 性能验收

| # | 标准 | 目标 |
|---|------|------|
| 1 | 目录扫描 < 1 秒 | 1000 文件以内 |
| 2 | 文件解析 < 5 秒/文件 | docx/pdf < 10MB |
| 3 | AI 提取 < 60 秒/案件 | D1-D5 全维度 |

### 7.3 数据质量验收

| # | 标准 |
|---|------|
| 1 | 案号格式规范（符合法院编号规则） |
| 2 | 当事人名称完整（无缩写/截断） |
| 3 | 法条引用准确（法规名称+条款号） |
| 4 | 证据清单完整（序号/名称/证明目的） |

---

## 8. 已实现子任务

- [x] **F-061** scanner.py：目录扫描器（递归扫描/文件分类/元数据提取/OCR噪音过滤）
- [x] **F-062** parser.py：文件解析器（docx/pdf/txt/md 支持）
- [x] **F-063** extractor.py：AI 提取器（Mock/Ollama 引擎/D1-D5 提取）
- [x] **F-064** importer.py：数据导入器（cases 表/artifacts 表写入）
- [x] **F-065** extract.py scan 命令：CLI 交互界面（--dry-run/--ai/--import）
- [ ] **F-066** 配置文件：ai_engines.yaml（引擎配置）
- [ ] **F-067** 单元测试：scanner/parser/extractor
- [x] **F-068** 端到端测试：完整流程（已验证扫描+解析+Mock提取）

### 验证结果（2026-09-26）

```bash
# 扫描目录（dry-run）
python bin/extract.py scan "/path/to/case" --dry-run --max-depth 1

# 扫描 + 文件解析
python bin/extract.py scan "/path/to/case" --max-depth 1

# 扫描 + AI 提取（Mock 引擎）
python bin/extract.py scan "/path/to/case" --max-depth 1 --ai --engine mock
```

**测试案例**：腾讯音乐诉北京雷石侵权纠纷案
- 发现 11 个核心文件（过滤掉 400+ OCR 噪音文件）
- 文件分类正确（起诉状/证据清单/答辩状/质证意见等）
- AI 提取 D1-D5 完整
- Markdown 输出格式规范

---

## 9. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 文件解析 | python-docx + pdfplumber | 成熟稳定，中文支持好 |
| AI 调用 | 抽象接口，支持 Ollama/飞书AI/OpenAI | 灵活切换 |
| CLI | argparse（现有框架扩展） | 一致性 |
| 配置 | YAML（ai_engines.yaml） | 可读性好 |
