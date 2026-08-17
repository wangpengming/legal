"""同步端点（docs/03 §6.2：POST /sync/run、GET /sync/status、GET /sync/logs）。

- 离线模式：飞书凭证未配置（决策 D2，get_settings().feishu_configured=False）
  时 POST /sync/run 直接 503（同步引擎只走夹具/测试路径，见 app.sync.engine）；
- 在线模式：async 端点 await SyncEngine.run_full|run_incremental|run_record
  （引擎自带并发锁 + 事务原子写 + 失败写 failed 后 re-raise）；
- 并发冲突 SyncConflictError → 409；上游飞书错误 → 502。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SyncRunRequest, audit, ok
from app.core.config import get_settings
from app.core.database import get_db
from app.jobs.scheduler import next_run_time
from app.models.ops import SyncJob
from app.sync.bitable import FeishuAPIError, SyncConflictError
from app.sync.engine import SyncEngine, sync_job_logs

router = APIRouter(tags=["sync"])


@router.post("/sync/run")
async def run_sync(payload: SyncRunRequest, db: Session = Depends(get_db)) -> dict:
    """手动触发同步：full（全量）/ incremental（增量）/ record（单条）。

    离线模式（飞书凭证未配置）拒绝执行；在线模式 async 等待引擎完成。
    写操作记录审计（op_type=sync/action=run）。
    """
    if not get_settings().feishu_configured:
        raise HTTPException(
            status_code=503,
            detail="飞书凭证未配置（离线模式）：同步仅可在注入 FEISHU_* 环境变量后执行",
        )
    if payload.type == "record" and not payload.id:
        raise HTTPException(status_code=422, detail="type=record 时 id（飞书 record_id）必填")

    engine = SyncEngine(get_settings())
    try:
        if payload.type == "full":
            result = await engine.run_full()
        elif payload.type == "record":
            result = await engine.run_record(payload.id)
        else:
            result = await engine.run_incremental()
    except SyncConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeishuAPIError as exc:
        raise HTTPException(status_code=502, detail=f"飞书上游错误：{exc}") from exc

    audit(db, op_type="sync", table_name="sync_jobs", action=f"run_{payload.type}",
          detail={"type": payload.type, "id": payload.id, "result": result})
    return ok(result, footnote="同步口径 v1.0：幂等跳过按全字段哈希比对（hash 未变不重写）")


@router.get("/sync/status")
def sync_status(db: Session = Depends(get_db)) -> dict:
    """同步状态（10-sync 页轮询）：是否正在运行 / 最近任务 / 下次定时触发 / 在线与否。"""
    running_job = db.scalar(
        select(SyncJob).where(SyncJob.status == "running").order_by(SyncJob.id.desc()).limit(1)
    )
    latest = db.scalar(select(SyncJob).order_by(SyncJob.id.desc()).limit(1))
    last = None
    if latest is not None:
        last = {
            "id": latest.id, "type": latest.job_type, "status": latest.status,
            "total": latest.total, "upserted": latest.upserted,
            "skipped": latest.skipped, "deleted": latest.deleted,
            "started_at": latest.started_at, "finished_at": latest.finished_at,
            "error_brief": latest.error_brief, "last_sync_at": latest.last_sync_at,
        }
    return ok(
        {
            "running": running_job is not None,
            "running_job_id": running_job.id if running_job else None,
            "last": last,
            "next_at": next_run_time("sync_incremental"),
            "feishu_configured": get_settings().feishu_configured,
            "jobs": {"incremental": "sync_incremental", "clean": "clean_all",
                     "metrics": "metrics_refresh", "casebase": "casebase_snapshot"},
        },
        footnote="next_at 为 APScheduler 注册的下次触发（cron 与 10-sync 页一致：增量 03:00 等）",
    )


@router.get("/sync/logs")
def get_sync_logs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    """最近同步任务日志（限 100 条）。"""
    logs = sync_job_logs(db, limit=limit)
    return ok(logs, total=len(logs), footnote="任务日志：running → success/failed 状态机，error_brief 不存完整堆栈")