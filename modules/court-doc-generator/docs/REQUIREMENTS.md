# 出庭手续生成器 · 需求文档（REQUIREMENTS）

> **文档版本**：v1.0
> **最后更新**：2026-08-17
> **模块名**：court-doc-generator
> **状态**：Active
> **来源**：从 `docs/qoder-raw/memories/` 全量记忆 + `docs/SPEC.md` + `docs/requirements/backlog.md` + `PROMPTS.md` 反推整合而成

---

## 0. 文档目的

本文件定义"出庭手续生成器"的**完整需求基线**，作为：

1. 团队评审 / 用户验收的基线
2. 后续 SPEC / DESIGN / 测试用例 / 验收清单的唯一参考源
3. 任何代码修改前的需求对齐依据

如本文件与 `module.yaml` / `PROMPTS.md` / 源码冲突，**以本文件为准**，并通过 CHANGELOG.md 记录变更。

---

## 1. 项目背景与问题陈述

### 1.1 业务背景

公司法人/外聘律师参加法院庭审前，必须向法院提交 **7 份标准化材料**：

| 编号 | 材料 | 类型 | 生成方式 |
|------|------|------|---------|
| 01 | 营业执照复印件 | 固定证件 | PDF 静态文件 |
| 02 | 法定代表人证明 | 动态生成 | Word 模板 + 占位符替换 |
| 03 | 法人身份证 | 固定证件 | PDF 静态文件 |
| 04 | 授权委托书 | 动态生成 | Word 模板 + 占位符替换 |
| 05 | 推荐信 | 动态生成 | Word 模板 + 占位符替换 |
| 06 | 代理人劳动合同 | 固定证件 | PDF 静态文件 |
| 07 | 代理人身份证 | 固定证件 | PDF 静态文件 |

### 1.2 现有痛点

| 痛点 | 量化影响 |
|------|---------|
| 每次出庭手动改日期/案号/案由 | 单次出庭耗时 30-60 分钟 |
| Word 模板字段填错（"民初"vs"民终"、日期格式、案号括号） | 月均返工 2-3 次 |
| 7 份文件分散在邮件/微信/打印店 | 出庭前一晚临时凑齐 |
| 涉及身份证/合同等敏感信息，邮件传输风险高 | 数据合规隐患 |
| 法务小白不会写代码，无法自己迭代工具 | 长期依赖外协或 IT |

### 1.3 项目目标

> **构建一个本地一键运行的"出庭手续 7 份材料生成器"，让法务小白能在 5 分钟内独立完成全部材料生成 + 合并 + 在线预览打印。**

---

## 2. 用户画像（Personas）

### P1 — 法务专员「小李」（主要用户）

- **角色**：公司法务，每天处理 3-5 个诉讼
- **技术能力**：Office 熟练，不懂代码，不会装 Python 虚拟环境
- **痛点**：出庭前一晚手动填 Word 模板到深夜
- **成功标准**：能在不读任何代码的情况下，自己完成生成 → 预览 → 打印

### P2 — 外聘律师「王律师」（次要用户）

- **角色**：律所律师，偶尔代理公司案件
- **技术能力**：略懂命令行
- **痛点**：想用工具但数据必须留在本地，不能上传到云
- **成功标准**：能拷贝整个文件夹到自己电脑，零配置启动

### P3 — IT 运维「赵工」（管理员）

- **角色**：公司 IT，负责工具分发与故障排查
- **技术能力**：熟悉 Windows CMD / macOS shell
- **痛点**：小白用户的环境问题（Python 没装、端口冲突、双击脚本闪退）
- **成功标准**：能通过 `bin/manage.sh status` 一键诊断，给出明确指引

---

## 3. 范围

### 3.1 In-Scope（必须实现）

