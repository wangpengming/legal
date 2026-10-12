# 需求池 / Requirements Backlog

> AI可解析格式，带YAML头部结构化元数据

---

## 2026-10-12 系统级：thunderbox 部署平台接入 + 模块域名规划（一模块一域名）

**类型**: chore（工程规范）
**模块**: 系统级（横切 4 模块：court-doc-generator / litigation-system / case-intelligence / portal）
**状态**: done
**优先级**: P0（部署红线：服务器只支持 GitHub 部署方式；域名随意创建会造成不可追溯的碎片）

### 描述

为统一部署到雷石内部平台 **thunderbox**（雷石盒子），固化两项系统级规范：

1. **部署平台信息固化**：thunderbox 控制台 / MCP 端点 / 域名规范 / 部署方式（GitHub 唯一通道）写入 `docs/`，避免每次口头传递。
2. **模块域名规划（一模块一域名）**：每个模块在 thunderbox 上**有且仅有一个域名**，域名绑定在应用创建时确定、不可随意新建；所有域名统一 `legal-*` 命名空间、`access_mode=internal`（仅内网）。域名必须像端口一样集中登记与查重。

### thunderbox 平台关键事实（实证）

| 项 | 值 |
|----|----|
| 控制台 | `https://box.tbox.ktvsky.com/` |
| MCP 端点 | `https://api-box.tbox.ktvsky.com/mcp`（HTTP transport） |
| 域名规范 | `<subdomain>.tbox.ktvsky.com` |
| 应用创建 | `thunderbox_create` **强制要求 subdomain** → 1 应用 = 1 域名，创建即绑定 |
| 域名占用查询 | `thunderbox_check(target=domain, value=<sub>)` → `{subdomain, domain, available}` |
| 访问模式 | `public` / `internal` / `restricted`（本项目一律 `internal`） |
| 删除应用 | **无 MCP 工具**，仅能在控制台人工删除（`thunderbox_control` 仅 start/stop/cancel） |
| 代码来源 | **仅支持 GitHub 方式**，部署前必须先将代码迁移到 GitHub 仓库 |
| Token 获取 | 控制台点入创建 token；token 严禁写入仓库（项目 scope 会被提交） |

### 模块域名规划（一模块一域名）

| 模块 | 规划域名 | 状态 | 说明 |
|------|---------|------|------|
| court-doc-generator | `legal-court` | ⚠️ **待回收** | 该 subdomain 已被遗留应用占用；候选回退 `legal-court-generator` / `legal-courtdocs`（均可用） |
| litigation-system | `legal-litigation` | ✅ 可用 | 待部署时申请 |
| case-intelligence | `legal-case` | ✅ 可用 | 待部署时申请 |
| portal | `legal-portal` | ✅ 可用 | 待部署时申请 |

> 全部 `access_mode=internal`。域名注册表见 [`shared/config/domains.yaml`](../../shared/config/domains.yaml)。

### 落地清单

- [x] **doc01** 新建 `shared/config/domains.yaml`：域名注册表（平台规范 + 4 模块唯一域名 + 占用状态 + 遗留冲突登记 + 申请/查重流程）
- [x] **doc02** `AGENTS.md` 新增域名管理规则 §10.4.5（一模块一域名 / 禁止随意创建 / 创建前必查重 / 必须登记 domains.yaml）+ §10.2 禁令 + §1.5 完整性表 + §2 模块清单域名列 + §11 速查
- [x] **doc03** 根 `README.md` 新增「部署到 thunderbox」章节 + 模块表域名列；`docs/SPEC.md` 新增「部署与域名」章节；`docs/README.md` 索引登记
- [x] **doc04** `docs/deployment-thunderbox.md`：thunderbox 部署手册（GitHub 通道 / MCP 工具 / 域名申请 / access_mode / 排障）
- [x] **cfg01** `modules/index.yaml` + 4× `module.yaml` 补 `domain` 字段（与 domains.yaml 一致）
- [x] **cfg02** 4× 模块 `README.md` + 模块 docs 补「部署/域名」章节；`court-doc-generator/docs/DEPLOYMENT.md` 补 thunderbox 通道
- [x] **cfg03** `shared/config/README.md` 更新（登记 domains.yaml）

### 验收标准

- [x] `shared/config/domains.yaml` 存在，登记 4 模块唯一域名 + 平台规范 + 遗留占用说明
- [x] `AGENTS.md` 含「一模块一域名，禁止随意创建」强制规则（dev flow 或 §10.4 中可检索到）
- [x] `modules/index.yaml` 与 4× `module.yaml` 均含 `domain` 字段，且与 domains.yaml **完全一致**
- [x] 根 README / 4× 模块 README / docs 均可检索到 thunderbox 部署方式与所属域名
- [x] 无任何 token / 密钥写入仓库（仅记录 token 获取入口）
- [x] 全部编辑的 YAML 可解析（`yaml.safe_load` 通过）

---

## 2026-10-12 case-intelligence 治理：版本归位 + backlog 纠偏 + 单测补齐 + 健康端点

**类型**: chore（文档/测试治理）
**模块**: case-intelligence
**状态**: done
**优先级**: P1

### 描述

对 case-intelligence 做一次一致性与完整性治理（A~E）：

- **A 版本归位**：确认 v3.3.0 内容 = Web UI + 目录扫描录入 + AI 引擎配置 + LangChain 文书生成 + prompts 固化 v1.2 + 飞书 Bot（commit `ea21774`）；补 `CHANGELOG` 3.3.0 条目；统一 `docs/SPEC.md` / `docs/REQUIREMENTS.md` / `docs/README.md` / 根 `docs/SPEC.md` 版本头至 3.3.0。
- **B backlog 状态纠偏**：目录扫描（2026-09-26）、v3.1 落地（2026-09-22）、遗留项修复（2026-09-27）→ `done`；Web UI 补勾验收项；飞书 Bot 条目降级为「代码就绪 · 通道暂停」。
- **C 合并重复**：合并同日（2026-09-27）两条「产品级达标」条目（SPEC-001~007 + 产品增强、LangChain + MiniMax）为一条。
- **D 处置 v4.0 提案**：2026-08-17「v3.0 → v4.0 案例分析输出生成器」标记 `superseded`（核心生成能力已由 v3.3.0 LangChain/MiniMax 实现；原 NocoDB + Paperless 方案作废），归档。
- **E1 单测补齐**：新增 `tests/test_langchain_llm.py` / `test_document_generator.py` / `test_lark_bot.py` / `test_ui.py`（stdlib + mock，无外部依赖，可 pytest 收集亦可独立运行）。
- **E2 健康端点**：新增 `bin/health.py` 轻量 JSON 探针（版本 + UI `/_stcore/health` + DB 统计，只读）；对齐 portal SPEC 健康契约（case-intelligence → `/case/_stcore/health`）。

### 验收标准
- [x] 版本头一致（3.3.0），`CHANGELOG` 3.3.0 条目存在
- [x] case-intelligence 相关 backlog 条目无 `in-progress` 残留
- [x] 同日重复「产品级达标」条目已合并
- [x] v4.0 提案状态为 `superseded` 并归档
- [x] 新增 4 份单测文件，独立运行全部通过（39 用例）
- [x] `bin/health.py` 输出 JSON 且退出码正确

---

## 2026-09-26 case-intelligence 目录扫描 + AI 辅助录入

**类型**: feature
**模块**: case-intelligence
**状态**: done
**优先级**: P1（短期任务）

### 描述

实现「提供目录 → AI 辅助扫描录入」的全流程自动化：

1. **目录扫描**：递归扫描指定目录，自动发现案件材料文件（docx/pdf/txt/md）
2. **文件解析**：解析文件内容，提取文本
3. **AI 辅助提取**：调用 LLM 按 D1-D5 维度提取结构化信息
4. **规范入库**：格式统一、内容准确、方便检索

### 核心流程

```
用户提供目录路径
       ↓
目录扫描（Scanner）→ 发现文件 → 识别类型 → 推断案件信息
       ↓
文件解析（Parser）→ docx/pdf/txt/md → 统一文本
       ↓
AI 提取（Extractor）→ D1-D5 维度 → 结构化 JSON
       ↓
规范入库（Importer）→ cases 表 + artifacts 表
```

### CLI 命令

```bash
# 扫描目录，列出发现的案件材料（dry-run）
python bin/extract.py scan /path/to/case --dry-run

# 扫描 + AI 提取 + 入库（交互式确认）
python bin/extract.py scan /path/to/case --ai --import

# 扫描 + 预览提取结果（不入库）
python bin/extract.py scan /path/to/case --ai --preview
```

### 子任务（F-061 ~ F-068）

- [x] **F-061** scanner.py：目录扫描器（递归扫描/文件分类/元数据提取/OCR噪音过滤）
- [x] **F-062** parser.py：文件解析器（docx/pdf/txt/md 支持）
- [x] **F-063** extractor.py：AI 提取器（Mock/Ollama 引擎/D1-D5 提取）
- [x] **F-064** importer.py：数据导入器（cases 表/artifacts 表写入）
- [x] **F-065** extract.py scan 命令：CLI 交互界面（--dry-run/--ai/--import）
- [x] **F-066** ai_engines.yaml：AI 引擎配置（MiniMax / Ollama，v3.3.0 落地）
- [x] **F-067** 单元测试：scanner/parser/extractor（`tests/test_scanner.py` / `test_parser.py` / `test_extractor.py`）
- [x] **F-068** 端到端测试：完整流程（已验证）

