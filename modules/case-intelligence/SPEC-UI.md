# case-intelligence Web UI SPEC

> **版本**: 3.4.0 | **更新**: 2026-10-13 | **状态**: active
> **范围**: 基于 Streamlit 的多页 Web UI（端口 `18503`，fallback `18504`）
> **对齐**: 与 CLI（`bin/extract.py` 16 子命令）能力对等；飞书 Bot 不在本 UI 范围

---

## 概述

基于 Streamlit 的 Web UI，提供案件管理、扫描录入、文书生成、模板管理、案件匹配、统计看板功能。
所有页面共用侧边栏导航（`ui/nav.py:render_sidebar`）与登录保护。

## 技术方案

### 目录结构

```
case-intelligence/
├── app.py                    # Streamlit 主入口（多页应用）
├── config.py                  # UI 配置（PORT / FALLBACK_PORT / AUTH_USERS / PAGE_SIZE）
├── SPEC-UI.md                 # 本文档
├── ui/
│   ├── __init__.py
│   ├── auth.py               # 登录认证（读取 config.USERS）
│   ├── nav.py                # 侧边栏导航（7 导航页 page_link）
│   └── utils.py              # 健康度（compute_health / get_case_health）+ ENGINE_OPTIONS
└── pages/
    ├── 1_登录.py
    ├── 2_案件列表.py
    ├── 2_案件详情.py          # 详情页（由列表页跳转，不在侧边栏）
    ├── 3_扫描录入.py
    ├── 4_文书生成.py
    ├── 5_统计看板.py
    ├── 6_模板管理.py          # v3.4.0 新增
    └── 7_案件匹配.py          # v3.4.0 新增
```

### 认证配置（环境变量注入，无明文入库）

```python
# config.py
# AUTH_USERS 格式：user:pass,user2:pass2（与 shared/config/deploy.yaml env_required 对齐）
_DEFAULT_USERS = "admin:admin123,test:test123"   # 仅本地默认，生产由部署注入 AUTH_USERS
USERS = _parse_users(os.environ.get("AUTH_USERS") or _DEFAULT_USERS)
```

### 端口 / 分页

- 端口：默认 `18503`，备用 `18504`（`config.PORT` / `config.FALLBACK_PORT`）
- 分页：`config.PAGE_SIZE = 20`（**单一真值**，列表页引用之，不再各自声明）

---

## 页面清单

| 页 | 文件 | 侧边栏 | 核心能力 |
|----|------|--------|---------|
| 登录 | `1_登录.py` | — | 用户名/密码、session_state 持久化 |
| 案件列表 | `2_案件列表.py` | ✅ | 新建案件、搜索/状态筛选/排序、分页(20)、健康度、详情入口、标记完成 |
| 案件详情 | `2_案件详情.py` | — | 基本信息 + D1–D5 提取物；编辑/删除/关联材料/手动提取/归档为模板/导出/标记完成/相似案件入口 |
| 扫描录入 | `3_扫描录入.py` | ✅ | 路径扫描→解析→提取→查重→导入；AI 引擎下拉；扫描历史 |
| 文书生成 | `4_文书生成.py` | ✅ | 4 类型；模板化三级降级；引擎下拉；MD/DOCX 导出 |
| 模板管理 | `6_模板管理.py` | ✅ | 模板 list/search/show + 新增/编辑/删除 + JSON 导入 |
| 案件匹配 | `7_案件匹配.py` | ✅ | 基准案件 → Top-N 相似案件（分值 + 命中理由） |
| 统计看板 | `5_统计看板.py` | ✅ | 3 卡片 + 案由分布 + 待提取列表 + 最近操作记录 + 扫描历史 |

---

## M1: 登录 + 案件列表

### 功能

#### 登录页
- 用户名/密码输入、登录按钮、错误提示
- 登录状态持久化（session_state）

#### 案件列表页
- 「➕ 新建案件」表单（等价 CLI `register`，落库 `entry_method=UI`）
- 搜索框（案号/原告/被告）
- 状态筛选（pending/extracted/archived）+ 排序
- 案件卡片：案件名称 / 案号 / 原告·被告 / 状态标签 / 健康度 / 提取物数量 / 详情入口
- 分页（每页 `config.PAGE_SIZE`=20；页码与 `session_state.page` 双向一致）
- 卡片操作：标记完成（等价 CLI `complete`）

### 验收

- [x] AUTH_USERS 账号可登录，失败显示错误
- [x] 案件列表正确显示，搜索/筛选正常
- [x] 分页正常（翻页不回弹）
- [x] 可新建案件并即时出现在列表
- [x] 健康度口径与详情页一致（`ui/utils.compute_health`，6 字段）

---

## M2: 案件详情

### 功能

