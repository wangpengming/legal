# Thunderbox Console 架构方案

> 2026-08-27 · 方案 A：FastAPI + MCP 直接封装

---

## 1. 背景

Thunderbox Console 的目标是：
- 给真人用户提供可视化 UI（代替 Thunderbox 平台 Web 控制台）
- 同时让 AI Agent 能通过 MCP 工具操作 Thunderbox

原型图已完成（`prototype.html`），包含：应用列表 / 创建向导 / 应用详情 / 数据库 / 域名探测等页面。

核心问题：**MCP 是给 AI Agent 用的协议（JSON-RPC over HTTP），真人 UI 如何接入？**

---

## 2. 方案 A：FastAPI + MCP 直接封装

### 2.1 架构

```
                          ┌─ 人类用户：浏览器 HTML UI
                          │     (prototype.html)
                          │
浏览器 / AI Agent  ──HTTP──┤
                          │     FastAPI 后端
                          │     (端口 18502)
                          │       │
                          │       ├── /api/apps         (列表/详情/启停/部署)
                          │       ├── /api/domains       (域名探测)
                          │       ├── /api/db/sql        (SQL 执行)
                          │       └── /api/config        (配置管理)
                          │
                          └─ Python MCP 封装层
                              (thunderbox_mcp.py)
                                  │
                                  └── http.client.HTTPSConnection
                                      Bearer Token 认证
                                      Mcp-Session-Id 管理
                                              │
                                              ↓ HTTPS
                                      api-box.tbox.ktvsky.com/mcp
                                              │
                                              ↓
                                      Thunderbox MCP API
                                      (thunderbox v0.2.0)
```

### 2.2 认证机制（已验证）

MCP endpoint 使用 **Bearer Token** 认证：

```
URL:     https://api-box.tbox.ktvsky.com/mcp
Token:   Bearer <token>
Headers: Content-Type: application/json
         Accept: application/json, text/event-stream
         Authorization: Bearer <token>
```

**MCP Session 管理**：
1. `POST /mcp` (initialize) → 响应头返回 `mcp-session-id`
2. 后续所有请求必须带 `Mcp-Session-Id: <session_id>` header
3. 必须用 **HTTP 持久连接**（`http.client.HTTPSConnection`），否则 session 不跨请求

### 2.3 MCP Session 生命周期

```python
import http.client
import json

TOKEN = "Bearer <token>"
conn = http.client.HTTPSConnection("api-box.tbox.ktvsky.com")

# 1. Initialize（获取 session_id）
conn.request("POST", "/mcp", body=json.dumps({...}), headers=HEADERS)
resp = conn.getresponse()
session_id = resp.getheader("mcp-session-id")
body = parse_sse(resp.read())

# 2. Initialized notification（带 session_id）
conn.request("POST", "/mcp", body=json.dumps({...}), headers={**HEADERS, "Mcp-Session-Id": session_id})

# 3. 所有 tool call（带 session_id）
conn.request("POST", "/mcp", body=json.dumps({...}), headers={**HEADERS, "Mcp-Session-Id": session_id})
```

### 2.4 文件结构

```
modules/thunderbox-console/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── thunderbox_mcp.py    # MCP 封装层（核心）
│   └── routers/
│       ├── apps.py          # /api/apps
│       ├── db.py            # /api/db
│       └── domains.py       # /api/domains
├── frontend/
│   └── src/
│       └── App.tsx          # React 入口（替代 prototype.html）
├── Dockerfile
├── requirements.txt
└── docs/
    └── PLAN-A.md            # 本文档
```

---

## 3. MCP 工具映射（13 Tools → REST API）

| MCP Tool | REST Endpoint | 说明 |
|----------|--------------|------|
| `thunderbox_query` | `GET /api/apps` | 列表+详情 |
| `thunderbox_query` (单app) | `GET /api/apps/{id}` | 单应用详情 |
| `thunderbox_query` (logs) | `GET /api/apps/{id}/logs` | 运行时日志 |
| `thunderbox_query` (build_logs) | `GET /api/apps/{id}/build-logs` | 构建日志 |
| `thunderbox_query` (health) | `GET /api/apps/{id}/health` | 健康检查 |
| `thunderbox_create` | `POST /api/apps` | 创建应用 |
| `thunderbox_deploy` | `POST /api/apps/{id}/deploy` | 部署/更新 |
| `thunderbox_control` | `POST /api/apps/{id}/control` | 启/停/取消 |
| `thunderbox_rollback` | `POST /api/apps/{id}/rollback` | 回滚 |
| `thunderbox_config` | `GET|PATCH /api/apps/{id}/config` | 配置读写 |
| `thunderbox_check` | `GET /api/domains/check` | 域名可用性 |
| `thunderbox_db_add` | `POST /api/apps/{id}/database` | 挂载数据库 |
| `thunderbox_db_remove` | `DELETE /api/apps/{id}/database` | 卸载数据库 |
| `thunderbox_sql` | `POST /api/apps/{id}/sql` | SQL 查询 |
| `thunderbox_describe_schema` | `GET /api/apps/{id}/schema` | 表结构 |
| `thunderbox_list_tables` | `GET /api/apps/{id}/tables` | 表列表 |
| `thunderbox_apply_migration` | `POST /api/apps/{id}/migrations` | 执行迁移 |

---

## 4. 与方案 B/C 的对比

