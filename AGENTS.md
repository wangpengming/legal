# Legal System — AI 代理工程行动约束

> **适用对象**：所有 AI 代理（Qoder / Claude / Cursor / 其他）在 `/Users/zhangyang/Desktop/code/legal/` 工作时必读。
>
> **配套文档**：
> - `.qoder/agents.md` — Qoder 专用配置（命名规范、开发流程、忽略规则）
> - `docs/SPEC.md` — 系统规格 v1.1（架构、模块、需求、安全红线、版本约定）
> - 本文件 — **工程行动约束与红线**，与上述两份文档互为补充

---

## 1. 工程定位

法务部工程化系统（Legal System），模块化 Monorepo，让非技术人员无需写代码即可使用 AI 程序。

**四大原则**：

1. **本地优先** — 数据不外传，离线可用
2. **AI 可解析** — 所有规范以 Markdown + YAML 头部编写
3. **模块独立** — 每个模块可单独运行 / 测试 / 部署
4. **演进可追溯** — 所有变更登记 `backlog.md` + `CHANGELOG.md`

---

## 1.5 模块完整性：完整系统原则 🔧

> "模块独立"不是"能跑就行"，而是每个子模块必须是一个**完整、自包含、可独立托管**的小型系统。

| 维度 | 强制要求 | 落地示例 |
|------|---------|---------|
| 独立运行 | 提供完整的启动/停止/重启/状态查询脚本（**4 件套**） | `bin/start.py` 等 |
| 脚本管理 | Python 核心脚本 + 跨平台壳层（`.sh` / `.bat`） | `bin/start.{py,sh,bat}` |
| 路由架构 | RESTful API：模块前缀 + 版本前缀 + 资源路径 | `/api/<module>/v1/<resource>` |
| 端口管理 | 固定端口 + 全局注册表 + 启动前冲突检测 | `module.yaml` 声明 `port` |
| 健康检查 | HTTP `/health` 端点返回 200 + 模块版本 | 启动 8 秒内可探测 |
| 日志 / PID | `.run/<name>.{pid,log}` 统一管理 | 已纳入 `.gitignore` |
| 模块登记 | `module.yaml` + `modules/index.yaml` 双登记 | 缺一不可 |

