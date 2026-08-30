"""FastAPI 主入口。"""
import hashlib
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import settings
from app.core.database import init_db
from app.migration import run_migration

# 固定 shared workspace ID（单租户模式）
SHARED_WORKSPACE_ID = "shared"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # FORCE_MIGRATION=1 时强制重新迁移（删除 shared workspace 再重建）
    data_dir = settings.DATA_DIR
    if os.environ.get("FORCE_MIGRATION") == "1":
        shared_db = data_dir / "workspaces" / SHARED_WORKSPACE_ID / "court_matters.db"
        if shared_db.exists():
            shared_db.unlink()
            print(f"[startup] FORCE_MIGRATION=1: removed {shared_db}")
        shared_ws_dir = data_dir / "workspaces" / SHARED_WORKSPACE_ID
        agents_dir = shared_ws_dir / "agents"
        if agents_dir.exists():
            import shutil
            shutil.rmtree(agents_dir)
            print(f"[startup] FORCE_MIGRATION=1: removed {agents_dir}")
    # 启动时迁移多 workspace 数据到 shared workspace（幂等）
    result = run_migration(data_dir)
    print(f"[startup] migration done: {result}")
    yield


app = FastAPI(
    title="出庭手续生成器 API",
    version="2.2.5",
    description="court-doc-generator FastAPI 后端（案件查看/预览/OCR 扫描/二次确认）",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境全开，生产环境由 Nginx 反代
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.2.5"}


def mount_frontend_static(app_obj: FastAPI, dist_dir: Path) -> bool:
    """把前端 build 产物挂到 app（生产形态，真实文件 + SPA fallback）。

    dist 不存在时返回 False（开发模式前端走 vite dev server，后端保持纯 API）。
    """
    if not dist_dir.is_dir():
        return False
    dist_root = dist_dir.resolve()
    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app_obj.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app_obj.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA fallback：真实文件直传，API 前缀 404，其余未知路径回 index.html。"""
        if full_path.startswith("api/") or full_path == "health":
            raise HTTPException(status_code=404, detail="Not Found")
        # 防路径穿越：解析后必须仍在 dist 目录内
        resolved = (dist_root / full_path).resolve()
        if resolved.is_relative_to(dist_root) and resolved.is_file():
            return FileResponse(str(resolved))
        return FileResponse(str(dist_root / "index.html"))

    return True


# 生产形态：前端 build 产物由后端统一托管（dist 存在时启用）
mount_frontend_static(app, settings.FRONTEND_DIST_DIR)


@app.exception_handler(HTTPException)
async def http_exc(_req: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": -1, "message": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exc(_req: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": -1, "message": "服务器内部错误", "detail": str(exc)},
    )
