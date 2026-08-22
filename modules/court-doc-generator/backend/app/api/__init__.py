"""API 路由聚合。"""
from fastapi import APIRouter

from app.api import auth, companies, agents, cases, generate, history, files, scan, print_api, presets, audit

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(companies.router, prefix="/companies", tags=["公司"])
api_router.include_router(agents.router, prefix="/agents", tags=["代理人"])
api_router.include_router(cases.router, prefix="/cases", tags=["案件"])
api_router.include_router(generate.router, prefix="/generate", tags=["生成"])
api_router.include_router(history.router, prefix="/history", tags=["历史"])
api_router.include_router(files.router, prefix="/files", tags=["文件"])
api_router.include_router(scan.router, prefix="/scan", tags=["扫描"])
api_router.include_router(print_api.router, prefix="/print", tags=["打印"])
api_router.include_router(presets.router, prefix="/presets", tags=["预设"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["操作日志"])
