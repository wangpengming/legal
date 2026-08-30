# Thunderbox 部署指南

> 2026-08-24 · court-doc-generator 首次成功部署经验总结

---

## 1. Thunderbox MCP 工具能力

| 工具 | 功能 | 关键参数 |
|------|------|---------|
| `thunderbox_create` | 创建应用 | `source_type`=`docker_image`\|`git_repo`，`source_url`，`build_pack`=`dockerfile`\|`nixpacks`\|`static`\|`spa`，`port`，`git_token`，`volumes` |
| `thunderbox_deploy` | 部署/更新 | `app_id`，`ref`（分支/tag） |
| `thunderbox_query` | 查询/日志/健康 | `app_id`，**`build_logs=true`**（构建日志），`logs=true`（运行时日志），`since`（时间范围），`health=true` |
| `thunderbox_config` | 配置更新 | `env_vars`，**`access_mode`=`public`**（公开访问），`ref`，`volumes` |
| `thunderbox_control` | 启动/停止/取消 | `action`=`start`\|`stop`\|`cancel` |
| `thunderbox_rollback` | 回滚 | 不带 `target`=列历史，带 `target`=回滚 |

---

## 2. 源码仓库规则

### 2.1 仅支持 GitHub / GitLab

| 平台 | 是否支持 |
|------|---------|
| GitHub 公开仓库 | ✅ 可用 |
| GitLab 公开仓库 | ✅ 可用 |
| Gitee | ❌ 不支持 |

**Gitee 不可用原因**：Thunderbox 解析 URL 为 `owner/repo` 格式，丢弃 `gitee.com` 域名。即使预检通过，实际 clone 时也会失败。

### 2.2 `git_token` 陷阱

- Thunderbox 将 `git_token` 当作 **GitLab CI token**，拼接 URL 为 `gitlab-ci-token:<TOKEN>@host/repo`
- 这对 GitHub/Gitee 均无效——GitHub 需要 `username:<PAT>`，Gitee 需要 `username:<token>`
- **公开仓库不传 `git_token`**，直接使用 HTTPS URL 即可

### 2.3 URL 格式

```
✅ https://github.com/<owner>/<repo>         # 不带 .git，不带 token
✅ https://github.com/<owner>/<repo>.git     # 带 .git 也可以
❌ https://gitee.com/<owner>/<repo>           # 不支持
❌ 带 git_token 的任何 URL                    # 除非是 GitLab 私有仓库
```

---

## 3. Dockerfile 规范

### 3.1 系统依赖必须完整

`scan_service.py` 在模块加载时调用 `shutil.which("tesseract")`，如果 tesseract 未安装则直接崩溃：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*
```

**教训**：排查问题时不要删除系统依赖，应先通过 `logs=true` 确认根因。

### 3.2 PyPI 必须用国内镜像

Thunderbox 服务器从 `files.pythonhosted.org` 下载大包（如 PyMuPDF 25MB）会超时：

```dockerfile
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt
```

### 3.3 apt 源使用默认

不要在 Dockerfile 中修改 apt 源为阿里云/清华等国内镜像——Thunderbox 服务器可能无法访问。

```dockerfile
# ✅ 默认 Debian 源
RUN apt-get update && apt-get install -y ...

# ❌ 不要换国内源
# RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' ...
```

### 3.4 端口与 CMD

```dockerfile
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

`thunderbox_create` 的 `port` 参数必须与 Dockerfile 的 EXPOSE/CMD 端口一致。

---

## 4. 部署流程

### 4.1 创建应用（`git_repo` 模式）

```json
{
  "name": "app-name",
  "subdomain": "app-name",
  "source_type": "git_repo",
  "source_url": "https://github.com/owner/repo",
  "build_pack": "dockerfile",
  "port": 8001,
  "ref": "main",
  "volumes": ["court-data:/app/data", "court-outputs:/app/outputs"]
}
```

**⚠️ volumes 必须传**：
- Thunderbox 容器文件系统是 ephemeral 的——**不挂载 volumes 每次重部署数据全丢**
- `court-data:/app/data` — SQLite 数据库（workspaces.db / workspaces_meta.db）
- `court-outputs:/app/outputs` — 生成结果（PDF / ZIP）
- `volumes` 是 Docker 格式字符串数组，示例：`["court-data:/app/data", "court-outputs:/app/outputs"]`
- **传 `thunderbox_config` 修改 volumes 是破坏性的**（会替换现有 volumes，旧数据丢失）

### 4.2 部署

```json
{ "app_id": "xxx" }
```

### 4.3 设为公开访问

```json
{ "app_id": "xxx", "access_mode": "public" }
```

**重要**：创建后默认 `internal`（需登录），必须设为 `public` 才能外部访问。

---

## 5. 调试工作流

### 5.1 构建失败时

```
thunderbox_query(app_id, build_logs=true)  → 查看构建日志
```

