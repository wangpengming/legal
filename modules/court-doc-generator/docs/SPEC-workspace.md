# 出庭手续生成器 · 工作空间（Workspace）技术规格

> **文档版本**：v1.0
> **最后更新**：2026-08-20
> **模块名**：court-doc-generator
> **对应需求**：backlog 2026-08-20（F-042 ~ F-048）
> **目标版本**：v1.3.0

---

## 0. 文档目的

本 SPEC 定义 court-doc-generator 的"用户注册/登录 + 工作空间（Workspace）数据隔离"功能的**可实施技术方案**。

---

## 1. 设计目标

### 1.1 一句话定义

> **在保持 Streamlit 技术栈不变的前提下，让同一台电脑上多个人各有独立的数据空间（DB 文件 + 输出目录 + 代理人文件），通过用户名+密码切换。**

### 1.2 核心原则

| 原则 | 说明 |
|------|------|
| 物理隔离 | 每个 workspace 独立的 `court_matters.db`，SQL 层零改动 |
| 零新依赖 | 密码哈希用 `hashlib.pbkdf2_hmac`（Python 标准库） |
| 不换框架 | 保持 Streamlit，仅加登录/注册页路由 |
| 向下兼容 | 旧数据自动迁移，现有测试全部通过 |

### 1.3 不做什么

- ❌ 不做真正的 Web session（cookie/token 持久化）
- ❌ 不做密码重置/找回（v1.3.0 范围内）
- ❌ 不做 workspace 删除 UI（手动删目录即可）
- ❌ 不做 RBAC/权限分级
- ❌ 不换 FastAPI/Flask 等后端框架

---

## 2. 架构设计

### 2.1 数据隔离模型

```
data/
├── workspaces.db                    ← 共享：workspace 元数据（id, name, password_hash）
└── workspaces/                      ← 每个 workspace 一个子目录
    ├── <workspace_id_1>/            ← 小李的 workspace
    │   ├── court_matters.db         ← 独立的业务数据库
    │   ├── outputs/                 ← 独立的输出目录
    │   └── agents/                  ← 独立的代理人 PDF 上传
    └── <workspace_id_2>/            ← 小王的 workspace
        ├── court_matters.db
        ├── outputs/
        └── agents/
```

### 2.2 登录流程

```
app.py main()
    │
    ├─ session_state.workspace_id 存在？
    │   ├─ YES → 加载该 workspace 的 DB → render_main()
    │   └─ NO  → render_auth_page()
    │
    render_auth_page()
    │
    ├─ Tab: [🔑 登录] [📝 注册]
    │
    ├─ 登录 Tab：
    │   - 选择 workspace 名称（下拉）
    │   - 输入密码
    │   - 点击"登录" → verify_workspace() → 通过则 session_state.workspace_id = xxx → rerun
    │
    └─ 注册 Tab：
        - 输入用户名
        - 输入密码 + 确认密码
        - 点击"注册" → create_workspace() → 自动登录 → rerun
```

### 2.3 模块边界

```
workspace.py          ← 🆕 新增：workspace 元数据 CRUD + 密码哈希
config.py             ← 改造：路径函数化（get_db_path / get_outputs_dir / get_agent_dir）
database.py           ← 改造：init_db(db_path) 接受参数
generator.py          ← 改造：save_agent_pdf 路径加 workspace 前缀
app.py                ← 改造：加 auth 页 + 路由切换
```

### 2.4 状态机

```
                    ┌──────────┐
         首次启动    │  未登录   │  关闭浏览器/F5
       ───────────→ │ (auth页)  │ ←──────────────
                    └─────┬────┘
                          │ 登录/注册成功
                          ▼
                    ┌──────────┐
                    │  已登录   │
                    │ (主界面)  │
                    └─────┬────┘
                          │ 点击"退出登录"
                          ▼
                    ┌──────────┐
                    │  未登录   │
                    └──────────┘
```

---

## 3. 数据模型

### 3.1 workspaces 元数据表（workspace.py）