| 维度 | 方案 A（当前） | 方案 B（直连 MCP） | 方案 C（纯前端） |
|------|--------------|------------------|----------------|
| AI 调用方式 | REST API 或 MCP tool | 直接 MCP stdio | REST API |
| 前端技术 | FastAPI + HTML | MCP Server 直连 | 静态 HTML + Proxy |
| 部署复杂度 | 中（单容器） | 高（多进程） | 低（纯前端） |
| MCP 封装 | Python 库（可复用） | N/A | N/A |
| 确定性调用 | ✅ REST 固定端点 | ✅ MCP tool | ✅ REST |
| **推荐度** | **✅ 首选** | ❌ 不适合 HTTP | ❌ 无后端代理 |

---

## 5. 关键实现细节

### 5.1 MCP Session 池

为每个请求创建独立 session 会导致性能问题。生产环境应使用 session 池：

```python
class MCPSessionPool:
    def __init__(self, token: str, max_sessions: int = 10):
        self._token = token
        self._sessions: dict[str, tuple[HTTPSConnection, str]] = {}
        self._lock = threading.Lock()

    def get_session(self) -> tuple[HTTPSConnection, str]:
        """获取或创建 session"""
        with self._lock:
            # 复用或新建
            ...

    def release(self, conn: HTTPSConnection):
        """归还连接"""
        conn.close()
```

### 5.2 错误重试

MCP Session 可能过期（`400 Server not initialized`），需要自动重连：

```python
def mcp_call_with_retry(conn, payload, session_id, max_retries=2):
    for attempt in range(max_retries):
        resp = mcp_call(conn, payload, session_id)
        if "not initialized" in str(resp.error):
            session_id = reinitialize(conn)  # 重新初始化
            continue
        return resp
    raise MCPError("Max retries exceeded")
```

### 5.3 异步支持

FastAPI 是 async 的，MCP 调用是同步 IO。可用 `run_in_executor` 避免阻塞：

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

@app.get("/api/apps")
async def list_apps():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, mcp_query_apps)
```

---

## 6. 安全考量

| 风险 | 缓解措施 |
|------|---------|
| Token 泄露 | 存 `.env`，不写入代码 |
| Session 劫持 | Session 与 IP 绑定（平台侧实现） |
| 恶意 SQL | 数据库仅允许 SELECT（不含 DDL） |
| 外部访问 | Thunderbox 平台强制 `access_mode=public` |

---

## 7. 部署流程

```bash
# 1. 构建 Docker 镜像
cd modules/thunderbox-console
docker build -t thunderbox-console .

# 2. 通过 Thunderbox MCP 创建应用
thunderbox_create(
    name="thunderbox-console",
    source_type="docker_image",
    source_url="<image>",
    port=80,
    access_mode="public"
)

# 3. 部署
thunderbox_deploy(app_id=xxx)

# 4. 注入环境变量
thunderbox_config(app_id=xxx, env_vars=[
    {"key": "THUNDERBOX_TOKEN", "value": "<token>"}
])
```

---

## 8. 实现状态

- ✅ Bearer Token 认证已验证
- ✅ MCP Session 管理已验证
- ✅ Python `http.client` 持久连接已验证
- ✅ `thunderbox_mcp.py` 核心库实现（545 行）
- ✅ `main.py` FastAPI 实现（397 行）
- ✅ REST API 全部端点测试通过（/health, /api/apps, /api/apps/{id}/config, /api/domains/check）
- ⏳ 前端 UI 接入（待实现）
- ⏳ Dockerfile 编写
- ⏳ Thunderbox 部署

## 9. 直接调用 MCP 的正确方式（无 AI 介入）

### 9.1 Python 库方式（推荐）

```python
from thunderbox_mcp import ThunderboxMCP

# 方式 1: context manager（自动管理连接）
with ThunderboxMCP(token="<Bearer>") as client:
    apps = client.list_apps()
    print(len(apps))  # 确定性返回，无需 AI 思考

# 方式 2: 手动管理
client = ThunderboxMCP(token="<Bearer>")
client.connect()
try:
    apps = client.list_apps()
finally:
    client.close()
```

### 9.2 REST API 方式（前端/AI 通用）

```
GET  /api/apps                       # 列表
GET  /api/apps/{id}                  # 详情
POST /api/apps                       # 创建
POST /api/apps/{id}/deploy          # 部署
POST /api/apps/{id}/control         # 启停
POST /api/apps/{id}/rollback        # 回滚
GET  /api/apps/{id}/logs            # 日志
GET  /api/apps/{id}/build-logs      # 构建日志
GET  /api/apps/{id}/health          # 健康检查
GET  /api/apps/{id}/config          # 配置
PATCH /api/apps/{id}/config         # 更新配置
GET  /api/domains/check?subdomain=x # 域名检测
```

### 9.3 AI Agent 方式

AI Agent 可以直接调用 `thunderbox_mcp.py` 的方法，或通过 MCP 工具调用，
与 REST API 完全等价：

```
AI 调用: thunderbox_query({})      =  REST: GET /api/apps
AI 调用: thunderbox_deploy({...})  =  REST: POST /api/apps/{id}/deploy
AI 调用: thunderbox_control({...}) =  REST: POST /api/apps/{id}/control
```

**核心设计原则**：同一套代码，AI（通过 MCP）和人（通过 UI）共用，无需 AI 思考。
