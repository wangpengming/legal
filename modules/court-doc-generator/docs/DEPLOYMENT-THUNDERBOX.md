# Thunderbox 云部署评估 · court-doc-generator（出庭手续生成器）

> 日期：2026-08-24 ｜ 状态：**评估稿（未部署）** ｜ 基线：v2.2.5
> 前提：Thunderbox（公司内部 PaaS，底层 Coolify）已通过 MCP 接入（13 工具，域名体系 `<前缀>.tbox.ktvsky.com`）
> 本文档只做可行性评估与方案设计，**未经用户确认不执行任何 create / deploy**。

---

## 1. TL;DR 结论

**结论：可行，且本地架构高度适配容器化**（单端口同源、文件型存储、无外部中间件）。核心缺口是**工程件而非代码**：

| # | 缺口 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | 无 Dockerfile | 🔴 阻塞 | 镜像/git 两路径的公共前置 |
| 2 | 无镜像推送通道 | 🔴 阻塞 | `docker_image` 模式需推送到 `registry.tbox.ktvsky.com`（凭证待确认） |
| 3 | git remote 为 SSH | 🟠 前置 | create 预检要求 HTTPS + git_token（Gitee 个人令牌，`read_repository`） |
| 4 | monorepo vs 平台根 Dockerfile 假设 | 🟠 决策 | 仓库根放 Dockerfile 或以镜像模式规避 |
| 5 | 数据双目录持久化 | 🟠 必须 | `data/` + `outputs/` 两个卷（二者路径分离） |
| 6 | Tesseract + 中文字体 | 🟡 容器内补齐 | apt 安装 `tesseract-ocr` / `tesseract-ocr-chi-sim` / `fonts-noto-cjk`（字体缺失会复发打印空白，见 §5.3） |
| 7 | Linux 全链路未验证 | 🟡 验证项 | macOS 单测通过 ≠ Linux 镜像内 PDF/OCR 链路 OK，需容器内跑 pytest |

**代码改动需求≈0**（纯工程配置：Dockerfile / .dockerignore / 环境变量 / 卷）。

---

## 2. 服务器端能力实测（MCP）

| 项 | 实测结果 | 影响 |
|----|---------|------|
| 现有应用 | `thunderbox_query list_scope=mine` → `[]`（token 名下无应用） | 全新环境，可直接创建 |
| 服务器资源 | `thunderbox_check target=server` → "server resources endpoint (P3)"（规划中） | 无法预知资源，只能部署后观察 |
| 域名体系 | `thunderbox_check target=domain` → 前缀即子域：`{"subdomain":"legal-court","domain":"legal-court.tbox.ktvsky.com","available":true}` | 见 §6 域名规划 |
| build_pack | dockerfile / nixpacks / static / spa 四模式 | 本服务用 `dockerfile` 或镜像模式 |
| source_type | `git_repo`（HTTPS + token 预检 `git ls-remote`）/ `docker_image`（镜像名） | SSH 格式不支持 |
| database | 可选 sqlite / postgres（注入 `DATABASE_URL` 等） | 本服务用 SQLite 文件 + 自有卷，**不附加平台数据库** |
| volumes | Docker 格式 `"源:目标[:ro]"`，**设置即整体替换（破坏性）** | 首次创建时一次性配好 |
| env_vars | 增量合并、可删 | 部署时注入 `DEBUG=false` 等 |
| access_mode | public / internal（公司 SSO）/ restricted（邮箱白名单） | 见 §7.2 |
| 健康检查 | 平台按 "running" 判定成功；应用自带 `/health` | ✅ 已有 |

---

## 3. 本地服务适配性矩阵（v2.2.5 实测）

