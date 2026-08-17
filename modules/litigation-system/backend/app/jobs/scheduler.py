"""APScheduler 组装（t08-6）。

部署形态（docs/03 §1.1）：单进程 uvicorn 1 worker，BackgroundScheduler
内置同一进程、不另起容器；start_scheduler 在主进程 lifespan 中调用。
作业注册与 config.py cron_*（= 10-sync 页 cron 约定）一一对应，cron 可经
环境变量覆盖；所有作业 coalesce=True（错过触发只补跑一次）+ misfire 宽限 1h。
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import Settings, get_settings
from app.jobs.tasks import casebase_job, clean_job, metrics_job, sync_incremental_job

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def build_scheduler(settings: Settings | None = None) -> BackgroundScheduler:
    """按 settings.cron_* 构建并注册 4 个作业；主进程启动前调用（幂等）。"""
    cfg = settings or get_settings()
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    jobs = [
        ("sync_incremental", sync_incremental_job, cfg.cron_incremental, "每日 03:00 增量同步"),
        ("clean_pipeline", clean_job, cfg.cron_clean, "03:00 清洗管道全量重跑"),
        ("metrics_recalc", metrics_job, cfg.cron_metrics, "03:40 指标重算 + 状态快照"),
        ("casebase_snapshot", casebase_job, cfg.cron_casebase, "周一 22:00 案例库快照"),
    ]
    for job_id, func, cron, desc in jobs:
        scheduler.add_job(
            func,
            trigger=CronTrigger.from_crontab(cron, timezone="Asia/Shanghai"),
            id=job_id,
            name=f"{job_id}（{desc}）",
            misfire_grace_time=3600,
            coalesce=True,
            replace_existing=True,
        )
        logger.info("scheduler 注册作业 %s：cron=%s", job_id, cron)
    return scheduler


def start_scheduler(settings: Settings | None = None) -> BackgroundScheduler:
    """启动全局调度器；已启动则直接返回现有实例（防止 lifespan 重复触发）。"""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = build_scheduler(settings)
    _scheduler.start()
    logger.info("scheduler 已启动：%d 个作业", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler() -> None:
    """优雅关闭全局调度器（进程退出前调用，幂等）。"""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler 已关闭")
    _scheduler = None


def next_run_time(job_id: str):
    """作业下次触发时刻（API GET /sync/status 用；未启动/未注册返回 None）。"""
    if _scheduler is None or not _scheduler.running:
        return None
    job = _scheduler.get_job(job_id)
    if job is None:
        return None
    nrt = job.next_run_time
    return nrt.isoformat() if nrt is not None else None