```sql
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,              -- UUID4 短哈希（8 位），作为目录名
    name TEXT NOT NULL UNIQUE,        -- 用户可见的 workspace 名称
    password_hash TEXT NOT NULL,      -- pbkdf2_hmac('sha256') 结果：salt$hash
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**为什么用 UUID 短哈希而不是自增 ID？**
- 自增 ID 在删除 workspace 后会有空洞，不利于目录管理
- UUID 短哈希保证唯一性，且目录名可读（8 位十六进制）

### 3.2 密码哈希格式

```
存储格式：{salt_hex}${hash_hex}
示例：    a1b2c3d4...（64字符）$e5f6a7b8...（64字符）

算法：    pbkdf2_hmac('sha256', password, salt, 600_000 iterations)
```

---

## 4. 文件改动清单

### 4.1 workspace.py（🆕 新增，~100 行）

```
函数：
- hash_password(password: str) -> str
- verify_password(password: str, password_hash: str) -> bool
- init_workspace_db() -> None
- create_workspace(name: str, password: str) -> str  # 返回 workspace_id
- verify_workspace(name: str, password: str) -> str | None  # 返回 workspace_id 或 None
- list_workspaces() -> list[dict]
- migrate_legacy_data() -> str | None  # 迁移旧 data/court_matters.db → 默认 workspace
```

### 4.2 config.py（改造，~30 行）

```python
# 旧（模块级常量）
DB_PATH = DATA_DIR / "court_matters.db"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# 新（函数，接受 workspace_id）
def get_workspace_dir(workspace_id: str) -> Path:
    return DATA_DIR / "workspaces" / workspace_id

