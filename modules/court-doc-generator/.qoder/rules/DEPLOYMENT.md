# Thunderbox 部署规范

> 2026-08-26 · court-doc-generator 首次成功部署经验总结

---

## 1. Thunderbox MCP 工具能力

| 工具 | 功能 | 关键参数 |
|------|------|---------|
| `thunderbox_create` | 创建应用 | `source_type`=`docker_image`\|`git_repo`，`source_url`，`build_pack`=`dockerfile`，`port`，`volumes` |
| `thunderbox_deploy` | 部署/更新 | `app_id`，`ref`（分支/tag） |
| `thunderbox_query` | 查询/日志/健康 | `app_id`，**`build_logs=true`**（构建日志），`logs=true`（运行时日志） |
| `thunderbox_config` | 配置更新 | `env_vars`，**`access_mode`=`public`** |
| `thunderbox_control` | 启动/停止 | `action`=`start`\|`stop` |
| `thunderbox_rollback` | 回滚 | 不带 `target`=列历史，带 `target`=回滚 |

---

## 2. 源码仓库规则

### 2.1 仅支持 GitHub / GitLab

| 平台 | 是否支持 |
|------|---------|
| GitHub 公开仓库 | ✅ 可用 |
| GitLab 公开仓库 | ✅ 可用 |
| Gitee | ❌ 不支持 |

**Gitee 不可用原因**：Thunderbox 解析 URL 为 `owner/repo` 格式，丢弃 `gitee.com` 域名。

### 2.2 `git_token` 陷阱

- Thunderbox 将 `git_token` 当作 **GitLab CI token**，拼接 URL 为 `gitlab-ci-token:<TOKEN>@host/repo`
- GitHub 需要 `username:<PAT>`，Gitee 需要 `username:<token>`
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

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*
```

**教训**：`scan_service.py` 在模块加载时调用 `shutil.which("tesseract")`，如果 tesseract 未安装则直接崩溃。

### 3.2 PyPI 必须用国内镜像

Thunderbox 服务器从 `files.pythonhosted.org` 下载大包（如 PyMuPDF 25MB）会超时：

```dockerfile
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt
```

### 3.3 apt 源使用默认

不要在 Dockerfile 中修改 apt 源为阿里云/清华等 — Thunderbox 服务器可能无法访问。

```dockerfile
# ✅ 默认 Debian 源
RUN apt-get update && apt-get install -y ...

# ❌ 不要换国内源
```

### 3.4 端口与 CMD

```dockerfile
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## 4. 部署流程

### 4.1 创建应用

```json
{
  "name": "court-generator",
  "subdomain": "court-generator",
  "source_type": "git_repo",
  "source_url": "https://github.com/wangpengming/court-generator",
  "build_pack": "dockerfile",
  "port": 8001,
  "ref": "main",
  "volumes": ["court-data:/app/data", "court-outputs:/app/outputs"]
}
```

### 4.2 volumes 必须传

- Thunderbox 容器文件系统是 ephemeral 的 — **不挂载 volumes 每次重部署数据全丢**
- `court-data:/app/data` — SQLite 数据库
- `court-outputs:/app/outputs` — 生成结果（PDF / ZIP）

### 4.3 设为公开访问

```json
{ "app_id": "xxx", "access_mode": "public" }
```

---

## 5. 调试工作流

### 5.1 构建失败时

```
thunderbox_query(app_id, build_logs=true)  → 查看构建日志
```

### 5.2 容器崩溃时

```
thunderbox_control(action="start")  → 重启
thunderbox_query(app_id, logs=true, since="5m")  → 查看日志
```

### 5.3 健康检查

```
curl https://<domain>/health           → 外部验证（可信）
```

---

## 6. 常见错误速查

| 错误现象 | 根因 | 修复 |
|----------|------|------|
| `no available server` | `access_mode` 不是 `public` | `thunderbox_config(access_mode="public")` |
| `build_failed` | 源码 clone 失败 | 检查 URL 格式、平台是否支持 |
| `Read timed out` (PyPI) | 大包下载超时 | 换清华镜像源 |
| `TypeError: NoneType` (tesseract) | 系统依赖缺失 | Dockerfile 加 `apt-get install tesseract-ocr` |
| `sqlite3.OperationalError: no such table` | volumes 未挂载 | `thunderbox_config(volumes=[...])` 挂载 |

---

## 7. scan_service.py 惰性初始化

### 7.1 问题根因

```python
# scan_service.py 第 24-36 行
_TESSERACT = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
_LANG = _detect_lang()  # ← 模块导入时立即执行！
```

问题链：
1. `shutil.which("tesseract")` 返回 `None`（Linux 容器中无 tesseract）
2. 短路求值后 `_TESSERACT = "/opt/homebrew/bin/tesseract"`（macOS 硬编码路径）
3. `shutil.which("/opt/homebrew/bin/tesseract")` 返回 `None`
4. `Path(None).parent` → **`TypeError`**

### 7.2 修复方案

```python
# ✅ 惰性求值 + try/except fallback
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

---

## 8. 当前部署实例

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
