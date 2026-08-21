"""FastAPI 主入口。"""
import hashlib
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时不需要初始化特定 workspace，workspace 在首次登录时初始化
    yield


app = FastAPI(
    title="出庭手续生成器 API",
    version="1.1.0",
    description="court-doc-generator FastAPI 后端（v1.1.0 案件查看/预览/二次确认）",
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
    return {"status": "ok", "version": "1.1.0"}


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