| 维度 | 本地现状 | 容器化适配 | 结论 |
|------|---------|-----------|------|
| 架构 | React(SPA) + FastAPI 单进程 8001 同源托管（`--prod` 形态） | 单端口天然贴合容器 | ✅ |
| 健康检查 | `GET /health` → `{"status":"ok","version":"2.2.5"}` | 平台可轮询 | ✅ |
| 存储 | SQLite：`data/court_matters.db` + `data/workspaces/*/`（每用户独立） | 卷挂 `/app/data` | ✅ |
| 输出 | `outputs/`（生成结果，独立于 data/） | 卷挂 `/app/outputs`（**第二个卷**） | ✅ |
| 只读资产 | `templates/`（docx 模板）`static/`（公司/代理人 PDF） | 打进镜像 | ✅ |
| 前端产物 | `frontend/dist/` 被 `.gitignore` 忽略 | **多阶段构建** `npm ci && npm run build` | ⚠️ |
| DOCX→PDF | reportlab 平台字体探测（macOS 仿宋/宋体；Linux Noto CJK）+ `FONT_DIR` 兜底 | 容器装 `fonts-noto-cjk`（见 §5.3） | ⚠️ |
| OCR | Tesseract 系统二进制 + `chi_sim` 语言包，`chi_sim` 缺失自动降级 eng | 容器装 `tesseract-ocr tesseract-ocr-chi-sim` | ⚠️ |
| 配置 | `HOST/PORT/DEBUG/DATA_DIR/FONT_DIR/CORS_ORIGINS` 全走 pydantic-settings（.env 可覆盖） | 平台 `env_vars` 注入 | ✅ |
| 密钥 | `.env` 允许入库但无真实密钥（私有仓库策略） | 无需特殊处理；部署时以 env_vars 覆盖 | ✅ |
| 外部中间件 | 无（无 Redis / 无必需 Postgres） | 零依赖 | ✅ |
| 端口 | 固定 8001 | create `port=8001` | ✅ |

---

## 4. 部署方案（二选一，用户拍板）

### 方案 A：git_repo + dockerfile build_pack（代码即部署）

```
git push（HTTPS + token）→ thunderbox_create(source_type=git_repo, build_pack=dockerfile, subdomain=legal-court, port=8001, volumes=[...]) → thunderbox_deploy → 平台 git clone + docker build + 运行
```

- **优点**：版本可追溯、天然支持 ref/回滚、不需要本地 Docker 与推送链路
- **缺点**：平台构建行为不可见细节多；monorepo 需在**仓库根**放 Dockerfile（`COPY modules/court-doc-generator/`），语义上"一个仓库一个应用"
- **前置**：gitee HTTPS 地址 `https://gitee.com/wpmdpzch/legal.git` + Gitee 个人访问令牌（`read_repository` 权限）；仓库根 Dockerfile + .dockerignore

### 方案 B：docker_image（用户偏好：镜像部署、环境统一）

```
本地/CI：docker build -t registry.tbox.ktvsky.com/legal/court-doc-generator:2.2.5 && docker push
→ thunderbox_create(source_type=docker_image, source_url=registry.tbox.ktvsky.com/legal/court-doc-generator:2.2.5, port=8001, volumes=[...]) → thunderbox_deploy
```

- **优点**：构建环境完全自控（一次构建到处跑），不依赖平台构建行为；符合"环境统一、少出问题"
- **缺点**：需 registry 推送凭证（**待确认**：registry 是否匿名可推/需登录）；构建机需 Docker；版本靠 tag 关联
- **前置**：Dockerfile 同样是必需项（B 也用它构建）

### 公共前置：Dockerfile（多阶段，草案）

```dockerfile
# ---------- 阶段 1：前端构建 ----------
FROM node:20-alpine AS fe
WORKDIR /build
COPY modules/court-doc-generator/frontend/package*.json ./
RUN npm ci
COPY modules/court-doc-generator/frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行环境 ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data HOST=0.0.0.0 PORT=8001 DEBUG=false
# OCR + 中文字体（缺 fonts-noto-cjk 会复发 DOCX→PDF 打印空白，见 §5.3）
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY modules/court-doc-generator/requirements.txt ./
COPY modules/court-doc-generator/backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt
# 应用代码（排除 data/ outputs/ .venv .run dist node_modules，见 .dockerignore）
COPY modules/court-doc-generator/ ./
COPY --from=fe /build/dist ./frontend/dist
RUN mkdir -p /app/data /app/outputs
EXPOSE 8001
# 后端入口：backend/app（sys.path 引 generator/docx_to_pdf/pdf_merger，需 CWD=模块根）
WORKDIR /app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
```