### 验收标准

- [x] 扫描目录能发现所有 docx/pdf/txt/md 文件（已测试：腾讯案发现 11 个核心文件）
- [x] 文件分类正确（起诉状/答辩状/证据等）（已测试：分类准确）
- [x] 从目录名推断案件名称（已测试：从"腾讯音乐诉北京雷石侵权纠纷案"目录名正确提取）
- [x] AI 提取 D1-D5 维度完整（已测试：Mock 引擎输出完整 D1-D5）
- [x] 提取结果格式规范（JSON + Markdown）（已测试：Markdown 输出格式正确）
- [x] 入库后可通过 CLI 检索（已通过 scan --ai --import 端到端验证；v3.3.0 亦可经 Web UI 检视）

### 规格文档

- `modules/case-intelligence/docs/SPEC-scan-intake.md`

---

---

---

## 2026-09-27 case-intelligence Web UI（登录 + 案件管理 + 扫描 + 生成）

**类型**: feature
**模块**: case-intelligence
**状态**: done
**优先级**: P1
**端口**: 18503（Streamlit）

### 背景问题

当前 case-intelligence 只有 CLI 界面，需要 Web UI 提升易用性：
- CLI 适合技术人员，普通用户难以直接使用
- 无法通过浏览器随时访问
- 缺乏直观的案件列表和搜索

### 用户故事

**作为** 法务人员/律师
**我想要** 通过浏览器管理案件、扫描新案例、生成分析产物
**以便** 更高效地处理日常工作

### 功能需求

#### 1. 登录认证
- [x] 简单Session认证（不引入复杂OAuth/JWT）
- [x] 默认账号：
  - `admin` / `admin123`（管理员）
  - `test` / `test123`（测试账号）
- [x] 无资源隔离，所有登录用户可见所有案件
- [x] 登录状态持久化（Streamlit session_state）

#### 2. 案件管理
- [x] 案件列表（分页、搜索）
- [x] 案件详情页（基本信息 + 提取物列表）
- [x] 健康度指标显示
- [x] 快速跳转到提取/生成功能

#### 3. 扫描录入
- [x] 目录选择器（上传或路径输入）
- [x] 触发 `scan --ai --import --yes` 流程
- [x] 实时显示扫描结果
- [x] 扫描历史记录

#### 4. 文书生成
- [x] 选择案件 + 选择文书类型
- [x] 调用 LLM 生成
- [x] 预览 + 导出（DOCX/Markdown）
- [x] 生成历史记录

#### 5. 统计看板
- [x] 案件总数/已提取/待提取
- [x] 案由分布图（简单文本图表）
- [x] 最近操作记录

### 技术方案

```
技术栈：
- Streamlit（与 court-doc-generator 一致）
- 复用 src/ 下现有模块（database, scanner, parser, extractor, langchain_llm）
- 复用 bin/extract.py CLI 功能

目录结构（实际落地）：
case-intelligence/
├── app.py                      # Streamlit 主入口
├── config.py                   # UI 配置（端口 18503、账号）
├── pages/
│   ├── 1_登录.py
│   ├── 2_案件列表.py
│   ├── 2_案件详情.py
│   ├── 3_扫描录入.py
│   ├── 4_文书生成.py
│   └── 5_统计看板.py
├── ui/
│   ├── auth.py                 # 登录守卫
│   └── utils.py                # UI 辅助函数
└── bin/
    ├── start_ui.py             # UI 启动（写 PID + 日志）
    ├── stop_ui.py
    └── status_ui.py            # 端口 + /_stcore/health 健康检查
```

### 验收标准

- [x] admin/test 账号可登录
- [x] 登录后可见所有案件
- [x] 可扫描目录并导入案件
- [x] 可为案件生成4种文书
- [x] 文书可导出为 DOCX/MD
- [x] 健康度检查显示正确
- [x] 统计看板显示正确

### 里程碑

- M1: 登录 + 案件列表（核心）
- M2: 扫描录入（高频）
- M3: 文书生成（核心）
- M4: 统计看板（辅助）

---

## 2026-09-27 case-intelligence 产品级达标（SPEC-001~007 + LangChain/MiniMax + 产品增强）

**类型**: feature + refactor
**模块**: case-intelligence
**状态**: done
**优先级**: P0

> **合并归档**：本条目合并同日两条重复的「产品级达标」需求（原「产品级达标 v2：SPEC-001~007 + 产品增强」与「产品级达标：LangChain + MiniMax」），统一为一条。

### 一、SPEC-001~007（工程缺陷修复）

#### SPEC-001: Prompts未用于文书生成
- [x] `langchain_llm.generate_direct()` 优先加载 `prompts/生成/` 下的提示词
- [x] 添加 `_load_prompt_for_doc_type()` / `_build_prompt_from_template()` / `_extract_system_prompt()`
- [x] fallback到硬编码prompt

#### SPEC-002: 案件去重检查
- [x] `cmd_scan()` 入库前检测重复案号
- [x] 用户可选择跳过/更新/退出

#### SPEC-003: 扫描完整性提示
- [x] scan命令解析后检查文件类型
- [x] 未发现标准文书时显示提示

#### SPEC-004: D1-D5自动入库
- [x] `MiniMaxAdapter._parse_response()` 增强解析D1-D5维度
- [x] 提取物入库后包含完整结构化信息

#### SPEC-005: 文书历史版本管理
- [x] artifacts表增加 `parent_id`, `generation_method`, `model_version` 字段
- [x] `create_artifact()` 支持版本链

#### SPEC-006: 批量导入进度
- [x] `cmd_import()` 显示进度条
- [x] 同一行更新进度

#### SPEC-007: 统计增强
- [x] `cmd_report()` 增加按案由分布统计（Top 10）

### 二、LangChain / LangGraph 架构（T-001~T-010）

实现 LangChain/LangGraph 架构，集成 MiniMax LLM：LangChain LLM 服务（MiniMax-Text-01）、scan 命令支持 minimax 引擎、模板 + LLM 混合生成、LangGraph 工作流（生成 → 审查 → 定稿）、import 命令（JSON 增量导入）。

- [x] **T-001** LarkBot search 格式统一（已验证正常）
- [x] **T-002** 统一 extractor 与 ai_engine（MiniMaxAdapter）
- [x] **T-003** scan 命令接入 MiniMax（--engine minimax）
- [x] **T-004** 扫描链路入库测试（--import --yes）
- [x] **T-005** 模板 + LLM 混合生成（template+llm source）
- [x] **T-006** LangGraph 工作流集成（review_node 实际调用 LLM）
- [x] **T-007** Database 类封装（函数式接口已可用，跳过）
- [x] **T-008** Prompts 规则库验证（load_prompt 正常工作）
- [x] **T-009** import 命令（JSON 增量导入 CLI）
- [x] **T-010** TemplateStore 类封装（函数式接口已可用，跳过）

### 三、产品增强

#### 增强1: 案件健康度检查
- [x] 新增 `health <case_id>` 命令
- [x] 检查6项指标：案号/原告/被告/案由/法院/提取物
- [x] 计算健康度百分比

#### 增强2: 导出格式扩展
- [x] 新增 `export <artifact_id> <output>` 命令
- [x] 支持 .docx 和 .md 格式
- [x] Markdown 包含 YAML frontmatter

### 验证结果

- pytest: 28 passed, 5 skipped ✅
- 文书生成：4种类型全部使用prompts（defense/evidence_objection/court_statement/evidence_index）✅
- scan链路：去重/完整性/入库 全部通过（--import --yes 端到端）✅
- 批量导入：进度条显示正常 ✅
- 健康度检查：83% / 100% 等 ✅
- 导出DOCX：37KB文件正常生成 ✅
- MiniMax LLM 生成：defense/evidence_objection/court_statement/evidence_index 全部通过（源码 MiniMax-Text-01）✅
- import 命令增量导入测试通过 ✅

## 2026-08-24 case-intelligence 飞书Bot集成

**类型**: feature
**模块**: case-intelligence
**状态**: in-progress（代码就绪 · 通道暂停）
**优先级**: P0

### 描述
将飞书 Bot 接入 case-intelligence 模块，实现通过飞书对话完成案件管理（/case list/search/register/detail）、提取物查询（/case artifacts）和文书生成（/case generate）。通过 Bot → CLI subprocess 模式，复用现有 extract.py。

> **当前状态（2026-10-12）**：代码已就绪——`src/lark_bot.py` 实现 `CaseBot.handle_message()`（命令 list/search/register/detail/artifacts/report/help）+ `LarkWebhookHandler` 事件处理 + CLI 自测模式，全部命令经本地自测通过。**通道暂停**：飞书 SDK 为可选依赖（未安装时走 mock 模式），上线需飞书企业权限（app_id / app_secret / 事件订阅回调）。待权限就绪后再推进网关接入。