- 7 份出庭材料一键生成（3 份动态 DOCX + 4 份静态 PDF）
- Word 模板【】占位符按文档顺序替换
- 7 份材料合并为单个 PDF
- 浏览器内 PDF 预览（PDF.js 全内联 base64 data URI 方案）
- 一键在线打印（浏览器内 + macOS 系统 Preview 降级）
- ZIP 打包下载（中文文件名 UTF-8 不乱码）
- 公司 / 代理人 / 案件 / 生成历史 数据管理（SQLite）
- 历史案件检索 + 重新生成
- 跨平台启动脚本：macOS (.command)、Windows (.bat + start.py)
- 服务管理：start / stop / restart / status（三重进程定位）
- 端口固定 18501，避开 80/443/3000/5000/8000/8080/8501/8888
- 局域网共享（Network URL）

### 3.2 Out-of-Scope（不在本期范围）

| 项 | 原因 | 优先级 |
|----|------|--------|
| 拍照扫描（生成扫描件/识别内容） | 需求未澄清 | P3 — 待澄清 |
| 飞书多维表格案件同步 | 已留 stub，未来扩展 | P3 |
| 飞书云盘文件上传 | 已留 stub，未来扩展 | P3 |
| 飞书 IM 通知 | 已留 stub，未来扩展 | P3 |
| 多用户并发（同一案件多人同时编辑） | Streamlit 单进程不适合 | P3 |
| 案件审批工作流 | 业务未明确 | P3 |
| 公网穿透 | 仅局域网 + 临时 Cloudflare Tunnel | P3 |

---

## 4. 需求优先级（MoSCoW 矩阵）

| ID | 需求 | MoSCoW | 验收方式 |
|----|------|--------|---------|
| F-001 | 7 份材料一键生成 | **Must** | 端到端生成测试 |
| F-002 | 【】占位符按文档顺序替换 | **Must** | 单元测试 + 视觉验证 |
| F-003 | DOCX 模板文件 | **Must** | 模板样例齐 |
| F-004 | 静态 PDF 复制 | **Must** | 文件复制成功 |
| F-005 | 7 份 PDF 合并为 1 份 | **Must** | 合并后页数 = 总页数 |
| F-006 | ZIP 打包（UTF-8 中文文件名） | **Must** | 解压测试 |
| F-007 | 浏览器内 PDF 预览 | **Must** | 视觉 + 功能测试 |
| F-008 | 一键打印（浏览器内） | **Must** | 打印对话框测试 |
| F-009 | macOS 系统 Preview 降级 | **Must** | macOS 平台测试 |
| F-010 | SQLite 数据持久化 | **Must** | 启停不丢数据 |
| F-011 | 公司/代理人 CRUD | **Must** | UI 表单测试 |
| F-012 | 案件 CRUD | **Must** | UI 表单测试 |
| F-013 | 历史案件检索 | **Must** | 搜索功能测试 |
| F-014 | 跨平台启动脚本 | **Must** | macOS + Windows 启动测试 |
| F-015 | 服务管理（start/stop/restart/status） | **Must** | shell 命令测试 |
| F-016 | 端口固定 18501 | **Must** | 端口监听测试 |
| F-017 | 健康检查（/_stcore/health） | **Must** | curl 200 测试 |
| F-018 | 双击启动脚本自动打开浏览器 | **Must** | UI 行为测试 |
| F-019 | UI 视觉（Vercel/Linear 风格） | **Should** | 视觉评审 |
| F-020 | 飞书集成（位表/云盘/IM 通知） | **Won't (this release)** | Stub 已预留 |
| F-021 | PDF 缩略图（多页概览） | **Could** | 视觉可选 |
| F-022 | Cloudflare Tunnel 公网分享 | **Could** | 临时演示 |
| F-023 | 拍照扫描功能 | **Won't (待澄清)** | 需求澄清后启动 |

---

## 5. 用户故事与验收标准

### US-001：法务小白首次启动

> **作为** 法务专员
> **我希望** 双击桌面图标就能启动工具
> **以便于** 不需要懂命令行

