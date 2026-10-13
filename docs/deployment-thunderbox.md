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

## 8. 部署分支模型（方案 A：一仓多分支快照）🔧

> 适用范围：**case-intelligence**（当前部署目标）。court-doc-generator 已部署、暂不动；portal 待定。

### 8.1 一句话流程

```
本地开发（Gitee monorepo）→ tools/deploy_sync.py 生成模块分支快照
  → 推到 GitHub 的 deploy/<module> 分支 → thunderbox 按 ref 部署
```

thunderbox **没有 root/base-directory 参数**（只能从仓库根构建），所以部署分支的**根目录 = 模块本体**（不带 `modules/` 前缀）。

### 8.2 分支模型与目录对照

| monorepo（Gitee origin） | GitHub 部署分支 | 分支根内容 |
|---|---|---|
| `modules/case-intelligence/` | `deploy/case-intelligence` | 模块本体：`app.py` `src/` `pages/` `ui/` `data/` `prompts/` `output_templates/` `templates_extracted/` … |

- GitHub 仓库 `https://github.com/wangpengming/legal.git`（私有）**只承载 `deploy/*` 分支**；**不推 `master`**（避免整个 monorepo 连同 `data/` 复制到 GitHub）。
- `deploy/*` 为**机器生成的镜像分支，禁止手改**；一切改动回 monorepo，再重新同步。

### 8.3 本地如何放置 GitHub 代码

**不需要**在本地 clone GitHub 仓库，也不需要第二份代码。在唯一工作副本 `/home/pengming/code/me/legal` 上加一个 remote 即可：

```
origin   git@gitee.com:wpmdpzch/legal.git          # 源码主库：日常开发、提交、推送
github   git@github.com:wangpengming/legal.git     # 部署目标：只推、不拉、不直接开发
```

```bash
git remote add github git@github.com:wangpengming/legal.git   # 一次性
```

- GitHub 侧那份代码由脚本生成，本机**从不 checkout**，因此不存在「放哪」的问题，也不会与 Gitee 副本漂移。
- SSH 不通时，改用 HTTPS + PAT（`https://github.com/wangpengming/legal.git`）。

### 8.4 同步命令（`tools/deploy_sync.py`）

```bash
# 预览（默认 dry-run：打印快照清单 + 将执行的推送命令，不推送）
python3 tools/deploy_sync.py --module case-intelligence

# 真正推送（受 §10.2 push 红线约束，需用户逐次明确授权）
python3 tools/deploy_sync.py --module case-intelligence --push

# 备选：推 Gitee，交由服务端镜像同步到 GitHub（绕开本机 GitHub 直连受限）
python3 tools/deploy_sync.py --module case-intelligence --push --via-gitee
```

- 注册表：`shared/config/deploy.yaml`（分支名 / 子域 / build_pack / 端口 / 卷 / 环境变量 / 快照排除项）。
- 快照集：模块内 tracked + untracked(非忽略) 文件（含已提炼数据与模板），按 `exclude` 剔除 `tests/ docs/ spec/ requirements/ __pycache__/` 等。
- ⚠️ 实现注意：取文件用 `git ls-files -z`——否则 git 会对中文名加引号转义，导致数据/模板文件被静默丢弃。

### 8.5 数据持久化（case-intelligence，硬需求）

需求：**新增案例提取后，重新部署不能丢数据**。

| 层 | 做法 |
|---|---|
| 镜像内 | `data/`（已提炼数据 + 模板 + 案库）在构建时拷为 `/app/seed-data`，作为**首次种子** |
| 运行期 | 挂卷 `case-data:/data`，环境变量 `DATA_DIR=/data` |
| 首启 | `docker-entrypoint.sh`：空卷 → 从 `/app/seed-data` 播种；非空卷 → 原样保留 |
| 代码 | `src/database.py` / `src/artifact_store.py` / `src/document_generator.py` 读 `DATA_DIR`（本地不设时默认 `PROJECT_ROOT/data`，行为不变）|

效果：运行期新增案例写入**卷**，镜像换代时卷保留 → 数据不丢；仓库中的 `data/` 仅作种子与版本基线。

### 8.6 环境变量与密钥

- 一律经 `thunderbox_config` 的 `env_vars` 注入：`DATA_DIR` / `AUTH_USERS` / `MINIMAX_*` / `LARK_*`，**不写回分支**。
- 现状：`ai_engines.yaml` 内含 MiniMax **明文 key**（用户已知悉并接受，可随时轮换）——推 GitHub 前请自行评估暴露面。
- `config.py` 默认口令 `admin/admin123` / `test/test123` 仅为本地默认；部署必须用 `AUTH_USERS` 覆盖。

### 8.7 case-intelligence 部署清单（MCP）

```bash
thunderbox_check(target=domain, value=legal-case)          # available?
thunderbox_create(name=legal-case, subdomain=legal-case,
                  source_type=git_repo,
                  source_url=https://github.com/wangpengming/legal.git,
                  ref=deploy/case-intelligence,
                  git_token=<PAT>, build_pack=dockerfile, port=18503)
thunderbox_config(app_id, access_mode=internal,
                  env_vars={DATA_DIR: "/data", AUTH_USERS: "..."},
                  volumes=["case-data:/data"])
thunderbox_deploy(app_id) → thunderbox_query(app_id, health=true)   # /_stcore/health
```

> ⚠️ thunderbox **无删除应用的 MCP 工具**，创建即绑定域名，删除只能控制台人工操作——**未确认前不要 create**。

### 8.8 部署前自检

- [ ] `python3 tools/deploy_sync.py --module case-intelligence` 快照含 `data/ prompts/ output_templates/ templates_extracted/` 且无 `modules/` 前缀
- [ ] 分支内容无意外 secrets（当前 minimax key 为已知例外）
- [ ] `deploy/<module>` 分支已推送
- [ ] 卷 + `DATA_DIR` 已在 `thunderbox_config` 设置
- [ ] 域名在 `shared/config/domains.yaml` 登记（`legal-case`）

---

## 9. 本地 `temp/` 目录（不入库）

项目根 `temp/` 为**本地专用**信息存储（已 gitignore）：任务状态、临时脚本、不便上传的信息等。
用途与约定见 `temp/README.md`，当前进度见 `temp/STATUS.md`。

---

## 10. 相关文档

- `AGENTS.md §10.4.5` — 域名管理规则（一模块一域名 / 禁止随意创建 / 查重 / 双登记）
- `shared/config/domains.yaml` — 域名注册表
- `modules/<name>/README.md` — 各模块专属部署说明
- `modules/court-doc-generator/docs/DEPLOYMENT.md` — 该模块生产运行形态（systemd / 字体 / 日志）