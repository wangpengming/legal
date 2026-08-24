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
  "ref": "main"
}
```

**注意**：不传 `git_token`（公开仓库），不传 `volumes`（先验证基本功能）。

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

---

## 7. 当前部署实例

| 项目 | 值 |
|------|-----|
| 域名 | `court-doc-gh.tbox.ktvsky.com` |
| 源码 | `https://github.com/wangpengming/court-generator` |
| 分支 | `main` |
| 构建方式 | `dockerfile` |
| 端口 | `8001` |
| 访问模式 | `public` |
| 状态 | `running` |