**验收标准（AC）**：
- [ ] AC-1.1：双击 `启动.command` 后弹出窗口不一闪而过（已修复）
- [ ] AC-1.2：服务起来后浏览器自动打开 `http://localhost:18501`
- [ ] AC-1.3：首次启动自动创建 SQLite 数据库与默认空数据（**严禁写死真实 PII**）
- [ ] AC-1.4：UI 显示引导提示："请先在左侧添加委托单位信息"
- [ ] AC-1.5：启动失败时终端窗口保留并显示明确错误指引

### US-002：填写案件信息并生成 7 份材料

> **作为** 法务专员
> **我希望** 在网页表单中填写案号、案由、法院、日期等
> **以便于** 一键生成全部 7 份标准化材料

**验收标准（AC）**：
- [ ] AC-2.1：必填字段标 *，缺失时按钮置灰
- [ ] AC-2.2：可选择委托单位（公司）、代理人
- [ ] AC-2.3：案由描述预览实时刷新（原告/被告/第三人三种文案）
- [ ] AC-2.4：点击生成后 ≤ 30s 出结果
- [ ] AC-2.5：生成结果按出庭顺序命名（01-07）
- [ ] AC-2.6：所有日期格式统一为 "YYYY 年 M 月 D 日" 中文格式
- [ ] AC-2.7：中文文件名 ZIP 下载解压不乱码（UTF-8）

### US-003：浏览器内预览合并 PDF 并打印

> **作为** 法务专员
> **我希望** 生成后立即在浏览器内查看合并后的 PDF 并直接打印
> **以便于** 出庭前最后确认 + 直接打印，不需要打开其他软件

**验收标准（AC）**：
- [ ] AC-3.1：生成成功后自动显示合并 PDF 预览（PDF.js 全内联）
- [ ] AC-3.2：预览支持缩放、翻页、文字选择
- [ ] AC-3.3：预览工具栏有"打印全部"按钮
- [ ] AC-3.4：点击"打印全部"调用浏览器原生打印对话框
- [ ] AC-3.5：打印样式隐藏工具栏（@media print）
- [ ] AC-3.6：中文 PDF 内嵌字体清晰显示（无方块）
- [ ] AC-3.7：**降级方案**：浏览器内预览失败时，"系统 Preview 打开"按钮仍可用（macOS）

### US-004：重新生成历史案件

> **作为** 法务专员
> **我希望** 在历史列表里一键重新生成同一案件的出庭材料
> **以便于** 案号/日期变了不用再输一遍

**验收标准（AC）**：
- [ ] AC-4.1：历史案件列表显示最近 50 条
- [ ] AC-4.2：按案号/案由/对方当事人模糊搜索
- [ ] AC-4.3：点击"重新生成"复用原案件信息生成到新目录（不覆盖）
- [ ] AC-4.4：生成完成后自动打开 Finder/Explorer 到输出目录

### US-005：维护公司/代理人信息

> **作为** 法务专员
> **我希望** 在侧边栏维护多个委托单位和多个代理人
> **以便于** 不同案件切换不同主体

**验收标准（AC）**：
- [ ] AC-5.1：可新增/编辑/删除公司
- [ ] AC-5.2：可新增/编辑/删除代理人
- [ ] AC-5.3：公司字段：公司全称*、法人姓名*、法人职务、信用代码、地址、电话
- [ ] AC-5.4：代理人字段：姓名*、性别、身份证号、职务、电话
- [ ] AC-5.5：身份证号字段在 UI 中默认隐藏，可点击显示
- [ ] AC-5.6：可标记默认公司/代理人（UI 提供入口）

### US-006：跨平台部署

> **作为** IT 运维
> **我希望** 同一份代码在 macOS 和 Windows 上都能跑
> **以便于** 给不同操作系统的法务分发

**验收标准（AC）**：
- [ ] AC-6.1：macOS 双击 `启动.command` 可启动
- [ ] AC-6.2：Windows 双击 `启动.bat` 可启动（Python 智能探测）
- [ ] AC-6.3：Python 未安装时 Windows 启动脚本自动打开下载页（不弹 Microsoft Store）
- [ ] AC-6.4：Linux 通过 `bash bin/manage.sh start` 可启动
- [ ] AC-6.5：跨平台脚本兼容 macOS bash 3.2（不用数组 += 语法）

