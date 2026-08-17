"""8 项指标口径 v1.0 语义测试（t08-5 验证固化；t08-8 套件子集）。

构造 9 条小样本覆盖 胜/判赔/和解/撤诉/在办/金额/日期 分布，逐项断言
metrics.py 表驱动引擎语义：口径 A/B 胜诉率、支持率、判赔率、单曲判赔、
结案周期、系列案系数、在办数；以及 {filters} 白名单过滤、非法入参防御、
版本历史。

隔离：本模块使用独立 engine（不复用 conftest 临时库），避免与 test_clean
的 23 条判赔样本互相污染全局计数断言。
"""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.fact import Case
from app.models.seed import seed_meta
from app.stats.metrics import METRIC_KEYS, compute_metric, compute_overview, metric_versions

DAY = 86_400_000  # 1 天 epoch_ms

_ENGINE = create_engine(f"sqlite:///{Path(tempfile.mkdtemp(prefix='litigation-metrics-')) / 'metrics.db'}")
_Session = sessionmaker(bind=_ENGINE, expire_on_commit=False)


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(_ENGINE)
    session = _Session()
    seed_meta(session)
    session.add_all(CASES)
    session.commit()
    yield session
    session.close()


def _case(rid: str, **kw) -> Case:
    base = {
        "record_id": rid,
        "case_no": f"({rid})",
        "case_status": "已结案",
        "merged_count": 1,
        "year": 2021,
        "biz_line": "音乐著作权",
        "payer": "雷石",
        "amount": None,
        "pay_amount": None,
        "per_song_amount": None,
        "song_count": None,
        "accept_date": None,
        "close_date": None,
    }
    base.update(kw)
    return Case(**base)


# 手算期望值（供断言注释对照）：
#   win_rate_a = 2 胜/(2 胜+2 败) = 0.5；win_rate_b = 3/(2+2+1) = 0.6
#   support_rate = (0+3000+5000)/(10000+10000+20000) = 0.2
#   verdict_rate = AVG(0.3, 0.25) = 0.275
#   per_song = AVG(1000, 1500, 2500) = 1666.6667；cycle = AVG(100, 190, 280) = 190
#   series_coef = (2+3+1*7)/9 = 1.3333；open_count = 3
CASES = [
    _case("m01", resolve="胜诉",
          amount=10000.0, pay_amount=0.0, per_song_amount=1000.0, song_count=2,
          accept_date=DAY * 10, close_date=DAY * 110, merged_count=2),
    _case("m02", resolve="裁定驳回对雷石的诉讼请求", year=2021),  # 胜（口径A/B 均计入）
    _case("m03", resolve="判赔", year=2021,
          amount=10000.0, pay_amount=3000.0, per_song_amount=1500.0, song_count=2,
          accept_date=DAY * 20, close_date=DAY * 210),
    _case("m04", resolve="判赔", year=2022, biz_line="其他",
          amount=20000.0, pay_amount=5000.0, per_song_amount=2500.0, song_count=2,
          accept_date=DAY * 30, close_date=DAY * 310, merged_count=3),
    _case("m05", resolve="双方和解", year=2022, biz_line="其他"),
    _case("m06", resolve="原告撤诉", year=2022, biz_line="其他"),
    # 在办样本：resolve 为空（不进入胜诉率分母），case_status 驱动 open_count
    _case("o1", resolve=None, case_status="审理中"),
    _case("o2", resolve=None, case_status="待立案", biz_line="其他", year=2022),
    _case("o3", resolve=None, case_status=None, biz_line="其他", year=2022),
]


def _v(db, key, filters=None):
    return compute_metric(db, key, filters)["value"]


# ---------------------------------------------------------------- ① 单项指标语义

def test_win_rates_a_b(db):
    assert _v(db, "win_rate_a") == pytest.approx(0.5)
    assert _v(db, "win_rate_b") == pytest.approx(0.6)
    assert _v(db, "win_rate_a") != _v(db, "win_rate_b")  # 和解进入 B 不入 A


def test_support_and_verdict_rates(db):
    assert _v(db, "support_rate") == pytest.approx(0.2)
    assert _v(db, "verdict_rate") == pytest.approx(0.275)


def test_per_song_cycle_series(db):
    assert _v(db, "per_song") == pytest.approx(5000 / 3, abs=1e-4)
    assert _v(db, "cycle") == pytest.approx(190)
    assert _v(db, "series_coef") == pytest.approx(12 / 9, abs=1e-4)


def test_open_count_excludes_closed(db):
    assert _v(db, "open_count") == 3  # 含 status 缺失（o3）与未结案枚举（o1/o2）


def test_metric_result_contract(db):
    r = compute_metric(db, "win_rate_a")
    assert set(r) == {"key", "title", "definition", "value", "version", "footnote"}
    assert r["version"] == "v1"


# ---------------------------------------------------------------- ② {filters} 白名单过滤

def test_filters_biz_line(db):
    f = {"biz_line": "音乐著作权"}
    assert _v(db, "win_rate_a", f) == pytest.approx(round(2 / 3, 4))  # 胜 m01/m02，败 m03
    assert _v(db, "win_rate_b", f) == pytest.approx(round(2 / 3, 4))
    assert _v(db, "open_count", f) == 1  # 仅 o1
    assert _v(db, "support_rate", f) == pytest.approx(0.15)  # (0+3000)/(10000+10000)
    assert _v(db, "verdict_rate", f) == pytest.approx(0.3)  # 仅 m03


def test_filters_year(db):
    f = {"year": 2022}
    assert _v(db, "win_rate_a", f) == pytest.approx(0.0)  # 无胜，败 m04
    assert _v(db, "open_count", f) == 2  # o2/o3


def test_filters_invalid_value_ignored(db):
    # 非法类型（year 需 int）→ 条件忽略 → 等价无过滤
    assert _v(db, "win_rate_a", {"year": "abc"}) == pytest.approx(0.5)
    # 白名单外字段忽略
    assert _v(db, "win_rate_a", {"evil": "1=1 OR 1=1"}) == pytest.approx(0.5)


# ---------------------------------------------------------------- ③ 版本与聚合入口

def test_overview_order_and_coverage(db):
    rows = compute_overview(db)
    assert [r["key"] for r in rows] == METRIC_KEYS
    assert len(rows) == 8
    for r in rows:
        assert r["value"] is not None


def test_metric_versions_and_missing_key(db):
    assert metric_versions(db) == ["v1"]
    assert compute_metric(db, "does_not_exist") is None