### 验收标准
- [x] /case list — 返回案件列表（表格格式）
- [x] /case search <关键词> — 返回匹配案件
- [x] /case register <信息> — 创建新案件（含年份/法院推断）
- [x] /case detail <case_id> — 返回案件详情
- [x] /case artifacts <case_id> — 返回提取物列表
- [x] /case report — 返回统计报告
- [x] /case help — 返回指令帮助
- [ ] 指令解析支持自然语言模糊匹配（当前仅支持显式 `/case <cmd>` 命令）
- [ ] /case generate — 文书生成（暂未接入 Bot，生成能力见 v3.3.0 LangChain/MiniMax 路径）

## 2026-08-22 court-doc-generator 案件搜索/筛选（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P1（案件量增长后的高频操作）

### 描述
案件管理页增加搜索与筛选能力：搜索框支持案号/法院/案由关键词匹配；筛选支持按状态/开庭日期范围/创建日期过滤。

### 验收标准
- [x] 搜索框输入关键词 → 匹配案号/法院/案由，实时过滤列表
- [x] 筛选：状态（全部/待处理/已生成/已提交/已结案）、日期范围
- [x] 无结果时显示空状态提示（可清空筛选）
- [x] UI 与现有 Vercel/Linear 风格一致
- [x] 前端 TDD 测试覆盖搜索/筛选逻辑

---

## 2026-08-22 court-doc-generator 表单草稿自动保存（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P2（防数据丢失）

### 描述
新建/编辑案件表单输入内容自动保存到 localStorage，浏览器崩溃/误关后恢复。保存时机：输入防抖 1s 后；恢复时机：进入新建页时检测到草稿 → 提示恢复。

### 验收标准
- [x] 表单输入防抖 1s 自动存草稿（字段级）
- [x] 重新打开新建页 → 检测到草稿 → 弹窗"恢复草稿？"
- [x] 用户明确"放弃草稿"后清除本地草稿
- [x] 提交成功后自动清除草稿
- [x] 草稿不包含 PII 外泄（仅本地 localStorage，不传服务器）
- [x] 前端 TDD 测试覆盖保存/恢复/清除分支

---

## 2026-08-22 court-doc-generator 开庭日期提醒（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P2

### 描述
案件开庭日期临近时提醒：进入系统时（Dashboard 加载）检测未来 7 天内开庭的案件，浏览器 Notification API 弹出提醒 + 系统内横幅展示。

### 验收标准
- [x] Dashboard 展示"即将开庭"卡片：未来 7 天内案件列表（案号/法院/时间）
- [x] 浏览器通知：用户授权后可弹系统通知（不强制）
- [x] 已过期的开庭日期不显示
- [x] 通知权限被拒绝时仅显示站内横幅，不报错
- [x] 前端 TDD 测试覆盖 7 天窗口计算与过滤

---

## 2026-08-22 court-doc-generator 案件数据导出 CSV（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P2（汇报/交接场景）

### 描述
案件列表支持导出 CSV（Excel 可打开，UTF-8 BOM）：导出当前筛选/搜索结果。列：案号/法院/案由/开庭日期/对当事人/我方角色/状态/创建时间/公司/代理人。

### 验收标准
- [x] 案件页"导出 CSV"按钮 → 下载当前筛选结果的 CSV
- [x] UTF-8 BOM 编码，Excel 直接打开中文不乱码
- [x] 表头 + 全部列（含公司/代理人名称）
- [x] CSV 注入防护：单元格以 `=`、`+`、`-`、`@` 开头时前缀 `'`
- [x] 后端 TDD 测试覆盖 CSV 生成 + 注入防护

---

## 2026-08-22 court-doc-generator 法院/案由预设库（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P1（高频重复输入）

### 描述
新建案件时法院与案由支持：预设列表选择（常用法院/案由，按使用频次排序）+ 手动输入新值。新输入的值自动进入预设（可管理删除）。

### 验收标准
- [x] 法院字段：下拉预设 + 可手输；新值自动入库（按使用频次排序）
- [x] 案由字段：同上
- [x] 预设列表可管理（删除不再使用的项）
- [x] 预设数据按 workspace 隔离
- [x] 后端 TDD 测试覆盖预设 CRUD + 频次排序 + workspace 隔离

---

## 2026-08-22 court-doc-generator 操作日志（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P2（审计追踪）

### 描述
记录用户在系统内的关键操作（登录/创建案件/修改/删除/生成文档），可按 workspace 查询。用途：多人共用时的审计追踪 + 排查问题。

### 验收标准
- [x] 记录操作：登录、案件创建/修改/删除、材料生成、导出
- [x] 日志字段：时间/用户/动作/对象描述/结果
- [x] 列表页面（管理入口）或 API 可查
- [x] 日志不含 PII 完整值（身份证号遮罩）
- [x] 后端 TDD 测试覆盖记录写入 + 查询 + PII 遮罩

---

## 2026-08-22 court-doc-generator 暗色模式（明暗切换）（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P3（体验优化）

### 描述
UI 支持明/暗主题切换：默认跟随系统偏好，右上角手动切换（记忆选择）。暗色主题所有页面适配。

### 验收标准
- [x] 主题切换按钮（右上角）：亮/暗/跟随系统 三态
- [x] 选择记忆到 localStorage，下次启动生效
- [x] 所有页面（登录/案件/公司/代理人/历史/扫描）暗色适配
- [x] 前端 TDD 测试覆盖主题状态管理与切换逻辑

---

## 2026-08-20 court-doc-generator 拍照扫描自动识别字段

**类型**: feature
**模块**: court-doc-generator
**状态**: in-progress
**优先级**: P2

### 描述
在出庭生成器页面加「📷 拍照扫描」按钮：用户上传起诉状/传票/开庭通知/立案通知等法律文书照片，
后端 OCR + 正则匹配提取关键字段（案号/法院/原告/被告/案由/开庭时间/标的金额），自动填到表单。

技术选型：
- **OCR**: Tesseract 5.5.2 + chi_sim（macOS Homebrew 自带，零依赖）
- **字段抽取**: 正则 + 关键词匹配（轻量，零 LLM 依赖；后续可加 LLM 增强）
- **UI**: Streamlit file_uploader（支持多图）→ 自动填字段 → 用户预览修改

### 子任务
- [ ] F-052-1 登记 backlog
- [ ] F-052-2 scan_service.py（extract_text + extract_fields）
- [ ] F-052-3 app.py「📷 拍照扫描」按钮 + file_uploader + 自动填
- [ ] F-052-4 端到端测试（用真实文档图片验证）
- [ ] F-052-5 5 个 pytest 覆盖

### 提取字段清单
- 案号（起诉状首部）
- 法院（法院名称）
- 案由（合同纠纷/侵权/知识产权等）
- 原告/被告（当事人）
- 开庭时间
- 立案日期
- 标的金额

---

## 2026-08-20 court-doc-generator 用户注册/登录与工作空间（Workspace）数据隔离

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P1（多人共用同一台电脑场景下的数据隔离需求）

### 描述

当前模块为单用户本地工具，同一台电脑上多人共用时，所有公司/代理人/案件/生成历史混在同一份 `court_matters.db` 中，无法区分"谁的数据"。需要在保持 Streamlit 技术栈不变的前提下，引入轻量用户注册/登录 + 工作空间（Workspace/Profile）机制，实现每人独立的数据隔离。

### 设计决策

- **方案**：工作空间（Profile）模式。每个注册用户 = 一个独立 workspace 子目录，内含独立的 `court_matters.db` + `outputs/` + `static/agents/`
- **认证**：用户名 + 密码（pbkdf2_hmac 哈希），零外部依赖
- **隔离粒度**：DB 文件级物理隔离（不改现有 CRUD SQL）
- **会话管理**：Streamlit session_state（关闭浏览器需重新登录，本地工具可接受）
- **技术栈**：不动 Streamlit，不换框架

### 子任务

- [x] **F-042** 新增 `workspace.py`：workspace 元数据管理（`CREATE TABLE workspaces`、`create_workspace`、`verify_workspace`、`list_workspaces`、`hash_password`）
- [x] **F-043** 改造 `config.py`：路径函数化（`get_db_path(ws_id)` / `get_outputs_dir(ws_id)` / `get_agent_dir(ws_id)`），自动创建目录
- [x] **F-044** 改造 `app.py`：登录/注册页路由（`render_login_page` / `render_register_page`），`session_state.workspace_id` 驱动
- [x] **F-045** 适配 `database.py`：`init_db()` 接受 `db_path` 参数（CRUD 函数不改）
- [x] **F-046** 适配 `generator.py`：`save_agent_pdf` 路径加 workspace 前缀
- [x] **F-047** 现有数据自动迁移：首次启动检测旧 `data/court_matters.db` → 创建"默认"workspace → 迁移
- [x] **F-048** 测试覆盖：`test_workspace.py`（密码哈希/创建/验证/重复注册/迁移）

