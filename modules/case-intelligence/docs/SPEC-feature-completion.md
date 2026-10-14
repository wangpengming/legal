---
type: spec
module: case-intelligence
version: 3.4.0
updated: 2026-10-13
status: active
---

# case-intelligence 功能补齐 SPEC v3.4.0

> **目标版本**: 3.4.0 | **前置**: v3.3.0（Streamlit Web UI + CLI 主干闭环）
> **范围**: 补齐「CLI 已实现 / UI 缺失」「需求已声明 / 未实现」「已知缺陷」「文档-实现漂移」四类缺口
> **排除**: 🔴 **飞书 Bot 全部工作**（`src/lark_bot.py` 代码就绪、通道暂停；backlog `fb01`–`fb08`）——本轮不动，用户另行确认。

---

## 1. 背景

v3.3.0 已交付「主干闭环」：登录 → 案件列表 → 扫描录入 → AI 提取 → 文书生成 → 统计看板，
以及 CLI 16 子命令（register/extract/promote/complete/list/search/check/health/report/
export/templates/import/artifacts/scan/link）。经 v3.3.0 功能盘点（2026-10-13）确认：

- **主干闭环齐全**（6 页 UI + CLI 双通道）；
- **功能面不全**：CLI 有 12 类能力 UI 未暴露；需求文档声明 4 项未实现；存在 9 处缺陷；
- 模块 `module.yaml` 声称的「案件匹配」「4 类固定模板生成」在 UI 与 CLI 均未落地。

本 SPEC 定义补齐范围、设计、优先级与验收，作为 v3.4.0 实现基线。

---

## 2. 现状矩阵（2026-10-13 实测）

### 2.1 前端能力（Streamlit 6 页）

| 页 | 文件 | 已实现 | 缺失 |
|----|------|--------|------|
| 登录 | `pages/1_登录.py` | 用户名/密码、session_state | 账号环境变量化 |
| 案件列表 | `pages/2_案件列表.py` | 搜索/状态筛选/排序/分页/健康度/详情入口 | 分页 bug、健康度口径、新建入口 |
| 案件详情 | `pages/2_案件详情.py` | 基本信息 + D1–D5 提取物展示 | **编辑/删除/导出/手动提取/关联/完成** |
| 扫描录入 | `pages/3_扫描录入.py` | 路径→扫描→解析→提取→导入 | **查重、引擎切换、选择文件夹** |
| 文书生成 | `pages/4_文书生成.py` | 4 类型→`generate_direct`→MD/DOCX | **模板化三级降级、引擎切换、临时文件泄漏** |
| 统计看板 | `pages/5_统计看板.py` | 3 卡片 + 案由分布 + 待提取列表 | **最近操作记录、扫描历史** |

### 2.2 CLI 子命令（16 个，`bin/extract.py`）

`register / link / extract / promote / complete / list / search / check / health / report /
export / templates(list|search|show) / import / scan / artifacts`

---

## 3. 缺口清单（四类）

### A 类：CLI 已实现 / UI 未暴露（12 项）

| # | 能力 | CLI | UI 现状 | 处置 |
|---|------|-----|---------|------|
| A1 | 手动注册案件 | `register` | 无 | 列表页「➕ 新建案件」表单 |
| A2 | 关联原始材料路径 | `link` | 无 | 详情页「🔗 关联材料」 |
| A3 | 手动提取 Artifact | `extract` | 无 | 详情页「✍️ 手动提取」 |
| A4 | 归纳为模板 | `promote` | 无 | 详情页/模板页「📦 归档为模板」 |
| A5 | 标记为已提取 | `complete` | 无 | 详情页/列表「✅ 标记完成」 |
| A6 | 案件查重 | `check` | 无 | 扫描录入接入查重 |
| A7 | 健康度 | `health` | inline 5 字段（与 `ui/utils.get_case_health` 6 字段重复） | 统一到 `utils.get_case_health` |
| A8 | 导出提取物 | `export` | 无 | 详情页「📤 导出 DOCX/MD」 |
| A9 | 模板 list/search/show | `templates` | 无 | 新增「模板管理」页 |
| A10 | JSON 增量导入 | `import` | 无 | 模板管理页「📥 导入 JSON」 |
| A11 | 案件编辑 / 删除 | ❌（DB 亦无） | 无 | **新增 `db.update_case` / `db.delete_case`** + 详情页 |
| A12 | 相似案件匹配 | ❌（`module.yaml` 声称有） | 无 | **新增**匹配函数 + CLI `match` + 匹配页 |

### B 类：需求已声明 / 未实现（4 项）

