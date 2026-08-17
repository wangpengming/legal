"""定时作业函数（t08-6）：增量同步 / 清洗 / 指标重算 / 案例库快照。

与 config.py cron_*（= 10-sync 页 cron 约定）一一对应；均为同步函数
（APScheduler 线程池执行），内部自建 Session、自管 asyncio 事件循环
（同步引擎为 async 接口）。离线模式（飞书凭证未配置）下增量作业跳过并
留审计；案例库作业为 Phase 2 前置挂载（数据源接入后启用）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clean.pipeline import CleanPipeline
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal, init_db
from app.models.ops import AuditLog, ExternalCase, Setting
from app.stats.metrics import compute_overview
from app.sync.engine import SyncEngine

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _audit(db: Session, *, op_type: str, table_name: str, action: str, detail: str) -> None:
    db.add(
        AuditLog(
            op_type=op_type,
            table_name=table_name,
            action=action,
            detail=detail,
            operator="scheduler",
            created_at=_now_ms(),
        )
    )
    db.commit()


# ── ① 增量同步（cron_incremental；离线模式跳过并留痕） ──────────────

def sync_incremental_job(settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    if not cfg.feishu_configured:
        db = SessionLocal()
        try:
            _audit(
                db,
                op_type="sync",
                table_name="sync_jobs",
                action="skipped",
                detail=json.dumps({"job": "incremental", "reason": "飞书凭证未配置（离线模式）"}, ensure_ascii=False),
            )
        finally:
            db.close()
        logger.warning("job sync_incremental skipped：飞书凭证未配置（离线模式）")
        return {"status": "skipped", "reason": "feishu_not_configured"}
    try:
        result = asyncio.run(SyncEngine(cfg).run_incremental())
        result["status"] = "ok"
        return result
    except Exception as exc:  # noqa: BLE001 —— 任务失败留痕不吞栈
        logger.exception("job sync_incremental failed")
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}


# ── ② 清洗管道全量重跑（cron_clean；紧随增量） ──────────────────────

def clean_job() -> dict:
    init_db()
    db = SessionLocal()
    try:
        result = CleanPipeline(db).run()
        payload = result.to_dict()
        if payload["errors"]:
            logger.error("job clean 完成但含错误：%s", payload["errors"])
        payload["status"] = "ok"
        return payload
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("job clean failed")
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        db.close()


# ── ③ 指标重算（cron_metrics；08-metrics 页状态快照） ───────────────

def metrics_job() -> dict:
    init_db()
    db = SessionLocal()
    try:
        rows = compute_overview(db)
        values = {r["key"]: r["value"] for r in rows}
        payload = json.dumps({"at": _now_ms(), "values": values}, ensure_ascii=False)
        setting = db.scalar(select(Setting).where(Setting.key == "last_metrics_run"))
        if setting is None:
            db.add(Setting(key="last_metrics_run", value=payload, updated_at=_now_ms()))
        else:
            setting.value, setting.updated_at = payload, _now_ms()
        db.commit()
        logger.info("job metrics_recalc：%d 项指标已重算", len(rows))
        return {"status": "ok", "count": len(rows), "values": values}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("job metrics failed")
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        db.close()


# ── ④ 案例库快照（cron_casebase；Phase 2 网上判决数据源接入后启用） ──

def casebase_job() -> dict:
    init_db()
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(ExternalCase)) or 0
        _audit(
            db,
            op_type="sync",
            table_name="external_cases",
            action="skipped",
            detail=json.dumps({"reason": "Phase 2 数据源接入后启用", "external_count": count}, ensure_ascii=False),
        )
        return {"status": "skipped", "reason": "phase2_not_connected", "external_count": count}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("job casebase failed")
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        db.close()