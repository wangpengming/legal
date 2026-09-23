# case-intelligence 需求基线 / Requirements Baseline

> 本文档定义 case-intelligence 模块的需求基线，采用 MoSCoW 优先级分类。
> 用户故事格式：作为 [角色]，我希望 [功能]，以便 [收益]。

---

## 1. Must Have（必须实现）

### M-1: 案件注册与管理

**类型**: feature
**优先级**: P0
**模块**: case-intelligence

#### 描述
能够注册新案件，记录案号、原告、被告、案由、原始材料路径等信息，并追踪提取状态。

#### 用户故事
作为法务人员，我希望注册新案件并记录基本信息，以便追踪每个案件的提取进度。

#### 验收标准
- [x] `python3 bin/extract.py register --name "..." --case-number "..."` 成功创建案件记录
- [x] `python3 bin/extract.py list` 能列出所有案件及状态
- [x] 案件状态支持 pending / extracted / archived 三种

---

### M-2: 提取物（Artifact）管理

**类型**: feature
**优先级**: P0
**模块**: case-intelligence

#### 描述
从已结案件中提取结构化参考源，支持 10 种类型，写入 SQLite + Markdown 文件。

#### 用户故事
作为法务人员，我希望将案件材料提取为结构化提取物，以便后续复用和 AI 生成文书参考。

#### 验收标准
- [x] `python3 bin/extract.py extract --case-id <id> --type defense_argument_chain` 能创建 Artifact 并写入 data/artifacts/
- [x] `python3 bin/extract.py artifacts --case-id <id>` 能列出案件下所有提取物
- [x] 支持全部 10 种 artifact_type

---

### M-3: 案件识别（重复检测）

**类型**: feature
**优先级**: P0
**模块**: case-intelligence

#### 描述
识别新案件是否与已有案件重复，支持案号精确匹配 + 当事人指纹匹配 + 案由模糊匹配。

#### 用户故事
作为法务人员，我希望在注册新案件前能识别是否已有重复案件，避免重复工作。

#### 验收标准
- [x] `python3 bin/extract.py check --case-number "2023京0491民初23751号"` 能识别重复案件
- [x] 支持案号精确匹配 > 当事人指纹匹配 > 案由模糊匹配三级识别

---

### M-4: 模板（Template）归纳与使用

**类型**: feature
**优先级**: P1
**模块**: case-intelligence

#### 描述
将提取物归纳为可复用的文书模板，支持分类管理和全文搜索。

#### 用户故事
作为法务人员，我希望将多个案件的提取物归纳为通用模板，以便快速生成新案件的诉讼文书。

#### 验收标准
- [x] `python3 bin/extract.py promote --artifact-id <id> --template-name "..." --category "答辩状"` 能创建模板
- [x] `python3 bin/extract.py templates list` 能列出所有模板
- [x] `python3 bin/extract.py templates search --query "赔偿数额"` 能搜索模板
- [x] 模板不少于 4 份

---

### M-5: 统计报告

**类型**: feature
**优先级**: P1
**模块**: case-intelligence

#### 描述
生成案件处理统计报告，显示已处理/待处理案件数量、提取物分布等信息。

#### 用户故事
作为法务人员，我希望看到案件处理的统计报告，以便了解工作进度。

#### 验收标准
- [x] `python3 bin/extract.py report` 能生成完整统计报告

---

### M-6: 飞书 Bot 集成

**类型**: feature
**优先级**: P0
**模块**: case-intelligence

#### 描述
将飞书 Bot 接入 case-intelligence 模块，实现通过飞书对话完成案件管理、提取物查询和文书生成等核心操作。用户在飞书群中通过指令与 Bot 交互，无需切换到本地 CLI。

#### 用户故事
作为法务人员，我希望在飞书群中直接通过 Bot 指令查询案件、提取文书参考、生成法律文书，以便随时随地高效工作。

#### 系统架构

```
飞书群用户
    │
    ▼
┌──────────────────────────────┐
│   飞书 Bot（lark-mcp 或     │
│   hermes-feishu channel）    │
└────────────┬─────────────────┘
             │ 接收消息/指令
             ▼
┌──────────────────────────────┐
│  case-intelligence CLI 层    │
│  bin/extract.py              │
│  （扩展支持 HTTP API 或      │
│   subprocess 调用模式）       │
└────────────┬─────────────────┘
             │
             ▼
┌──────────────────────────────┐
│  case-intelligence Core      │
│  database.py / artifact_     │
│  store.py / template_store   │
└──────────────────────────────┘
```

#### 指令设计