### 5.2 容器崩溃时

```
thunderbox_query(app_id, logs=true, since="5m")  → 查看运行时日志
```

**关键**：`logs=true` 仅在容器运行时有效。如果容器已崩溃，需要先 `thunderbox_control(action="start")` 重启，然后立刻拉日志。

### 5.3 健康检查

```
thunderbox_query(app_id, health=true)  → MCP 内部健康检查（可能返回 405，不影响）
curl https://<domain>/health           → 外部验证（可信）
```

### 5.4 外部访问

```
curl https://<domain>/      → 验证前端 SPA
curl https://<domain>/health → 验证后端 API
```

### 5.5 轮询策略

- **sleep 不超过 30 秒**，多次短轮询而非一次长等待
- 构建中：每 10-30 秒轮询一次 `build_logs`
- 启动后：立刻拉 `logs` 和 `health`

---

## 6. 常见错误速查

| 错误现象 | 根因 | 修复 |
|----------|------|------|
| `no available server` | `access_mode` 不是 `public` | `thunderbox_config(access_mode="public")` |
| `build_failed` 且 `deploy_key_uuid=null` | 源码 clone 失败 | 检查 URL 格式、平台是否支持 |
| `gitlab-ci-token` 403 | 传了 `git_token` 但仓库不在 GitLab | 去掉 `git_token` |
| `Read timed out` (PyPI) | 大包下载超时 | 换清华镜像源 |
| `TypeError: NoneType` (tesseract) | 系统依赖缺失 | Dockerfile 加 `apt-get install tesseract-ocr` |
| `Connection reset by peer` (clone) | 网络瞬断 | 重试 deploy |
| `build_logs` 卡在 `Preparing container` | 构建挂起 | `thunderbox_control(action="cancel")` 后重试 |
| `sqlite3.OperationalError: no such table` | volumes 未挂载，每次重部署数据库清零 | `thunderbox_config(volumes=[...])` 挂载；后续 `thunderbox_create` 必须带 `volumes` 参数 |

---

## 7. 当前部署实例

| 项目 | 值 |
|------|-----|
| 域名 | `legal-court-app.tbox.ktvsky.com` |
| 源码 | `https://github.com/wangpengming/court-generator` |
| 分支 | `main` |
| 构建方式 | `dockerfile` |
| 端口 | `8001` |
| 访问模式 | `public` |
| 数据卷 | `court-data:/app/data` + `court-outputs:/app/outputs` |
| 状态 | `running` |

---

## 8. Monorepo vs Standalone：Dockerfile 差异分析与设计教训

> 2026-08-26 · 对比 legal monorepo 版与 GitHub standalone 版，分析部署成功的关键差异

### 8.1 代码对比结论

对两个目录做 `diff -rq`（排除 `__pycache__`、`data`、`outputs`、`node_modules` 等运行时产物）：

```
Only in legal/modules/court-doc-generator: .DS_Store
Only in court-generator (GitHub): Dockerfile
```

**结论：所有 Python 源码、前端源码、配置文件完全一致。唯一差异是 Dockerfile 的位置和内容。**

### 8.2 两个版本的 Dockerfile 差异

| 维度 | Legal 根 Dockerfile（monorepo） | GitHub 版 Dockerfile（standalone） |
|------|------|------|
| 位置 | `/legal/Dockerfile` | `/court-generator/Dockerfile` |
| COPY 路径 | `modules/court-doc-generator/frontend/...` | `frontend/...`（扁平） |
| apt 源 | 阿里云镜像（`mirrors.aliyun.com`） | 默认 Debian 源 |
| PyPI 源 | 默认 `pypi.org` | 清华镜像（`tuna.tsinghua.edu.cn`） |
| 注释 | 含 DNS `--add-host` 说明 | 无注释 |

**关键差异**：Legal 版的 Dockerfile 是为本地 `docker build` 设计的（含阿里云源、DNS 绕过），GitHub 版是为 Thunderbox 远程构建优化的（默认 apt 源、清华 PyPI 镜像）。

### 8.3 Dockerfile 演进过程（5 次提交）

GitHub 仓库 `wangpengming/court-generator` 的 5 次提交记录了完整的调试过程：

| 提交 | 说明 | 构建结果 | 运行时 |
|------|------|---------|--------|
| `17bbea4` init | 初始版本：扁平路径，无 tesseract，无 PyPI 镜像 | ✅ 成功 | ❌ 容器崩溃 |
| `aad44f7` pip镜像 | 加清华 PyPI 镜像 | ✅ 成功 | ❌ 容器崩溃 |
| `7d316b0` 最小化 | 删掉前端构建、tesseract、所有 pip 依赖 | ✅ 成功 | ✅ 能跑（无功能） |
| `e2e3006` 回退 | 回退到 aad44f7 状态 | ✅ 成功 | ❌ 容器崩溃 |
| `1b545bd` 最终 | **加回 tesseract** | ✅ 成功 | ✅ 完全正常 |

