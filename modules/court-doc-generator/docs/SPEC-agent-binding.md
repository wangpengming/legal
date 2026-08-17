# 出庭手续生成器 · 多代理人材料动态绑定 专项 SPEC

> **配套索引**：
> - 系统规格：`docs/SPEC.md`
> - 模块规格：`modules/court-doc-generator/docs/SPEC.md`
> - 需求池：`docs/requirements/backlog.md`（搜"多代理人材料动态绑定"）
> - 本文件：明天实现对照文档

---

## 0. 文档目的与读者

### 0.1 目的

定义"切换代理人后整套出庭材料正确反映新代理人"的完整实施方案，作为：

- 明天实施的逐步 Checklist
- 技术决策的论证档案
- 单测 / 端到端测试的覆盖依据

### 0.2 目标读者

| 读者 | 关注点 |
|------|--------|
| 主开发（明天） | 实施 Checklist §12 |
| Code Reviewer | 决策矩阵 §3 + 风险 §11 |
| 测试 | 测试策略 §9 + 验收标准 §10 |

---

## 1. 背景与目标

### 1.1 业务背景

公司法务可能存在多个代理人（内部法务 + 外聘律师）。不同代理人持各自的劳动合同与身份证，出庭时必须使用对应的材料。

### 1.2 现状问题（代码层）

| 项 | 现状 | 引用 |
|----|------|------|
| `06_代理人劳动合同.pdf` | `config.py:STATIC_FILES` 写死单一文件 | `config.py:30-35` |
| `07_代理人身份证.pdf` | 同上写死 | `config.py:30-35` |
| `04_授权委托书` 被授权人 | `values_for_power_of_attorney` 完全未用 `agent` 字段 | `generator.py:151-166` |
| `agents` 表结构 | 无材料路径字段 | `database.py:27-40` |
| UI 上传入口 | 侧边栏代理人表单无上传控件 | `app.py:288-311` |

### 1.3 目标

切换代理人后，`06/07` 文件内容与新代理人对齐，`04_授权委托书` 中被授权人姓名/身份证号正确更新。

---

## 2. 现状与差距

### 2.1 数据库层（database.py）

```sql
-- 当前 agents 表
CREATE TABLE agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT,
    id_card TEXT,
    position TEXT,
    phone TEXT,
    company_id INTEGER,
    is_default INTEGER DEFAULT 0,
    ...
    UNIQUE (name, company_id)
);
```

**缺口**：无 `contract_pdf_path`、`id_card_pdf_path` 字段。

### 2.2 配置层（config.py）

```python
# 当前 STATIC_FILES（写死）
STATIC_FILES = [
    "1.营业执照复印件.pdf",
    "法人身份证.pdf",
    "代理人劳动合同.pdf",   # ← 问题：所有代理人共用
    "代理人身份证.pdf",     # ← 问题：所有代理人共用
]
```

**缺口**：未区分"公司级静态"与"代理人级静态"。

### 2.3 核心逻辑（generator.py）

```python
# 当前 _generate_to_dir 内联写死
static_files = [
    ("01_营业执照.pdf", STATIC_DIR / "1.营业执照复印件.pdf"),
    ("03_法人身份证.pdf", STATIC_DIR / "法人身份证.pdf"),
    ("06_代理人劳动合同.pdf", STATIC_DIR / "代理人劳动合同.pdf"),  # ← 写死
    ("07_代理人身份证.pdf", STATIC_DIR / "代理人身份证.pdf"),     # ← 写死
]
```

```python
# 当前 values_for_power_of_attorney 完全未用 agent
def values_for_power_of_attorney(case, company, agent):
    ...
    return [
        description,        # 1. 【】纠纷
        case_number,        # 2. （案号：【】）
        parts["年"], parts["月"], parts["日"],  # 3-5. 日期
    ]
    # ← agent 完全没出现
```

**缺口**：未按 agent 取材料路径；被授权人字段未填充。

### 2.4 UI 层（app.py）

```python
# 当前 render_sidebar 代理人表单
with st.form("add_agent"):
    a_name = st.text_input("代理人姓名*", ...)
    a_gender = st.selectbox("性别", ...)
    a_idcard = st.text_input("身份证号", ...)
    a_position = st.text_input("职务", ...)
    a_phone = st.text_input("电话", ...)
    submitted_a = st.form_submit_button("保存")
    # ← 无 file_uploader
```

**缺口**：无上传入口。

### 2.5 模板层（templates/4.授权委托书.docx）

