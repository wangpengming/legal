# 部署手册 · court-doc-generator

> 版本：2.2.5 ｜ 生产形态：**后端运行**（FastAPI 单进程统一托管前端 build 产物，单端口对外）
> 适用：Linux 服务器（Ubuntu/Debian 示例路径 `/opt/legal`）；macOS 本机验证步骤一致（路径替换即可）

---

## 1. 部署形态总览

```
浏览器 ──► :8001 FastAPI/Uvicorn（唯一对外进程）
              ├── /api/v1/*       业务 API
              ├── /assets/*       前端静态资源（挂载 frontend/dist/assets）
              ├── /               页面路由（SPA fallback → index.html）
              └── /health         健康检查
数据：模块根 data/（SQLite + workspaces）→ 需持久化的唯一数据目录
日志：手动模式 backend/.run/backend.log（5MB × 5 份轮转）；systemd 模式 journalctl
```

| 要点 | 说明 |
|------|------|
| 前端产物 | `frontend/dist/` 由 `npm run build` 生成。**dist/ 被根 .gitignore 忽略**，随代码库不会自动到达 server，需单独携带（构建机 scp）或在 server 上构建（见 §2.3） |
| 端口 | 8001（与 `shared/config/ports.yaml` 注册一致） |
| 域名 | `legal-court.tbox.ktvsky.com`（thunderbox，唯一域名，见 §8 与本模块 `module.yaml`） |
| 同源 | 前端 API 请求为相对路径 `/api/v1`，生产无跨域问题 |
| 进程模型 | 手动模式 `bin/start.py` 用 `os.fork()` 后台化；systemd 模式直接托管 uvicorn（Type=simple），两者二选一 |

---

## 2. 安装步骤（手动模式，推荐先跑通）

### 2.1 获取代码

```bash
sudo mkdir -p /opt/legal && cd /opt/legal
git clone <repo> /opt/legal          # 或 scp -r 本地目录
cd modules/court-doc-generator
```

### 2.2 后端依赖（Python 3.10+）

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r ../requirements.txt   # Word/PDF 处理（docx_to_pdf/pdf_merger）
.venv/bin/pip install -r requirements.txt      # FastAPI/Uvicorn 等
```

> 两个 requirements 都要装：模块根那份供 `generator.py/docx_to_pdf.py`（经 sys.path 引用），backend 那份供 API 服务。

### 2.3 前端产物（dist）

方式 A（推荐，构建机产出）——本地执行后把 **整个 `frontend/dist/`** 目录拷贝到服务器：

```bash
cd frontend && npm ci && npm run build
scp -r frontend/dist server:/opt/legal/modules/court-doc-generator/frontend/
```

方式 B（服务器上构建，需 Node 18+）：

```bash
sudo apt install -y nodejs npm
cd /opt/legal/modules/court-doc-generator/frontend
npm ci && npm run build
```

### 2.4 配置 .env

```bash
cd /opt/legal/modules/court-doc-generator/backend
cp .env.example .env      # 按需修改（HOST/PORT/DEBUG/DATA_DIR/FONT_DIR）
```

### 2.5 启动 / 停止 / 查询

```bash
cd /opt/legal/modules/court-doc-generator

python3 bin/start.py --prod     # 🏭 生产启动（校验 dist 存在，单起后端）
python3 bin/status.py           # 📊 状态：端口/PID/健康检查/日志大小
python3 bin/stop.py             # 🛑 停止全部服务
python3 bin/restart.py          # 🔄 重启
```

启动成功标志：`🌐 生产模式：前端由后端统一托管，浏览器访问 http://<server>:8001`

> perf 提示：生产首次请求较慢（docx_to_pdf reportlab 注册字体等），属正常预热。

---

## 3. systemd 托管（生产推荐）

手动模式在 SSH 会话退出后进程仍在（已 fork 脱壳），但无崩溃自愈。生产请用 systemd：

```bash
sudo cp docs/court-doc-generator.service.example \
     /etc/systemd/system/court-doc-generator.service
# 编辑该文件：路径 / 用户（www-data）按实际调整，补齐 data/outputs/.run 的属主
sudo systemctl daemon-reload
sudo systemctl enable --now court-doc-generator
systemctl status court-doc-generator     # 状态
journalctl -u court-doc-generator -f     # 实时日志
```

> systemd 模式下**不要**再跑 `bin/start.py` 等四件套（避免端口占用冲突）；启停统一用 `systemctl`。

---

## 4. 日志与运维

### 4.1 日志位置（手动模式）

| 文件 | 内容 |
|------|------|
| `backend/.run/backend.log` | 后端 API 全部 stdout/stderr（生产唯一日志源） |
| `frontend/.run/frontend.log` | 仅 dev 模式（`npm run dev`）存在；生产无前端进程，此文件不存在属正常 |