### 8.4 根因：`scan_service.py` 模块级初始化

```python
# scan_service.py 第 24-36 行
_TESSERACT = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"

def _detect_lang() -> str:
    tessdata_dir = Path(shutil.which(_TESSERACT)).parent.parent / "share" / "tessdata"
    # ...

_LANG = _detect_lang()  # ← 模块导入时立即执行！
```

**问题链**：
1. `shutil.which("tesseract")` 返回 `None`（tesseract 未安装）
2. 短路求值后 `_TESSERACT = "/opt/homebrew/bin/tesseract"`（macOS 硬编码路径）
3. `shutil.which("/opt/homebrew/bin/tesseract")` 返回 `None`（容器内无此路径）
4. `Path(None).parent.parent` → **`TypeError: argument should be a string, bytes or os.PathLike object, not 'NoneType'`**
5. 这发生在 `import scan_service` 时 → FastAPI 启动失败 → 容器崩溃

**为什么 init 版（17bbea4）Dockerfile 没有 tesseract？**

因为 init 版是从 legal 版直接复制后修改 COPY 路径得到的，而 legal 版的 Dockerfile **有** tesseract 安装。但 init 版在复制时**遗漏了 apt-get 安装部分**——这是从 monorepo 迁移到 standalone 时的人为失误。

### 8.5 设计教训

#### 8.5.1 模块级初始化不应依赖外部二进制

```python
# ❌ 当前写法：模块导入时立即执行，无容错
_LANG = _detect_lang()

# ✅ 应改为惰性求值 + try/except 保护
_LANG: Optional[str] = None

def get_lang() -> str:
    global _LANG
    if _LANG is None:
        try:
            _LANG = _detect_lang()
        except Exception:
            _LANG = "chi_sim"  # fallback
    return _LANG
```

**影响范围**：`scan_service.py` 的 `_LANG`、`_TESSERACT` 两个模块级变量都有此问题。

#### 8.5.2 Dockerfile 应自包含所有系统依赖

不要假设基础镜像已安装任何工具。Dockerfile 是唯一的事实来源：

```dockerfile
# ✅ 明确声明所有依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*
```

#### 8.5.3 Monorepo 和 Standalone 需要不同的 Dockerfile

| 场景 | Dockerfile 位置 | COPY 路径 |
|------|----------------|-----------|
| Monorepo（本地构建） | `/legal/Dockerfile` | `modules/court-doc-generator/...` |
| Standalone（Thunderbox 部署） | `/court-generator/Dockerfile` | `frontend/...`（扁平） |

**规则**：每次修改 monorepo 版 Dockerfile 后，必须同步更新 standalone 版 Dockerfile，反之亦然。两者应保持功能等价（仅路径不同）。

#### 8.5.4 构建日志是首要排查入口

| 做法 | 效率 |
|------|------|
| `build_logs=true` 看日志 → 定位根因 → 一次修复 | 高 |
| 反复修改 Dockerfile 试探 → 多次构建 → 猜测根因 | 低 |

在 `1b545bd` 之前，我们走了 3 次弯路（最小化→回退→加回 tesseract），如果能直接从 `logs=true` 看到 `TypeError: NoneType`，一次就能修复。

#### 8.5.5 `git_token` 陷阱

`thunderbox_create` 的 `git_token` 参数被 Thunderbox 当作 GitLab CI token：
- 拼接 URL：`gitlab-ci-token:<TOKEN>@host/repo`
- GitHub 需要 `username:<PAT>`，Gitee 需要 `username:<token>`
- 公开仓库不传 `git_token` 即可

#### 8.5.6 环境差异矩阵

| 环境 | apt 源 | PyPI 源 | 网络特征 |
|------|--------|---------|---------|
| 本地 Mac（Docker Desktop） | 国内镜像（阿里云） | 默认 pypi.org | 需代理，大文件不稳 |
| Thunderbox 服务器 | 默认 Debian | 国内镜像（清华） | 直连，PyPI 大文件超时 |
| 10.10.11.37（内网） | 默认 Debian | 默认 pypi.org | 内网，需代理 |

**结论**：不存在一份 Dockerfile 同时适配所有环境。必须按目标环境选择 apt 源和 PyPI 源。

### 8.6 后续改进建议

1. **`scan_service.py` 重构**：将 `_LANG` 和 `_TESSERACT` 改为惰性初始化 + fallback
2. **Dockerfile 同步机制**：在 `AGENTS.md` 中增加规则——修改任一 Dockerfile 后必须同步另一个
3. **构建前自检**：在 Dockerfile 中加 `RUN tesseract --version` 验证系统依赖完整性
4. **Standalone 仓库作为部署源**：`~/code/work/me/court-generator` 是 Thunderbox 部署的 canonical 源码，legal 内的是开发版