### US-007：网络共享（局域网 / 公网）

> **作为** 外聘律师
> **我希望** 在局域网内或通过临时公网链接访问法务同事的实例
> **以便于** 远程试用而无需对方拷贝整个文件夹

**验收标准（AC）**：
- [ ] AC-7.1：Streamlit 配置开启 `server.headless=true` 支持局域网访问
- [ ] AC-7.2：README 给出 Network URL 使用说明
- [ ] AC-7.3：可选 Cloudflare Tunnel 启动脚本生成临时公网 URL（**仅限临时演示**，禁止生产）

### US-008：服务管理与故障排查

> **作为** IT 运维
> **我希望** 一键查看服务状态/日志/重启
> **以便于** 小白用户的工单能快速定位

**验收标准（AC）**：
- [ ] AC-8.1：`bash bin/manage.sh status` 显示：PID、端口、CPU/内存、健康检查 URL、最后 5 行日志
- [ ] AC-8.2：`bash bin/manage.sh restart` 完成 stop + start
- [ ] AC-8.3：`bash bin/manage.sh stop` 三重验证（PID + 端口 + 进程名），避免僵尸进程
- [ ] AC-8.4：服务意外崩溃后下次 `start` 自动清理残留 PID 文件
- [ ] AC-8.5：日志路径 `.run/streamlit.log` 滚动记录

---

## 6. 非功能需求（NFR）

### NFR-1 安全与隐私

- [ ] NFR-1.1：所有数据存储在本地 SQLite，**不连接任何外网业务 API**
- [ ] NFR-1.2：默认数据使用占位符（空字符串 + 引导文案），**严禁硬编码真实身份证号/手机号**
- [ ] NFR-1.3：身份证号字段 UI 默认遮罩（`*** ********** 1143`）
- [ ] NFR-1.4：飞书凭证（app_id/app_secret）走 `.env`，被 `.gitignore` 屏蔽
- [ ] NFR-1.5：PDF.js / PDF 文件以 base64 data URI 内联，不走 HTTP 路由（避免被中间人嗅探）

### NFR-2 性能

- [ ] NFR-2.1：单案件 7 份材料端到端生成 ≤ 30 秒（含 PDF 转换/打包）
- [ ] NFR-2.2：浏览器内 PDF 预览首屏渲染 ≤ 3 秒（基于 5MB PDF）
- [ ] NFR-2.3：UI 表单输入响应延迟 ≤ 200ms

### NFR-3 易用性

- [ ] NFR-3.1：法务小白无需阅读任何代码即可完成首次启动 → 生成 → 打印
- [ ] NFR-3.2：UI 关键操作按钮文案明确（"🚀 生成出庭手续（7 份文件）"）
- [ ] NFR-3.3：错误信息明确指出问题与下一步（如"未检测到 Python，请安装"）
- [ ] NFR-3.4：UI 视觉风格参考 Vercel / Linear（克制渐变 + Inter 字体 + 8px 圆角 + 200ms 微动画）

### NFR-4 跨平台

- [ ] NFR-4.1：macOS 11+（Big Sur 起）
- [ ] NFR-4.2：Windows 10+（包括 1809 之前的无 curl 老版本）
- [ ] NFR-4.3：Linux（Ubuntu 20.04+）
- [ ] NFR-4.4：Python 3.9 - 3.12 全版本兼容

### NFR-5 鲁棒性

- [ ] NFR-5.1：服务进程三重定位（PID 文件 + 端口占用 + 进程名匹配）
- [ ] NFR-5.2：端口冲突时明确报错（不自动换端口，避免找不到）
- [ ] NFR-5.3：macOS bash 3.2 兼容（不用 bash 4 数组语法）
- [ ] NFR-5.4：.command 双击窗口不闪退（read 等待输入）
- [ ] NFR-5.5：Word 模板占位符不足时优雅降级（缺失值填空串，不崩）
- [ ] NFR-5.6：PDF 转换失败时降级为只生成 DOCX（不阻塞其他文件）