**缺口**：未审模板【】分布（需打开 docx 确认是否已有被授权人字段），建议先备份再调整。

---

## 3. 关键决策

### 3.1 PDF 存储位置（D-001）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **A.** `modules/court-doc-generator/static/agents/<agent_id>/` | 与现有 static/ 一致；可 gitignore 屏蔽；分发友好 | 路径含模块目录，绝对路径 | ⭐⭐⭐⭐⭐ |
| B. 用户本地任意目录（绝对路径） | 灵活 | 路径失效无保护；UI 选目录麻烦 | ⭐⭐ |
| C. 用户工作目录 `agents_data/` | 与 data/ 风格一致 | 需新增跨模块目录 | ⭐⭐⭐ |

**结论**：选 **A**（模块内 `static/agents/<id>/`）。理由：
- 路径稳定（不依赖用户机器）
- 可 gitignore 屏蔽（含 PII）
- 分发包可整包复制
- 与现有 static/ 资源管理一致

### 3.2 数据库迁移策略（D-002）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **A.** 显式 `ALTER TABLE ... ADD COLUMN`（启动时执行） | 透明可控；幂等 | 需 try/except 捕获"重复列" | ⭐⭐⭐⭐⭐ |
| B. 删表重建 | 简单 | **丢数据，绝对禁止** | ❌ |
| C. 用 SQLAlchemy 等 ORM 自动迁移 | 高级 | 项目当前用裸 sqlite3，不引入新依赖 | ⭐⭐ |

**结论**：选 **A**。在 `init_db()` 中加：
```python
try:
    conn.execute("ALTER TABLE agents ADD COLUMN contract_pdf_path TEXT")
except sqlite3.OperationalError:
    pass  # 已存在
try:
    conn.execute("ALTER TABLE agents ADD COLUMN id_card_pdf_path TEXT")
except sqlite3.OperationalError:
    pass
```

### 3.3 模板被授权人字段（D-003）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **A.** 模板新增【】姓名 +【】身份证号 | 复用现有占位符机制；改动最小 | 称呼"先生/女士"需另算 | ⭐⭐⭐⭐⭐ |
| B. 替换整段（含称呼、性别） | 完整 | 实现复杂，需识别 Word 段落 | ⭐⭐ |
| C. 只填姓名 | 极简 | 身份证号缺失不合规 | ❌ |

**结论**：选 **A**。姓名 + 身份证号 2 个【】占位符，称呼按性别自动加"先生"/"女士"（在 values 阶段处理）。

### 3.4 旧记录兼容策略（D-004）

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A.** 缺路径字段时跳过该份文件 + UI 提示补传 | 不崩，向前兼容 | UI 需提示 |
| B. 用默认文件 fallback | 简单 | 老 bug 复发（换人用同一份合同） |
| C. 强制要求上传才能生成 | 严格 | 旧数据无法生成 |

**结论**：选 **A**（缺路径则跳过 + UI 提示）。理由：
- 不破坏现有数据
- 用户体验渐进
- 提示文案明确

---

## 4. 数据模型变更

### 4.1 agents 表新增字段

```sql
ALTER TABLE agents ADD COLUMN contract_pdf_path TEXT;
ALTER TABLE agents ADD COLUMN id_card_pdf_path TEXT;
```

### 4.2 SCHEMA_SQL 同步更新（database.py）

```sql
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT,
    id_card TEXT,
    position TEXT,
    phone TEXT,
    company_id INTEGER,
    is_default INTEGER DEFAULT 0,
    contract_pdf_path TEXT,        -- 🆕
    id_card_pdf_path TEXT,         -- 🆕
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE (name, company_id)
);
```

> 注：旧数据库启动时会自动 ALTER TABLE 补齐两个字段。

### 4.3 upsert_agent 函数兼容

`upsert_agent()` 增加对两个新字段的读写。

---

## 5. 目录结构变更

```
modules/court-doc-generator/
├── static/
│   ├── 1.营业执照复印件.pdf
│   ├── 法人身份证.pdf
│   ├── 代理人劳动合同.pdf       ← 旧 fallback（保留）
│   ├── 代理人身份证.pdf         ← 旧 fallback（保留）
│   ├── pdfjs/
│   └── agents/                  🆕 代理人材料目录（gitignore 屏蔽）
│       ├── 1/
│       │   ├── contract_<uuid>.pdf
│       │   └── id_card_<uuid>.pdf
│       ├── 2/
│       │   └── ...
│       └── ...
```

