"""
Thunderbox Console — FastAPI 后端
=================================
REST API 封装层，调用 thunderbox_mcp.py 提供给前端 UI。

入口：ThunderboxMCP(client) → REST Endpoints → JSON → 前端
"""

from __future__ import annotations

import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:
    from backend.thunderbox_mcp import ThunderboxMCP, App, MCPError
except ImportError:
    from thunderbox_mcp import ThunderboxMCP, App, MCPError

try:
    from backend.audit import audit_middleware, query_audit, _init_db
except ImportError:
    from audit import audit_middleware, query_audit, _init_db

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 全局 MCP 客户端
# ---------------------------------------------------------------------------

_token: str = ""
_client: Optional[ThunderboxMCP] = None


def get_client() -> ThunderboxMCP:
    global _token, _client
    if _client is None:
        _token = os.environ.get(
            "THUNDERBOX_TOKEN",
            "581e571d13a34b750b2c9fef2d8342ad40491952659860db0cb8b2637504846a",
        )
        _client = ThunderboxMCP(token=_token)
        _client.connect()
        log.info("MCP client connected (token prefix: %s...)", _token[:8])
    return _client


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化审计数据库
    try:
        await _init_db()
        log.info("Audit DB initialized at %s", _DB_PATH)
    except Exception as e:
        log.warning("Audit DB init failed: %s (non-fatal)", e)
    yield
    global _client
    if _client:
        _client.close()
        _client = None
        log.info("MCP client closed")


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Thunderbox Console API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 审计中间件（拦截所有写操作）
app.middleware("http")(audit_middleware)

# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class CreateAppRequest(BaseModel):
    name: str = Field(..., description="应用名（用于子域名）")
    source_type: str = Field(..., description="'git_repo' 或 'docker_image'")
    source_url: str = Field(..., description="仓库 URL 或镜像名")
    build_pack: Optional[str] = Field(None, description="'dockerfile'|'nixpacks'|'spa'|'static'")
    port: Optional[int] = Field(None, description="监听端口")
    ref: str = Field("main", description="分支")
    git_token: Optional[str] = Field(None, description="Git token（私有仓库）")
    volumes: Optional[list] = Field(None, description="数据卷列表")


class ControlAppRequest(BaseModel):
    action: str = Field(..., description="'start'|'stop'|'cancel'")


class UpdateConfigRequest(BaseModel):
    access_mode: Optional[str] = Field(None, description="'public'|'internal'|'restricted'")
    ref: Optional[str] = Field(None, description="默认分支")
    env_vars: Optional[list] = Field(None, description="环境变量列表")
    volumes: Optional[list] = Field(None, description="数据卷列表")
    add_emails: Optional[list] = Field(None, description="添加邮箱白名单")
    remove_emails: Optional[list] = Field(None, description="移除邮箱白名单")
    manager_email: Optional[str] = Field(None, description="协作者邮箱")
    manager_action: Optional[str] = Field(None, description="'add'|'remove'")


class SQLRequest(BaseModel):
    sql: str = Field(..., description="SQL 语句")


class MigrationRequest(BaseModel):
    name: str = Field(..., description="迁移名称")
    sql: str = Field(..., description="SQL 语句")


class AddDatabaseRequest(BaseModel):
    database: str = Field("postgres", description="'postgres'|'sqlite'")


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _app_to_dict(a: App) -> dict:
    d = a.to_dict()
    # 解析 volumes JSON string
    if d.get("volumes") and isinstance(d["volumes"], str):
        import json
        try:
            d["volumes"] = json.loads(d["volumes"])
        except Exception:
            d["volumes"] = []
    return d


def _sync_call(fn, *args, **kwargs):
    """在同步线程中调用 MCP 函数（FastAPI async handler 用）"""
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# 应用列表/详情
# ---------------------------------------------------------------------------

@app.get("/api/apps")
async def list_apps():
    """列出所有应用"""
    client = get_client()
    apps = await asyncio.to_thread(_sync_call, client.list_apps)
    return [_app_to_dict(a) for a in apps]


@app.get("/api/apps/{app_id}")
async def get_app(app_id: str):
    """获取单个应用详情"""
    client = get_client()
    app_obj = await asyncio.to_thread(_sync_call, client.get_app, app_id)
    if app_obj is None:
        raise HTTPException(status_code=404, detail=f"App not found: {app_id}")
    return _app_to_dict(app_obj)


@app.get("/api/apps/{app_id}/logs")
async def get_app_logs(app_id: str, since: Optional[str] = None):
    """获取运行时日志"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.get_app_logs, app_id, since)


@app.get("/api/apps/{app_id}/build-logs")
async def get_build_logs(app_id: str):
    """获取构建日志"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.get_build_logs, app_id)