### NFR-6 国际化与本地化

- [ ] NFR-6.1：界面文案全中文
- [ ] NFR-6.2：Word 模板中文全角【】占位符
- [ ] NFR-6.3：日期显示中文格式 "2026 年 8 月 17 日"
- [ ] NFR-6.4：ZIP 中文文件名 UTF-8 编码

### NFR-7 可维护性

- [ ] NFR-7.1：所有依赖固定版本号（requirements.txt）
- [ ] NFR-7.2：源码分模块（config / database / generator / docx_to_pdf / pdf_merger / feishu_api）
- [ ] NFR-7.3：核心逻辑（占位符替换）有单元测试覆盖
- [ ] NFR-7.4：每次版本变更同步更新 CHANGELOG.md

---

## 7. 数据模型

### 7.1 表结构

| 表名 | 字段 |
|------|------|
| companies | id, name(唯一), credit_code, legal_rep_name, legal_rep_position, legal_rep_id_card, address, phone, is_default, created_at, updated_at |
| agents | id, name, gender, id_card, position, phone, company_id(FK), is_default, created_at, updated_at |
| cases | id, case_number, case_cause, court, hearing_date, opposing_party, our_role, authority_type, company_id(FK), agent_id(FK), notes, created_at, updated_at |
| generation_history | id, case_id(FK), case_number, output_dir, file_count, generated_at |

### 7.2 字段约束

- `companies.name` 唯一索引
- `agents` 唯一性 = `(name, company_id)`（**修复旧版的 `(name, id_card)` bug：未填身份证会被认作同一人**）
- `cases.case_number` 不唯一（同一案号可能多次生成）
- 所有时间戳 ISO 8601 字符串（便于跨平台/调试）

### 7.3 隐私字段

- `companies.legal_rep_id_card`、`agents.id_card` 默认 UI 遮罩显示
- 数据库文件不入 git（已在 `.gitignore` 屏蔽 `data/`）

---

## 8. 接口约定

### 8.1 模块入口

```bash
# macOS
bash 启动.command

# Windows
启动.bat

# Linux / 通用
bash bin/manage.sh {start|stop|restart|status}
```

### 8.2 内部 API（Python）

```python
# 数据库
db.list_companies() -> list[dict]
db.upsert_company(data: dict) -> int
db.list_agents() -> list[dict]
db.upsert_agent(data: dict) -> int
db.create_case(data: dict) -> int
db.get_case(case_id: int) -> dict | None
db.search_cases(keyword: str) -> list[dict]
db.list_cases(limit: int = 50) -> list[dict]
db.add_history(case_id, case_number, output_dir, file_count) -> None

# 生成器
generator.values_for_legal_rep_cert(case, company) -> list
generator.values_for_power_of_attorney(case, company, agent) -> list
generator.values_for_recommendation(case, company, agent) -> list
generator.generate_court_matters(case, company, agent) -> Path
generator.open_in_finder(path: Path) -> None

# DOCX → PDF
docx_to_pdf.docx_to_pdf(docx_path: Path, pdf_path: Path) -> None

# PDF 合并
pdf_merger.merge_pdfs(pdf_paths: list, output_path: Path) -> Path

# 飞书（占位）
feishu_api.sync_case_to_bitable(case, company, agent) -> Optional[str]
feishu_api.upload_files_to_drive(folder_path, case_number) -> Optional[str]
feishu_api.notify_via_lark(user_open_id, message) -> bool
```

---