`.gitignore` 增加（建议在工程根 .gitignore）：
```
modules/*/static/agents/
```

---

## 6. 实施方案（F-031 ~ F-035）

### F-031 数据库迁移

**改动文件**：`modules/court-doc-generator/database.py`

**步骤**：

1. `SCHEMA_SQL` 中 `CREATE TABLE agents` 增加 `contract_pdf_path TEXT` + `id_card_pdf_path TEXT`
2. 新增 `migrate_add_agent_pdf_paths(conn)` 函数：
   ```python
   def migrate_add_agent_pdf_paths(conn):
       """幂等迁移：给 agents 表新增两个 PDF 路径字段"""
       for col in ("contract_pdf_path", "id_card_pdf_path"):
           try:
               conn.execute(f"ALTER TABLE agents ADD COLUMN {col} TEXT")
           except sqlite3.OperationalError:
               pass  # 已存在
   ```
3. `init_db()` 调用 `migrate_add_agent_pdf_paths(conn)`（在 `executescript` 之后）
4. `upsert_agent()` / `set_default_agent()` / `list_agents()` 等涉及字段的函数同步更新
5. 单测：`test_database.py` 增加：
   - `test_migrate_add_agent_pdf_paths`（旧库能升级）
   - `test_upsert_agent_with_pdf_paths`（写入读取新字段）

**验证**：启动后 SQLite 中 agents 表有 2 个新字段，旧记录不报错。

---

### F-032 UI 上传入口

**改动文件**：`modules/court-doc-generator/app.py`

**步骤**：

1. 在 `render_sidebar()` 中"添加/编辑代理人"表单（`st.form("add_agent")`）内增加：
   ```python
   st.markdown("---")
   st.caption("📎 代理人材料（按需上传）")
   contract_file = st.file_uploader(
       "劳动合同 PDF", type="pdf",
       key=f"contract_upload_{current_agent['id'] if current_agent else 'new'}"
   )
   id_card_file = st.file_uploader(
       "身份证 PDF（复印件）", type="pdf",
       key=f"id_card_upload_{current_agent['id'] if current_agent else 'new'}"
   )
   ```
2. 表单提交逻辑中（`if submitted_a and a_name:` 内）：
   ```python
   # 路径准备
   agent_id = current_agent["id"] if current_agent else None
   if agent_id is None:
       # 新代理人：先 upsert 拿到 id
       agent_id = db.upsert_agent({...基础字段...})
   agent_dir = STATIC_DIR / "agents" / str(agent_id)
   agent_dir.mkdir(parents=True, exist_ok=True)
   
   # 保存上传文件
   if contract_file is not None:
       contract_path = agent_dir / f"contract_{uuid.uuid4().hex[:8]}.pdf"
       contract_path.write_bytes(contract_file.read())
       contract_pdf_path = str(contract_path.relative_to(PROJECT_ROOT))
   else:
       contract_pdf_path = current_agent.get("contract_pdf_path") if current_agent else None
   
   # 类似处理 id_card_file
   ```
3. 已上传文件显示：
   ```python
   if current_agent and current_agent.get("contract_pdf_path"):
       st.success(f"✅ 已绑定：{Path(current_agent['contract_pdf_path']).name}")
       if st.button("🗑 删除劳动合同 PDF", key="del_contract"):
           ...
   ```
4. 单测：手动验证（UI 测试难自动化）

**验证**：UI 能上传、保存、显示已绑定文件名。

---

### F-033 核心逻辑改造

**改动文件**：`modules/court-doc-generator/generator.py`、`modules/court-doc-generator/config.py`

**步骤**：

1. **`config.py`**：拆 `STATIC_FILES` 为两层：
   ```python
   COMPANY_STATIC = [
       ("01_营业执照.pdf", "1.营业执照复印件.pdf"),
       ("03_法人身份证.pdf", "法人身份证.pdf"),
   ]
   AGENT_STATIC_FALLBACK = {
       "06_代理人劳动合同.pdf": "代理人劳动合同.pdf",
       "07_代理人身份证.pdf": "代理人身份证.pdf",
   }
   ```
