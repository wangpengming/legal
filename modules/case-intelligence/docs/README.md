# case-intelligence 模块使用手册

> **模块定位**：案件情报提取与模板归纳系统。接收已结案件材料，提取结构化参考源（Artifact），归纳可复用文书模板（Template），为 AI 生成诉讼文书提供高质量燃料。

---

## 1. 快速开始

### 1.1 环境要求

- Python 3.10+
- 无需额外依赖（仅标准库 + 内置 SQLite）

### 1.2 查看帮助

```bash
cd modules/case-intelligence
python3 bin/extract.py --help
```

---

## 2. 核心概念

| 概念 | 说明 | 示例 |
|------|------|------|
| **Case（案件）** | 已结案的原始案件记录 | 腾讯音乐诉北京雷石侵权纠纷案 |
| **Artifact（提取物）** | 从案件中提取的结构化参考源 | 主体不适格四层递进论证 |
| **Template（模板）** | 从多个提取物归纳的通用文书结构 | 答辩状四层递进模板 |

> 关系：Case → 提取 N 个 Artifact → 归纳为 1 个 Template

---

## 3. 核心工作流

### 3.1 注册案件

```bash
python3 bin/extract.py register \
  --name "腾讯音乐诉北京雷石侵权纠纷案" \
  --case-number "2023京0491民初23751号" \
  --plaintiff "腾讯音乐" \
  --defendant "北京雷石天地" \
  --cause "侵害作品信息网络传播权纠纷" \
  --source-path "/Users/zhangyang/Desktop/腾讯案/"
```

### 3.2 提取 Artifact

```bash
# 提取抗辩论证链
python3 bin/extract.py extract \
  --case-id <案件ID> \
  --type defense_argument_chain \
  --title "主体不适格四层递进论证" \
  --source-ref "从答辩状第3-15段提取"
```

支持的提取物类型：

| 类型 | 说明 |
|------|------|
| `defense_argument_chain` | 抗辩论证链 |
| `cross_exam_strategy` | 质证策略 |
| `evidence_structure` | 证据结构 |
| `legal_reasoning_chain` | 法律推理链 |
| `quantitative_analysis` | 量化分析 |
| `liability_calculation` | 责任计算 |
| `contingency_response` | 应变话术 |
| `reverse_strategy` | 反向维权路径 |
| `court_statement` | 当庭陈述 |
| `case_key_facts` | 关键事实清单 |

### 3.3 将 Artifact 归纳为 Template

```bash
python3 bin/extract.py promote \
  --artifact-id <Artifact ID> \
  --template-name "答辩状四层递进模板" \
  --category "答辩状"
```

### 3.4 标记案件提取完成

```bash
python3 bin/extract.py complete --case-id <案件ID>
```

---

## 4. CLI 命令参考

### 4.1 案件管理

```bash
# 注册案件
python3 bin/extract.py register --name "案件名" ...

# 列出所有案件
python3 bin/extract.py list
python3 bin/extract.py list --status pending

# 搜索案件
python3 bin/extract.py search --query "腾讯"

# 检查案件重复
python3 bin/extract.py check --case-number "2023京0491民初23751号"

# 关联原始材料路径
python3 bin/extract.py link --case-id <ID> --path "/path/to/materials"
```

### 4.2 提取物管理

```bash
# 列出某案件所有提取物
python3 bin/extract.py artifacts --case-id <案件ID>

# 提取新的提取物
python3 bin/extract.py extract --case-id <案件ID> --type <类型> --title "标题"
```

### 4.3 模板管理

```bash
# 列出所有模板
python3 bin/extract.py templates list

# 按分类筛选模板
python3 bin/extract.py templates list --category "答辩状"

# 搜索模板
python3 bin/extract.py templates search --query "赔偿数额"

# 查看模板详情
python3 bin/extract.py templates show --template-id <模板ID>
```

### 4.4 报告与统计

```bash
# 生成统计报告
python3 bin/extract.py report
```

---

## 5. 数据库结构

```
data/case_registry.db
├── cases         案件表
├── artifacts      提取物表
└── templates      模板表
```

---

## 6. 文件存储

```
data/
├── case_registry.db          SQLite 数据库
└── artifacts/               提取物 Markdown 文件（按 case_id 目录）
    └── {case_id}/
        ├── metadata.yaml
        └── *.md

templates_extracted/          案件归档模板（从历史案件提取）
├── 腾讯音乐诉北京雷石侵权纠纷案/
└── 浙江广电诉雷石广汽埃安案件/
```

---

## 7. 已有数据

### 7.1 已注册案件（3 个）

| 案件 | 案号 | 提取物 | 状态 |
|------|------|--------|------|
| 腾讯音乐诉北京雷石侵权纠纷案 | 2023京0491民初23751号 | 7 个 | ✅ extracted |
| 浙江广电诉雷石:广汽埃安案件 | — | 5 个 | ⏳ pending |
| 安徽酝醒追偿权纠纷 | 2025-18841号 | 0 个 | ⏳ pending |

### 7.2 已有模板（7 个）

| 模板名 | 分类 |
|--------|------|
| 答辩状四层递进模板 | 答辩状 |
| 主观无过错四点论证模板 | 答辩状 |
| 质证意见四性分别表述格式 | 质证意见 |
| 当庭陈述四段式结构 | 当庭陈述 |
| 双主线当庭陈述四段式 | 当庭陈述 |
| 证据三级分类清单 | 证据目录 |
| 赔偿数额应变话术体系 | 其他 |

---

## 8. 注意事项

- **原文件不移动**：原始案件文件留在原位，case-intelligence 仅通过 `reference_index.yaml` 索引引用
- **暂不 RAG**：当前版本不使用向量检索，使用结构化字段匹配
- **提取物是燃料**：提取物本身不是最终文书，而是 AI 生成文书时的参考输入