### 验收标准

- [x] 首次启动显示登录页，可注册新用户（用户名 + 密码）
- [x] 已注册用户可登录，密码错误被拒绝
- [x] 登录后进入主界面（现有功能不变），数据仅限当前 workspace
- [x] 小李注册 → 创建公司/案件 → 退出 → 小王注册登录 → 看不到小李的数据
- [x] 关闭浏览器 → 重新打开 → 回到登录页（session 不持久化）
- [x] 旧版 `data/court_matters.db` 自动迁移到"默认"workspace
- [x] 所有现有测试继续通过（向下兼容）
- [x] PII 安全：workspace 密码哈希存储，不存明文

### 待澄清

- 忘记密码：是否需要重置功能？（建议：v1.3.0 先不做，用户可手动删 workspace 目录重新注册）
- 删除 workspace：是否需要 UI 入口？（建议：先不做，手动删目录即可）

---

## 2026-08-18 court-doc-generator 多代理人材料绑定边界场景处理（F-039~F-041）

**类型**: improvement
**模块**: court-doc-generator
**状态**: in-progress
**优先级**: P2（完善功能，非阻塞）

### 描述
F-031~F-035 已完成多代理人材料动态绑定主体功能，但 3 个边界场景未处理：
1. **F-039 删除代理人级联清理**：删除 agent 时是否清理由 static/agents/<id>/ 下的文件？
2. **F-040 重传替换清旧文件**：同一代理人重新上传 PDF 时，旧文件是否清理？
3. **F-041 启动时校验路径**：agent.contract_pdf_path / id_card_pdf_path 文件丢失/被外部改动时怎么办？

### 子任务
- [ ] **F-039** `database.delete_agent(agent_id)` 实现：先查关联案件 → 有关联不删文件 → 无关联级联删 static/agents/<id>/
- [ ] **F-040** `app.py` 代理人表单提交逻辑：检测已有路径 → 先删旧 PDF → 再保存新 PDF
- [ ] **F-041** `generator.validate_agent_paths()` + `app.py` UI 提示：启动时/侧边栏加载时校验所有 agent 路径 → 失效的标红 + 提示"重新上传"
- [ ] 测试覆盖：3 个 helper 各加 2-3 个用例

### 验收标准
- [ ] F-039：删无关联代理人 → 文件全清；有关联 → 弹确认"保留文件"
- [ ] F-040：同代理人重传 → 旧文件消失，新文件就位（DB 路径已更新）
- [ ] F-041：路径失效 → UI 警告 + 一键重传入口

### 待澄清
- F-039：关联案件判定用 cases.agent_id 还是 generation_history.case_id（间接）？
- F-040：旧文件删除失败怎么办？（OSError → 静默？报警？）
- F-041：UI 警告是阻塞式（强制重传）还是提示式（继续用 fallback）？

---

## 2026-08-18 court-doc-generator 增加在线打印功能（直送系统打印机）

**类型**: feature
**模块**: court-doc-generator
**状态**: in-progress
**优先级**: P1

### 描述
当前 PDF.js 工具栏的"打印全部"按钮触发 `window.print()`，**总会弹 macOS 打印对话框**（浏览器安全沙箱限制）。法务用户实际诉求是：点击按钮 → **直接送到系统默认打印机 → 出纸质文件**，无任何中间对话框。

实现思路：Streamlit 后端调系统打印命令（macOS `lp` / Linux `lp` / Windows `Start-Process -Verb Print`），绕过浏览器限制。

### 验收标准
- [ ] 结果卡片区新增"🖨 在线打印"按钮（结果已生成后显示）
- [ ] 点击按钮 → 合并 PDF（00_合并出庭手续）直接送系统默认打印机
- [ ] 不弹任何浏览器/系统对话框（区别于 `window.print()`）
- [ ] 跨平台支持：macOS / Linux / Windows
- [ ] 失败时显示明确错误（如无打印机 / 命令超时）
- [ ] pytest 单测覆盖 helper 函数（mock subprocess）

### 待澄清
- 默认打印机策略：总是用系统默认，还是让用户在 UI 里选？（推荐：先默认）
- 打印份数：固定 1 份还是 UI 让用户选？（推荐：先固定 1）
- 纸张大小 / 双面：固定还是可选？（推荐：固定 A4 单面，后续可加）

### 关联
- 复用 PDF.js 工具栏的"🖨 打印"按钮可保留（兼容老流程）
- 新按钮是真正的"在线打印"，无需用户介入

---

## 2026-08-17 Legal Portal 统一门户（v0.1 原型）

**类型**: feature
**模块**: portal
**状态**: in-progress
**优先级**: P1

### 描述

法务部统一门户：注册表驱动的子系统集成框架 + 系统健康监控总览。四项设计决策已定：形态从简（无认证、登录页可有可无，重在框架/效果/功能/集成）、商务蓝浅色庄重视觉、暂不做统一认证、首版聚焦系统健康监控。

已交付：
1. `modules/portal/docs/SPEC.md` — v0.1 规格（设计语言 / 同源反代架构 / apps.yaml 注册表 schema / 健康监控协议 / 页面结构 / 验收标准 / 演进路线）
2. `modules/portal/prototype.html` — 单文件交互原型（欢迎页 + 主框架 + Dashboard 健康总览 + 子系统嵌入演示 + 日志），APPS 注册表驱动，浏览器自测通过（控制台零报错、状态机 on→degraded→offline 切换、返回门面状态同步）

正式版待办（未开始）：
- [ ] nginx 同源反代配置落地（/court→18501、/litigation→8000、/case→8090+8091，仅内网 10.10.11.37）
- [ ] apps.yaml 注册表转正并接入真实健康端点
- [ ] litigation-system / case-intelligence 补齐健康端点（/api/health、/api/healthz）
- [ ] 健康趋势图历史落库、一键启停、WebSocket 实时日志（P1）
- [ ] 正式版形态确认（静态多页 or Vite/React）与部署

### 验收标准（原型阶段）
- [x] SPEC 覆盖设计语言/架构/注册表 schema/健康协议/验收标准
- [x] 原型集成为一个 HTML 文件，APPS 数组驱动四视图
- [x] 本地起服务 + 浏览器自测渲染与交互无误（控制台零报错）
- [ ] 正式版开发（proposed）

---

## 2026-08-17 扩展 case-intelligence 为案例分析输出生成器（v3.0 → v4.0 升级）

**类型**: feature
**模块**: case-intelligence（吸收方案，原 cross-module 决策已并入）
**状态**: superseded（已被 v3.3.0 实现，原方案作废归档）
**优先级**: P1（业务核心需求）
**版本演进**: case-intelligence v3.0 → v4.0（原计划引入 LLM 生成能力，打破 v3.0"不做 AI"原则）

> ### ⚠️ 处置结论（2026-10-12）：superseded / 作废
>
> **核心生成能力已由 v3.3.0 落地实现**：case-intelligence v3.3.0 已通过 **LangChain + MiniMax** 路径实现 LLM 文书生成（答辩状 / 质证意见 / 当庭陈述 / 证据目录），本提案的"引入 LLM 生成层"目标已达成（见 `src/langchain_llm.py` / `src/document_generator.py`，CHANGELOG 2026-10-12）。
>
> **原规划的基础设施方案作废**：本提案原设想复用 **NocoDB + Paperless-ngx 多容器**（v3.0 方案）作为底座，该方案**已废弃**——模块现状收敛为 **Python CLI + SQLite（三表）+ Streamlit Web UI** 轻量形态（v3.3.0）。
>
> **剩余未覆盖项（如需推进请重新登记新需求）**：① 我方证据目录 / 我方证据资料 生成；② 与 court-doc-generator 出庭材料的一站式对接；③ 六阶段分析框架（`case-analysis-master`）的方法论沉淀。这些不再沿用本提案的 NocoDB/Paperless 前置条件。

### 描述
基于原告方材料（起诉状 + 证据清单 + 证据），自动生成我方全套应对材料：答辩状、我方证据目录、我方证据资料、质证意见。**通过扩展 case-intelligence 模块实现**——复用其三对象模型（案件+文档+规则）、Paperless-ngx OCR、检查清单等现有 v3.0 基础设施，仅引入 LLM 生成层（限于答辩状 / 质证意见 / 证据目录）。

### 决策依据（v3.0 → v4.0 升级理由）
1. 三对象模型与本需求天然契合：原告材料 = "文档" 对象；检查清单可扩展为"答辩状必填项 / 质证意见三性原则清单"
2. 复用基础设施：Paperless-ngx OCR  + NocoDB 存储 + 7 步审核工作流 → 新增生成后处理环节
3. 技术债最小：不重建 OCR/检索/存储；只新增一个 LLM 生成模块
4. 打破 v3.0"不做 AI"原则是受控、可解释的（仅限文档生成，不做案件判断）

### 输入（用户提供）
1. 原告起诉状（DOCX / PDF）
2. 对方证据清单（DOCX / Excel / 图片）
3. 对方证据材料（DOCX / PDF / 图片）
4. （可选）案件基本信息（案号 / 法院 / 案由 / 我方身份 / 我方主张要点）