2. **`generator._generate_to_dir()`**：
   - 接收 `agent: dict` 参数（已接收）
   - 公司级静态照旧
   - 代理人级静态按 agent 路径取，fallback 到 AGENT_STATIC_FALLBACK：
     ```python
     def resolve_agent_pdf(agent, target_name, fallback_filename):
         path_key = "contract_pdf_path" if "劳动合同" in target_name else "id_card_pdf_path"
         custom = agent.get(path_key)
         if custom and Path(custom).exists():
             return Path(custom)
         fallback = STATIC_DIR / fallback_filename
         return fallback if fallback.exists() else None
     
     for target_name, fallback in AGENT_STATIC_FALLBACK.items():
         src = resolve_agent_pdf(agent, target_name, fallback)
         if src:
             shutil.copy2(src, output_dir / target_name)
     ```
3. 单测 `test_generator.py`：
   - `test_generate_with_custom_agent_pdf`（用临时 PDF 验证）
   - `test_generate_fallback_to_default`（agent 路径为空时用 fallback）

**验证**：切换 agent 后 06/07 PDF 内容不同。

---

### F-034 模板调整

**改动文件**：`modules/court-doc-generator/templates/4.授权委托书.docx`

**步骤**：

1. **先备份**：`cp templates/4.授权委托书.docx templates/4.授权委托书.docx.bak`
2. 打开模板（用 python-docx 或 LibreOffice），定位"被授权人"段落
3. 改为：
   ```
   我单位现委托【】（先生/女士，身份证号：【】）作为我方代理人
   ```
   或更简洁的：
   ```
   委托【】（身份证号：【】）为本案代理人
   ```
4. 占位符顺序：
   ```
   【】纠纷 + 【】（被授权人姓名） + 【】（身份证号） + （案号：【】）+ 【】年【】月【】日
   ```
5. 重新审视其他【】位置，确保不冲突
6. 测试模板加载：`generate_dynamic_docx("power_of_attorney", [...], tmp_path)`

**注意**：模板结构调整需谨慎，先备份再操作。

---

### F-035 values 函数补充

**改动文件**：`modules/court-doc-generator/generator.py`

**步骤**：

1. `values_for_power_of_attorney()` 改为接收 agent 字段：
   ```python
   def values_for_power_of_attorney(case: dict, company: dict, agent: dict) -> list:
       """授权委托书模板（7 个【】，按位置）：
         1. 【】纠纷  → 案由描述
         2. 【】（被授权人姓名）
         3. 【】（身份证号）
         4. （案号：【】）  → 案号
         5. 日期：【】年【】月【】日  → 年、月、日
       """
       description = build_case_description(case)
       agent_name = (agent.get("name") or "").strip()
       agent_id = (agent.get("id_card") or "").strip()
       case_number = case.get("case_number", "")
       parts = parse_hearing_date(case.get("hearing_date"))
       return [
           description,        # 1. 【】纠纷
           agent_name,        # 2. 【】（姓名）
           agent_id,          # 3. 【】（身份证号）
           case_number,        # 4. （案号：【】）
           parts["年"],        # 5. 日期：【】年
           parts["月"],        # 6. 【】月
           parts["日"],        # 7. 【】日
       ]
   ```
2. 单测 `test_generator.py`：
   - `test_values_for_power_of_attorney_includes_agent_fields`
   - `test_replace_placeholders_with_7_values`

**验证**：生成的 DOCX 中被授权人姓名/身份证号正确。

---

## 7. 模板占位符规范（4.授权委托书）

新模板占位符顺序：

| # | 占位符 | 填充内容 | 来源 |
|---|--------|---------|------|
| 1 | 【】纠纷 | 案由描述 | `build_case_description(case)` |
| 2 | 【】（姓名） | 代理人姓名 | `agent["name"]` |
| 3 | 【】（身份证号） | 代理人身份证 | `agent["id_card"]` |
| 4 | 【】（案号） | 案号 | `case["case_number"]` |
| 5 | 【】年 | 年 | `parse_hearing_date()["年"]` |
| 6 | 【】月 | 月 | `parse_hearing_date()["月"]` |
| 7 | 【】日 | 日 | `parse_hearing_date()["日"]` |

**称呼处理**：根据 `agent["gender"]` 自动加"先生"/"女士"：
- 模板中写：`委托【】（先生/女士，身份证号：【】）`
- 在 `values_for_power_of_attorney` 中按性别决定"先生"/"女士"字符串，插入到合适位置

> **简化方案**：模板只放【】姓名 +【】身份证号，称呼"先生/女士"由 UI 提示或单独段落处理（推荐先实现简化方案）。

---

## 8. UI 规范

### 8.1 代理人编辑表单（侧边栏）

