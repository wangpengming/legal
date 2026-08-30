# Thunderbox Console · SPEC 功能能力对齐

> **目标**：对照 Thunderbox MCP 全部 13 个工具的能力，与当前原型 v1.2 逐项对比，找出 **MCP 可驱动但原型未呈现** 的有意义功能，补充完善原型。

---

## 一、MCP 全部能力矩阵（13 Tools）

| # | Tool | 核心输入 | 核心输出 / 能力 |
|---|------|---------|----------------|
| 1 | `thunderbox_query` | `app_id?`, `health?`, `build_logs?`, `logs?`, `list_scope?`, `since?` | 列表/详情：id, name, domain, status, build_pack, source_type, source_url, ref, is_public, healthy, http_status, response_time_ms, env, volumes, database, updated_at, created_at |
| 2 | `thunderbox_create` | name, subdomain, source_type, source_url, git_token?, build_pack?, **build_command?**, **install_command?**, **start_command?**, port?, **publish_directory?**, database?, volumes? | 创建应用 |
| 3 | `thunderbox_deploy` | app_id, ref? | estimated_seconds, poll_interval_seconds（指导轮询） |
| 4 | `thunderbox_control` | app_id, action(start/stop/cancel) | 启停 + 取消构建 |
| 5 | `thunderbox_rollback` | app_id, target?(history id) | 无 target → 历史列表；有 target → 执行回滚 |
| 6 | `thunderbox_check` | target(domain/server), value? | 域名可用性 / 服务器资源 |
| 7 | `thunderbox_config` | app_id, env_vars?, remove_env?, **access_mode?**, **add_emails?**, **remove_emails?**, **manager_action?**, **manager_email?**, **ref?**, **volumes?**, **bypass_trusted_ips?** | 查看完整配置（env, access_mode, managers, bypass_trusted_ips, ref, volumes）；增量更新 |
| 8 | `thunderbox_db_add` | app_id, database(type: sqlite/postgres, sqlite_path?) | 附加数据库 |
| 9 | `thunderbox_db_remove` | — | **禁用**，返回引导消息 |
| 10 | `thunderbox_sql` | app_id, sql, mode(rw/ro), params?, timeout_ms? | rows, rowCount, columns, truncated |
| 11 | `thunderbox_apply_migration` | app_id, name, sql | 幂等迁移 |
| 12 | `thunderbox_describe_schema` | app_id | tables[], columns(name, type, nullable, default?, primary_key?) |
| 13 | `thunderbox_list_tables` | app_id | tables[{name}] |

---

## 二、原型 v1.2 已覆盖的 MCP 能力

| 功能 | MCP 来源 | 状态 |
|------|---------|------|
| 应用列表 / 状态 / 域名 | `thunderbox_query()` | ✅ |
| 构建 Pack 分布 | `thunderbox_query()` → `build_pack` | ✅ |
| 健康状态 / HTTP / 响应时间 | `thunderbox_query(health:true)` → `healthy`, `http_status`, `response_time_ms` | ✅ |
| 域名探测 | `thunderbox_check(target:"domain")` | ✅ |
| 服务器探测（server） | `thunderbox_check(target:"server")` | ✅（已引导到 server 功能）|
| 部署操作 | `thunderbox_deploy()` | ✅ |
| 启停控制 | `thunderbox_control(start/stop/cancel)` | ✅ |
| 回滚（交互 + 历史） | `thunderbox_rollback(history:true)` | ✅ |
| 环境变量（增删改） | `thunderbox_config(env_vars, remove_env)` | ✅ |
| 访问模式（public/internal） | `thunderbox_config(access_mode)` | ✅ |
| 数据库附加（Postgres/SQLite） | `thunderbox_db_add()` | ✅ |
| 数据库删除引导 | `thunderbox_db_remove()`（禁用）| ✅ |
| SQL 工作台（ro/rw） | `thunderbox_sql(mode)` | ✅ |
| 迁移管理 | `thunderbox_apply_migration()` | ✅ |
| 表结构展示 | `thunderbox_describe_schema()` | ✅ |
| 迁移列表 | `thunderbox_apply_migration()` 幂等返回 | ✅ |
| 创建向导：基础信息 | `thunderbox_create()` | ✅ |
| 创建向导：Git Token 私有仓库 | `thunderbox_create(git_token)` | ✅ |
| 创建向导：构建方式 | `thunderbox_create(build_pack)` | ✅ |
| 创建向导：数据库 | `thunderbox_create(database)` | ✅ |
| 创建向导：数据卷 | `thunderbox_create(volumes)` | ✅ |
| 部署历史（回滚来源） | `thunderbox_rollback(history:true)` | ✅ |
| 构建日志 / 运行日志 | `thunderbox_query(build_logs/logs:true)` | ✅ |