| 指令 | 功能 | 示例 |
|------|------|------|
| `/case register` | 注册新案件 | `/case register 案号：（2026）xxx号 原告：xxx 被告：xxx` |
| `/case list` | 列出案件 | `/case list` 或 `/case list --status pending` |
| `/case search` | 搜索案件 | `/case search 腾讯音乐` |
| `/case detail` | 查看案件详情 | `/case detail <case_id>` |
| `/case extract` | 提取案件（调用 prompts） | `/case extract <case_id>` |
| `/case artifacts` | 查询提取物 | `/case artifacts <case_id>` |
| `/case generate` | 生成文书 | `/case generate <case_id> 答辩状` |
| `/case status` | 修改案件状态 | `/case status <case_id> extracted` |
| `/case help` | 查看帮助 | `/case help` |

#### 技术方案

**方案A（推荐）：Bot → CLI subprocess**
- Bot 接收消息 → 解析指令 → 调用 `python3 bin/extract.py <args>` subprocess
- 输出截获 → 格式化回复 → 发送到飞书群
- 优点：复用现有 CLI，无需重写核心逻辑
- 缺点：每次调用有 Python 启动开销（可接受）

**方案B：Bot → HTTP API**
- 在 `bin/` 新增 HTTP server（如 FastAPI）暴露 REST API
- Bot 通过 API 调用核心功能
- 优点：响应更快，支持长连接
- 缺点：引入额外依赖，需要管理 API 认证

#### 验收标准

- [ ] 飞书 Bot 能响应 `/case list` 并返回案件列表（表格格式）
- [ ] 飞书 Bot 能响应 `/case search <关键词>` 并返回匹配案件
- [ ] 飞书 Bot 能响应 `/case register <信息>` 创建新案件
- [ ] 飞书 Bot 能响应 `/case detail <case_id>` 返回案件详情
- [ ] 飞书 Bot 能响应 `/case help` 返回指令帮助
- [ ] Bot 与 legal 模块共用水印/模板文件（如需生成 DOCX）
- [ ] 指令解析容错：支持自然语言模糊匹配

#### 依赖项

- `lark-mcp`（飞书多维表格等 17 个工具）
- 或 `hermes-feishu channel`（Hermes 内置飞书集成）
- case-intelligence CLI（现有 `bin/extract.py`）

#### 备注

- 本需求复用现有 `case-intelligence` 的 database、prompts 和 templates，不复制数据
- 文书生成调用 `prompts/生成/` 下的提示词，由 AI 填充内容后返回

### S-1: 外部数据源索引

**类型**: feature
**优先级**: P2
**模块**: case-intelligence

#### 描述
通过 `reference_index.yaml` 索引引用外部原始案件文件，原文件不移动不复制。

#### 用户故事
作为法务人员，我希望保留原始案件文件在原位，同时在系统中建立索引引用，避免文件重复。

#### 验收标准
- [x] `reference_index.yaml` 登记 3 个已知历史案件
- [x] 原始路径仅作索引引用，不移动不复制

---

### S-2: 案件归档

**类型**: feature
**优先级**: P2
**模块**: case-intelligence

#### 描述
将已完成提取的案件归档到 `templates_extracted/` 目录，保留案件级元数据。

#### 用户故事
作为法务人员，我希望将已完成提取的案件归档保存，以便后续查阅和复用。

#### 验收标准
- [x] `templates_extracted/` 目录下有腾讯案和广电案的归档文件
- [x] 每个归档包含 metadata.json 和提取物 Markdown 文件

---

### S-3: 提取操作日志

**类型**: documentation
**优先级**: P2
**模块**: case-intelligence

#### 描述
记录每次提取操作的时间线，便于追溯和审计。

#### 用户故事
作为法务人员，我希望记录每次提取操作，以便追溯和审计。

#### 验收标准
- [x] `docs/EXTRACTION_LOG.md` 记录了所有提取操作
- [x] 包含操作人、关联案件、操作类型、提取物列表

---

## 3. Could Have（可以实现）

### C-1: 提取物版本管理

**类型**: enhancement
**优先级**: P3
**模块**: case-intelligence

#### 描述
提取物支持版本管理，每次更新 +1 版本。

#### 验收标准
- [ ] `artifact.version` 字段支持自动 +1
- [ ] 支持查看历史版本

---

### C-2: 模板使用统计

**类型**: enhancement
**优先级**: P3
**模块**: case-intelligence

#### 描述
记录模板被引用的次数，追踪模板的使用频率。

#### 验收标准
- [x] `template.usage_count` 字段已存在
- [ ] 模板被使用后 +1

---

## 4. Won't Have（本版本不实现）

### W-1: RAG / 向量检索
**原因**：Phase X 以后再引入，当前使用结构化字段匹配。

### W-2: 多用户 / workspace 隔离
**原因**：本轮单用户先行。

### W-3: 自动 OCR / 文档解析
**原因**：人工手动输入提取物内容。