> ⚠️ 关键细节：
> - 后端 `from app.main:app` 启动，但 `generator.py`/`docx_to_pdf.py` 在模块根（backend 经 `sys.path` 引用）→ **CWD 必须在模块根 `/app`**，且 `PYTHONPATH=/app/backend:/app`
> - 单 worker：`workspace.py` 会话互斥锁是进程内实现，多 worker 会各自成锁（生成并发保护失效）；文件缓存等也是单进程语义
> - 卷：`court-data:/app/data`、`court-output:/app/outputs`（两个卷分开挂，不要挂 `/app` 根，会遮蔽镜像内只读资产）
> - 平台 SSO（internal）由反代层处理，应用无感；应用自带登录保留

---

## 5. 本地缺口明细（不满足部署条件的逐项清单）

### 5.1 阻塞项

1. **无 Dockerfile / .dockerignore**（仓库根）：两方案公共前置。
   `.dockerignore` 必须排除：`**/node_modules` `**/dist`（阶段1 自行构建）`**/.venv` `data/` `outputs/` `.run/` `.pytest-data/` `**/.git`
2. **git remote 是 SSH**（`git@gitee.com:wpmdpzch/legal.git`）：`thunderbox_create` 的 git 预检走 HTTPS + token，SSH 格式直接拒绝。→ 需用户提供 Gitee 个人令牌（`read_repository` 最小权限）
3. **镜像推送通道未知**（仅方案 B）：`registry.tbox.ktvsky.com` 是否允许匿名/需登录推送 → 部署前与平台确认

### 5.2 必须项（不影响环境搭建但部署前必须解决）

4. **数据卷双挂载**：`settings.OUTPUTS_DIR = MODULE_ROOT/outputs` 独立于 `DATA_DIR` → 两个卷；否则容器重启后生成结果丢失（数据库在卷里、outputs 在临时层）
5. **启动参数细节**：`uvicorn app.main:app` + CWD=模块根 + `PYTHONPATH`；单 worker（互斥锁是进程内）
6. **生产变量注入**：`DEBUG=false`（当前默认 `true`，FastAPI 会输出请求日志+异常栈）、`FONT_DIR` 通常不需要（装了 fonts-noto-cjk 即可自动探测）

### 5.3 容器环境依赖（Dockerfile 内补齐）

7. **fonts-noto-cjk（必须）**：`docx_to_pdf.py` 平台探测链 Linux 靠 Noto CJK；缺它回退 reportlab CID 伪字体 → **04/05 打印空白**（2026-08 已踩坑，见代码注释）。`.env.example` 亦明确"Linux 生产关键"
8. **tesseract-ocr + chi_sim**：`scan_service._TESSERACT = shutil.which("tesseract")` 兜底 `/opt/homebrew/bin/tesseract`（macOS 路径）→ 容器内 must which 到；`chi_sim` 缺失自动降级 eng（有兜底，识别率降）

### 5.4 验证项（部署前容器内回归）

9. **Linux 全链路单测**：`pytest tests/`（docx→pdf / pdf_merger / preview / scan / workspace）在镜像内跑一遍——字体探测、PDF 渲染、OCR 语言包均与 macOS 不同
10. **e2e 冒烟**：注册专用验证账号（`verify_*`，§7 测试隔离规范）→ 建案 → 生成 7 份材料 → 合并 PDF 在线预览 → 删除验证账号

### 5.5 非缺口（已确认 OK）

- CORS：生产同源（相对路径 `/api/v1`），无需改
- 模板/静态文件：只读打进镜像即可
- .env：无真实密钥，已入库策略无需动
- ZIP 打包 / PDF.js 预览：纯 Python/静态资源
- 时区：应用内无固定时区依赖（时间戳显示本地格式，容器 TZ 可后续 env 补充）

---

## 6. 域名规划（法务 `legal` 体系）

平台现状：仅支持 `<前缀>.tbox.ktvsky.com` 子域（实测 `thunderbox_check target=domain`）。规划：