- 基本信息 + 健康度指标（6 项：案号/原告/被告/案由/法院/提取物）
- 编辑信息（等价 CLI `update_case`，白名单字段）
- 关联原始材料路径（等价 CLI `link`）
- 删除案件（二次确认 checkbox + 级联清除 artifacts，等价 `delete_case` + `purge_case_dir`）
- 标记为已提取（`complete`）
- 手动提取 Artifact（等价 CLI `extract`，`generation_method="manual"`）
- 提取物列表：展开查看内容、`source_ref` 完整展示、归档为模板（`promote`）
- 导出提取物为 MD / DOCX
- 相似案件入口（跳转 `7_案件匹配.py`）

### 验收

- [x] 编辑保存后列表/详情同步
- [x] 删除二次确认 + 级联清除
- [x] 手动提取落库并可归档为模板
- [x] 导出 DOCX/MD 正常（临时文件已清理）
- [x] `source_ref` 完整展示

---

## M3: 扫描录入

### 功能

- 路径输入框（手动输入目录路径）
- AI 引擎下拉（minimax/ollama/openai/mock/basic）
- 扫描按钮 + 实时结果
- **查重**：对已存在案件给出提示，可选「跳过 / 仍要导入」
- 确认导入（`import_full`，按引擎标记 `generation_method`）
- 扫描历史（最近 5 条，session_state）

### 流程

1. 用户输入路径 + 选择引擎
2. `scanner.scan_directory()` → `parser` 解析
3. 显示文件列表
4. 查重（`case_recognizer.recognize_case`）
5. 用户确认 → `extractor.extract_case()` → `importer.import_full()`
6. 显示导入结果 + 记入扫描历史

### 验收

- [x] 路径输入正常，扫描/导入成功
- [x] 重复案件给出查重提示
- [x] 可切换 AI 引擎
- [x] 无死按钮（「选择文件夹」已移除，改为路径提示）

---

## M4: 文书生成

### 功能

- 案件选择下拉框
- 文书类型选择（答辩状/质证意见/当庭陈述/证据目录）
- AI 引擎下拉 + 是否引用模板复选框
- 生成按钮 → **模板化三级降级**：
  1. 有模板 + LLM：模板 + LLM 润色
  2. 无模板 + LLM：纯 LLM 生成
  3. 均不可用：fallback（基于提取物组装）
- 预览区域（Markdown 渲染）+ 来源标识（`result.source`）
- 导出按钮（DOCX/MD，临时文件使用后清理）

### 验收

- [x] 案件/类型选择正常，生成成功
- [x] 生成走 `DocumentGenerator` 三级降级，来源如实展示
- [x] 可切换引擎
- [x] 导出 DOCX/MD 正常且无 `/tmp` 泄漏

---

## M5: 模板管理

### 功能

- 模板列表（按分类过滤 + 关键词搜索，`template_store.search_templates`）
- 展开查看模板内容
- 新增模板（`template_store.create_template`）
- 编辑模板（名称/分类/内容，`template_store.update_template`，同步重写 `output_templates/` 文件）
- 删除模板（文件 + DB 行，`template_store.delete_template`）
- JSON 增量导入案件（`extractor.extracted_from_dict` → `import_full`，跳过已存在案号）

### 验收

- [x] 模板可 list/search/show
- [x] 模板可新增/编辑/删除（双源一致：DB 行 + `output_templates/` 文件）
- [x] JSON 可导入

---

## M6: 案件匹配

### 功能

- 基准案件下拉框 + Top-N 条数选择
- 调用 `src.case_matcher.match_cases`（规则打分）
- 结果卡片：相似度分值 + 命中理由（案由/年份/场景/D1-D5 覆盖）+ 查看详情

### 验收

- [x] 返回 Top-N 相似案件（按案由/年份/场景/D1–D5 覆盖）
- [x] 结果含分值 + 命中理由

---

## M7: 统计看板

### 功能

- 案件总数 / 已提取 / 待提取（三个卡片）
- 案由分布（文本图表）
- 待提取案件列表
- 最近操作记录（最近案件 + 最近提取物）
- 扫描历史（session_state）

### 验收

- [x] 统计数字正确，案由分布显示
- [x] 待提取列表正确
- [x] 最近操作记录 + 扫描历史显示

---

## 通用规范

### 登录保护
- 除登录页外，其他页面需登录后访问；未登录自动跳转登录页

### 错误处理
- 所有操作显示成功/失败提示；失败显示具体错误信息

### 样式
- 使用 Streamlit 原生组件；简洁实用布局；状态用颜色区分（pending=黄，extracted=绿）

### 导航
- 统一侧边栏（`ui/nav.py`），7 个导航页 `page_link` + 退出登录；详情页由列表页跳转进入