# 出庭手续生成器 v2.1 体验增强 · 技术规格（SPEC）

> **文档版本**：v2.1
> **最后更新**：2026-08-22
> **分支**：dev
> **开发模式**：TDD（RED-GREEN-REFACTOR，参考 `~/code/work/projects/oem_ai_agent/flow/08-TDD落地实施方案.md`）
> **对应需求**：`docs/requirements/backlog.md`（2026-08-22 登记的 7 项）

---

## 0. 总览

| # | 功能 | 优先级 | 主端 | 状态 |
|---|------|:--:|:--:|:--:|
| F1 | 案件搜索/筛选 | P1 | 前后端 | 待开发 |
| F2 | 表单草稿自动保存 | P2 | 前端 | 待开发 |
| F3 | 开庭日期提醒 | P2 | 前端 | 待开发 |
| F4 | 案件数据导出 CSV | P2 | 后端 | 待开发 |
| F5 | 法院/案由预设库 | P1 | 前后端 | 待开发 |
| F6 | 操作日志 | P2 | 后端 | 待开发 |
| F7 | 暗色模式（明暗切换） | P3 | 前端 | 待开发 |

**实施顺序**：F5 → F1 → F6 → F4 → F2 → F3 → F7（后端先行，前端随后；F4 依赖 F1 的筛选参数）。

**TDD 前置**：后端 pytest 已就绪（tests/ 51 passed）；前端需先配置 Vitest + @testing-library/react。

---

## 1. F5 法院/案由预设库

### 1.1 数据模型（新表 `presets`）

```sql
CREATE TABLE IF NOT EXISTS presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,      -- workspace 隔离
    kind TEXT NOT NULL,              -- 'court' | 'cause'
    value TEXT NOT NULL,             -- 预设值（法院名/案由）
    usage_count INTEGER DEFAULT 0,   -- 使用频次（排序）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, kind, value)
);
```

### 1.2 API 设计

```
GET    /api/v1/presets?kind=court        → 列表（按 usage_count DESC）
POST   /api/v1/presets/{id}/bump         → 使用频次 +1（案件保存时调用）
POST   /api/v1/presets                    → 新增预设 {kind, value}
DELETE /api/v1/presets/{id}              → 删除预设
```

案件创建/更新时：court / cause 值若不在预设表 → 自动插入（usage_count=1）；存在 → bump。

### 1.3 TDD 测试用例（后端 pytest）

| # | 测试 | 预期 |
|---|------|------|
| 1 | 新增预设（court/cause） | 插入成功，唯一约束生效 |
| 2 | 重复新增同一 (workspace, kind, value) | UNIQUE 冲突，复用旧记录 |
| 3 | bump 次数排序 | 高频项排前面 |
| 4 | 不同 workspace 隔离 | 互不可见 |
| 5 | 案件保存自动注册新值 | 新法院自动入库 usage_count=1 |
| 6 | 删除预设 | 删除成功，列表不再含该项 |

---

## 2. F1 案件搜索/筛选

### 2.1 API 扩展（cases.py）

```
GET /api/v1/cases?search=<kw>&status=<s>&hearing_from=<date>&hearing_to=<date>
```

- `search`：LIKE 匹配 case_number / court / cause
- `status`：精确匹配（pending/generated/submitted/closed）
- `hearing_from/to`：hearing_date 范围
- 全部参数可选；不传 = 返回全部（兼容现有调用）

### 2.2 前端（CasesPage）

- 搜索框（防抖 300ms）+ 状态下拉 + 日期范围选择
- 查询参数直接驱动 API 调用（服务端过滤，不前端过滤）

### 2.3 TDD 测试用例

| # | 层 | 测试 | 预期 |
|---|----|------|------|
| 1 | 后端 | search=案号关键词 | 只返回匹配案件 |
| 2 | 后端 | status 过滤 | 只返回对应状态 |
| 3 | 后端 | hearing_from/To 范围 | 只返回范围内 |
| 4 | 后端 | 多参数组合 | 交集结果 |
| 5 | 后端 | 无参数 | 全部案件 |
| 6 | 前端 | 搜索输入防抖调用 | 300ms 内只发一次请求 |

---

## 3. F6 操作日志

### 3.1 数据模型（新表 `audit_logs`）

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    username TEXT NOT NULL,
    action TEXT NOT NULL,        -- login / case_create / case_update / case_delete / generate / export
    target TEXT NOT NULL,        -- 对象描述（如 'case 5 案号'）
    result TEXT DEFAULT 'ok',    -- ok | failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 API 设计

```
GET /api/v1/audit-logs?limit=50&offset=0   → 当前 workspace 日志列表
```

记录时机：auth 登录成功、cases 创建/更新/删除、generate 成功/失败、cases/export。

### 3.3 TDD 测试用例

| # | 测试 | 预期 |
|---|------|------|
| 1 | 登录成功写日志 | 1 条 login 记录 |
| 2 | 案件创建写日志（含遮罩） | 记录 target 中身份证号被遮罩 |
| 3 | 生成成功/失败写日志 | result 正确 |
| 4 | 跨 workspace 查询隔离 | 看不到别人的日志 |
| 5 | 分页 limit/offset | 正确切片 |

PII 遮罩：复用 `mask_id_card()`（前4后4）。

---

## 4. F4 案件数据导出 CSV

### 4.1 API 设计

```
GET /api/v1/cases/export?search=&status=&hearing_from=&hearing_to=
→ text/csv; charset=utf-8-bom（带 BOM，Excel 直接开）
```