### 输出（系统生成）
1. **答辩状**（DOCX / PDF）— 含管辖权异议 / 事实与理由 / 证据目录引用
2. **我方证据目录**（DOCX / Excel）— 规范格式、与对方目录可对照
3. **我方证据资料**（DOCX / PDF）— 模板文件 + 待用户补充原始材料
4. **质证意见**（DOCX / PDF）— 逐条对应对方证据（三性原则：真实性 / 合法性 / 关联性）

### 子任务（F-041 ~ F-046）
- [ ] **F-041** 需求基线 v4.0：用户画像 / MoSCoW / 用户故事 / 验收（`case-intelligence/docs/REQUIREMENTS.md`）
- [ ] **F-042** 技术规格 v4.0：架构 / LLM 引擎选型 / 数据模型扩展 / 接口（`case-intelligence/spec/SPEC.md`）
- [ ] **F-043** 输入处理：起诉状 / 证据清单 / 证据材料 → 复用 Paperless-ngx OCR + 文档 API
- [ ] **F-044** 分析引擎：复用 `case-analysis-master` 六阶段框架 + LLM 集成（本地 / 云端）
- [ ] **F-045** 输出生成：答辩状 / 证据目录 / 质证意见模板 + 渲染（DOCX/PDF）
- [ ] **F-046** UI + 服务：Streamlit / NocoDB 表单 / 跨平台启动脚本

### 验收标准
- [ ] 输入 4 份原告材料，能输出 4 份我方材料
- [ ] 答辩状结构完整（含管辖权异议 / 事实与理由 / 证据目录引用）
- [ ] 质证意见逐条对应对方证据（三性原则）
- [ ] 我方证据目录格式规范（与对方目录可对照）
- [ ] PII 安全：所有数据本地存储，不上云
- [ ] 与 court-doc-generator 输出对接（出庭时一站式生成）
- [ ] case-intelligence v4.0 SPEC 同步更新

### 待澄清
- **AI 引擎**：本地 LLM（ollama + qwen2.5）vs 云端 API（飞书 AI / OpenAI / Claude）？
- **输入交互**：一次性上传 4 份 vs 分步引导（先起诉状 → 提纲 → 补证据）？
- **输出格式**：DOCX / PDF / 飞书云文档？
- **复用范围**：是否复用 `case-analysis-master` skill 的全部方法论？
- **案件类型**：是否限定案由（合同 / 知识产权 / 劳动争议）？还是通用？
- **v3.0 → v4.0 升级策略**：保留 v3.0 全部能力 + 新增生成能力，还是重写？

### 关联资源
- 方法论：`case-analysis-master` skill（六阶段案件分析 + 抗辩方法论）
- 范式：`office-workflow-litigation-doc` skill（答辩状结构）
- 文档：`documents` / `pdf-extractor` / `image-ocr` skill（多格式输入）
- 上游：现有 v3.0 三对象模型 + Paperless-ngx + 检查清单
- 下游：court-doc-generator（出庭手续，出庭时一站式消费方）
- 同级：litigation-system（638 条历史案件可作为"同类案参考"输入）

### 模块影响（开工时同步更新）
- `modules/case-intelligence/module.yaml`：version `3.0.0` → `4.0.0`；status 保持 `planning`；features 增加 4 项
- `modules/index.yaml`：case-intelligence 描述补充"v4.0 起含 LLM 生成能力"
- `modules/case-intelligence/spec/SPEC.md`：v3.0 → v4.0，新增"生成引擎"章节
- `modules/case-intelligence/requirements/`：新增 `requirements/02-需求v4.md`

### 后续行动（以后启动时）
1. 在 case-intelligence 下新建 `docs/REQUIREMENTS-v4.md`，复用 v3 模板
2. 明确 LLM 引擎选型（需评估本地 Ollama + qwen2.5 vs 云端 API 的中文法律场景能力）
3. 评估 case-analysis-master 六阶段框架在答辩状生成场景的复用度
4. 同步 litigation-system：评估"同类案参考"输入是否走 MCP 调用

---

---

## 2026-08-20 court-doc-generator 04/05 模板加 agent.phone 自动填入

**类型**: feature
**模块**: court-doc-generator
**状态**: in-progress
**优先级**: P1

### 描述
用户诉求：输入代理人时同时填联系电话，且能自动填到 04_授权委托书 + 05_推荐信。

**F-051 调研发现**：
- ✅ DB agents.phone 字段已有
- ✅ UI a_phone 字段已有（app.py:364）
- ✅ 04_授权委托书.docx 模板已有"电话：【】"占位符（第 7 段）
- ❌ 05_推荐信.docx 模板没"电话"字段（之前 11 个【】，少电话）

### 子任务
- [x] F-051-1 05 模板加"电话：【】"占位符（在第 5 段"职务："后插入）
- [x] F-051-2 generator.values_for_recommendation 加 agent_phone（第 6 个值）
- [x] F-051-3 端到端测试（05 PDF 含"电话：13800138000"）

### 验收标准
- [x] 04 模板电话已自动填（之前已实现，仅需用户知晓）
- [x] 05 模板电话已自动填（F-051 新增）
- [x] 字体嵌入子集（F-050 保证打印正常）

### 备注
04 的 phone 值是 values_for_power_of_attorney 第 3 个（按文档顺序对应第 7 段电话【】）。
05 的 phone 值是 values_for_recommendation 第 6 个（按文档顺序对应"职务：【】电话：【】"）。

---

## 2026-08-17 出庭手续生成器支持多代理人材料动态绑定

**类型**: feature
**模块**: court-doc-generator
**状态**: proposed
**优先级**: P1（影响核心业务流程，不同代理人不能用同一套材料）

### 描述
当前代理人切换后，06_代理人劳动合同.pdf 与 07_代理人身份证.pdf 仍指向同一份静态文件，且 04_授权委托书 的"被授权人"字段未动态绑定当前 agent。需要让"切换代理人"后整套材料正确反映新代理人。

### 子任务（F-031 ~ F-035）
- [ ] **F-031** agents 表新增 `contract_pdf_path` / `id_card_pdf_path` 字段（数据库迁移）
- [ ] **F-032** 代理人编辑表单增加"上传劳动合同 PDF"与"上传身份证 PDF"入口（UI）
- [ ] **F-033** `generator._generate_to_dir` 改为按 agent 路径取 PDF（核心逻辑）
- [ ] **F-034** 04_授权委托书.docx 模板新增【】被授权人姓名 + 【】身份证号占位符
- [ ] **F-035** `values_for_power_of_attorney` 函数补充 agent 字段填充

### 验收标准
- [ ] 切换代理人后，06/07 文件内容与新代理人对齐
- [ ] 切换代理人后，04_授权委托书 中被授权人姓名/身份证号正确更新
- [ ] 数据库迁移兼容旧记录（缺路径字段时降级为跳过）
- [ ] PII 安全：上传的 PDF 默认仅存路径，不上传到云
- [ ] UI 与 Vercel/Linear 风格一致
- [ ] 完整端到端测试通过（pytest + 手动验证）

### 待澄清
- 劳动合同 / 身份证 PDF 存哪里？（模块内 `static/agents/<agent_id>/`？用户本地任意目录？）
- 历史案件已生成的 06/07 PDF 怎么处理？（不重生成？还是标记"已过期"？）
- 多人共用同一份劳动合同的可能？（同公司多代理人）

### 配套文档
- 详细 SPEC：`modules/court-doc-generator/docs/SPEC-agent-binding.md`（明天实现用）

---

## 2026-08-17 出庭手续生成器增加导出功能按钮（待细化）

**类型**: feature
**模块**: court-doc-generator
**状态**: proposed
**优先级**: P2

### 描述
用户提出给"出庭手续生成器"增加一个**导出功能按钮**，作为结果卡片 / 历史案件列表的快捷动作之一，便于把生成结果快速分发或备份。具体形态待用户细化。

### 待澄清点（v0）
- **导出范围**：单案件当前结果 / 历史案件批量 / 整库备份？
- **导出目标**：本地下载 / 本地指定目录 / 飞书云盘？
- **导出格式**：ZIP（现有）/ JSON / CSV / Excel？
- **按钮位置**：结果卡片区 / 侧边栏 / 历史列表？

### 验收标准
- [ ] 澄清点全部明确
- [ ] 导出按钮位置与文案确定
- [ ] 导出逻辑实现 + 端到端测试通过
- [ ] PII 安全：导出范围可控制（避免误导出敏感数据）
- [ ] UI 与 Vercel/Linear 风格一致

---

## 2026-08-17 出庭手续生成器增加拍照扫描功能

**类型**: feature
**模块**: court-doc-generator
**状态**: proposed
**优先级**: P2

### 描述

出庭手续生成器新增「拍照扫描」能力，方向暂定两种，具体场景待业务确认后选定：

1. **拍照识别内容** — 通过摄像头/手机拍照，OCR 识别证件/文书内容，自动提取并填充表单字段（如营业执照、身份证、授权材料等）
2. **拍照生成 PDF** — 拍照后直接转为 PDF 文件，作为附件材料并入出庭手续全套打包（替代扫描仪）