---

## 三、MCP 可驱动但原型缺失的功能（待补充）

### 3.1 应用详情页 — 配置 Tab

| 缺失功能 | MCP 来源 | 说明 |
|---------|---------|------|
| **应用管理者（Co-manager）** | `thunderbox_config(manager_action, manager_email)` | 添加/移除协作者；协作者可帮助运维该应用 |
| **restricted 模式：邮箱白名单** | `thunderbox_config(add_emails, remove_emails)` | restricted 模式下增删允许访问的邮箱；原型目前只有 UI 入口，无实际操作 |
| **默认分支（ref）** | `thunderbox_config(ref)` | 展示 + 修改默认部署分支 |
| **信任 IP 跳过 SSO** | `thunderbox_config(bypass_trusted_ips)` | 内部网络可跳过 SSO；目前配置页无此选项 |
| **数据库类型展示** | `thunderbox_query()` → `database` 字段 | 详情页概览应显示"数据库类型：PostgreSQL / SQLite / 无" |

### 3.2 创建向导 — Step 2（构建配置）

| 缺失功能 | MCP 来源 | 说明 |
|---------|---------|------|
| **构建命令（build_command）** | `thunderbox_create(build_command)` | nixpacks/spa 下可覆盖默认构建命令 |
| **安装命令（install_command）** | `thunderbox_create(install_command)` | nixpacks/spa 下可覆盖默认安装命令 |
| **启动命令（start_command）** | `thunderbox_create(start_command)` | nixpacks 下可覆盖默认启动命令 |
| **发布目录（publish_directory）** | `thunderbox_create(publish_directory)` | spa 下指定构建产物路径（/dist /build /.next 等）|

### 3.3 应用详情页 — 概览 Tab

| 缺失功能 | MCP 来源 | 说明 |
|---------|---------|------|
| **创建时间** | `thunderbox_query()` → `created_at` | 应用何时创建 |
| **当前分支（ref）** | `thunderbox_query()` → `ref` | 概览信息网格应增加"分支"行 |
| **数据库类型** | `thunderbox_query()` → `database` | 概览信息网格应增加"数据库"行 |

---

## 四、MCP 无此能力（不应展示）

| 原型曾有内容 | 说明 |
|------------|------|
| 通知推送 badge（铃铛） | MCP 无 webhook 推送 |
| 审计日志模拟数据 | MCP 无全局审计 API |
| CPU / 内存 / 磁盘使用率 | MCP 无此字段 |
| 模板库 | MCP 无列表 API |
| 数据库删除按钮（真实操作） | `thunderbox_db_remove` 被禁用 |

---

## 五、补充优先级

| 优先级 | 功能 | 状态 |
|--------|------|------|
| P0（必须） | 配置 Tab：Co-manager 管理 | ✅ 已完成（`addMgr`/`removeMgr`，`thunderbox_config(manager_action, manager_email)`） |
| P0（必须） | 配置 Tab：restricted 邮箱白名单增删 | ✅ 已完成（`addEmail`/`removeEmail`，`thunderbox_config(add_emails/remove_emails)`） |
| P0（必须） | 创建向导 Step 2：build/install/start 命令 | ✅ 已完成（`WZ.build_cmd`/`install_cmd`/`start_cmd`） |
| P0（必须） | 创建向导 Step 2：publish_directory | ✅ 已完成（`WZ.publish_dir`，SPA 模式动态出现） |
| P1（重要） | 详情概览：创建时间 | ✅ 已完成（`a.created_at`） |
| P1（重要） | 详情概览：当前分支 | ✅ 已完成（`a.ref`，badge 展示） |
| P1（重要） | 详情概览：数据库类型 | ✅ 已完成（`a.database.type`，PostgreSQL/SQLite 区分） |
| P2（次要） | 配置 Tab：默认分支修改 | ⏳ 待实现 |
| P2（次要） | 配置 Tab：信任 IP | ⏳ 待实现 |

---

*文档版本：v1.1*
*生成时间：2026-08-26*
*依据：Thunderbox MCP 13 Tools JSON Schema 逐一对照原型 v1.3*
