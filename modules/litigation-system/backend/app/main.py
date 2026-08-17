"""FastAPI 应用入口。

部署形态（docs/03 §1.1）：单进程 uvicorn 1 worker + 线程池；APScheduler
（BackgroundScheduler）内置进程，不另起容器。
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.jobs.scheduler import shutdown_scheduler, start_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()  # create_all + 种子（幂等）
    start_scheduler(settings)  # APScheduler 内置进程（docs/03 §1.1：单 worker）
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="法务诉讼业务平台 API",
    version="0.1.0",
    description="按 docs/03 §6 API 设计；前端契约以本文 OpenAPI 为准",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 单用户工作台；生产由 Nginx 反代收敛
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


# 错误契约（docs/03 §6.1）：HTTP 4xx/5xx + {code, message, detail}；500 detail 带 request_id。
# FastAPI 默认 HTTPException 输出 {detail: ...}，这里统一为契约格式（前端错误态依赖）。


@app.exception_handler(HTTPException)
async def _http_exc_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": -1, "message": str(exc.detail), "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def _validation_exc_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": -1, "message": "请求参数校验失败", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def _unhandled_exc_handler(_request: Request, exc: Exception) -> JSONResponse:
    """500 兜底：统一包裹 + request_id（前端错误态可用 request_id 反馈）。"""
    request_id = uuid.uuid4().hex[:12]
    return JSONResponse(
        status_code=500,
        content={
            "code": -1,
            "message": "服务器内部错误",
            "detail": {"request_id": request_id, "error": str(exc)},
        },
    )


@app.get("/healthz", tags=["system"])
def healthz() -> dict:
    return {"status": "ok", "version": app.version}