| 用途 | 域名 | 状态 |
|------|------|------|
| 法务顶级（门户预留） | `legal.tbox.ktvsky.com` | ✅ 实测可用 |
| **出庭生成器（本需求）** | **`legal-court.tbox.ktvsky.com`** | ✅ 实测可用 |
| 诉讼业务平台 | `legal-litigation.tbox.ktvsky.com` | 待部署时 check |
| 案件情报 | `legal-intel.tbox.ktvsky.com` | 待部署时 check |
| 雷盒控制台 | `legal-box.tbox.ktvsky.com` | 待规划 |

**命名规范**：`legal-<模块短名>` —— "legal" 词根后接子模块名，符合同法务统一品牌；
备选方案：`<子模块>.legal.tbox.ktvsky.com`（如 `court.legal.tbox.ktvsky.com`，实测也可用，但 4 段过长、语义为"子模块在 legal 前"）。
> 注：平台暂不支持独立顶级域 `.legal`（无自定义域名绑定能力）；若未来平台开放，可再映射。

---

## 7. 数据与安全

### 7.1 数据持久化

- 卷 1 `court-data:/app/data`：中心 DB + workspaces（每用户独立 SQLite）+ agents 上传
- 卷 2 `court-output:/app/outputs`：生成结果
- 备份：仍按 §4.4 既有机制（sqlite 备份），卷层面由平台快照策略兜底（能力待查）

### 7.2 访问模式决策（待用户拍板）

| 选项 | 说明 | 推荐度 |
|------|------|--------|
| `internal`（公司 SSO） | 网络层加公司登录；应用自带用户注册/登录继续生效（平台不注入用户身份，两层并存） | ⭐ 推荐（多一层保护，PII 系统） |
| `restricted`（邮箱白名单） | 需维护白名单与变更流程 | 可选 |
| `public` | 完全开放，仅靠应用自带登录 | 不推荐（PII 数据，§6 安全红线） |

### 7.3 PII 基线（AGENTS.md §6）

- 容器内无硬编码真实 PII（测试占位符制度延续）
- 日志遮罩 `mask_id_card()` 已有；平台日志不打印敏感字段（生产 DEBUG=false）
- 前端静态资源无密钥

---

## 8. 待用户决策项

> 状态：2026-08-24 用户已拍板 D1-D3（D4/D5 待办）

| # | 决策 | 结论 | 影响 |
|---|------|------|------|
| D1 | 部署路径 | ✅ **B. 镜像推送**（`docker_image` 推 `registry.tbox.ktvsky.com`） | 需 registry 推送凭证；构建机需 Docker |
| D2 | 域名 | ✅ **`legal-court.tbox.ktvsky.com`**（实测可用） | 创建时 subdomain=legal-court |
| D3 | 访问模式 | ✅ **public**（应用自带注册/登录 + workspace 隔离做防线） | ❗ PII 系统提示：public 下仅应用层认证，建议留意平台若开放 internal 后再切换；注册页可考虑暂不开放对外注册（见 D5 关联） |
| D4 | 镜像仓库凭证 | ⏳ 待平台确认 | `registry.tbox.ktvsky.com` 推送需登录/匿名？ |
| D5 | 代码变更边界 | 默认纯工程件；`OUTPUTS_DIR 收敛入 DATA_DIR` 重构仅在挂卷不便时启动 | 影响未来维护 |

---

## 9. 下一步（已确认 D1-D3，待 D4 凭证）

1. 登记 backlog（`proposed`）→ 已登记见 docs/requirements/backlog.md；决策已定：B 镜像推送 / legal-court / public
2. 编写 Dockerfile + .dockerignore（方案 B 同样需要；本地 docker build + tag registry.tbox.ktvsky.com/legal/court-doc-generator:2.2.5）
3. **待确认**：registry.tbox.ktvsky.com 推送凭证（登录 vs 匿名）→ 用户向平台确认后即可 push
4. 本地 `docker build` + 容器内跑 `pytest tests/` 全量回归 + e2e 冒烟（§5.4）
5. `thunderbox_create`（source_type=docker_image, subdomain=legal-court, port=8001, volumes 双卷）→ `thunderbox_deploy` → 验证 `/health` + 冒烟
6. 域名/卷/访问模式落地，更新本模块 docs/README.md 与 DEPLOYMENT.md