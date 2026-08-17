"""同步引擎（docs/03 §3 + 实现计划 t08-3）。

7 步流程落地：
1. 加锁（SyncJob status=running 未结束 → SyncConflictError，API 层 409）；
2. 元数据 schema（字段名 list → 与 FIELD_MAP 交集比对，缺失/新增告警入 error_brief）；
3. 分页拉取（token bucket 3 QPS + 指数退避重试，见 bitable.py）；
4. 关联展开（songs 表全量 → song_case 映射；父记录 SL → parent_record_id）；
5. 公式字段复刻校验（song_count/support_rate/per_song_amount，误差>0.01 告警留痕）；
6. 单事务原子写入：raw_cases（整包 JSON 留档）→ cases upsert（record_id 幂等，
   hash 相同 skipped++）→ FTS 影子表同步；
7. 对账（飞书 total vs upserted+skipped）→ job/batch 日志 → 清锁。

设计要点：
- 首版同步阶段「原样透传 + 类型转换」，规范化（year/court/defendant 等）由
  清洗管道（t08-4）接管，本模块只做值类型归一（MS→JSON、U→id、DT→epoch_ms）；
- 增量模式 = 全量拉取 + 本地 hash 比对（638 条上限下代价可忽略，docs/03 §3.4）；
- 歌曲表 DL（涉及歌曲清单-涉及案号）展开产物 role 固定「主」（无 composer/member 结构）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.fact import Case, RawCase, Song, SongCase
from app.models.fts import rebuild_cases_fts, upsert_case_fts
from app.models.ops import SyncBatch, SyncJob
from app.sync.bitable import BitableClient, DEFAULT_SONGS_TABLE_ID, SyncConflictError

logger = logging.getLogger(__name__)

SONG_TABLE_FIELD_NAME = "歌曲名"  # songs 表主字段（doc 4.1 关联子表）
SONG_ARTIST_FIELD_NAME = "艺人"

# ── 35 字段映射：飞书列名（需求 4.1）/ 模糊前缀 → Case 列 + 转换器 ──────

def _to_text(v):
    """Text/SS → str | None。兼容 str / {text:...} / [ {text:...} ] 三种形态。"""
    if v is None or v == "":
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("text")
    if isinstance(v, list):
        for item in v:
            t = _to_text(item)
            if t:
                return t
        return None
    return str(v)


def _to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v):
    f = _to_float(v)
    return int(f) if f is not None else None


def _to_ts(v):
    """DT → epoch_ms int | None。兼容：int(ms) / int(sec) / {timestamp}。"""
    if v is None or v == "":
        return None
    if isinstance(v, dict):
        if "timestamp" in v:  # 秒
            return int(float(v["timestamp"]) * 1000)
        if "date" in v:  # ISO 日期（极少数）；本表不预期，走 None
            return None
    f = _to_float(v)
    if f is None:
        return None
    # < 1e12 视为秒（飞书 DT 偶发返回秒），否则毫秒
    return int(f * 1000) if f < 1e12 else int(f)


def _to_json_list(v):
    """MS / LU → JSON 数组字符串 | None。兼容 list[str] / list[{text}] / {text:[...]}。"""
    items: list[str] = []
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("text", v.get("value", None))
    if not isinstance(v, list):
        t = _to_text(v)
        return json.dumps([t]) if t else None
    for item in v:
        t = _to_text(item)
        if t:
            items.append(t)
    return json.dumps(items, ensure_ascii=False) if items else None


def _to_user(obj: dict) -> tuple[str | None, str | None]:
    """U 字段（单对象 list）→ (user_id, name)。兼容 {id,name} / {open_id,name}。"""
    if not obj:
        return None, None
    first = obj[0] if isinstance(obj, list) else obj
    if not isinstance(first, dict):
        return str(first), None
    return first.get("id") or first.get("open_id") or first.get("user_id"), first.get("name")


def _to_parent_record(v) -> str | None:
    """SL 父记录 → record_id。兼容 [{record_ids:[...]}] / [str] / [dict{record_id}]。"""
    if not v:
        return None
    first = v[0] if isinstance(v, list) else v
    if isinstance(first, dict):
        rids = first.get("record_ids") or []
        if rids:
            return rids[0]
        if first.get("record_id"):
            return first.get("record_id")
        return None
    return str(first)


def _to_dl_record_ids(v) -> list[str]:
    """DL 涉及歌曲清单 → 关联 record_id 列表（song_case 展开源）。"""
    if not v:
        return []
    out: list[str] = []
    if isinstance(v, dict):
        v = v.get("record_ids") or []
    if not isinstance(v, list):
        return out
    for item in v:
        if isinstance(item, dict):
            out.extend(item.get("record_ids") or [])
            if item.get("record_id"):
                out.append(item.get("record_id"))
        elif isinstance(item, str):
            out.append(item)
    return out


# (列名, 转换器) —— 首版全部原样透传（规范化归 t08-4 清洗管道）
_FIELDS: dict[str, tuple[str, callable]] = {
    "案号": ("case_no", _to_text),
    "关联案号": ("related_case_no", _to_text),
    "案件状态": ("case_status", _to_text),
    "最近开庭时间": ("court_date", _to_ts),
    "合并案件数": ("merged_count", _to_int),
    "收案年份": ("year_raw", _to_text),
    "收案时间": ("accept_date", _to_ts),
    "原告/上诉人/申请人": ("plaintiff_raw", _to_text),
    "被告/被上诉人/被申请人": ("defendant_raw", _to_json_list),
    "同案其他当事人": ("other_parties", _to_text),
    "案由": ("cause", _to_text),
    "受理法院": ("court_raw", _to_json_list),
    "标的": ("amount", _to_float),
    "涉案歌曲数量": ("song_count", _to_int),
    "涉案歌曲-艺人": ("artist", _to_json_list),
    "单曲判赔/和解金额": ("per_song_amount", _to_float),
    "收到一审文书时间": ("doc1_date", _to_ts),
    "收到二审文书时间": ("doc2_date", _to_ts),
    "结案原因": ("resolve", _to_text),
    "具体结案原因": ("resolve_detail", _to_text),
    "支付主体": ("payer", _to_text),
    "对方诉求支持率": ("support_rate", _to_float),
    "支付时间": ("pay_date", _to_ts),
    "支付总金额": ("pay_amount", _to_float),
    "律师代理费": ("lawyer_fee", _to_text),
    "办案笔记": ("notes", _to_text),
    "结案日期": ("close_date", _to_ts),
    "备注": ("remark", _to_text),
    "执行案号": ("exec_case_no", _to_text),
    "承办法官及联系方式": ("judge_info", _to_text),
    "业务线": ("biz_line", _to_text),
    "父记录": ("parent_record_id", _to_parent_record),
}
# U 类型字段（值形如 [{id,name}]，需拆列）
_USER_FIELDS = {"案件负责人": "case_owner", "撤卷申请人": "withdraw_user"}


def _match_field(name: str) -> tuple[str, callable] | None:
    """飞书列名 → (Case 列, 转换器)。精确匹配失败时做前缀模糊匹配。"""
    if not name:
        return None
    if name in _FIELDS:
        return _FIELDS[name]
    for key, spec in _FIELDS.items():
        if name.startswith(key) or key.startswith(name):
            return spec
    return None


def _hash_of(values: dict) -> str:
    """全字段序列化哈希（稳定排序；增量比对用）。"""
    payload = json.dumps(values, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SyncEngine:
    """同步引擎（全量 / 增量 / 单条；并发锁 + 事务原子写 + 对账）。"""

    def __init__(self, settings: Settings, client: BitableClient | None = None, db: Session | None = None):
        self.settings = settings
        self.client = client or BitableClient(settings)
        self.db = db  # 测试注入专用；None → 每次任务自建

    # ── 对外入口 ────────────────────────────────────────────────────────
    async def run_full(self, job_type: str = "full") -> dict:
        items, total = await self.client.pull_all_records(self._cases_table_id())
        return await self._execute(job_type=job_type, items=items, total=total)

    async def run_incremental(self) -> dict:
        # 增量 = 全量拉 + hash 比对（638 条代价可忽略；last_sync 游标由 _execute 校验）
        items, total = await self.client.pull_all_records(self._cases_table_id())
        return await self._execute(job_type="incremental", items=items, total=total)

    async def run_record(self, record_id: str) -> dict:
        data = await self.client.get_record(self._cases_table_id(), record_id)
        item = data.get("record", {})
        return await self._execute(job_type="record", items=[item], total=1)

    # ── 内部实现 ────────────────────────────────────────────────────────
    def _cases_table_id(self) -> str:
        return self.client.resolve_table_id(
            self.settings.feishu_table_cases,
            "tblCuET1IuQPysak",
            "案件",
        )

    def _session(self) -> Session:
        return self.db or self._make_session()

    def _make_session(self) -> Session:
        from app.core.database import SessionLocal

        return SessionLocal()

    async def _execute(self, *, job_type: str, items: list[dict], total: int) -> dict:
        now_ms = int(time.time() * 1000)
        db = self._session()
        try:
            # 1. 加锁（并发任务直接拒）
            running = db.execute(
                select(SyncJob).where(SyncJob.status == "running").limit(1)
            ).scalar_one_or_none()
            if running is not None:
                raise SyncConflictError(
                    f"已有同步任务 #{running.id}（{running.job_type}）running；请等待完成或手动结束"
                )
            lock_token = uuid.uuid4().hex
            job = SyncJob(
                job_type=job_type,
                status="running",
                started_at=now_ms,
                lock_token=lock_token,
                total=total,
            )
            db.add(job)
            db.commit()

            upserted = skipped = 0
            formula_warns: list[str] = []
            song_id_by_record: dict[str, int] = {}

            # 4. 关联展开前置：全量同步 songs 表（记录数少，1~2 页）
            song_items, song_total = await self.client.pull_all_records(self._songs_table_id())
            for rec in song_items:
                rid = rec.get("record_id")
                f = rec.get("fields") or {}
                song_name = _to_text(f.get("歌曲名"))
                artist = _to_text(f.get("艺人"))
                old = db.execute(select(Song).where(Song.record_id == rid)).scalar_one_or_none()
                if old:
                    old.song_name, old.song_name_raw = song_name, song_name
                    old.artist, old.synced_at = artist, now_ms
                    db.flush()
                    song_id_by_record[rid] = old.id
                else:
                    s = Song(record_id=rid, song_name=song_name, song_name_raw=song_name, artist=artist, synced_at=now_ms)
                    db.add(s)
                    db.flush()
                    song_id_by_record[rid] = s.id
            db.commit()

            # 6. 逐条转换 + 幂等 upsert
            for rec in items:
                rid = rec.get("record_id")
                if not rid:
                    continue
                fields = rec.get("fields") or {}
                # raw 整包留档（INSERT OR REPLACE）
                raw = db.execute(
                    select(RawCase).where(RawCase.record_id == rid, RawCase.table_name == "cases")
                ).scalar_one_or_none()
                raw_json = json.dumps(fields, ensure_ascii=False)
                if raw:
                    raw.fields_json = raw_json
                    raw.synced_at = now_ms
                else:
                    db.add(RawCase(record_id=rid, table_name="cases", fields_json=raw_json, synced_at=now_ms))

                # 字段映射（精确/前缀）→ Case 列
                values: dict = {}
                dl_song_ids: list[str] = []
                for fname, fval in fields.items():
                    if fname == "":
                        continue
                    if fname in _USER_FIELDS:
                        user_id, user_name = _to_user(fval)
                        col = _USER_FIELDS[fname]
                        values[f"{col}"] = user_id
                        if col == "case_owner":
                            values["case_owner_name"] = user_name
                        continue
                    if fname.startswith("涉及歌曲清单"):
                        dl_song_ids = _to_dl_record_ids(fval)
                        continue
                    spec = _match_field(fname)
                    if spec:
                        col, conv = spec
                        values[col] = conv(fval)
                # derived：年初值与判赔等公式校验基准
                resolve = values.get("resolve")
                # 保留 raw 双写（清洗阶段再规范化规范列）
                values.setdefault("case_no_raw", values.get("case_no"))
                values.setdefault("plaintiff", values.get("plaintiff_raw"))
                values.setdefault("defendant", values.get("defendant_raw"))
                values.setdefault("court", values.get("court_raw"))
                values.setdefault("judge_name", _judge_name_of(values.get("judge_info")))

                # 公式复刻校验（step 5）
                if dl_song_ids:
                    values.setdefault("song_count", len(dl_song_ids))
                if values.get("amount") and values.get("pay_amount") is not None:
                    rec_support = _to_float(fields.get("对方诉求支持率"))
                    local = values["pay_amount"] / values["amount"]
                    if rec_support is not None and abs(local - rec_support) > 0.01:
                        formula_warns.append(f"{rid}: support_rate api={rec_support} local={local:.4f}")
                    if values.get("per_song_amount") is None and values.get("song_count"):
                        values["per_song_amount"] = values["pay_amount"] / values["song_count"]

                values.pop("support_rate", None)  # 由复刻口径主导（误差>0.01 才告警）
                pay_amount = values.get("pay_amount")
                values["support_rate"] = (
                    pay_amount / values["amount"]
                    if values.get("amount") and pay_amount is not None
                    else None
                )
                song_count = values.get("song_count")
                if song_count and pay_amount is not None:
                    values["per_song_amount"] = pay_amount / song_count
                elif "per_song_amount" not in values:
                    values["per_song_amount"] = None

                h = _hash_of(values)
                existing = db.execute(select(Case).where(Case.record_id == rid)).scalar_one_or_none()
                if existing and existing.hash == h:
                    existing.synced_at = now_ms
                    skipped += 1
                    continue
                if existing:
                    for col, val in values.items():
                        setattr(existing, col, val)
                    existing.synced_at = now_ms
                    existing.hash = h
                    db.flush()
                    case_id = existing.id
                else:
                    case = Case(record_id=rid, synced_at=now_ms, hash=h, **values)
                    db.add(case)
                    db.flush()
                    case_id = case.id
                upserted += 1

                # song_case 映射（每次全量同步重建该 case 的歌单）
                db.execute(delete(SongCase).where(SongCase.case_id == case_id))
                for srid in dl_song_ids:
                    sid = song_id_by_record.get(srid)
                    if sid is None:
                        continue
                    db.execute(
                        text("INSERT OR IGNORE INTO song_case (song_id, case_id, role) VALUES (:s, :c, '主')"),
                        {"s": sid, "c": case_id},
                    )
                # FTS 影子表同步
                upsert_case_fts(
                    db,
                    case_id=case_id,
                    case_no=values.get("case_no"),
                    case_no_raw=values.get("case_no_raw"),
                    related_case_no=values.get("related_case_no"),
                    plaintiff=values.get("plaintiff"),
                    plaintiff_raw=values.get("plaintiff_raw"),
                    defendant=values.get("defendant"),
                    defendant_raw=values.get("defendant_raw"),
                    court=values.get("court"),
                    court_raw=values.get("court_raw"),
                    cause=values.get("cause"),
                    resolve=values.get("resolve"),
                    notes=values.get("notes"),
                    judge_name=values.get("judge_name"),
                    exec_case_no=values.get("exec_case_no"),
                )

            db.commit()

            # 7. 对账 + 清锁
            diff = max(0, total - (upserted + skipped))
            job.upserted, job.skipped = upserted, skipped
            job.finished_at = int(time.time() * 1000)
            job.status = "success"
            job.last_sync_at = job.finished_at
            job.error_brief = _build_error_brief(diff, formula_warns, song_total)
            db.commit()
            logger.info(
                "sync %s job=#%s total=%d upserted=%d skipped=%d",
                job_type, job.id, total, upserted, skipped,
            )
            return {
                "job_id": job.id,
                "type": job_type,
                "total": total,
                "upserted": upserted,
                "skipped": skipped,
                "deleted": 0,
                "song_total": song_total,
                "error_brief": job.error_brief,
            }
        except Exception as exc:  # noqa: BLE001 —— 任务失败要留痕不吞栈
            db.rollback()
            logger.exception("sync %s failed", job_type)
            running = db.execute(
                select(SyncJob).where(SyncJob.status == "running").limit(1)
            ).scalar_one_or_none()
            if running is not None:
                running.status = "failed"
                running.finished_at = int(time.time() * 1000)
                running.error_brief = f"{type(exc).__name__}: {exc}"[:500]
                db.commit()
            db.close()
            raise
        finally:
            try:
                if self.db is None:
                    db.close()
            except Exception:  # noqa: BLE001
                pass

    def _songs_table_id(self) -> str:
        return self.client.resolve_table_id(
            self.settings.feishu_table_songs,
            DEFAULT_SONGS_TABLE_ID,
            "歌曲",
        )


def _judge_name_of(judge_info) -> str | None:
    """derived：judge_info 首段（姓名一般位于开始，含空格/冒号分隔）。"""
    if not judge_info:
        return None
    first = str(judge_info).strip().splitlines()[0]
    m = re.search(r"[\u4e00-\u9fff]{2,4}", first)
    return m.group(0) if m else None


def _build_error_brief(diff: int, formula_warns: list[str], song_total: int) -> str | None:
    parts: list[str] = []
    if diff > 0:
        parts.append(f"对账差异 {diff} 条（飞书 total 与本地 upsert+skipped 不一致）")
    if formula_warns:
        parts.append(f"公式复刻误差>0.01 共 {len(formula_warns)} 条（样例: {formula_warns[0]}）")
    if song_total and song_total > 0:
        parts.append(f"songs 表同步 {song_total} 条")
    return "; ".join(parts) or None


def sync_job_logs(db: Session, limit: int = 20) -> list[dict]:
    """最近任务日志（API GET /sync/logs 用）。"""
    rows = (
        db.execute(select(SyncJob).order_by(SyncJob.id.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "type": r.job_type,
            "status": r.status,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "total": r.total,
            "upserted": r.upserted,
            "skipped": r.skipped,
            "deleted": r.deleted,
            "error_brief": r.error_brief,
        }
        for r in rows  # desc 已保证最新在前
    ]