| # | 需求 | 声明处 | 现状 | 处置 |
|---|------|--------|------|------|
| B1 | 相似案件匹配 | `REQUIREMENTS.md` US-03 | 无 | 同 A12 |
| B2 | AI 引擎可切换 | `REQUIREMENTS.md` US-02 | UI 硬编码 `engine_type="minimax"` | 扫描录入/文书生成加引擎下拉（手动提取为人工填写，无引擎） |
| B3 | 模板管理增删改 | `REQUIREMENTS.md` US-04 | 仅 CLI 只读三命令 | 模板页新增/编辑/删除 |
| B4 | 模板化文书生成 | `module.yaml`「4 类固定模板」 | 生成页仅 `generate_direct` | 接 `DocumentGenerator`（模板→模板+LLM→LLM→fallback） |

### C 类：缺陷（9 项）

| # | 缺陷 | 位置 | 影响 |
|---|------|------|------|
| C1 | 分页失效 | `2_案件列表.py:97` `number_input(value=1)` 无 `key="page"`；prev/next 写 `st.session_state.page` | 翻页回弹/无效 |
| C2 | 健康度口径双份 | 列表页 inline 5 字段 vs `ui/utils.get_case_health` 6 字段（含提取物） | 排序/展示不一致，utils 函数死代码 |
| C3 | 扫描录入无查重 | `3_扫描录入.py` / `ui/utils.scan_and_import` | 重复入库风险 |
| C4 | 「选择文件夹」永久禁用 | `3_扫描录入.py:43` `disabled=True` | 死按钮误导用户 |
| C5 | DOCX 临时文件泄漏 | `4_文书生成.py:107` `delete=False` 无清理 | `/tmp` 累积 |
| C6 | UI 账号硬编码 | `config.py` `USERS={admin/admin123,...}` | 违反 §6.2；backlog `ci04` |
| C7 | `PROJECT_ROOT` 派生错误 | `config.py` `dirname×2` = `modules/`（少一层），当前未被使用 | 潜在误用；backlog `ci05` |
| C8 | `source_ref` 截断 100 字符 | `2_案件详情.py:81` `source[:100]` | 长来源被截断 |
| C9 | 分页大小不一致 | `config.py PAGE_SIZE=20` vs 列表页 `PAGE_SIZE=15`（SPEC-UI 声明 20） | 配置漂移 |

### D 类：文档-实现不一致（2 项）

| # | 漂移 | 处置 |
|---|------|------|
| D1 | `SPEC-UI.md` 声明「扫描历史（最近5条）」「最近操作记录」「每页20条」；详情页未登记在页面清单 | 按 v3.4.0 实现更新 SPEC-UI |
| D2 | `REQUIREMENTS.md` §5.2/§5.3/§5.4/§5.5 复选框未勾选 | 随实现推进勾选/标注 |

---

## 4. 设计

### 4.1 数据层新增（`src/database.py`）

```python
def update_case(case_id: str, db_path=None, **fields) -> Optional[dict]:
    """按白名单更新案件字段（case_number/case_name/plaintiff/defendant/cause/
    court/result/scene/source_path/notes/quality/status）。"""

def delete_case(case_id: str, db_path=None) -> None:
    """删除案件及其全部 artifacts（级联）。"""
```

> `cases` 表当前无 `updated_at` 列；如需变更审计，走 `_ensure_columns` 幂等迁移（不破坏存量）。

### 4.2 匹配能力（`src/case_matcher.py` 新增）

```python
def match_cases(case_id: str, limit: int = 5, db_path=None) -> list[dict]:
    """基于 D1–D5 画像 + 案由/年份/场景 计算相似度，返回 Top-N 相似案件。"""
```

- 匹配信号：案由（等权）、年份邻近、`scene` 命中、D1–D5 artifact 类型覆盖重合度。
- 无向量检索（`REQUIREMENTS.md` §2.4 Won't Have），纯规则打分。
- 新增 CLI：`python bin/extract.py match --case-id <id> [--limit N]`。

### 4.3 UI 页面改动

| 页 | 改动 |
|----|------|
| `2_案件列表.py` | 修 C1 分页（`key="page"`）；A7 健康度统一；A1 新建案件表单；A5 标记完成 |
| `2_案件详情.py` | A11 编辑/删除；A2 关联路径；A3 手动提取；A4 归档为模板；A5 标记完成；A8 导出；C8 来源完整展示；A12 相似案件入口 |
| `3_扫描录入.py` | A6 查重；B2 引擎下拉；C4 选择文件夹（实现或移除） |
| `4_文书生成.py` | B4 接 `DocumentGenerator` 三级降级；B2 引擎下拉；C5 DOCX 临时文件清理 |
| `5_统计看板.py` | D1 最近操作记录 + 扫描历史 |
| **`6_模板管理.py`（新增）** | A9 list/search/show；B3 新增/编辑/删除；A4 归纳；A10 导入 JSON |
| **`7_案件匹配.py`（新增）** | A12/B1 相似案件匹配 |

### 4.4 基础设施