@app.get("/api/apps/{app_id}/health")
async def get_health(app_id: str):
    """健康检查"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.get_health, app_id)


@app.get("/api/apps/{app_id}/rollback-history")
async def get_rollback_history(app_id: str):
    """获取部署历史"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.get_rollback_history, app_id)


@app.get("/api/apps/{app_id}/config")
async def get_app_config(app_id: str):
    """获取应用配置"""
    client = get_client()
    cfg = await asyncio.to_thread(_sync_call, client.get_app_config, app_id)
    return {
        "ref": cfg.ref,
        "access_mode": cfg.access_mode,
        "bypass_trusted_ips": cfg.bypass_trusted_ips,
        "env_vars": cfg.env_vars,
        "volumes": cfg.volumes,
        "managers": cfg.managers,
    }


# ---------------------------------------------------------------------------
# 应用操作
# ---------------------------------------------------------------------------

@app.post("/api/apps")
async def create_app(req: CreateAppRequest):
    """创建应用"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.create_app,
        name=req.name, source_type=req.source_type, source_url=req.source_url,
        build_pack=req.build_pack, port=req.port, ref=req.ref,
        git_token=req.git_token, volumes=req.volumes,
    )


@app.post("/api/apps/{app_id}/deploy")
async def deploy_app(app_id: str, ref: Optional[str] = None):
    """部署/更新应用"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.deploy_app, app_id, ref)


@app.post("/api/apps/{app_id}/control")
async def control_app(app_id: str, req: ControlAppRequest):
    """启/停/取消应用"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.control_app, app_id, req.action)


@app.post("/api/apps/{app_id}/rollback")
async def rollback_app(app_id: str, target: Optional[int] = None):
    """回滚应用"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.rollback_app, app_id, target)


@app.patch("/api/apps/{app_id}/config")
async def update_app_config(app_id: str, req: UpdateConfigRequest):
    """更新应用配置"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.update_config, app_id,
        access_mode=req.access_mode, ref=req.ref, env_vars=req.env_vars,
        volumes=req.volumes, add_emails=req.add_emails, remove_emails=req.remove_emails,
        manager_email=req.manager_email, manager_action=req.manager_action,
    )


# ---------------------------------------------------------------------------
# 域名
# ---------------------------------------------------------------------------

@app.get("/api/domains/check")
async def check_domain(subdomain: str):
    """检测域名是否可用"""
    client = get_client()
    result = await asyncio.to_thread(_sync_call, client.check_domain, subdomain)
    return {
        "subdomain": result.subdomain,
        "domain": result.domain,
        "available": result.available,
    }


# ---------------------------------------------------------------------------
# 数据库
# ---------------------------------------------------------------------------

@app.post("/api/apps/{app_id}/database")
async def add_database(app_id: str, req: AddDatabaseRequest = None):
    """挂载数据库"""
    client = get_client()
    db_type = req.database if req else "postgres"
    return await asyncio.to_thread(_sync_call, client.add_database, app_id, db_type)


@app.delete("/api/apps/{app_id}/database")
async def remove_database(app_id: str):
    """卸载数据库"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.remove_database, app_id)


@app.get("/api/apps/{app_id}/tables")
async def list_tables(app_id: str):
    """列出数据库表"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.list_tables, app_id)


@app.get("/api/apps/{app_id}/schema")
async def describe_schema(app_id: str):
    """获取数据库表结构"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.describe_schema, app_id)


@app.post("/api/apps/{app_id}/sql")
async def execute_sql(app_id: str, req: SQLRequest):
    """执行 SQL"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.execute_sql, app_id, req.sql)


@app.post("/api/apps/{app_id}/migrations")
async def apply_migration(app_id: str, req: MigrationRequest):
    """执行迁移（幂等）"""
    client = get_client()
    return await asyncio.to_thread(_sync_call, client.apply_migration, app_id, req.name, req.sql)


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------

@app.get("/api/audit")
async def get_audit_logs(
    page: int = 1,
    page_size: int = 50,
    action: Optional[str] = None,
    app_id: Optional[str] = None,
    result: Optional[str] = None,
):
    """查询审计日志（分页）"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 50
    return await query_audit(
        page=page,
        page_size=page_size,
        action=action,
        app_id=app_id,
        result=result,
    )


# ---------------------------------------------------------------------------
# 静态文件（前端）
# ---------------------------------------------------------------------------

_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(_frontend_dir, "dist", "index.html"))


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "18502"))
    uvicorn.run(app, host="0.0.0.0", port=port)
