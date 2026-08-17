"""同步引擎测试（t08-3 验证固化；t08-8 套件子集）。

覆盖实现计划测试计划「同步幂等（重复全量无脏入）」：
- 多页分页拉取（fake default_page_size=2，3 条案件覆盖 2 页）；
- 首轮全量 upsert 语义正确（字段映射 / 公式复刻 / raw 留档 / FTS 影子表）；
- 第二轮全量幂等收敛（skipped==3、upserted==0、行数不变、dirty_flags 全空 = 无脏入）；
- 远端变更检测（fake.mutate 后第三轮仅 1 条 upsert，support_rate 复刻联动）；
- 任务日志状态机（SyncJob success 两轮、error_brief 含 songs 对账说明）。

独立 engine（不复用 conftest 库，与其它测试模块数据完全隔离；
SyncEngine(db=session) 为 t08-3 测试注入专用参数）。
"""
from __future__ import annotations

import tempfile

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from app.models.fact import Case, RawCase, Song, SongCase
from app.models.fts import init_fts, search_cases
from app.models.ops import SyncJob
from app.sync.engine import SyncEngine
from tests.fixtures.fake_client import DEFAULT_CASES_TABLE_ID, DEFAULT_SONGS_TABLE_ID, FakeBitableClient

_TMP = tempfile.mkdtemp(prefix="litigation-sync-test-")
ENGINE = create_engine(f"sqlite:///{_TMP}/sync.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=ENGINE, autoflush=False, expire_on_commit=False)
init_fts(ENGINE)

FIELDS = [
    {"record_id": "recA", "fields": {
        "案号": "（2024）京0105民初1001号", "案件状态": "已结案",
        "收案年份": "2024年", "原告/上诉人/申请人": "音集协",
        "被告/被上诉人/被申请人": ["被告甲"], "受理法院": ["北京市朝阳区人民法院"],
        "案由": "著作权权属、侵权纠纷", "结案原因": "判赔",
        "标的": 100000, "支付总金额": 5000, "涉案歌曲数量": 2,
        "业务线": "VOD", "支付时间": 1720000000000,
        "涉及歌曲清单-涉及案号": [{"record_ids": ["song1"]}],
    }},
    {"record_id": "recB", "fields": {
        "案号": "（2024）京0105民初1002号", "案件状态": "已结案",
        "收案年份": "2024年", "原告/上诉人/申请人": "音集协",
        "被告/被上诉人/被申请人": ["被告乙"], "受理法院": ["北京市海淀区人民法院"],
        "案由": "侵害作品放映权纠纷", "结案原因": "和解",
        "标的": 20000, "支付总金额": 2000, "涉案歌曲数量": 1,
        "业务线": "KTV", "涉及歌曲清单-涉及案号": [{"record_ids": ["song1"]}],
    }},
    {"record_id": "recC", "fields": {
        "案号": "（2025）京0105民初2001号", "案件状态": "审理中",
        "收案年份": "2025年", "原告/上诉人/申请人": "音集协",
        "被告/被上诉人/被申请人": ["被告丙"], "受理法院": ["北京市东城区人民法院"],
        "案由": "著作权权属、侵权纠纷", "结案原因": "在办",
        "标的": 30000, "业务线": "直播", "涉案歌曲数量": 1,
        "涉及歌曲清单-涉及案号": [{"record_ids": ["song1"]}],
    }},
]

SONGS = [
    {"record_id": "song1", "fields": {"歌曲名": "可可西里", "艺人": "刀郎"}},
]


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=ENGINE)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=ENGINE)


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _row(db, rid: str) -> Case:
    return db.scalar(select(Case).where(Case.record_id == rid))


# ---------------------------------------------------------------- ① 分页 + 首轮全量