列：case_number, court, cause, hearing_date, opposing_party, our_role, status, created_at, company_name, agent_name

CSV 注入防护：单元格首字符为 `=` `+` `-` `@` 时，前缀 `'`。

### 4.2 TDD 测试用例

| # | 测试 | 预期 |
|---|------|------|
| 1 | 导出空列表 | 只有表头 |
| 2 | 导出含中文 | UTF-8 BOM 开头，中文正常 |
| 3 | 注入防护 | `=SUM(A1)` 变 `'=SUM(A1)` |
| 4 | 导出含筛选参数 | 只导出筛选结果 |
| 5 | 列完整性 | 10 列全部在场 |

---

## 5. F2 表单草稿自动保存（前端）

### 5.1 设计

- 新建 `src/hooks/useFormDraft.ts`：
  - `useFormDraft(key, formState, enabled)` → 输入防抖 1s 写 localStorage
  - localStorage key：`courtdoc:draft:<workspaceId>:<formName>`
- CasesPage 新建表单挂载时：检测草稿 → 弹 ConfirmDialog "检测到未提交的草稿，恢复？" → 恢复 / 放弃
- 提交成功 → `clearDraft()`

### 5.2 TDD 测试用例（Vitest）

| # | 测试 | 预期 |
|---|------|------|
| 1 | 输入变化 1s 后写入 localStorage | 防抖生效 |
| 2 | 输入变化 500ms 内不写入 | 防抖生效 |
| 3 | 恢复草稿 | 返回已存值 |
| 4 | 清除草稿 | localStorage 键删除 |
| 5 | 提交后自动清除 | 清空 |

---

## 6. F3 开庭日期提醒（前端）

### 6.1 设计

- 新建 `src/lib/hearingAlert.ts`：
  - `getUpcomingHearings(cases, days=7)` → 开庭日期在未来 N 天内（含今天）的案件列表
  - 纯函数，可测
- Dashboard：加载案件 → 计算 upcoming → 顶部横幅 + 浏览器 Notification（用户已授权时）
- 通知权限：`Notification.requestPermission()` 仅用户点击"开启提醒"时调用

### 6.2 TDD 测试用例

| # | 测试 | 预期 |
|---|------|------|
| 1 | 7 天内开庭被选中 | 包含 |
| 2 | 已过期开庭不选中 | 排除 |
| 3 | 超过 7 天不选中 | 排除 |
| 4 | 无 hearing_date 的案件 | 排除（不报错） |
| 5 | 空列表 | 返回空 |

---

## 7. F7 暗色模式（前端）

### 7.1 设计

- 新建 `src/stores/themeStore.ts`（zustand）：
  - `mode: 'light' | 'dark' | 'system'`（默认 system）
  - `apply()`：system 时读 `window.matchMedia('(prefers-color-scheme: dark)')`
  - 持久化 localStorage：`courtdoc:theme`
- `index.css` 用 CSS 变量（`--bg` / `--text` / `--card` ...），`[data-theme="dark"]` 覆盖
- Layout 右上角三态切换按钮（亮/暗/跟随系统）

### 7.2 TDD 测试用例

| # | 测试 | 预期 |
|---|------|------|
| 1 | 默认 system | localStorage 无值时为 system |
| 2 | 切换 dark | localStorage 写入 dark |
| 3 | 切换 light | 写入 light |
| 4 | system + 偏好 dark | apply 结果 dark |
| 5 | 刷新恢复 | 从 localStorage 恢复选择 |

---

## 8. TDD 工作流约束

1. **铁律**：没有失败测试，不写生产代码；先写实现 → 删除从头来
2. 每个功能：RED（写一个测试 → 运行看到失败）→ GREEN（最小实现 → 看到通过）→ REFACTOR（保持全绿）
3. 一个测试只测一件事，命名描述行为
4. 后端：`pytest tests/ -v`；前端：`npx vitest run`
5. 每个 RED-GREEN-REFACTOR 循环一个 commit（feat(scope): description）
6. 全量测试必须保持通过（后端 51 + 新增；前端 vitest 全绿）

## 9. 验收标准（总）

> 注：前端 Vitest 因依赖安装受阻，经用户确认跳过前端 TDD（2026-08-22），改以 `npx tsc --noEmit` 零错误 + 浏览器 E2E 全链路验证代替。后端 pytest TDD 照常执行。

- [x] F1：案件页搜索/筛选可用，后端 pytest 覆盖（7 用例）
- [x] F2：草稿自动保存/恢复/放弃/清除全链路，浏览器 E2E 验证（保存→刷新→弹窗→恢复→放弃）
- [x] F3：7 天窗口计算 + Dashboard 横幅 + 通知按钮，浏览器 E2E 验证（含”今天开庭”高亮）
- [x] F4：CSV 导出含 BOM + 注入防护，pytest 覆盖（6 用例）+ 浏览器点击下载验证
- [x] F5：预设 CRUD + 频次排序 + workspace 隔离，pytest 覆盖（6 用例）
- [x] F6：操作日志写入 + 查询 + PII 遮罩，pytest 覆盖（7 用例）+ 列表页展示验证
- [x] F7：明暗切换 + 记忆 + 系统跟随，浏览器 E2E 验证（dark/light 往返 + localStorage 持久化）
- [x] 后端全量 pytest 通过（35 passed）；前端 `npx tsc --noEmit` 零错误 + 生产构建成功