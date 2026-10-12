# thunderbox 部署手册（雷石盒子）

> 部署平台：**thunderbox（雷石盒子）** · 本手册适用于 legal 系统全部 4 个模块。
> 配套规则：`AGENTS.md §10.4.5`（域名管理）· 域名注册表：`shared/config/domains.yaml`

---

## 1. 平台信息

| 项 | 值 |
|----|----|
| 控制台 | `https://box.tbox.ktvsky.com/` |
| MCP 端点 | `https://api-box.tbox.ktvsky.com/mcp`（HTTP transport） |
| 域名规范 | `<subdomain>.tbox.ktvsky.com` |
| 代码来源 | **GitHub（唯一通道）** — 服务器只支持从 GitHub 拉取构建 |
| Token 获取 | 控制台 → 创建 token（**严禁写入仓库**） |

---

## 2. 部署前置：代码迁移到 GitHub

thunderbox **只支持 GitHub 方式**，部署前必须：

1. 将 legal 工程代码推送到 GitHub 仓库（私有仓库即可）。
2. 在 thunderbox 创建应用时选择该 GitHub 仓库作为来源。
3. 后续每次部署从 GitHub 构建。

> 🔴 **Push 红线**（`AGENTS.md §10.2`）：`git push` 必须由用户逐次明确授权，AI 代理不得擅自推送。

---

## 3. 域名规则：一模块一域名 🔴

**每个模块在 thunderbox 上有且仅有一个域名**，域名在应用创建时绑定，**不得随意新建**。

| 模块 | 规划域名 | 状态 |
|------|---------|------|
| court-doc-generator | `legal-court.tbox.ktvsky.com` | ⚠️ 待回收（`legal-court` 被遗留应用占用；回退候选 `legal-court-generator` / `legal-courtdocs`） |
| litigation-system | `legal-litigation.tbox.ktvsky.com` | ✅ 可用 |
| case-intelligence | `legal-case.tbox.ktvsky.com` | ✅ 可用 |
| portal | `legal-portal.tbox.ktvsky.com` | ✅ 可用 |

- 命名空间统一 `legal-*`，访问模式一律 `access_mode=internal`（仅内网）。
- 完整注册表与遗留冲突登记见 `shared/config/domains.yaml`；规则详见 `AGENTS.md §10.4.5`。

---

## 4. MCP 工具清单（13 个）

| 工具 | 用途 |
|------|------|
| `thunderbox_check` | 查重（`target=domain` 查子域是否可用） |
| `thunderbox_create` | 创建应用（**强制携带 `subdomain`** → 域名即绑定） |
| `thunderbox_config` | 应用配置（环境变量 / 访问模式等） |
| `thunderbox_deploy` | 部署（从 GitHub 构建） |
| `thunderbox_rollback` | 回滚到上一版本 |
| `thunderbox_query` | 查询应用状态 |
| `thunderbox_control` | 启停控制（start / stop / cancel） |
| `thunderbox_db_add` / `thunderbox_db_remove` | 数据库实例增删 |
| `thunderbox_sql` | 执行 SQL |
| `thunderbox_apply_migration` | 应用数据库迁移 |
| `thunderbox_describe_schema` | 查看表结构 |
| `thunderbox_list_tables` | 列出数据表 |

> ⚠️ **无删除应用的 MCP 工具**：删除应用只能在控制台人工操作；删除后须同步移除 `domains.yaml` 条目。

---

## 5. 部署流程

### 5.1 首次部署（含域名申请）

1. **查重**：`thunderbox_check(target=domain, value=<subdomain>)` → 确认 `available=true`
2. **创建应用**：`thunderbox_create`（携带 `subdomain` + `access_mode=internal`）→ 域名绑定
3. **登记**：在 `shared/config/domains.yaml` 登记域名，并在模块 `module.yaml` 补 `domain` 字段（两处一致）
4. **配置**：`thunderbox_config` 注入环境变量（飞书凭证等敏感项走 secret，勿明文）
5. **部署**：`thunderbox_deploy`（从 GitHub 构建）
6. **验证**：`thunderbox_query` 查状态 + 访问 `https://<subdomain>.tbox.ktvsky.com/health`（或模块对应健康端点）

### 5.2 迭代部署

```text
改代码 → 本地 commit → （用户授权）git push → thunderbox_deploy → thunderbox_query 验证
```

### 5.3 回滚

`thunderbox_rollback` 回退到上一可用版本。

---

## 6. Token 配置（严禁入库）🔴

- Token 在控制台创建。
- **禁止写入仓库**：项目 scope 的 `.qoder/settings.json` 会被提交，会泄露 token。
- 允许位置：Qoder **user/local** scope、Hermes `~/.hermes/config.yaml`（值走 `${MCP_THUNDERBOX_API_KEY}` 环境变量）、或本地 `.env`。

示例（Hermes）：

```yaml
mcp_servers:
  thunderbox:
    url: https://api-box.tbox.ktvsky.com/mcp
    headers:
      Authorization: Bearer ${MCP_THUNDERBOX_API_KEY}
```

---

## 7. 排障

| 现象 | 排查 |
|------|------|
| `invalid_token` / `unauthorized` | token 无效或已撤销 → 控制台重新创建并替换（注意 user/local scope 与 Hermes 两处） |
| 域名 `available=false` | 该子域已被占用 → 查 `domains.yaml` 的 `legacy_occupancy`，改用回退候选或控制台回收 |
| 部署失败 | 确认代码已推送到 GitHub；确认 GitHub 仓库已授权给 thunderbox |
| 应用无法删除 | thunderbox 无删除 MCP，只能控制台人工删除 |

---

## 8. 相关文档

- `AGENTS.md §10.4.5` — 域名管理规则（一模块一域名 / 禁止随意创建 / 查重 / 双登记）
- `shared/config/domains.yaml` — 域名注册表
- `modules/<name>/README.md` — 各模块专属部署说明
- `modules/court-doc-generator/docs/DEPLOYMENT.md` — 该模块生产运行形态（systemd / 字体 / 日志）