查看方式：

```bash
tail -f backend/.run/backend.log        # 实时跟踪
tail -100 backend/.run/backend.log      # 最近 100 行
python3 bin/status.py                   # 附带显示日志文件大小
```

### 4.2 日志轮转

- 触发：每次 `bin/start.py` 启动时，若 `backend.log` 超过 **5MB** 自动归档；
- 保留：**5 份**（`backend.log.1` 最新 → `.5` 最旧，旧档删除）；
- 启动输出可见 `🔄 日志轮转：backend.log 已归档为 backend.log.1（保留 5 份）`。

systemd 模式由 journald 管理，按容量/时间裁剪：`journalctl --vacuum-size=200M`。

### 4.3 中文字体（生产 Linux 关键）

docx_to_pdf 自动探测多平台候选字体（macOS Songti / Linux Noto+文泉驿 / Windows 宋体），全部缺失时回退 reportlab 内置 CID（部分系统可能空白）。

生产 Linux 推荐二选一：

```bash
# 方式 1：装系统字体（推荐）
sudo apt install -y fonts-noto-cjk

# 方式 2：指定字体目录（FONT_DIR 优先级最高，命中即独占使用）
echo 'FONT_DIR=/usr/share/fonts/truetype/noto' >> backend/.env
```

### 4.4 数据备份

唯一持久化目录为模块根 `data/`（SQLite + 各 workspace 文件），备份：

```bash
# 停写窗口或直接 sqlite 备份
tar czf court-data-$(date +%F).tar.gz -C /opt/legal/modules/court-doc-generator data
```

---

## 5. 健康检查与排障

```bash
curl -s http://localhost:8001/health
# {"status":"ok","version":"2.2.5"}
```

| 症状 | 原因 / 处置 |
|------|-------------|
| 首页 404 / 空页 | `frontend/dist` 缺失：按 §2.3 补 dist 后重启 |
| 访问 `:8001` 是 API 而非页面 | 同左，dist 未就位时 SPA fallback 不注册 |
| 启动提示端口占用 | 8001 被占则自动 +1；`bin/stop.py` 后重试，或 `lsof -i :8001` 排查 |
| 生成的 PDF 中文空白 | 中文字体缺失：按 §4.3 处理 |
| 生成按钮卡住提示「正在生成」 | 同案号并发互斥锁（正常防护，稍后重试） |
| systemd 起不来 | `journalctl -u court-doc-generator -e` 看报错；多为路径/属主/.env 语法 |

---

## 6. 安全红线（§6 摘要）

- `.env` 可随代码库提交**但严禁写入真实密钥**；本模块无密钥配置，FONT_DIR 等为普通配置；
- 前端构建 `dist/` 与 `data/`、`outputs/`、`.run/` 均不入库，部署时单独处理；
- PII（身份证/手机号/合同）仅存在于运行数据与生成产物，随 `data/` 一并备份，勿外传；
- 对外部署建议前置 Nginx 做 TLS 与限流（本手册不覆盖，可作为后续主题）。

---

## 7. 相关文件

| 文件 | 作用 |
|------|------|
| `bin/start.py --prod` | 生产启动（校验 dist） |
| `bin/{stop,status,restart}.py` | 停/查/重启 |
| `backend/bin/*` | 后端单服务四件套（手动模式内部调用） |
| `backend/.env.example` | 环境变量模板 |
| `docs/court-doc-generator.service.example` | systemd 单元样例 |
| `backend/app/core/config.py` | Settings（.env 字段来源） |

---

## 8. 云平台部署（thunderbox / 雷石盒子）

云平台部署统一走雷石 **thunderbox**，与本地/服务器（systemd）模式并存：

- **本模块域名（唯一）**：`legal-court.tbox.ktvsky.com` · `access_mode=internal`
  - ⚠️ `legal-court` 当前被遗留应用占用，**待控制台回收**；回退候选：`legal-court-generator` / `legal-courtdocs`
- **代码来源**：**仅支持 GitHub** —— 部署前须先把代码推送到 GitHub 仓库（Push 需用户授权）
- **平台信息**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`
- **健康端点**：`/health`（返回 `{"status":"ok","version":"2.2.5"}`）

> 🔴 **域名规则**：每个模块**有且仅有一个域名**，不得随意创建；域名统一登记 `shared/config/domains.yaml`（详见 `AGENTS.md §10.4.5`）。
> 📖 系统级 thunderbox 手册：[`docs/deployment-thunderbox.md`](../../../docs/deployment-thunderbox.md)

**部署流程**（首次）：查重 `thunderbox_check` → 创建 `thunderbox_create`（携 `subdomain`）→ 登记 `domains.yaml` → `thunderbox_config` 注入环境变量 → `thunderbox_deploy`（GitHub 构建）→ `thunderbox_query` 验证。