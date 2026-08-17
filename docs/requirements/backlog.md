# 需求池 / Requirements Backlog

> AI可解析格式，带YAML头部结构化元数据

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
