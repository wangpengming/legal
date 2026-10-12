# case-intelligence 模块规格文档 v3.3.0

> **版本**: 3.3.0 | **更新**: 2026-10-12
> **状态**: active
> **架构**: 五维度提取 + prompts 驱动 + 固定模板输出
> **部署/域名**: thunderbox · `legal-case.tbox.ktvsky.com`（唯一域名 / `internal`），代码来源 GitHub（见 `AGENTS.md §10.4.5`）

---

## 1. 核心概念

### 1.1 三个核心对象

| 概念 | 定义 | 示例 |
|------|------|------|
| **案源（Case）** | 一份案件记录，含基本信息 + 画像标签 + 录入方式 | 腾讯音乐诉北京雷石侵权纠纷案 |
| **提取物（Artifact）** | 从案件材料中按 5 维度提取的结构化知识，供 AI 生成文书参考 | D3: 主体不适格四层递进论证 |
| **模板（Template）** | 固定的文书格式，通用不变，供 AI 生成文书时填充 | 答辩状四段式 / 质证意见四性格式 |

### 1.2 核心原则

- **提取物是燃料**：Artifact 是 AI 生成文书的参考输入，不是最终产物
- **提取维度固定，内容随案由变化**：5 个维度（D1-D5）适用于所有案由类型
- **模板格式固定**：答辩状/质证意见/当庭陈述/证据目录 4 种文书类型通用
- **Prompts 是系统大脑**：所有 AI 操作通过 prompts/ 目录的提示词驱动

---

## 2. 目录结构

```
modules/case-intelligence/
├── src/
│   ├── __init__.py
│   ├── database.py              # SQLite: cases + artifacts + templates
│   ├── artifact_store.py         # 提取物 CRUD
│   ├── template_store.py         # 模板 CRUD（output_templates/）
│   ├── case_recognizer.py        # 案件匹配（D1-D5 画像）
│   └── extractor_cli.py          # CLI 工具
├── data/
│   ├── case_registry.db          # SQLite 数据库
│   └── artifacts/                # 提取物文件（按 case_id 目录）
├── prompts/                     # ⭐ AI 提示词规则库（核心）
│   ├── prompts.yaml             # 索引 + 使用指南
│   ├── 提取/
│   │   ├── 1_新案材料提取_D1-D5.md      # 5维度提取
│   │   ├── 2_跨案归纳_Artifact汇聚.md    # 跨案归纳
│   │   └── 3_质量检查_提取物审核.md     # 质量审核
│   ├── 匹配/
│   │   └── 4_新案匹配_相似案源检索.md   # 新案匹配
│   └── 生成/
│       ├── 5_答辩状生成.md
│       ├── 6_质证意见生成.md
│       ├── 7_当庭陈述生成.md
│       └── 8_证据目录生成.md
├── output_templates/             # 固定模板（MD 格式）
│   ├── 答辩状/
│   ├── 质证意见/
│   ├── 当庭陈述/
│   └── 证据目录/
├── output/                      # 生成的文书（按案件+日期组织）
│   └── {case_id}/
│       └── {YYYY-MM-DD}/
│           ├── 答辩状.md + 答辩状.docx
│           ├── 质证意见.md + 质证意见.docx
│           └── ...
├── templates_extracted/          # 历史案件归档
├── reference_index.yaml          # 外部原始案件索引
├── docs/
│   ├── README.md               # 用户手册
│   ├── REQUIREMENTS.md         # 需求基线
│   ├── SPEC.md                # 本文档
│   └── EXTRACTION_LOG.md      # 提取操作日志
└── bin/
    ├── extract.py              # CLI 入口
    └── 4件套                  # start/stop/status/restart
```

---

## 3. 数据库 schema

### 3.1 cases 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | UUID |
| case_number | TEXT UNIQUE | 案号 |
| case_name | TEXT | 案件名称 |
| plaintiff | TEXT | 原告 |
| defendant | TEXT | 被告 |
| cause | TEXT | 案由 |
| result | TEXT | 案件结果 |
| source_path | TEXT | 原始材料路径 |
| status | TEXT | pending / extracted / archived |
| extracted_at | TEXT | 提取时间 |
| notes | TEXT | 备注 |
| created_at | TEXT | 创建时间 |
| entry_method | TEXT | 录入方式（CLI / UI / AI） |
| scene | TEXT | 涉案场景 |
| plaintiff_auth_level | TEXT | 原告授权层级 |
| defendant_auth_status | TEXT | 被告授权状态 |