未决事项（暂不定义，业务确认后补入）：
- 适用场景：哪些材料需要拍照、单张还是批量、是否需前端预处理（裁剪/增强/去斜）
- OCR 路线：本机引擎（如 Tesseract）抑或云端服务（飞书/云 OCR）
- 识别结果是否需要人工校对环节

### 验收标准
- [ ] 确认场景：识别内容 or 生成 PDF（二选一或双路线）
- [ ] 拍照/图片上传入口集成到生成流程
- [ ] 产出物可并入出庭手续全套打包

---

## 2026-08-17 双子模块并入 legal（litigation-system + case-intelligence）

**类型**: improvement
**模块**: cross-module
**状态**: done
**优先级**: P1

### 描述

将 `~/code/tmp/dev` 下两个法务项目并入 `legal/modules/`，与 court-doc-generator 并列形成「文书生成 · 诉讼数据平台 · 卷宗检索规则」三角模块布局：

1. **litigation-system**（active, v0.2.0）— 完整迁移 backend/（FastAPI + SQLite FTS5，exclude litig.db/.venv）、frontend/（React 18 + Vite，exclude node_modules/dist）、docs/ research/ requirements/ spec/、docker-compose.yml、.env.example；补 module.yaml + docs/README.md
2. **case-intelligence**（planning, v3.0.0）— 迁移 README.md、requirements/、spec/（方案设计 v3）；补 module.yaml + docs/README.md + spec/SPEC.md（三对象模型/架构/演化路线/6 项待确认）
3. **系统文档** — modules/index.yaml 注册两模块；根 README.md 增加目录结构、模块注册表、模块间关系图；docs/README.md 增加模块文档入口表；docs/SPEC.md 升 v1.1（模块清单/数据流/演进说明）