**完整规范见 [§10.4](#104-模块基础设施规范强制)**。

---

## 2. 当前模块清单（截至 2026-08-17）

| 模块 | 状态 | 版本 | 职责 | 入口 | 来源 |
|------|------|------|------|------|------|
| `court-doc-generator` | active | 1.1.4 | 出庭手续文档生成器（7 份材料 + PDF 合并预览） | `modules/court-doc-generator/app.py` | 原生开发 |
| `litigation-system` | active | 0.2.0 | 法务诉讼业务平台（飞书历年案件天级同步 + 检索/统计/AI） | `modules/litigation-system/backend/app/main.py` | 2026-08-17 并入 |
| `case-intelligence` | planning | 3.0.0 | 同质化案件文档检索与规则系统 | `none` | 2026-08-17 并入（方案设计） |
| `portal` | planning | 0.1.0 | Legal 统一门户（注册表驱动子系统集成框架 + 系统健康监控总览） | `modules/portal/prototype.html` | 2026-08-17 原生开发 |

> 模块注册表：`modules/index.yaml`。任何模块变更须先改此处再改代码。

---

## 3. 目录导航

```
legal/
├── AGENTS.md              ← 本文件（AI 代理必读）
├── README.md              项目总览
├── .gitignore             屏蔽 data/outputs/.venv/.env 等
├── docs/
│   ├── SPEC.md            系统规格 v1.1
│   ├── README.md          文档索引
│   └── requirements/
│       ├── backlog.md     需求池（YAML 头部结构化）
│       └── CHANGELOG.md   变更日志
├── modules/
│   ├── index.yaml         模块注册表
│   └── <module-name>/     各功能模块（详见 §2）
├── shared/
│   ├── common/            🚧 规划中：跨模块共享代码
│   ├── templates/         🚧 规划中：跨模块共享模板
│   └── config/            跨模块共享配置
├── tools/                 🚧 规划中：工程脚本
└── .qoder/
    ├── agents.md          Qoder 专用工作指南
    └── projects/          🚧 各模块独立 Qoder 项目配置（待建）
```

---

## 4. 开发流程（5 步强制）

> **严禁跳过任何一步**。AI 代理在任何修改前必须先确认当前所处阶段。

| 步骤 | 动作 | 产出 |
|------|------|------|
| ① 需求登记 | 在 `docs/requirements/backlog.md` 新增条目（含 YAML 头部） | `proposed` 状态条目 |
| ② 评审 | 与用户确认优先级 + 模块归属 + 验收标准 | 状态保持 `proposed`，标准明确 |
| ③ 开发 | 在 `modules/<name>/` 下实现，遵循模块自身 SPEC | 可运行的代码 + 单测 |
| ④ 注册 | 更新 `modules/index.yaml` + 模块 `module.yaml`（必要时） | 模块元数据同步 |
| ⑤ 上线 | 改 `backlog.md` 状态为 `done` + 在 `CHANGELOG.md` 登记版本变更 | 完成归档 |

---

## 5. 命名规范（强制）

| 元素 | ✅ 正确 | ❌ 错误 |
|------|---------|---------|
| 模块目录 | `court-doc-generator` | `智能出庭文书` |
| 文件名 | `pdf_merger.py` | `PDF合并器.py` |
| 函数名 | `def merge_pdfs()` | `def 合并PDF()` |
| 类名 | `class CaseRecord` | `class 案件记录` |
| 变量名 | `case_number` | `案件案号` |
| 配置键 | `DB_PATH` | `数据库路径` |

**中文仅出现在**：`README.md` / `SPEC.md` / `REQUIREMENTS.md` / 注释 / UI 文案。

---

## 6. 数据安全红线 🔴

### 6.1 PII（个人敏感信息）

| 红线 | 措施 |
|------|------|
| ❌ 严禁硬编码真实身份证号 / 手机号 / 真实姓名 | 默认数据全部留空（`""`），由用户在 UI 填写真实信息 |
| ❌ 严禁将真实 PII 写入代码 / 注释 / 测试 fixture | 测试用 `000000000000000000` 等占位符 |
| ❌ 严禁在日志中打印完整身份证 / 手机号 | 必要时用 `mask_id_card()` 遮罩（`前4位****后4位`） |

### 6.2 密钥管理

- `.env` / `.env.local` / `.env.*.local` — 私有仓库可提交，但**严禁写入真实密钥**
- `secrets.yaml` / `secrets.json` / `credentials.*` — **一律不提交**（gitignore 屏蔽）
- 飞书 `app_id` / `app_secret` 等走 `.env`，调飞书 API 时不回显

### 6.3 gitignore 强制项

```
data/             SQLite（含敏感数据）
outputs/          生成结果
.run/             PID + 日志
.venv/ venv/      虚拟环境
.env .env.local   环境变量
*.db *.zip *.log  运行时数据与产物
```

---

## 7. 测试要求

| 类型 | 要求 |
|------|------|
| 单元测试 | `tests/test_*.py`，覆盖核心逻辑（占位符、CRUD、PDF 处理） |
| 端到端 | 关键路径至少 1 个 e2e（浏览器内 PDF 预览、生成流程） |
| 覆盖率 | 核心模块 ≥ 60%，关键路径 ≥ 80% |
| 跨平台 | bash 脚本兼容 macOS bash 3.2（不用数组 += 语法） |

测试命令：

```bash
cd modules/<module-name> && pytest tests/ -v
```

---

## 8. 文档要求

### 8.1 每个模块的"三件套"（强制）

```
modules/<name>/docs/
├── README.md          模块说明（用户视角）
├── REQUIREMENTS.md    需求基线（MoSCoW + 用户故事 + AC）
├── SPEC.md            技术规格（架构 + 决策 + Checklist）
└── PROMPTS.md         AI 提示词反推（可复用 + 培训新人）
```

### 8.2 系统级文档

- `docs/SPEC.md` — 架构、模块、接口、版本
- `docs/requirements/backlog.md` — 需求池
- `docs/requirements/CHANGELOG.md` — 变更日志

### 8.3 文档同步

- **任何代码变更** → 对应 `SPEC.md` 必须同步
- **任何需求新增** → `backlog.md` 必须先有条目
- **任何版本变更** → `CHANGELOG.md` + 模块 `module.yaml` 必须更新

---

## 9. 提交规范

### 9.1 commit message 格式

```
[类型] 模块名: 一句话描述

详细说明（可选）
```

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档变更 |
| `refactor` | 重构 |
| `test` | 测试变更 |
| `chore` | 工程配置 / 脚本 |

**示例**：

```
[feat] court-doc-generator: 增加导出功能按钮（单案件 ZIP 下载）

- 结果卡片新增"导出"按钮
- 默认导出当前生成结果的 ZIP
- 待澄清批量/整库/飞书云盘场景
```

### 9.2 提交前自检清单

- [ ] 代码运行 `pytest` 通过
- [ ] 无 PII 硬编码
- [ ] 无密钥泄露
- [ ] `backlog.md` 状态已更新
- [ ] `CHANGELOG.md` 已记录（如有版本变更）

---

## 10. AI 代理特定指令

### 10.1 必须做的事

| 场景 | 动作 |
|------|------|
| 接到新需求 | **必查 4 处避免重复**：① `backlog.md` 是否已登记同主题需求？② `modules/index.yaml` 现有 3 个模块（court-doc-generator / litigation-system / case-intelligence）的职责范围？③ 目标模块的 `SPEC.md` / `docs/` 是否已有该功能？④ `shared/` 跨模块工具是否已实现？**确认无重复后才登记新条目**（避免重复造轮子） |
| 修改模块代码 | **先读该模块 `SPEC.md`**，遵守模块内部规范 |
| 涉及跨模块 | **先查 `docs/SPEC.md §4`**（模块间接口约定） |
| 涉及安全 | **必查 §6 数据安全红线**，PII / 密钥 / gitignore |
| 测试相关 | **必查 §7 测试要求**，覆盖率与跨平台兼容 |
| 提交前 | **执行 §9.2 自检清单** |

### 10.2 严禁做的事

| 禁止 | 原因 |
|------|------|
| ❌ 跳过 `backlog.md` 直接改代码 | 需求不可追溯 |
| ❌ 硬编码中文文件名 / 函数名 | 违反 §5 命名规范 |
| ❌ 把真实 PII / 密钥写入文件 | 违反 §6 安全红线 |
| ❌ 修改 `modules/index.yaml` 之外的模块根路径 | 破坏 §3 目录导航 |
| ❌ 直接 `git push --force` / `git reset --hard` | 高危操作需用户确认 |
| 🔴 **未经用户明确允许，不得执行任何 `git push` 操作** | **Push 红线**：本地 commit 与远程推送是两回事；本地 commit 后必须用户逐次明确授权才能 push |
| ❌ 删除 `data/` / `outputs/` / `.run/` 之外的内容 | 可能误删源码 |
| ❌ 在其他工作空间（如 `/Users/zhangyang/Desktop/Ai工作/`）操作 | 当前窗口仅限 legal 工程 |
| ❌ 接到新需求未做全系统重复性检查就登记 backlog | 违反 §10.1"接到新需求"4 步检查要求，会造成重复造轮子 / 同主题多个需求并存 |
| ❌ 模块不提供 `bin/` 4 件套（直接 `python app.py` 启动） | 违反 §10.4.1，无法稳定托管 PID/日志/健康检查 |
| ❌ 硬编码非注册表端口（魔法数字） | 端口冲突无法溯源，违反 §10.4.2 |
| ❌ 模块无 `/health` 健康检查端点 | 启动状态不可观测，违反 §10.4.4 |
| ❌ 跨模块 `from modules.<other>.xxx import ...` | 破坏 §4 跨模块接口约定，违反 §10.4.3 |

### 10.3 响应规范

- **简洁优先** — 用户偏好"不要太复"，高信息密度
- **执行导向** — 不啰嗦理论，直接给可执行步骤
- **可追溯** — 关键决策引用规范条目（如 §6.1 / §7）
- **确认优先** — 高危操作（删除 / 推送 / 强制重置）必须先问
- **🔴 Push 红线** — `git push` 必须用户逐次明确允许，AI 不得擅自推送（即使本地 commit 已成功，远程同步仍需用户授权）

---

## 10.4 模块基础设施规范（强制）

### 10.4.1 脚本管理 4 件套

每个模块必须在 `bin/` 下提供：

```
modules/<name>/bin/
├── start.py / start.sh / start.bat     # 后台启动，写 PID + 日志
├── stop.py  / stop.sh  / stop.bat      # 三重定位停止（PID / 端口 / 进程名）
├── restart.py / restart.sh / restart.bat
└── status.py / status.sh / status.bat  # 端口 + PID + 健康检查 + 日志尾部
```

| 要求 | 说明 |
|------|------|
| **核心逻辑统一在 `.py`** | 避免 bash 3.2 / PowerShell 差异，跨平台一致 |
| **壳层仅 1-2 行** | `.sh` 内 `exec python3 bin/<x>.py "$@"`，`.bat` 内 `python bin\<x>.py %*` |
| **PID 路径** | `modules/<name>/.run/<name>.pid` |
| **日志路径** | `modules/<name>/.run/<name>.log` |
| **三重定位停止** | PID 文件 → 端口（lsof/netstat）→ 进程名（pgrep/wmic） |
| **健康检查** | 启动后等待端口就绪 + GET `/_stcore/health`（Streamlit）或 `/health`（FastAPI） |

参考实现：`modules/court-doc-generator/bin/`（v1.1.4，已含完整跨平台逻辑）。

### 10.4.2 端口管理

#### 端口注册表：`shared/config/ports.yaml`

```yaml
# 模块端口注册表（启动时校验冲突）
allocations:
  court-doc-generator:
    app: 18501      # Streamlit（避开 8501 默认）
    fallback: 19000 # 默认端口被占用时备选
  litigation-system:
    api: 8000       # FastAPI
    web: 8080       # 前端（Nginx）
  case-intelligence:
    nocodb: 8090
    paperless: 8091
    gotenberg: 8092
    postgres_nocodb: 5432
    postgres_paperless: 5433
    redis: 6379
```

#### 端口分配规则

| 类型 | 推荐段 | 说明 |
|------|--------|------|
| Streamlit | 18500-18599 | 避开 8501（Streamlit 默认） |
| FastAPI | 8000-8099 | 8000 为首选 |
| 前端（Vite/Nginx） | 5173 / 8080 | 5173 = Vite dev；8080 = 生产 |
| 数据库容器 | 5432 / 8090+ | PostgreSQL / NocoDB / Paperless |
| OCR / 文件转换 | 8092-8099 | Gotenberg / Tika |

#### module.yaml 强制声明

```yaml
name: court-doc-generator
port:
  app: 18501
  fallback: 19000
```

#### 启动前端口检测

`start.py` 必须实现：
- 默认端口被占用 → 自动切 fallback
- fallback 也被占用 → 报错并提示手动释放（不要默默换端口，避免配置漂移）

### 10.4.3 路由架构

#### 后端 API（FastAPI / Flask）

| 规则 | 示例 |
|------|------|
| **版本前缀** | `/api/<module>/v<major>/<resource>` |
| **资源路径** | 复数名词 + kebab-case |
| **健康检查** | `GET /health`（无版本前缀） |
| **OpenAPI 文档** | `GET /docs`（FastAPI 自动生成） |

**示例**：

```
GET    /api/litigation/v1/cases
GET    /api/litigation/v1/cases/{case_id}
POST   /api/litigation/v1/cases/{case_id}/sync
GET    /api/case-intelligence/v1/checklists
```

#### 前端路由

- 单模块前端：`/` 为模块主页
- 多模块门户（远期）：`/<module>/...` 由统一门户代理

#### 跨模块调用

- **必须经 `shared/common/` 抽象层**（HTTP 客户端封装 + 数据模型）
- ❌ **禁止直接 `import` 另一个模块的内部代码**（破坏 §4 跨模块接口约定）

### 10.4.4 健康检查与日志

#### 健康检查端点

| 框架 | 端点 | 返回 |
|------|------|------|
| FastAPI | `GET /health` | `{"status": "ok", "version": "x.y.z"}` |
| Streamlit | `GET /_stcore/health` | `200 ok`（内置） |

启动后 8 秒内必须可被 `status.py` 探测通过。

#### 日志格式

```
[YYYY-MM-DD HH:MM:SS] [LEVEL] [module_name] message
```

- 日志路径：`modules/<name>/.run/<name>.log`
- `.run/` 已纳入根目录 `.gitignore`

#### status.py 输出规范

```bash
$ cd modules/<name> && python bin/status.py
📊 <模块名> · 服务状态
==================================================
🔌 端口 18501: ✅ 已监听
📄 PID 文件: 12345
💚 健康检查 (http://localhost:18501/_stcore/health): ✅ 通过
📋 日志文件: .run/<name>.log（42.3 KB）

� 服务正常运行
   访问 http://localhost:18501
```

退出码：`0` = 运行中 / `1` = 未运行 / `2` = 异常。

---

## 11. 关联文档速查

| 文档 | 何时读 |
|------|--------|
| `README.md` | 首次进入工程 |
| `docs/SPEC.md` | 架构 / 模块 / 接口 / 安全 / 版本问题 |
| `docs/requirements/backlog.md` | 需求查询 / 新增 |
| `docs/requirements/CHANGELOG.md` | 版本历史 |
| `modules/index.yaml` | 模块注册表 |
| `modules/<name>/module.yaml` | 模块元数据 |
| `modules/<name>/SPEC.md` | 模块内部规格 |
| `modules/<name>/README.md` | 模块使用说明 |
| `.qoder/agents.md` | Qoder 特定配置 |
| `.gitignore` | 屏蔽规则 |
| [`shared/config/ports.yaml`](file:///Users/zhangyang/Desktop/code/legal/shared/config/ports.yaml) | 模块端口注册表（§10.4.2） |

---

## 11.1 端口注册表（联动）

所有模块端口分配统一登记在 [`shared/config/ports.yaml`](file:///Users/zhangyang/Desktop/code/legal/shared/config/ports.yaml)。

| 何时读 | 场景 |
|--------|------|
| 新增模块 | 先在 `ports.yaml` 申请端口 → 再写 `module.yaml` |
| 端口冲突 | 先查 `ports.yaml` 定位占用方 → 再调整 |
| 模块登记 | `modules/index.yaml` 不必重复登记端口（仅 `module.yaml` 即可） |

---

## 12. 紧急联络

如发现本文件与其他规范冲突，**以最高优先级为准**：

1. `docs/SPEC.md`（系统规格）
2. 本文件（工程行动约束）
3. `.qoder/agents.md`（Qoder 专用）
4. 模块自身 `SPEC.md`

**冲突时**：停下修改，告知用户冲突点，由用户裁决。