| 文件 | 改动 |
|------|------|
| `config.py` | C6 改读 `AUTH_USERS` 环境变量（默认仅本地，与 `deploy.yaml` `env_required` 对齐）；C7 修正/删除 `PROJECT_ROOT`；C9 `PAGE_SIZE` 统一 |
| `app.py` | 导航补齐 6/7 页入口 |
| `docs/SPEC-UI.md` | D1 按实现更新 |
| `docs/REQUIREMENTS.md` | D2 勾选推进 |

> 所有新页面与既有页保持一致的侧边栏导航（`st.page_link`）× 7.

---

## 5. 优先级与里程碑

| 里程碑 | 内容 | 类型 |
|--------|------|------|
| **M0 缺陷清零** | C1–C9 全部 | 修 |
| **M1 案件闭环** | A11（含 db 函数）、A1、A2、A3、A4、A5、A6、A8 | feat |
| **M2 模板与生成** | A9、A10、B3、B4、A7 | feat |
| **M3 匹配与增强** | A12、B1、B2、D1、D2、扫描历史/最近操作 | feat |
| **M4 文档与收口** | SPEC-UI/REQUIREMENTS 更新、CHANGELOG、backlog 状态 | docs |

> 全部四类缺口均纳入本轮；M0→M4 为推荐顺序，非排除关系（用户要求「实现所有内容」）。

---

## 6. 验收标准

### 6.1 缺陷（M0）

- [x] 案件列表翻页按钮可用，页码与 `session_state.page` 双向一致
- [x] 列表页与详情页健康度口径统一（`utils.get_case_health`，6 字段）
- [x] 扫描录入对已存在案件给出查重提示，可选择跳过/继续
- [x] 「选择文件夹」按钮可用或已移除（无死按钮）
- [x] 文书生成 DOCX 导出后临时文件被清理
- [x] `config.py` 无明文账号；`AUTH_USERS` 注入生效
- [x] `PROJECT_ROOT` 指向模块根（或已删除）
- [x] 详情页 `source_ref` 完整展示（或可展开）
- [x] `PAGE_SIZE` 单一真值

### 6.2 案件闭环（M1）

- [x] UI 可新建案件（`register` 等价），落库 `entry_method=UI`
- [x] UI 可编辑案件字段（`update_case`），保存后列表/详情同步
- [x] UI 可删除案件（`delete_case`），级联清除 artifacts，二次确认
- [x] UI 可关联原始材料路径（`link`）
- [x] UI 可手动提取 Artifact（`extract`）
- [x] UI 可将 Artifact 归纳为模板（`promote`），落 `output_templates/` + DB
- [x] UI 可标记案件为已提取（`complete`）
- [x] 详情页可导出提取物为 DOCX/MD

### 6.3 模板与生成（M2）

- [x] 模板管理页可 list/search/show
- [x] 模板管理页可新增/编辑/删除模板
- [x] 模板管理页可导入 JSON 案件
- [x] 文书生成走 `DocumentGenerator`：有模板走模板/模板+LLM，无模板走 LLM，均无则 fallback 提示

### 6.4 匹配与增强（M3）

- [x] 匹配页/CLI `match` 返回 Top-N 相似案件（按案由/年份/场景/D1–D5 覆盖）
- [x] 扫描录入（AI 提取）与文书生成可切换 AI 引擎（minimax/ollama/openai/mock/basic）；手动提取为人工填写（无引擎）

### 6.5 兼容与红线

- [x] 不引入破坏性 schema 变更（`_ensure_columns` 幂等）
- [x] 无明文密钥 / 无真实 PII 入库（§6.1/§6.2）
- [x] 现有 CLI 16 命令行为不回退
- [x] 🔴 飞书相关代码/配置**零改动**

---

## 7. 风险与约束

| 项 | 说明 |
|----|------|
| 本机无 Streamlit/venv | UI 无法本地启动；验证以 `py_compile` + 隔离 harness + 逻辑单测为准（§7.5 数据隔离） |
| 模板双源 | DB `templates` 表（注册） + `output_templates/<category>/*.md`（内容），管理页需保持两者一致 |
| `delete_case` 破坏性 | 必须二次确认 + 级联，参照 §6「删除类操作需谨慎」 |
| 匹配无向量 | 纯规则打分，非语义检索（§2.4 Won't Have） |
| 飞书冻结 | `src/lark_bot.py`、`fb01`–`fb08`、回调/凭证一律不动 |

---

## 8. 版本与关联

- 版本：3.3.0 → **3.4.0**（功能补齐）
- 关联 backlog：`docs/requirements/backlog.md`（case-intelligence 功能补齐条目）
- 关联 CHANGELOG：`docs/requirements/CHANGELOG.md`
- 关联文档：`SPEC-UI.md`（D1 更新）、`REQUIREMENTS.md`（D2 勾选）、`module.yaml`（version/features）