排除项：`.env`（飞书凭证）、node_modules、dist、data/*.db*、backend/litig.db、__pycache__、.DS_Store 等运行时与临时产物。

### 验收标准
- [x] litigation-system 128 文件迁入 modules/，无 node_modules/dist/db/.env 混入
- [x] case-intelligence 3 份文档迁入 modules/，补 SPEC.md 模块规格
- [x] 两模块补 module.yaml（tech_stack / features / env / created / integrated）
- [x] modules/index.yaml 注册生效（litigation-system=active，case-intelligence=planning）
- [x] 根 README.md / docs/README.md / docs/SPEC.md 同步更新
- [x] git status 无敏感文件混入，index.yaml 可被 AI 解析

---

## 2026-08-17 出庭手续生成器需求与 SPEC 重新整合

**类型**: improvement
**模块**: court-doc-generator
**状态**: done
**优先级**: P0

### 描述
从 `docs/qoder-raw/memories/` 下的全量项目记忆（project_introduction、learned_skill_experience、development_practice_specification、project_build_configuration、project_environment_configuration、project_dependency_configuration、common_pitfalls_experience、development_code_specification 共 8 个分类、约 50 份记忆卡）+ `PROMPTS.md` 反推整理，形成两套文档：

1. `modules/court-doc-generator/docs/REQUIREMENTS.md` — 需求基线（用户画像 / MoSCoW / 8 个用户故事 / 23 项功能 / NFR / 风险 / 验收）
2. `modules/court-doc-generator/docs/SPEC.md` — 技术规格（架构 / 5 项关键决策评分 / 目录结构 / 数据模型 / 9 个主题方案 / 17 项演进路线 / 7 个 Phase 实施 Checklist）

### 验收标准
- [x] 需求文档覆盖 F-001~F-023 MoSCoW 分类
- [x] SPEC.md 包含关键决策量化对比表（Streamlit vs Flask / reportlab vs docx2pdf / PDF.js 全内联 / 端口选择）
- [x] 明确修复旧代码的 P0 问题（src 包结构 / PII 硬编码 / agents 唯一性 bug / docx_to_pdf 未被调用 / pdf_merger 死代码 / 浏览器内 PDF 预览缺失）
- [x] 给出 7 个 Phase、37 条 Checklist 供重新实施使用

---

## 2026-08-17 出庭手续生成器全面开发（v1.1.0）

**类型**: implementation
**模块**: court-doc-generator
**状态**: done
**优先级**: P0

### 描述
按 SPEC §18 的 7 个 Phase、37 条 Checklist 全面重做出庭手续生成器至可运行 v1.1.0：

**Phase 0 基础设施** — 修复 src 包 import 错误 · 写 requirements.txt 锁定版本 · 建齐 7 个目录（data/outputs/.run/bin/tests/templates/static）
**Phase 1 核心逻辑** — 修复 database.py agents 唯一性 bug（UNIQUE(name, company_id)）· 移除 app.py ensure_default_* 硬编码 PII
**Phase 2 PDF 处理** — 接入 docx_to_pdf（reportlab + STSong-Light）+ pdf_merger（pypdf）+ 生成 00_合并出庭手续_<案号>.pdf
**Phase 3 浏览器内预览** — 新增 pdf_viewer_component.py：PDF.js 全内联（Worker Blob URL + eval(atob) 注入 + atob PDF 数据 + 工具栏 + @media print 隐藏 + macOS Preview 降级按钮）
**Phase 4 UI** — Vercel/Linear 风格 CSS（Inter + PingFang SC、8-12px 圆角、200ms 动画）· 身份证号字段 max_chars=18 限长 · PDF 预览集成到生成流程
**Phase 5 服务管理** — bin/{start,stop,restart,status}.{py,sh,bat} 跨平台 · 三重进程定位（PID + 端口 + 进程名）· 健康检查 `/_stcore/health` · macOS bash 3.2 兼容 · 启动.command（双击窗口保持）
**Phase 6 测试与文档** — tests/{conftest,test_generator,test_database,test_pdf_merger,test_pdf_viewer}.py · README.md 三平台启动指引
**Phase 7 飞书 Stub** — feishu_api.py 明确 STUB 标注（sync_case_to_bitable / upload_files_to_drive / notify_via_lark）

### 验收标准
- [x] 7 个 Phase 全部完成
- [x] 单元测试（sanitize_filename、agents 唯一性、PDF 合并、PDF.js 路径）
- [x] requirements.txt 锁定版本（streamlit≥1.40、python-docx≥1.1、reportlab≥4、pypdf≥4、PyMuPDF≥1.24）
- [x] PII 全部移除（app.py、database.py 默认数据为空）
- [x] 跨平台启动脚本（macOS .command + .sh + Windows .bat + Linux .sh）
- [x] README 三平台启动指引
- [ ] 实际打包分发验证（待业务侧提供 templates/ + static/ 素材后补验，条目已完成并留档）

---

## 2026-08-17 系统初始化

**类型**: system
**模块**: system
**状态**: done
**优先级**: P0

### 描述
法务部工程化系统骨架初始化。

### 验收标准
- [x] 目录结构建立
- [x] .gitignore配置
- [x] README.md编写
- [x] SPEC.md系统规格
- [x] modules/index.yaml模块注册表
- [x] docs/requirements/backlog.md需求池
- [x] shared/目录结构
- [ ] 第一个功能模块开发

---

## 2026-08-22 court-doc-generator 拍照扫描集成到新建案件（增强）

**类型**: feature
**模块**: court-doc-generator
**状态**: done
**优先级**: P1（法务日常工作流：收到起诉状 → 拍照扫描 → 自动建档）

### 描述

法务收到起诉状后，在「案件」页的新建案件入口直接拍照/扫描上传起诉状，OCR 自动识别起诉状内容（案号、法院、案由、原告、被告、开庭时间等）并填入新建案件表单，无需手工逐个录入。原独立「拍照扫描」页面的功能并入案件页（新建按钮旁并列扫描入口），我方角色选项扩展为：原告 / 被告 / 第三人 / 法院。

### 验收标准

- [x] 案件页新建按钮旁有「扫描起诉状」按钮，点击打开扫描面板（支持上传图片/PDF 与 URL 两种方式）
- [x] OCR 识别结果显示字段表（案号/法院/案由/原告/被告/开庭时间等）
- [x] 「填入表单」将识别结果映射填充到新建案件表单（案号/审理法院/案由/开庭日期/对方当事人），并自动展开表单
- [x] 对方当事人智能推断：识别到被告 → 填入被告；仅识别到原告 → 填入原告并默认我方角色为被告
- [x] 我方角色下拉包含：原告 / 被告 / 第三人 / 法院 四个选项
- [x] 移除独立「拍照扫描」导航入口与路由，功能收敛到案件页
- [x] 后端 pytest 回归通过；前端 tsc 零错误 + 浏览器 E2E 验证扫描→填充全链路

---

## 需求格式模板

```markdown
## YYYY-MM-DD 需求标题

**类型**: feature | fix | improvement
**模块**: <module-name> | cross-module | system
**状态**: proposed | in-progress | done | rejected
**优先级**: P0(紧急) | P1(重要) | P2(一般) | P3(低)

### 描述
需求详细描述...

### 验收标准
- [ ] 标准1
- [ ] 标准2
```

---

## 2026-09-22 case-intelligence v3.1 落地：案件注册+提取物管理+模板归纳 CLI

**类型**: implementation
**模块**: case-intelligence
**状态**: done
**优先级**: P1

### 描述

Phase 1 基础设施（本周完成）：
- src/database.py（SQLite 三表：cases/artifacts/templates）+ artifact_store.py + template_store.py + case_recognizer.py + extractor_cli.py（register/extract/promote/complete/search/check/report/list 10 子命令）
- bin/start.py/stop.py/restart.py/status.py（4 件套，CLI 模块适配版）
- reference_index.yaml（登记腾讯/广电/安徽酝醒/海帆 4 个历史案件，引用不移动原文件）
- module.yaml 更新：planning→active，entry→bin/extract.py，tech_stack 更新为 CLI+SQLite+Markdown

Phase 2 历史案件迁移（本周）：
- 腾讯案 8 个 Artifact + 广电案 5 个 Artifact 入库 + 归档到 templates_extracted/
- 归纳 4+ 个通用 Template（答辩状/质证意见/当庭陈述/证据目录）
- EXTRACTION_LOG.md 记录迁移操作

### 核心概念

| 概念 | 定义 |
|------|------|
| 案件（Case） | 已结案原始案件，含原告/被告/案由/结果 |
| 提取物（Artifact） | 从案件中提取的结构化参考源（10 种类型） |
| 模板（Template） | 从多个提取物归纳的通用文书结构 |

### CLI 命令速查

```bash
cd modules/case-intelligence
python bin/extract.py register  --name '腾讯案' --case-number '2023京0491民初23751号'
python bin/extract.py extract  --case-id <id> --type defense_argument_chain --title '主体不适格四层论证'
python bin/extract.py promote  --artifact-id <id> --template-name '主体不适格答辩状模板' --category '答辩状'
python bin/extract.py complete --case-id <id>
python bin/extract.py check   --case-number '2023京0491民初23751号'
python bin/extract.py list
python bin/extract.py report
```

### 验收标准
- [x] Phase1 infrastructure（DB + store + CLI + bin/4件套 + reference_index.yaml）
- [x] 腾讯案 8 个 Artifact 入库
- [x] 广电案 5 个 Artifact 入库
- [x] 通用 Template ≥ 4 份
- [x] docs/README.md 完成
- [x] docs/REQUIREMENTS.md 完成

> **状态归档**：本条目对应 v3.1 阶段，后续演进见「v3.2.0 落地」（CHANGELOG 2026-09-22）与「v3.3.0 落地」（CHANGELOG 2026-10-12）。

---

## 2026-09-27 case-intelligence 遗留项修复（已完成 P0 Bug + P1 功能）

**类型**: fix + feature
**模块**: case-intelligence
**状态**: done
**优先级**: P0（Bug修复）

### 已完成修复

#### P0 Bug 修复（✅ 已完成）

- [x] **B-001** `src/lark_bot.py:300` — 修复 `case.get('court')` → `case['court']`（sqlite3.Row 无 .get() 方法）
- [x] **B-002** `src/ai_engine.py` — 添加 `use_cases`/`pros`/`cons` 字段到 EngineConfig（支持 ai_engines.yaml 全字段）
- [x] **B-003** document_generator.py — 经确认模板内容未截断，无需修复
- [x] **B-004** `src/lark_bot.py` — register 命令添加 `year`/`court` 字段（从案号正则推断年份）

#### P1 功能实现（✅ 已完成）

- [x] **F-001** `src/lark_bot.py` — 添加 `/case report` 命令（统计报告：总数/已提取/年度分布/案由分布）
- [x] **F-002** `src/langchain_llm.py` — 新建 LangChain LLM 集成（基于 langchain-openai，调用 MiniMax API）
- [x] **F-003** `src/document_generator.py` — 集成 langchain_llm，支持真实 LLM 生成

### 待处理

| 项目 | 状态 | 说明 |
|------|------|------|
| **飞书Bot接入** | ⏸️ 通道暂停 | 代码就绪（`src/lark_bot.py` 全部命令已实现并通过 CLI 自测，见 2026-08-24 条目）；**通道暂停**——等待飞书企业权限（app_id / app_secret / 事件订阅）方可上线 |
| **容器化部署** | ⏸️ 暂停 | 优先级较低 |

### 验证结果

```bash
# 飞书Bot命令测试
/case list ✅ 返回案件列表
/case search ✅ 搜索功能正常
/case register ✅ 登记成功（含年份推断）
/case detail ✅ 详情显示正常
/case artifacts ✅ 提取物列表
/case report ✅ 统计报告（93案件/89已提取）
/case help ✅ 帮助文本

# LangChain LLM + MiniMax
✅ langchain_llm.py 初始化成功
✅ document_generator 集成成功
✅ 答辩状生成测试通过（1628字符，完整结构）
✅ 源码: MiniMax-Text-01

# pytest
✅ 28 passed, 5 skipped
```

---

## 归档需求（已完成/已拒绝）

| 日期 | 需求 | 结果 |
|------|------|------|
| 2026-08-17 | 系统骨架初始化 | done |
| 2026-08-20 | 案件管理页：查看详情 + 文件预览 + 生成/删除二次确认 | done |
| 2026-08-17 | 扩展 case-intelligence 为案例分析输出生成器（v3.0 → v4.0 升级） | superseded（核心生成能力已由 v3.3.0 LangChain/MiniMax 实现；原 NocoDB + Paperless 方案作废） |

---

## 2026-08-20 court-doc-generator 案件管理页查看/预览 + 二次确认

**类型**: feature + fix
**模块**: court-doc-generator（FastAPI + Vite 前端）
**状态**: done
**优先级**: P1（误操作防护 + 查看报错影响日常使用）

### 描述

案件管理页面只有"生成"没有"查看/预览"，且点查看报错（历史文件 404）。删除/生成均无二次确认，容易误操作。

### 子任务

- [x] **F-053** 后端 history.py：list_history_files 文件路径改为相对 `DATA_DIR`（含 `workspaces/` 前缀），与 files API 拼接逻辑一致（修复预览 404）
- [x] **F-054** 后端 generate.py：记录生成历史时 PRAGMA 动态检测列，兼容新旧 generation_history schema（修复插入 500）
- [x] **F-055** 前端 CasesPage：新增"查看"按钮 + 生成/删除二次确认（ConfirmDialog 组件，删除红色 danger）
- [x] **F-056** 前端 CaseDetailModal：案件详情弹窗（基本信息 + 生成记录 + 文件列表，PDF 可预览 / 全部可下载 ZIP）
- [x] **F-057** 前端生成后预览路径提取修复（output_dir 取 `workspaces/` 前缀相对路径）
- [x] **F-058** generator.py：_resolve_company_pdf 的 None fallback 保护（授权委托书/推荐信传 None 不再 TypeError）

### 验收标准

- [x] 案件行有"查看"按钮，打开详情弹窗显示基本信息 + 生成记录 + 文件列表
- [x] 详情内 PDF 文件可预览（PDF.js canvas 分页），ZIP 可下载
- [x] 生成按钮二次确认（显示案号 + 公司 + 代理人）
- [x] 删除按钮二次确认（红色 danger，提示不可恢复）
- [x] 历史文件预览不再 404，新案件生成后自动预览路径正确
- [x] `npx tsc --noEmit` 零错误；前端浏览器全链路验证通过

---

## 2026-08-22 court-doc-generator 扫描入口位置修正（并入新建表单）

**类型**: fix
**模块**: court-doc-generator（Vite 前端）
**状态**: done
**优先级**: P1（入口错位，用户明确指正）

### 描述

v2.2.0 将「扫描起诉状」按钮放在案件页工具栏（新建按钮旁）。用户反馈：扫描按钮应位于点击「新建案件」后弹出的表单页面内部，否则无法明确扫描识别信息是填入哪个表单。

### 子任务

- [x] 移除 page-actions 工具栏「扫描起诉状」按钮（工具栏仅剩「新建案件」）
- [x] 新建表单卡片标题行右侧新增「扫描起诉状填入」按钮，点击打开 ScanModal
- [x] onApply 移除 setShowForm(true)（按钮仅在表单打开时可见，表单必然已打开）

### 验收标准

- [x] 案件页工具栏无扫描按钮
- [x] 点击「新建案件」→ 表单内出现「扫描起诉状填入」按钮
- [x] 表单内打开 Modal → 上传自造起诉状图 → OCR 识别 7/7 → 填入表单（案号/案由/法院/开庭日期/对方当事人/角色推断正常）
- [x] tsc 零错误；浏览器实测截图 docs/qoder-raw/v221-entry-fix/01-scan-in-form.png

---

## 2026-08-22 court-doc-generator 测试数据隔离与生产数据治理（434 workspace 清理）

**类型**: fix
**模块**: court-doc-generator（backend）
**状态**: done
**优先级**: P1（生产数据被 pytest 污染 + 真实数据被 E2E 误删）

### 描述

pytest 直连真实 FastAPI 应用，累计产生 434 个测试 workspace（TestUser_* 429 + T_* 2 + v21 验证工作室 1 + e2e_scan_ws 2）；多轮浏览器 E2E 复用「张洋」真实账号演练删除验证，导致 case 1~4（含（2026）京0101民初9999号）、company 1、agent 1 被删。

### 根因

1. pytest 无数据隔离：test_api.py 等 5 个模块 TestClient(app) 直连真实 app + random_name() 注册
2. config.py 派生路径类体求值：DATA_DIR 被 env 覆盖后 WORKSPACES_DIR 仍指向生产目录（注册表隔离但业务库未隔离）
3. E2E 无专用账号规范：删除验证打在真实数据上

### 子任务

- [x] 清理 434 测试 workspace（data/workspaces 目录 + 注册表白名单法，仅保留「张洋」）
- [x] 恢复 case 4（（2026）京0101民初9999号）：案号取自 generation_history#8，法院由 0101 推导，公司/代理人关联现存雷石/张洋；案由/开庭/对方待用户补充
- [x] 删除垃圾案件 5/6（E2E 数字填充产物）+ 关联 generation_history 11/12 + outputs/1
- [x] backend/tests/conftest.py 全局 DATA_DIR → .pytest-data（临时目录，session 结束清理）
- [x] config.py 派生路径改 property（WORKSPACES_DIR / STATIC_DIR / TEMPLATES_DIR / OUTPUTS_DIR 不再类体固定）
- [x] .gitignore 追加 .pytest-data/
- [x] AGENTS.md §7.5 测试/验证数据隔离规范（E2E 专用账号强制）

### 验收标准

- [x] 生产注册表仅剩 1 个 workspace（张洋）
- [x] pytest 40 passed 且运行前后生产 data/ 零增长
- [x] 张洋库恢复 case 4 且 generation_history 关联完好
- [x] 备份存档 data/backups/2026-08-22_fix/（workspaces.db + zhangyang_court_matters.db）

---

## 2026-08-22 court-doc-generator 生成正确性与稳定性修复（进程级锁 + 失败显性化 ）

**类型**: fix
**模块**: court-doc-generator（generator.py + generate API + 前端）
**状态**: done
**优先级**: P0（用户实测：doc 模板生成的 PDF 未被合并进最终 PDF，静默缺份）

### 描述

用户实测：点击生成后 04 授权委托书 + 05 推荐信（doc 模板动态生成）的 PDF 未并入最终合并 PDF。

**根因（静默降级链）**：

1. generator.py：docx→PDF 转换失败仅 `warnings.warn`（stderr，前端不可见）→ 04/05 PDF 缺失
2. pdf_merger.py：缺失文件 `continue` 静默跳过 → 合并件悄悄少 1-2 份
3. generator.py：`except ValueError: pass` 吞掉「无任何可合并 PDF」

**触发器（已实证）**：generator.py 的 `rmtree + mkdir` 非原子 + generate.py 全程无锁 → 同一案件重复点击/多端并发时互相删除目录（8 进程复现：FileNotFoundError / EmptyFileError / 「OK 但 merged 缺失」）。

### 修复

- [x] F-059 generator.py：`_generate_to_dir` 加进程级互斥锁（fcntl.flock / msvcrt.locking 兼容，锁文件放 output_dir 父目录避免被 rmtree 误删）；抢锁失败抛出「该案件正在生成中」
- [x] F-060 generator.py：生成结束收集缺失 PDF 清单（7 份材料的 glob 校验），`_generate_to_dir` 增可选 `missing` 参数透出
- [x] F-061 generate.py API：`GenerateOut` 增 `missing` / `total_expected` 字段 ，生成不完整时响应带缺失清单（不再假装成功）
- [x] F-062 前端：CasesPage 生成结果提示——缺失时显示告警「已生成 X/7 份，缺：01 营业执照…」，合并件缺份同样提示
- [x] F-063 tests：并发抢锁（第二进程拒绝）+ 缺失清单收集（monkeypatch docx_to_pdf 失败）单测

### 验收标准

- [x] 同案号并发生成：第二个请求快速失败并提示「正在生成中」，不再出现 rmtree 竞态
- [x] docx→PDF 转换失败时，前端显示「已生成 X/7 份，缺：04 授权委托书、05 推荐信」而非「✅ 生成完成」
- [x] 合并 PDF 缺份时前端同样显性告警
- [x] pytest 全量通过（含新增并发锁/缺失清单用例）
- [x] `npx tsc --noEmit` 零错误

---

## 2026-08-22 court-doc-generator 拍照扫描多图合并 + OCR 识别鲁棒化（增强）

**类型**: feat
**模块**: court-doc-generator（scan_service.py + backend/app/api/scan.py + 前端 ScanModal/scan.ts）
**状态**: done
**优先级**: P1（用户实测：起诉状常为多页/多图，单图上传信息不全；真实照片识别准确率不足）

### 描述

用户补充需求：起诉状往往不止一张图片，需要一次上传多个图片/文档并整合识别信息；同时用真实拍摄的起诉状照片（Downloads/20260822-220005.jpg + 20260822-220019.jpg，腾讯音乐诉北京雷石著作权案）实测，识别准确率不足。

### 实现

- [x] svc01 scan_service.py：双 PSM 交叉 OCR（psm3 自动分页 + psm6 统一文本块，逐图双通道互补拼接）；法院「人民法院」形近字映射还原（法→活、院→区等）；当事人全候选评分截断（身份词/公司尾词截断 + 机构词评分选优）；案由四级抽取策略（案由标签行 → 复合案由词表 → XX纠纷正则清洗 → 关键词兜底）
- [x] api01 scan.py：/api/v1/scan/scan 支持 files 多文件列表参数（FormData 同名多次）+ file 单文件向后兼容；逐文件类型/大小校验 → PDF 转图 → img_paths 合并统一识别；finally 统一清理临时文件
- [x] fe01 前端：ScanModal input multiple 多选 → 已选文件列表（名称/大小/移除）→「开始识别（N 个文件）」批量上传；scan.ts 新增 scanUploadFiles(files: File[])
- [x] tst01 测试：test_scan_service 新增 5 个真实场景用例（法院形近字/案由标签行/复合词表/真实 OCR 段落当事人截断/多页合并抽取）

### 验收标准

- [x] 双图上传端到端实测：法院=北京市朝阳区人民法院、案由=侵害作品信息网络传播权纠纷、原告=腾讯音乐娱乐(珠海) 有限公司、被告=北京雷石天地电子技术股份有限公司、标的金额=2260000 全部精确识别
- [x] 单文件 file 参数向后兼容（旧版前端调用不破坏）
- [x] pytest 全量 45 passed（含新增 5 用例）；`npx tsc --noEmit` 零错误

---

## 2026-08-22 court-doc-generator server 部署完备性补全

**类型**: feat
**模块**: court-doc-generator
**状态**: proposed
**优先级**: P1（用户计划部署到 server，当前缺生产运行形态）

### 描述

用户拟将 court-doc-generator 部署到 server。评估结论：本地自洽（bin 4件套 + PID/日志 + /health + ports.yaml + README 一键启动），但缺生产形态：① 前端仅 Vite dev server（无 build 产物托管）；② docx_to_pdf 中文硬编码 macOS 字体路径（server 无该路径 → CID fallback 打印空白）；③ 无部署手册/.env.example；④ 日志无轮转；⑤ docs/README.md 仍为旧 Streamlit 架构描述。

### 实现方案（用户裁决）

- [ ] svc01 docx_to_pdf.py 字体自适应：多平台候选探测（macOS Songti/STFangsong → Linux Noto CJK → Windows SimSun/SimHei）+ FONT_DIR 环境变量自定义 + CID fallback 兜底
- [ ] svc02 生产形态：后端 FastAPI 自动托管 frontend/dist/（检测到 build 产物则挂载 + SPA fallback），server 单进程访问
- [ ] svc03 日志轮转：bin 启动脚本对旧日志 rollover 保留 N 份，防单文件激增
- [ ] fe01 README 新增「生产部署」章节：前端 build → 后端统一端口运行 → systemd 可选单元样例
- [ ] docs01 新增部署手册（docs/部署指南.md）：前置依赖/字体/数据迁移/日志查看/升级
- [ ] docs02 .env.example：PORT/HOST/DATA_DIR/CORS 等可覆盖项示例
- [ ] docs03 更新 docs/README.md 为 React+FastAPI 当前架构
- [ ] tst01 字体自适应单测（多平台路径候选探测顺序 + FONT_DIR 覆盖）+ 全量 pytest 回归

### 验收标准

- [ ] tesseract 安装后（无 screen 服务器）OCR 扫描可用
- [ ] 无 macOS 字体环境下生成 04/05 PDF 不依赖 CID fallback（有 Linux/Windows 字体即真嵌入）
- [ ] 生产模式：npm run build 一次 → 仅启动后端 → http://server:8001 完整可用
- [ ] 日志文件不无限增长（保留最近 N 份）
- [ ] docs/README.md 与当前 React+FastAPI 架构一致，无 Streamlit 残留