### 3.2 artifacts 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | UUID |
| case_id | TEXT FK | 所属案件 |
| artifact_type | TEXT | 维度（D1/D2/D3/D4/D5） |
| title | TEXT | 标题 |
| content | TEXT | 内容（Markdown） |
| source_ref | TEXT | 来源引用 |
| version | INTEGER | 版本号 |
| created_at | TEXT | 创建时间 |

### 3.3 D1-D5 维度定义

| 维度 | 名称 | 提取内容 | 适用所有案由 |
|------|------|---------|------------|
| D1 | **事实认定** | 当事人/背景/争议焦点/关键事实/权利基础/行为定性 | ✅ |
| D2 | **法律依据** | 适用法条/法律关系定性/权利基础/抗辩可行性 | ✅ |
| D3 | **攻防策略** | 原告诉请/被告抗辩排序/论证结构/主战场决策 | ✅ |
| D4 | **证据体系** | 双方证据清单/质证要点/举证责任分配 | ✅ |
| D5 | **赔偿裁量** | 赔偿请求/抗辩理由/计算方式/裁量因素/预估区间 | ✅ |

---

## 4. 工作流

### 4.1 流程A：案例库建设（历史案件 → 知识库）

```
桌面案例分析目录（原始材料）
         ↓
prompts/提取/1_新案材料提取_D1-D5.md
         ↓
AI 按 5 维度提取 → 5 个 Artifact
         ↓
prompts/提取/3_质量检查_提取物审核.md
         ↓
人工复核 → 确认入库
         ↓
artifacts/知识库 积累
         ↓
定期：prompts/提取/2_跨案归纳_Artifact汇聚.md
         ↓
output_templates/ 通用模板完善
```

### 4.2 流程B：新案分析（新案 → 文书输出）

```
新案材料
         ↓
prompts/匹配/4_新案匹配_相似案源检索.md
         ↓
AI 匹配相似案件 + 相关 Artifact
         ↓
prompts/生成/（5-8）各文书生成.md
         ↓
AI 生成文书内容
         ↓
output/ → MD + DOCX
```

---

## 5. Prompts 管理规范

| 规范 | 说明 |
|------|------|
| 版本锁定 | 每个提示词文件头部含版本号，修改需更新版本 |
| 不可随意修改 | prompts 是系统大脑，修改需审查 |
| 索引同步 | prompts/prompts.yaml 维护完整索引 |
| 测试验证 | 每次修改提示词后，需重新验证生成效果 |

---

## 6. 与其他模块的关系

```
桌面案例分析目录（原始材料）
         ↓
┌─────────────────────────────────────┐
│     case-intelligence                 │
│                                      │
│  prompts/ ← AI 规则的大脑             │
│  artifacts/ ← 知识库（5维度提取）    │
│  output_templates/ ← 固定模板        │
│  output/ ← 生成文书                  │
└─────────────────────────────────────┘
         ↓ 调用
office-workflow-litigation-doc（诉讼文书生成）
```

---

## 7. 健康检查

本模块为 **CLI + Streamlit** 形态，HTTP 健康端点由 Streamlit 内置提供。

| 方式 | 端点 / 命令 | 说明 |
|------|------------|------|
| HTTP（UI 运行时） | `GET /_stcore/health` → `200 ok` | Streamlit 内置；端口 `18503`（fallback `18504`）；符合 `AGENTS.md §10.4.4` |
| 轻量探针（JSON） | `python bin/health.py` | 输出 `{status, module, version, ui, db}`；退出码 `0`=健康 / `1`=异常；**只读**，不创建数据库 |
| 状态检查 | `python bin/status_ui.py` | 端口 + PID + `/_stcore/health` + 日志尾部 |

### 7.1 bin/health.py 输出示例

```json
{
  "status": "ok",
  "module": "case-intelligence",
  "version": "3.3.0",
  "ui": { "running": true, "port": 18503, "endpoint": "/_stcore/health", "http_status": 200, "ok": true },
  "db": { "ok": true, "initialized": true, "total_cases": 93, "total_artifacts": 12, "total_templates": 7 }
}
```

> **portal 集成**：统一门户通过 `/case/_stcore/health`（nginx 同源反代）判定在线；`bin/health.py` 供无 HTTP 依赖的集成方（脚本 / CI）补充版本与数据库维度。

---

## 8. 暂不引入

- RAG / 向量检索（未来引入）
- 自动 OCR / 文档解析（人工手动）
- 多用户 / workspace 隔离（单用户先行）