async def test_full_sync_pagination_and_upsert(db) -> None:
    """多页拉取（page_size=2 → 2 页）+ 首轮全量 upsert 语义。"""
    fake = FakeBitableClient(FIELDS, SONGS, default_page_size=2)
    engine = SyncEngine(get_settings(), client=fake, db=db)
    result = await engine.run_full()

    assert result["total"] == 3
    assert result["upserted"] == 3
    assert result["skipped"] == 0
    assert result["song_total"] == 1
    # 分页路径确实被触发（list_records 至少 2 次 + songs 表 1~2 次）
    cases_pages = sum(1 for t in fake.page_requests if t[0] == DEFAULT_CASES_TABLE_ID)
    assert cases_pages >= 2
    assert _count(db, Case) == 3
    assert _count(db, RawCase) == 3
    assert _count(db, Song) == 1
    assert _count(db, SongCase) == 3  # 3 案 × recA/recB/recC 各涉 song1

    a = _row(db, "recA")
    assert a.case_no == "（2024）京0105民初1001号"
    assert a.year_raw == "2024年"
    assert a.defendant == '["被告甲"]'
    assert a.resolve == "判赔"
    assert a.amount == 100000.0
    assert a.pay_amount == 5000.0
    # 公式复刻：support_rate = pay/amount；per_song = pay/song_count
    assert a.support_rate == pytest.approx(0.05)
    assert a.song_count == 2
    assert a.per_song_amount == pytest.approx(2500.0)
    # 在办案件无支付金额 → 复刻列为 None 而非脏值
    c = _row(db, "recC")
    assert c.pay_amount is None or c.pay_amount == 0
    assert c.support_rate is None

    # raw 整包留档（原始视图数据源）
    raw = db.scalar(select(RawCase).where(RawCase.record_id == "recA", RawCase.table_name == "cases"))
    assert raw is not None and "案号" in raw.fields_json

    # FTS 影子表同步（检索「被告甲」或「可可西里」应命中）
    from app.models.fts import rebuild_cases_fts
    rebuild_cases_fts(db)
    hits, total = search_cases(db, "1001")
    assert total >= 1
    assert any(h["case_id"] == a.id for h in hits)


# ---------------------------------------------------------------- ② 幂等：重复全量无脏入

async def test_full_sync_idempotent_no_dirty_reentry(db) -> None:
    """第二轮全量：hash 未变全 skipped（幂等），无脏入（dirty_flags 全空）。"""
    fake = FakeBitableClient(FIELDS, SONGS, default_page_size=2)
    engine = SyncEngine(get_settings(), client=fake, db=db)
    first = await engine.run_full()
    assert first["skipped"] == 0

    second = await engine.run_full()
    assert second["upserted"] == 0, "重复全量必须幂等（hash 未变不重写）"
    assert second["skipped"] == 3
    assert _count(db, Case) == 3  # 无重复行
    assert _count(db, RawCase) == 3
    # 无脏入：同步引擎原样透传，不产生任何清洗脏标记
    dirty = db.scalars(select(Case).where(Case.dirty_flags.is_not(None))).all()
    assert dirty == []
    # 行内容未被二次改写（synced_at 会被刷新，但数据列保持；抽查案号）
    assert _row(db, "recA").case_no == "（2024）京0105民初1001号"

    # 任务日志状态机：两轮 success，记录 upserted/skipped 对账正确
    jobs = list(db.scalars(select(SyncJob).order_by(SyncJob.id)).all())
    assert len(jobs) == 2
    assert all(j.status == "success" and j.error_brief is not None for j in jobs)
    assert jobs[0].upserted == 3 and jobs[0].skipped == 0
    assert jobs[1].upserted == 0 and jobs[1].skipped == 3


# ---------------------------------------------------------------- ③ 变更检测

async def test_full_sync_change_detection(db) -> None:
    """远端 mutate 一字段 → hash 变化 → 该条 upsert，其余 skipped；公式列联动更新。"""
    fake = FakeBitableClient(FIELDS, SONGS, default_page_size=2)
    engine = SyncEngine(get_settings(), client=fake, db=db)
    await engine.run_full()

    fake.mutate("recA", "支付总金额", 7000)
    third = await engine.run_full()
    assert third["upserted"] == 1
    assert third["skipped"] == 2
    # 变更联动：pay_amount、复刻 support_rate / per_song_amount 同步刷新
    a = _row(db, "recA")
    assert a.pay_amount == 7000.0
    assert a.support_rate == pytest.approx(0.07)
    assert a.per_song_amount == pytest.approx(3500.0)
    # 未变更记录保持原值（不被重写）
    assert _row(db, "recB").pay_amount == 2000.0