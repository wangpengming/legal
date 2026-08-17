# 需求池 / Requirements Backlog

> AI可解析格式，带YAML头部结构化元数据

---

## 2026-08-17 扩展 case-intelligence 为案例分析输出生成器（v3.0 → v4.0 升级）

**类型**: feature
**模块**: case-intelligence（吸收方案，原 cross-module 决策已并入）
**状态**: proposed
**优先级**: P1（业务核心需求）
**版本演进**: case-intelligence v3.0 → v4.0（起引入 LLM 生成能力，打破 v3.0"不做 AI"原则）

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
