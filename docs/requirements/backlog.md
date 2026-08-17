# 需求池 / Requirements Backlog

> AI可解析格式，带YAML头部结构化元数据

---

## 2026-08-17 出庭手续生成器需求与 SPEC 重新整合

**类型**: improvement
**模块**: court-doc-generator
**状态**: in-progress
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

## 2026-08-17 系统初始化

**类型**: system
**模块**: system
**状态**: in-progress
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

## 归档需求（已完成/已拒绝）

| 日期 | 需求 | 结果 |
|------|------|------|
| 2026-08-17 | 系统骨架初始化 | done |
