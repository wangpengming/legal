"""API v1 路由聚合。

端点按 docs/03 §6.2 与实现计划「API 面」实现（t08-7 全量注册）：
metadata / search / cases{id,raw,batch} / stats{overview,party,bizline,songs,fees} /
sync{run,status,logs} / dicts{test,dirty-items} / export / ai{query,chat,report-templates} /
similar（F4.2 同质案类推）/ reports{T1~T7 生成,列表,详情} / tags{M4 标签 CRUD,打标,批量,合并}。
"""
from fastapi import APIRouter

# 注意：sync 模块名与 stdlib 冲突，以 sync_api 命名空间引入（docs/03 §6.2）
from app.api import ai, dicts, export, metadata, reports, search, similar, stats, tags
from app.api import sync as sync_api

api_router = APIRouter()

api_router.include_router(metadata.router)
api_router.include_router(search.router)
api_router.include_router(stats.router)
api_router.include_router(sync_api.router)
api_router.include_router(dicts.router)
api_router.include_router(export.router)
api_router.include_router(ai.router)
api_router.include_router(similar.router)
api_router.include_router(reports.router)
api_router.include_router(tags.router)