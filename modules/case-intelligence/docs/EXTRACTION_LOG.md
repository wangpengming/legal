# 提取操作日志 / Extraction Operation Log

> 记录每次提取操作的时间线，用于追溯和审计。
> 格式：时间线 + 操作摘要 + 关联提取物/模板列表。

---

## 操作日志模板

```
## YYYY-MM-DD HH:MM 操作摘要

**操作人**: 张洋
**关联案件**: [case_id] [案件名]
**操作类型**: register | extract | promote | complete

### 本次提取物

| # | 类型 | 标题 | Artifact ID | 备注 |
|---|------|------|-------------|------|
| 1 | defense_argument_chain | 主体不适格四层论证 | a1b2c3d4 | 从答辩状第3-15段提取 |

### 本次模板（promote 时填写）

| # | 模板名 | 分类 | 来源 Artifact | 备注 |
|---|--------|------|--------------|------|
| 1 | 主体不适格答辩状模板 | 答辩状 | a1b2c3d4 | 归纳自腾讯案 |

### 备注
...
```

---

## 历史操作记录

<!-- 以下为操作记录，按时间倒序，新增时在下方追加 -->

## 2026-09-22 Phase 2 迁移：腾讯案 Artifact 入库

**操作人**: 张洋
**关联案件**: f843bae6 腾讯音乐诉北京雷石侵权纠纷案
**操作类型**: batch_extract

### 本次提取物

| # | 类型 | 标题 | Artifact ID |
|---|------|------|-------------|
| 1 | case_key_facts | 案件关键事实清单 | 52211a0d |
| 2 | cross_exam_strategy | 质证意见四性分别表述格式 | 4e914e96 |
| 3 | contingency_response | 庭审应变话术体系 | 5afea8f6 |
| 4 | reverse_strategy | 反向维权九维打击路径 | 4efcce31 |
| 5 | court_statement | 当庭陈述四段式结构 | 39e761fd |
| 6 | evidence_structure | 证据三级分类清单 | 71801719 |
| 7 | defense_argument_chain | 主体不适格四层递进论证 | 5fbbbb12 |

### 本次归档
归档目录: templates_extracted/腾讯音乐诉北京雷石侵权纠纷案/（7个MD + metadata.json）

---

## 2026-09-22 Phase 2 迁移：广电案 Artifact 入库

**操作人**: 张洋
**关联案件**: 0bf66137 浙江广电诉雷石:广汽埃安案件
**操作类型**: batch_extract

### 本次提取物

| # | 类型 | 标题 | Artifact ID |
|---|------|------|-------------|
| 1 | defense_argument_chain | 主观无过错四点论证 | 4a162c6c |
| 2 | legal_reasoning_chain | 赔偿数额六点论证 | 8e96668a |
| 3 | quantitative_analysis | 传播范围量化分析 | 944003fc |
| 4 | contingency_response | 赔偿数额应变话术 | bc611421 |
| 5 | court_statement | 双主线当庭陈述四段式 | b8bd2a5c |

### 本次归档
归档目录: templates_extracted/浙江广电诉雷石广汽埃安案件/（5个MD + metadata.json）

---

## 2026-09-22 Phase 2 迁移：Template 归纳

**操作人**: 张洋
**操作类型**: promote (批量)

### 本次模板

| # | 模板名 | 分类 | 来源 Artifact |
|---|--------|------|--------------|
| 1 | 答辩状四层递进模板 | 答辩状 | 5fbbbb12 (腾讯案) |
| 2 | 质证意见四性分别表述格式 | 质证意见 | 4e914e96 (腾讯案) |
| 3 | 当庭陈述四段式结构 | 当庭陈述 | 39e761fd (腾讯案) |
| 4 | 证据三级分类清单 | 证据目录 | 71801719 (腾讯案) |
| 5 | 双主线当庭陈述四段式 | 当庭陈述 | b8bd2a5c (广电案) |
| 6 | 赔偿数额应变话术体系 | 其他 | bc611421 (广电案) |
| 7 | 主观无过错四点论证模板 | 答辩状 | 4a162c6c (广电案) |

---

## 统计摘要

| 统计项 | 数量 |
|--------|------|
| 累计提取案件数 | 3 |
| 累计提取 Artifact 数 | 12 |
| 累计 Template 数 | 7 |
| 最近操作 | 2026-09-22 Phase 2 迁移完成 |