## 9. 风险评估与缓解

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|---------|
| **R1：PII 泄露到仓库** | 🔴 高 | 违反隐私规范、可能违法 | 默认数据清空 + .gitignore 屏蔽 data/ + UI 遮罩 + 提交前 lint |
| **R2：PDF.js 版本升级破坏兼容性** | 🟡 中 | 浏览器内预览失效 | 锁定 pdfjs-dist 版本 + 季度回顾 |
| **R3：LibreOffice/docx2pdf 跨平台差异** | 🟡 中 | PDF 转换失败 | 双方案 fallback；本期使用 reportlab 自渲染（零外部依赖） |
| **R4：macOS bash 3.2 数组语法** | 🟢 低 | 服务脚本无法运行 | 改用字符串拼接 |
| **R5：Streamlit 单进程并发** | 🟢 低 | 多人同时编辑冲突 | 文档明确"单用户本地工具" |
| **R6：.command 窗口闪退** | 🟢 低 | 用户误以为未启动 | 末尾 read 等待输入 |
| **R7：PDF.js 内联方案被 iframe sandbox 拦截** | 🟡 中 | 浏览器内预览完全失败 | 已用 base64 data URI 绕过 + 保留 macOS Preview 降级 |
| **R8：云端 OpenAPI 不可用导致飞书集成无法上线** | 🟢 低 | MVP 不依赖飞书 | Stub 接口预留，等开通权限再接 |
| **R9：Word 模板字段填错导致法院退回** | 🟡 中 | 出庭失败 | 必填字段校验 + 预览 + 打印前最后检查 |
| **R10：端口 18501 偶发冲突** | 🟢 低 | 服务无法启动 | 启动时检测 + 明确报错指引改端口 |

---

## 10. 验收测试清单

### 10.1 端到端流程测试

| TC-ID | 场景 | 步骤 | 预期 |
|-------|------|------|------|
| TC-E2E-01 | 首次启动（macOS） | 双击 .command → 浏览器打开 → 表单填案号"（2026）京0101民初1234号" → 点生成 | 7 份文件出现在 `outputs/2026-XX-XX_*/` |
| TC-E2E-02 | 浏览器内预览 | 生成后 | PDF.js 显示合并 PDF，中文清晰 |
| TC-E2E-03 | 一键打印 | 点"打印全部" | 浏览器打印对话框弹出 |
| TC-E2E-04 | 系统 Preview 降级 | macOS 点击降级按钮 | Preview.app 打开 |
| TC-E2E-05 | ZIP 下载 | 点"下载完整 zip 包" | 文件下载，文件名含中文，解压无乱码 |
| TC-E2E-06 | 历史检索 | 输案号"（2026）"搜索 | 列出含此案号的记录 |
| TC-E2E-07 | 重新生成 | 历史记录点"重新生成" | 新目录出现 7 份文件 + ZIP |
| TC-E2E-08 | macOS 重启服务 | `bash bin/manage.sh restart` | stop 旧进程 → start 新进程 → 健康检查通过 |
| TC-E2E-09 | Windows 双击 | 双击 启动.bat | 服务起来 + 浏览器打开（Python 已装场景） |
| TC-E2E-10 | Windows 无 Python | 未装 Python 时双击 | 自动打开 python.org 下载页（不弹 Store） |

### 10.2 单元测试

| TC-ID | 覆盖 | 场景 |
|-------|------|------|
| TC-UNIT-01 | replace_placeholders_by_position | 段落含 3 个【】按顺序替换 |
| TC-UNIT-02 | replace_placeholders_by_position | 跨段落占位符 |
| TC-UNIT-03 | replace_placeholders_by_position | 表格内占位符 |
| TC-UNIT-04 | build_case_description | 三种身份文案 |
| TC-UNIT-05 | parse_hearing_date | 多种日期格式 |
| TC-UNIT-06 | sanitize_filename | 含非法字符 |
| TC-UNIT-07 | generate_court_matters | 完整流程 |
| TC-UNIT-08 | pdf_merger.merge_pdfs | 7 文件按序合并 |

---

## 11. 变更日志

| 日期 | 版本 | 变更摘要 |
|------|------|---------|
| 2026-08-17 | v1.0 | 首次从 docs/ + qoder-raw 全量反推整合，确立需求基线 |