```
➕ 添加/编辑代理人
─────────────────────────
代理人姓名*       [张三]
性别             [男 ▼]
身份证号         [__________] (18位)
职务             [法务经理]
电话             [13800138000]
─────────────────────────
📎 代理人材料（按需上传）
劳动合同 PDF     [📎 上传]  ✅ 已绑定：contract_a1b2c3d4.pdf [🗑 删除]
身份证 PDF       [📎 上传]  ⏳ 未上传（生成时将使用 fallback）
─────────────────────────
                  [保存]
```

### 8.2 主区域提示

切换代理人后，结果卡片显示：
```
当前代理人：张三（已绑定合同 + 身份证）
```

未绑定时：
```
⚠️ 当前代理人未上传劳动合同与身份证 PDF，将使用 fallback 文件。建议补传以确保材料准确。
```

---

## 9. 测试策略

| 测试类型 | 覆盖范围 | 文件 |
|---------|---------|------|
| 单元测试 | schema 迁移、upsert、generator 路径解析、values 函数 | `tests/test_database.py` / `tests/test_generator.py` |
| 端到端 | 上传文件 → 切换 agent → 重新生成 → 验证 06/07/04 | 手动 |
| 兼容性 | 旧记录（无路径字段）不报错 | 单测 + 手动 |
| PII | 上传 PDF 不入 git | 手动 + git status |
| 跨平台 | macOS / Windows 路径兼容 | 单测 |

**新增测试用例**（最少覆盖）：

```python
# test_database.py
def test_migrate_add_agent_pdf_paths(tmp_path):
    """旧库迁移能成功添加 2 个字段"""

def test_upsert_agent_with_pdf_paths(tmp_path):
    """能写入和读取 contract_pdf_path / id_card_pdf_path"""

# test_generator.py
def test_generate_with_custom_agent_contract(tmp_path):
    """agent 有 contract_pdf_path 时，使用该文件"""

def test_generate_fallback_to_default_contract(tmp_path):
    """agent 无 contract_pdf_path 时，使用 fallback 文件"""

def test_generate_skip_missing_agent_pdf(tmp_path):
    """agent 路径失效时，跳过该份文件，不崩"""

def test_values_for_power_of_attorney_includes_agent():
    """values 包含 agent 姓名 + 身份证号"""
```

---

## 10. 验收标准

- [ ] F-031 数据库迁移成功，旧库不报错
- [ ] F-032 UI 能上传并保存 PDF 到 `static/agents/<id>/`
- [ ] F-033 切换 agent 后 06/07 文件内容变化
- [ ] F-034 模板新增【】姓名 + 【】身份证号占位符
- [ ] F-035 生成的 DOCX 中被授权人姓名/身份证号正确
- [ ] 旧记录兼容：缺路径字段时跳过该份文件，UI 提示补传
- [ ] PII 安全：上传 PDF 不入 git（gitignore 生效）
- [ ] UI 与 Vercel/Linear 风格一致
- [ ] pytest 全部通过（含新增 5 个用例）
- [ ] CHANGELOG.md 记录 v1.2.0
- [ ] backlog 状态改 done

---

## 11. 风险与回滚

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 模板结构调整破坏现有 DOCX | 🟡 中 | 备份 `4.授权委托书.docx` 为 `.bak`；调整前在测试环境验证 |
| ALTER TABLE 失败导致启动崩 | 🟢 低 | try/except 捕获 `OperationalError`；幂等执行 |
| 上传路径失效（用户改目录） | 🟡 中 | 启动时校验路径存在性；缺失则 UI 提示 |
| PII 上传到 git | 🔴 高 | `.gitignore` 屏蔽 `modules/*/static/agents/`；上传文件用 UUID 命名 |
| 旧记录被破坏 | 🟢 低 | ALTER TABLE 仅新增字段，不删字段；旧数据保持完整 |

**回滚方案**（如需）：

```bash
# 1. 恢复模板
cp templates/4.授权委托书.docx.bak templates/4.授权委托书.docx

# 2. 恢复代码（git revert 或手动）

# 3. 数据库字段保留（新增字段不影响旧字段，可选 DROP COLUMN）
```

---

## 12. 实施 Checklist（明天对照）

### Phase 1：数据层（F-031）· 0.5h

- [ ] C-1.1 备份 `data/court_matters.db` → `data/court_matters.db.bak`
- [ ] C-1.2 修改 `database.py` SCHEMA_SQL 增加 2 个字段
- [ ] C-1.3 新增 `migrate_add_agent_pdf_paths(conn)` 并接入 `init_db()`
- [ ] C-1.4 更新 `upsert_agent()` / `list_agents()` / `get_default_agent()` 函数
- [ ] C-1.5 单测：test_migrate_add_agent_pdf_paths + test_upsert_agent_with_pdf_paths
- [ ] C-1.6 跑 pytest 确认旧库迁移不报错