def get_db_path(workspace_id: str) -> Path:
    d = get_workspace_dir(workspace_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / "court_matters.db"

def get_outputs_dir(workspace_id: str) -> Path:
    d = get_workspace_dir(workspace_id) / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_agent_dir(workspace_id: str, agent_id: int) -> Path:
    d = get_workspace_dir(workspace_id) / "agents" / str(agent_id)
    d.mkdir(parents=True, exist_ok=True)
    return d

# 向后兼容：保留旧常量供非 workspace 场景（如测试）使用
DB_PATH = DATA_DIR / "court_matters.db"       # 保留，测试用
OUTPUTS_DIR = PROJECT_ROOT / "outputs"         # 保留，测试用
```

### 4.3 database.py（改造，~5 行）

```python
# init_db() 改为接受可选 db_path 参数
def init_db(db_path=None):
    if db_path is None:
        db_path = DB_PATH  # 向后兼容
    with get_conn_for_path(db_path) as conn:
        ...

# 新增：按路径获取连接
@contextmanager
def get_conn_for_path(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    ...
```

### 4.4 app.py（改造，~150 行）

```python
def render_auth_page():
    """登录/注册页"""
    tab_login, tab_register = st.tabs(["🔑 登录", "📝 注册"])
    
    with tab_login:
        # 下拉选择 workspace + 密码输入 + 登录按钮
    
    with tab_register:
        # 用户名 + 密码 + 确认密码 + 注册按钮

def render_logout_button():
    """主界面右上角退出按钮"""
    if st.sidebar.button("🚪 退出登录"):
        st.session_state.workspace_id = None
        st.session_state.workspace_name = None
        st.rerun()

def main():
    ws.init_workspace_db()
    ws.migrate_legacy_data()  # 幂等，仅首次执行
    
    if "workspace_id" not in st.session_state:
        st.session_state.workspace_id = None
    
    if st.session_state.workspace_id is None:
        render_auth_page()
    else:
        # 加载 workspace 的 DB
        db_path = config.get_db_path(st.session_state.workspace_id)
        db.init_db(db_path)
        render_logout_button()
        current_company, current_agent = render_sidebar()
        render_main(current_company, current_agent)
```

### 4.5 generator.py（改造，~10 行）

```python
# save_agent_pdf 改为接受 workspace_id
def save_agent_pdf(workspace_id: str, agent_id: int, file_bytes: bytes, file_type: str) -> str:
    agent_dir = config.get_agent_dir(workspace_id, agent_id)
    ...
```

---

## 5. 现有数据迁移

### 5.1 迁移逻辑（workspace.py: migrate_legacy_data）

```python
def migrate_legacy_data() -> str | None:
    """
    检测 data/court_matters.db 是否存在。
    存在 → 创建"默认"workspace → 移动 DB + outputs/ + static/agents/ → 返回 workspace_id
    不存在 → 返回 None（幂等）
    """
    legacy_db = DATA_DIR / "court_matters.db"
    if not legacy_db.exists():
        return None
    
    # 创建默认 workspace
    ws_id = create_workspace("默认", "admin")  # 默认密码 admin
    
    # 移动 DB
    shutil.move(str(legacy_db), str(get_db_path(ws_id)))
    
    # 移动 outputs/
    legacy_outputs = PROJECT_ROOT / "outputs"
    if legacy_outputs.exists():
        shutil.move(str(legacy_outputs), str(get_outputs_dir(ws_id)))
    
    # 移动 static/agents/
    legacy_agents = STATIC_DIR / "agents"
    if legacy_agents.exists():
        shutil.move(str(legacy_agents), str(get_agent_dir(ws_id).parent))
    
    return ws_id
```

### 5.2 迁移后的用户提示

```
登录页顶部显示：
ℹ️ 检测到旧版本数据，已自动迁移到 workspace「默认」（密码：admin）。请立即登录并修改密码。
```

---

## 6. 测试策略

### 6.1 test_workspace.py（🆕 新增，~60 行）

```python
def test_hash_password():
    h = hash_password("test123")
    assert "$" in h
    assert verify_password("test123", h)
    assert not verify_password("wrong", h)

def test_create_and_verify():
    ws_id = create_workspace("测试用户", "pass123")
    assert ws_id is not None
    assert verify_workspace("测试用户", "pass123") == ws_id
    assert verify_workspace("测试用户", "wrong") is None

def test_duplicate_name():
    create_workspace("重复名", "p1")
    with pytest.raises(ValueError):
        create_workspace("重复名", "p2")

def test_list_workspaces():
    # 清理后创建 2 个
    ws_list = list_workspaces()
    assert len(ws_list) >= 2

def test_migrate_legacy_idempotent():
    # 第二次调用应该返回 None（幂等）
    assert migrate_legacy_data() is None
```

### 6.2 现有测试兼容性

- `test_database.py`：`init_db()` 无参数调用仍走 `DB_PATH`，向后兼容 ✅
- `test_generator.py`：`OUTPUTS_DIR` 常量保留，测试不受影响 ✅
- `conftest.py`：temp dir 中创建测试 DB，不依赖 workspace ✅

---

## 7. 验收检查清单

- [ ] 首次启动 → 显示登录/注册页（无 workspace 时引导注册）
- [ ] 注册 → 输入用户名+密码 → 自动登录 → 进入主界面
- [ ] 登录 → 选择已有 workspace → 输入密码 → 进入主界面
- [ ] 密码错误 → 显示错误提示 → 不进入主界面
- [ ] 登录后 → 创建公司/代理人/案件 → 数据持久化
- [ ] 退出登录 → 回到登录页 → 换另一个 workspace 登录 → 看不到前一个的数据
- [ ] 关闭浏览器 → 重新打开 → 回到登录页（session 不持久化）
- [ ] 旧版 `data/court_matters.db` 存在 → 自动迁移到"默认"workspace → 提示修改密码
- [ ] 旧版 `outputs/` 存在 → 自动迁移到 workspace 子目录
- [ ] 重复注册同名 workspace → 报错"用户名已存在"
- [ ] 所有现有 pytest 测试通过
- [ ] 新 `test_workspace.py` 全部通过

---

## 8. 变更日志

| 日期 | 版本 | 变更摘要 |
|------|------|---------|
| 2026-08-20 | v1.0 | 首次编写，定义 workspace 隔离方案完整技术规格 |