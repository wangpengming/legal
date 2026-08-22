# 需求池 / Requirements Backlog

> AI可解析格式，带YAML头部结构化元数据

---

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

## 归档需求（已完成/已拒绝）

| 日期 | 需求 | 结果 |
|------|------|------|
| 2026-08-17 | 系统骨架初始化 | done |
| 2026-08-20 | 案件管理页：查看详情 + 文件预览 + 生成/删除二次确认 | done |

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