### Phase 2：核心逻辑（F-033 + F-035）· 1.5h

- [ ] C-2.1 修改 `config.py`：拆 COMPANY_STATIC + AGENT_STATIC_FALLBACK
- [ ] C-2.2 修改 `generator._generate_to_dir()` 按 agent 路径取 PDF
- [ ] C-2.3 修改 `values_for_power_of_attorney()` 补充 agent 字段
- [ ] C-2.4 单测：test_generate_with_custom_agent_contract / test_generate_fallback / test_generate_skip_missing / test_values_for_power_of_attorney_includes_agent
- [ ] C-2.5 pytest 全部通过

### Phase 3：模板调整（F-034）· 0.5h

- [ ] C-3.1 备份 `templates/4.授权委托书.docx` → `.bak`
- [ ] C-3.2 调整模板"被授权人"段落，新增 2 个【】占位符
- [ ] C-3.3 测试 `generate_dynamic_docx("power_of_attorney", values_with_7, tmp_path)`
- [ ] C-3.4 验证生成的 DOCX 中姓名/身份证号填充正确

### Phase 4：UI（F-032）· 1h

- [ ] C-4.1 `render_sidebar()` 代理人表单增加 2 个 `st.file_uploader`
- [ ] C-4.2 表单提交逻辑：保存上传文件到 `static/agents/<id>/`，UUID 命名
- [ ] C-4.3 已绑定文件显示 + "删除"按钮
- [ ] C-4.4 主区域添加"未绑定提示"
- [ ] C-4.5 手动端到端验证：上传 → 切换 agent → 重新生成 → 检查 06/07/04

### Phase 5：回归与文档 · 0.5h

- [ ] C-5.1 pytest 全部通过
- [ ] C-5.2 手动端到端：旧案件（无路径）能正常生成（fallback 或跳过）
- [ ] C-5.3 `.gitignore` 增加 `modules/*/static/agents/`
- [ ] C-5.4 `CHANGELOG.md` 记录 v1.2.0
- [ ] C-5.5 `module.yaml` 版本号 v1.1.4 → v1.2.0
- [ ] C-5.6 `backlog.md` 状态改 done + 验收勾选

**总计估时**：4 小时

---

## 13. 关键文件清单

| 文件 | 改动类型 |
|------|---------|
| `modules/court-doc-generator/database.py` | 修改（schema + CRUD） |
| `modules/court-doc-generator/config.py` | 修改（拆静态文件） |
| `modules/court-doc-generator/generator.py` | 修改（路径解析 + values） |
| `modules/court-doc-generator/app.py` | 修改（UI 上传） |
| `modules/court-doc-generator/templates/4.授权委托书.docx` | 修改（占位符） |
| `modules/court-doc-generator/tests/test_database.py` | 新增（迁移测试） |
| `modules/court-doc-generator/tests/test_generator.py` | 新增（路径 + values 测试） |
| `.gitignore` | 修改（屏蔽 agents/） |
| `docs/requirements/backlog.md` | 修改（状态 → done） |
| `docs/requirements/CHANGELOG.md` | 新增（v1.2.0 记录） |
| `modules/court-doc-generator/module.yaml` | 修改（版本号） |

---

## 14. 待澄清问题（实施前最好确认）

1. **路径硬编码 vs 相对路径**：数据库存绝对路径还是相对 `PROJECT_ROOT` 的相对路径？
   - 推荐：相对路径（便于整包分发），代码侧用 `Path(p).resolve()` 转绝对

2. **历史案件处理**：已经生成的 outputs/ 下 06/07 是否需要重新生成？
   - 推荐：不主动重新生成；新案件用新逻辑；历史案件用户点"重新生成"按钮走新流程

3. **多人共用合同**：是否支持同公司多代理人共用一份合同 PDF？
   - 推荐：暂不支持，每 agent 独立绑定（简化模型）

4. **身份证 PDF 是否加水印**：上传时是否自动加"仅供出庭使用"水印？
   - 推荐：暂不处理，由用户在上传前自行加水印

5. **删除代理人时的级联**：删除 agent 时是否同时删除 `static/agents/<id>/` 下的文件？
   - 推荐：是，避免垃圾文件；但要先检查该 agent 是否关联历史案件