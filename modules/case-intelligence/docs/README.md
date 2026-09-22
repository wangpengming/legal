# case-intelligence 模块使用手册

> **模块定位**：案件情报提取与文书生成系统。接收案件材料，按 5 维度提取结构化知识（Artifact），通过 prompts 驱动 AI 生成文书，输出 MD + DOCX 格式。

---

## 1. 核心概念

```
案源（Case）
    ├── 录入方式（CLI / UI / AI）
    ├── 画像标签（涉案场景 / 授权状态 / ...）
    │
    ├── 提取 → Artifact（按 5 维度 D1-D5）
    │         └── 知识库积累（随案件增多）
    │
    └── 生成 → Template（固定 4 种文书格式）
              └── MD 格式 + DOCX 输出
```

### 三个核心对象

| 对象 | 定义 | 特征 |
|------|------|------|
| **案源** | 案件基本信息 + 画像标签 | 录入方式固定（CLI/UI/AI） |
| **提取物** | 按 5 维度（D1-D5）提取的知识 | 内容随案由变化，维度固定 |
| **模板** | 固定的文书格式 | 不随案由变化，4 种通用 |

### 5 个提取维度（D1-D5）

| 维度 | 名称 | 说明 |
|------|------|------|
| D1 | 事实认定 | 当事人/背景/争议焦点/关键事实/权利基础/行为定性 |
| D2 | 法律依据 | 适用法条/法律关系定性/权利基础/抗辩可行性 |
| D3 | 攻防策略 | 原告诉请/被告抗辩/论证结构/主战场决策 |
| D4 | 证据体系 | 双方证据清单/质证要点/举证责任分配 |
| D5 | 赔偿裁量 | 赔偿请求/抗辩理由/计算方式/裁量因素/预估区间 |

---

## 2. prompts/ 目录（核心）

**所有 AI 操作通过 prompts/ 目录的提示词驱动**，提示词是系统的"大脑"。

```
prompts/
├── prompts.yaml              # 索引 + 使用指南
├── 提取/
│   ├── 1_新案材料提取_D1-D5.md    # 从材料提取 5 维度
│   ├── 2_跨案归纳_Artifact汇聚.md  # 从多个同类 artifact 归纳通用结构
│   └── 3_质量检查_提取物审核.md   # 提取物质量审核
├── 匹配/
│   └── 4_新案匹配_相似案源检索.md  # 新案匹配相似案件
└── 生成/
    ├── 5_答辩状生成.md
    ├── 6_质证意见生成.md
    ├── 7_当庭陈述生成.md
    └── 8_证据目录生成.md
```

### 使用流程A：建设知识库（历史案件 → artifacts）

```
1. 准备原始案件材料
2. 复制 prompts/提取/1_新案材料提取_D1-D5.md
3. AI 按 5 维度提取 → 输出结构化结果
4. 人工复核 → 入库
```

### 使用流程B：生成文书（新案 → output/）

```
1. 输入新案基本信息
2. 复制 prompts/匹配/4_新案匹配_相似案源检索.md
3. AI 匹配相似案件 + 列出相关 artifact
4. 选择文书类型 → 复制对应 prompts/生成/5-8_*.md
5. AI 生成文书 → 导出 MD + DOCX
```

---

## 3. CLI 命令参考

### 3.1 案源管理

```bash
# 注册案源（支持画像标签）
python3 bin/extract.py register \
  --name "腾讯音乐诉北京雷石侵权纠纷案" \
  --case-number "2023京0491民初23751号" \
  --plaintiff "腾讯音乐" \
  --defendant "北京雷石" \
  --cause "侵害作品信息网络传播权纠纷" \
  --entry-method "CLI" \
  --scene "实体KTV" \
  --defendant-auth-status "已获音集协授权"

# 列出所有案源
python3 bin/extract.py list
python3 bin/extract.py list --status pending

# 搜索案源
python3 bin/extract.py search --query "腾讯"

# 检查重复
python3 bin/extract.py check --case-number "2023京0491民初23751号"
```

### 3.2 提取物管理（D1-D5）

```bash
# 提取 Artifact（5 维度）
python3 bin/extract.py extract \
  --case-id <案件ID> \
  --type D1 \
  --title "腾讯案事实认定"

# 列出案件下所有提取物
python3 bin/extract.py artifacts --case-id <案件ID>
```

### 3.3 模板管理

```bash
# 列出所有模板
python3 bin/extract.py templates list
python3 bin/extract.py templates list --category "答辩状"

# 搜索模板
python3 bin/extract.py templates search --query "主体不适格"

# 查看模板详情
python3 bin/extract.py templates show --template-id <模板ID>
```

### 3.4 统计报告

```bash
python3 bin/extract.py report
```

---

## 4. 目录说明

| 目录 | 用途 |
|------|------|
| `src/` | 源代码（database / artifact_store / template_store / case_recognizer / extractor_cli） |
| `data/artifacts/` | 提取物文件（按案件 ID 目录组织） |
| `prompts/` | AI 提示词规则库（系统大脑） |
| `output_templates/` | 固定模板（答辩状/质证意见/当庭陈述/证据目录） |
| `output/` | 生成的文书（按案件 ID + 日期组织，MD + DOCX） |
| `templates_extracted/` | 历史案件归档 |

---

## 5. 数据统计

- 案源总数: 3
- 提取物总数: 12（D1:1 / D2:1 / D3:2 / D4:2 / D5:6）
- 模板总数: 7

---

## 6. 注意事项

- **Prompts 是核心**：所有 AI 操作通过 prompts/ 驱动，修改需谨慎
- **维度固定，内容变化**：5 个维度（D1-D5）适用于所有案由
- **原文件不移动**：原始案件文件留在原位，通过 reference_index.yaml 索引引用
- **暂不 RAG**：当前版本使用结构化字段匹配，不引入向量检索
