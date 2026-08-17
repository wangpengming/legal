"""API 契约测试（t08-8 套件子集；docs/03 §6 契约快照）。

覆盖实现计划「API 面」全部端点：metadata / enums / search（FTS+筛选+排序+分页）/
cases 详情五区 + raw 留档 404 契约 / cases batch / dicts（rule_toggle↔enum↔test↔
dirty-items 治理流）/ stats 五端点 / sync（离线 503 + status + logs）/ export
（CSV BOM+中文表头+口径脚注+审计）/ ai（query 证据命中 + report-templates T1~T7）/
错误契约 {code:-1, message, detail}（main.py 三个 exception_handler）。

隔离：conftest 每模块重置共享临时库（module autouse drop_all+init_db），本模块
与 test_clean 数据现场互不残留；TestClient 必须 with 语句触发 lifespan
（init_db + start_scheduler）。合成数据 record_id 前缀 api0★，避开 test_clean
已占用的 clean/r0★/r_td_★ 命名空间。

⚠ 断言依赖 pytest 按文件名收集顺序（api < clean < metrics < sync）：
q="音"（LIKE 兜底）与 case_no contains "api" 均只命中本模块合成数据。
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, init_db
from app.main import app
from app.models.fact import Case, RawCase, Song, SongCase
from app.models.fts import rebuild_cases_fts
from app.models.meta import CompanyMap
from app.models.ops import AuditLog, Setting
from app.stats.metrics import METRIC_KEYS

DAY = 86_400_000  # 1 天 epoch_ms


def _case(rid: str, **kw) -> Case:
    base = {
        "record_id": rid,
        "case_no": f"（2021）京0105民初{rid}号",
        "case_status": "已结案",
        "merged_count": 1,
        "year": 2021,
        "year_raw": "2021年",
        "plaintiff": "原告A",
        "plaintiff_raw": "原告A",
        "defendant": '["被告B"]',
        "defendant_raw": '["被告B"]',
        "court": '["北京市朝阳区人民法院"]',
        "court_raw": '["北京市朝阳区人民法院"]',
        "cause": "著作权权属、侵权纠纷",
        "resolve": "判赔",
        "payer": "雷石",
        "biz_line": "音乐著作权",
        "amount": 50000.0,
        "pay_amount": 5000.0,
        "song_count": 2,
        "per_song_amount": 2500.0,
        "support_rate": 0.1,
    }
    base.update(kw)
    return Case(**base)


# 合成数据（api01 带 dirty_flags + raw 留档 + 歌曲关联 + 系列案子记录 api03）
API_CASES = [
    _case("api01", plaintiff="音集协", plaintiff_raw="音集协",
          dirty_flags='["defendant"]', resolve="判赔",
          accept_date=DAY * 20, close_date=DAY * 90),
    _case("api02", amount=1000.0, pay_amount=100.0, resolve="胜诉",
          accept_date=DAY * 30, close_date=DAY * 100, dirty_flags=None),
    _case("api03", amount=2000.0, pay_amount=200.0, parent_record_id="api01",
          resolve="原告撤诉", dirty_flags=None,
          accept_date=DAY * 40, close_date=DAY * 150),
]
RAW_CASES = [
    RawCase(record_id="api01", table_name="cases",
            fields_json=json.dumps({"case_no": "（2021）京0105民初api01号",
                                    "plaintiff": "音集协", "_extra": 1}, ensure_ascii=False),
            synced_at=DAY * 300),
]
SONGS = [
    Song(record_id="song01", song_name="可可西里", song_name_raw="可可西里(现场版)", artist="某某"),
]


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    for c in API_CASES:
        session.add(c)
    session.add_all(RAW_CASES)
    session.add_all(SONGS)
    session.flush()
    case = session.scalar(select(Case).where(Case.record_id == "api01"))
    song = session.scalar(select(Song).where(Song.record_id == "song01"))
    session.add(SongCase(song_id=song.id, case_id=case.id, role="主"))
    session.commit()
    rebuild_cases_fts(session)
    session.commit()  # 写锁必须释放：TestClient lifespan 的 init_db 会再写 cases_fts
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(db):
    # with 触发 lifespan：init_db（幂等）+ start_scheduler；退出时 shutdown_scheduler
    with TestClient(app) as c:
        yield c


def _envelope(resp) -> None:
    """成功包裹契约：{code:0, data, meta:{total,page,page_size,footnote}（非空字段）}。"""
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert "data" in body
    assert isinstance(body["meta"], dict)
    return body


# ---------------------------------------------------------------- ① metadata / enums

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": app.version}


def test_metadata_contract(client):
    r = client.get("/api/v1/metadata")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    data = body["data"]
    # 字段元数据：47 列 + in_default 标记（DEFAULT_COLUMNS 18 列）
    assert len(data["fields"]) >= 47
    assert sum(1 for f in data["fields"] if f["in_default"]) == 18
    assert data["view_fields"] and data["view_fields"][0] == "case_no"
    # 枚举/规则/口径：seed 已灌
    assert isinstance(data["enums"], dict) and len(data["enums"]) >= 1
    assert any(r["rule_tag"] == "R01" for r in data["rules"])
    # metric_defs 按 key 字母序（order_by(MetricDef.key)）；断言全量 8 项而非顺序
    assert {m["key"] for m in data["metric_defs"]} == set(METRIC_KEYS)
    assert data["versions"]["metric"] == {k: "v1" for k in METRIC_KEYS}
    assert data["versions"]["baseline"]["total"] == 638
    # 离线模式 + 无同步任务
    assert data["feishu_configured"] is False
    assert data["latest_sync"] is None
    assert "口径" in body["meta"]["footnote"]


def test_enums_single_field(client):
    r = client.get("/api/v1/enums/case_status")
    body = _envelope(r)
    assert body["meta"]["total"] >= 1
    first = body["data"][0]
    assert set(first) >= {"enum_key", "label", "color", "aliases", "version"}


# ---------------------------------------------------------------- ② search：FTS/筛选/排序/分页

def test_search_q_fts_and_like_fallback(client):
    # 多字符走 FTS5：命中 plaintiff=音集协 的 api01（test_clean 原告均为「原告A」）
    r = client.post("/api/v1/search", json={"q": "音集协", "page": 1, "page_size": 20})
    body = _envelope(r)
    assert body["meta"]["total"] == 1
    assert body["data"][0]["record_id"] == "api01"
    assert "检索口径 v1.0" in body["meta"]["footnote"]
    # 单字符走 LIKE 兜底（case_no/plaintiff/court/cause/notes）
    r = client.post("/api/v1/search", json={"q": "音"})
    body = _envelope(r)
    assert body["meta"]["total"] >= 1


def test_search_filters_sort_paging(client):
    # contains 筛选：case_no 含 api → 仅本模块 3 条
    r = client.post(
        "/api/v1/search",
        json={"filters": [{"field": "case_no", "op": "contains", "value": "api0"}]},
    )
    body = _envelope(r)
    assert body["meta"]["total"] == 3
    # 排序 amount desc + 分页第 2 页（1 条/页）：api01(50000) → api03(2000) → api02(1000)
    r = client.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "case_no", "op": "contains", "value": "api0"}],
            "sorts": [{"field": "amount", "desc": True}],
            "page": 2,
            "page_size": 1,
        },
    )
    body = _envelope(r)
    assert body["meta"]["total"] == 3
    assert body["meta"]["page"] == 2
    assert body["meta"]["page_size"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["record_id"] == "api03"  # 2000 是次大
    # range 筛选（year=2021）+ eq
    r = client.post(
        "/api/v1/search",
        json={"filters": [{"field": "year", "op": "range", "min": 2021, "max": 2021},
                          {"field": "biz_line", "op": "eq", "value": "音乐著作权"}]},
    )
    body = _envelope(r)
    assert body["meta"]["total"] >= 3


def test_search_invalid_filter_op_ignored(client):
    # 非法 op → Pydantic Literal 422（防御契约，不 500）；非法 field 合法 op → 条件忽略
    r = client.post("/api/v1/search",
                    json={"filters": [{"field": "evil", "op": "hack", "value": "1"}]})
    assert r.status_code == 422 and r.json()["message"] == "请求参数校验失败"
    r = client.post(
        "/api/v1/search",
        json={"filters": [{"field": "evil", "op": "eq", "value": "1"},
                          {"field": "year", "op": "eq", "value": 2021}]},
    )
    body = _envelope(r)
    assert body["meta"]["total"] >= 3


# ---------------------------------------------------------------- ③ cases 详情 + raw + batch

def test_case_detail_five_sections(client):
    r = client.get("/api/v1/cases/api01")
    body = _envelope(r)
    data = body["data"]
    assert set(data) == {"base", "songs", "raw", "audit", "series"}
    assert data["base"]["record_id"] == "api01"
    assert data["base"]["dirty_flags"] == ["defendant"]  # JSON 反序列化
    assert data["songs"][0]["song_name"] == "可可西里"
    assert data["songs"][0]["role"] == "主"
    assert data["raw"]["synced_at"] == DAY * 300
    # 系列案：api03.parent_record_id=api01 → siblings 含 api03
    assert data["series"]["siblings"][0]["record_id"] == "api03"
    assert "详情口径 v1.0" in body["meta"]["footnote"]
    # 数字 id 也可解析
    cid = data["base"]["id"]
    r2 = client.get(f"/api/v1/cases/{cid}")
    assert r2.json()["data"]["base"]["record_id"] == "api01"


def test_case_detail_404_contract(client):
    r = client.get("/api/v1/cases/not_exist")
    assert r.status_code == 404
    assert r.json() == {"code": -1, "message": "案件不存在：not_exist",
                        "detail": "案件不存在：not_exist"}


def test_case_raw_has_and_missing(client):
    # api01 有留档 → 200 {record_id, fields, synced_at}
    r = client.get("/api/v1/cases/api01/raw")
    body = _envelope(r)
    assert body["data"]["record_id"] == "api01"
    assert body["data"]["fields"]["_extra"] == 1  # 原始值整包
    # api02 无留档 → 404 契约
    r = client.get("/api/v1/cases/api02/raw")
    assert r.status_code == 404
    assert r.json()["message"] == "无原始留档：api02"


def test_cases_batch_tag_and_errors(client):
    # tag：幂等（第一次 linked=1，第二次 0）
    r = client.post("/api/v1/cases/batch", json={"ids": ["api01"], "action": "tag", "tag": "重点案件"})
    body = _envelope(r)
    assert body["data"] == {"tag": "重点案件", "linked": 1, "ids": ["api01"]}
    r = client.post("/api/v1/cases/batch", json={"ids": ["api01"], "action": "tag", "tag": "重点案件"})
    assert r.json()["data"]["linked"] == 0
    # 404 ids 均未命中
    r = client.post("/api/v1/cases/batch", json={"ids": ["ghost"], "action": "tag", "tag": "x"})
    assert r.status_code == 404 and r.json()["message"] == "ids 均未命中案件"
    # 422 tag 必填
    r = client.post("/api/v1/cases/batch", json={"ids": ["api01"], "action": "tag"})
    assert r.status_code == 422 and r.json()["message"] == "action=tag 时 tag 必填"
    # 422 非法 action → 请求参数校验失败
    r = client.post("/api/v1/cases/batch", json={"ids": ["api01"], "action": "boom"})
    assert r.status_code == 422 and r.json()["message"] == "请求参数校验失败"


# ---------------------------------------------------------------- ④ dicts：rule_toggle/enum/test/dirty-items

def test_dicts_rule_toggle_version_pointer(client, db):
    # 翻转 R01 → changed True + clean_rule_version 指针移除；再翻回恢复
    for enabled in (False, True):
        r = client.post("/api/v1/dicts", json={"action": "rule_toggle", "rule_tag": "R01",
                                               "enabled": enabled})
        body = _envelope(r)
        assert body["data"] == {"rule_tag": "R01", "enabled": enabled, "changed": True}
    # 同值再发 → changed False（幂等）
    r = client.post("/api/v1/dicts", json={"action": "rule_toggle", "rule_tag": "R01",
                                           "enabled": True})
    assert r.json()["data"]["changed"] is False
    # 版本指针同步：clean_rule_version（seed 权威格式）enabled_rules 恢复含 R01
    ver = db.scalar(select(Setting).where(Setting.key == "clean_rule_version"))
    assert ver is not None
    snap = json.loads(ver.value)
    assert snap["version"] == "v1" and "R01" in snap["enabled_rules"]
    # 404 规则不存在
    r = client.post("/api/v1/dicts", json={"action": "rule_toggle", "rule_tag": "R99"})
    assert r.status_code == 404 and r.json()["message"] == "规则不存在：R99"


def test_dicts_enum_upsert_and_aliases(client):
    r = client.post("/api/v1/dicts", json={"action": "enum", "field": "case_status",
                                           "enum_key": "测试状态", "label": "测试状态A",
                                           "color": "yellow"})
    body = _envelope(r)
    assert body["data"]["enum_key"] == "测试状态"
    assert body["data"]["aliases"] is None
    # 第二次带 aliases → 合并追加
    r = client.post("/api/v1/dicts", json={"action": "enum", "field": "case_status",
                                           "enum_key": "测试状态",
                                           "aliases": {"历史值X": "测试状态"}})
    body = _envelope(r)
    assert body["data"]["aliases"] == {"历史值X": "测试状态"}
    # 422：action=enum 缺 field
    r = client.post("/api/v1/dicts", json={"action": "enum", "enum_key": "x"})
    assert r.status_code == 422 and r.json()["message"] == "action=enum 时 field/enum_key 必填"


def test_dicts_test_rules_dry_run(client, db):
    # R01 extract_year：year_raw=2022年 → year=2022 → changed + 事件
    r = client.post("/api/v1/dicts/test", json={
        "samples": [{"record_id": "sim01", "year_raw": "2022年", "year": 2021}],
        "rule_tags": ["R01"],
    })
    body = _envelope(r)
    assert body["meta"]["total"] == 1
    item = body["data"][0]
    assert item["changed"] is True
    assert any(e["rule_tag"] == "R01" for e in item["events"])
    # 内存执行不落库：库里没有 sim01
    assert db.scalar(select(Case).where(Case.record_id == "sim01")) is None
    # 422：rule_tags 未命中任何启用规则
    r = client.post("/api/v1/dicts/test", json={
        "samples": [{"record_id": "sim02"}], "rule_tags": ["R99"]})
    assert r.status_code == 422
    assert r.json()["message"] == "无启用规则（规则全禁用或 rule_tags 未命中）"


def test_dicts_dirty_items_governance(client, db):
    # GET 聚合：api01:defendant 出现（raw_value 取 defendant_raw）
    r = client.get("/api/v1/dicts/dirty-items")
    body = _envelope(r)
    keys = [it["key"] for it in body["data"]]
    assert "api01:defendant" in keys
    item = next(it for it in body["data"] if it["key"] == "api01:defendant")
    assert item["raw_value"] == "被告B"
    assert item["case_no"].endswith("api01号")
    # 422 key 缺冒号
    r = client.post("/api/v1/dicts/dirty-items/nocolon", json={"action": "adopt", "value": "x"})
    assert r.status_code == 422 and r.json()["message"] == "key 格式应为 record_id:field"
    # 404 案件不存在
    r = client.post("/api/v1/dicts/dirty-items/ghost:defendant", json={"action": "adopt", "value": "x"})
    assert r.status_code == 404 and r.json()["message"] == "案件不存在：ghost"
    # 404 该字段无脏标记（api02 无 dirty）
    r = client.post("/api/v1/dicts/dirty-items/api02:defendant", json={"action": "adopt", "value": "x"})
    assert r.status_code == 404
    assert r.json()["message"] == "该字段无脏标记：defendant（key=api02:defendant）"
    # 422 adopt 无 value
    r = client.post("/api/v1/dicts/dirty-items/api01:defendant", json={"action": "adopt"})
    assert r.status_code == 422 and r.json()["message"] == "action=adopt 时 value（规范值）必填"
    # adopt：写入 CompanyMap（原始值→规范值）+ 清除脏标记
    r = client.post("/api/v1/dicts/dirty-items/api01:defendant",
                    json={"action": "adopt", "value": "音集协"})
    body = _envelope(r)
    assert body["data"]["remaining_flags"] == []
    row = db.scalar(select(CompanyMap).where(CompanyMap.company_raw == "被告B"))
    assert row is not None and row.canonical == "音集协" and row.source == "人工采纳"
    # 详情 dirty_flags 已清空
    detail = client.get("/api/v1/cases/api01").json()["data"]["base"]
    assert detail["dirty_flags"] is None
    # audit 追溯
    aud = db.scalar(select(AuditLog).where(AuditLog.record_id == "api01",
                                           AuditLog.action == "dirty_adopt"))
    assert aud is not None and aud.op_type == "api"


# ---------------------------------------------------------------- ⑤ stats 五端点

def test_stats_overview_contract(client):
    body = _envelope(client.get("/api/v1/stats/overview"))
    data = body["data"]
    assert [k["key"] for k in data["kpis"]] == METRIC_KEYS
    assert data["metric_versions"] == ["v1"]
    assert data["trend"] and data["bizline"]  # 非空聚合
    assert all(k["value"] is not None for k in data["kpis"])
    # summary 摘要（01-overview hero 数字）
    s = data["summary"]
    assert s["total_cases"] >= 1
    assert s["acmc_cases"] >= 0 and s["acmc_cases"] <= s["total_cases"]
    assert s["monthly_new"] >= 0
    assert s["verdict_total"] >= 0


def test_stats_party_required_and_hit(client):
    # name 缺省 → 请求参数校验失败；空串 → 业务 422
    assert client.get("/api/v1/stats/party").status_code == 422
    r = client.get("/api/v1/stats/party", params={"name": "   "})
    assert r.status_code == 422 and r.json()["message"] == "name 必填（被告名称）"
    # 命中：api01/02/03 defendant 均含「被告B」
    body = _envelope(client.get("/api/v1/stats/party", params={"name": "被告B"}))
    assert body["data"]["total"] == 3
    assert body["data"]["verdict_count"] == 1  # 仅 api01 resolve=判赔
    assert body["data"]["verdict_amount"] == 5000.0


def test_stats_party_detail_extension(client):
    """G5-02 画像详情：年份分布 / 案由分布 / 胜诉率A / 近期案件扩展字段。"""
    body = _envelope(client.get("/api/v1/stats/party", params={"name": "被告B"}))
    d = body["data"]
    assert {"win_rate_a", "years", "causes"} <= set(d)
    # 胜诉率A：api02 胜诉 / (api02 胜诉 + api01 判赔) = 0.5；api03 原告撤诉为待定不计
    assert d["win_rate_a"] == 0.5
    assert d["years"] == [{"year": 2021, "case_count": 3, "verdict_amount": 5000.0}]
    assert d["causes"][0]["cause"] == "著作权权属、侵权纠纷"
    assert d["causes"][0]["case_count"] == 3
    # 近期案件表需要业务线/支持率/案由（04-parties 表格列）
    row = d["cases"][0]
    assert {"biz_line", "cause", "support_rate"} <= set(row)
    assert row["biz_line"] == "音乐著作权"
    assert row["support_rate"] == 0.1  # api01 公式字段


def test_stats_parties_list(client):
    """G5-01 主体清单：defendant JSON 数组扁平化聚合（案件数倒序 + 胜诉率）。"""
    body = _envelope(client.get("/api/v1/stats/parties"))
    d = body["data"]
    assert {"items", "total_parties", "covered_cases"} <= set(d)
    assert d["total_parties"] >= 1 and d["covered_cases"] == 3
    first = d["items"][0]
    assert first["name"] == "被告B"
    assert first["case_count"] == 3
    assert first["win_rate_a"] == 0.5
    assert first["verdict_count"] == 1 and first["verdict_amount"] == 5000.0
    assert first["offsite_count"] == 0  # court 含北京 → 非异地
    assert first["biz_lines"] == ["音乐著作权"]
    assert first["first_year"] == 2021 and first["last_year"] == 2021
    assert first["share"] == 1.0
    # limit 参数生效
    body = _envelope(client.get("/api/v1/stats/parties", params={"limit": 1}))
    assert len(body["data"]["items"]) == 1


def test_stats_bizline_and_songs(client):
    body = _envelope(client.get("/api/v1/stats/bizline"))
    assert {"year", "items"} <= set(body["data"])
    body = _envelope(client.get("/api/v1/stats/songs"))
    assert {"songs", "aggregate", "metric"} <= set(body["data"])
    assert body["data"]["songs"][0]["song_name"] == "可可西里"


def test_stats_fees_contract(client):
    body = _envelope(client.get("/api/v1/stats/fees"))
    data = body["data"]
    assert {"year", "four", "monthly", "dubious"} <= set(data)
    assert set(data["four"]) == {"verdict", "recovered", "expense", "net"}
    assert data["four"]["verdict"] == {"amount": 5000.0, "count": 1}  # api01 判赔支付
    assert data["four"]["expense"]["amount"] is None  # 支出口径 Phase 2 前置（hint 提示不可得）


# ---------------------------------------------------------------- ⑤⑤ analysis：多维热力矩阵 + 下钻（G6）

def test_stats_analysis_matrix(client):
    """G6-01 热力矩阵：三维 rows/cols/cells 与判赔占比（案件数聚合 + year 脏值剔除）。"""
    body = _envelope(client.get("/api/v1/stats/analysis", params={"dim": "bizYear"}))
    d = body["data"]
    assert {"dim", "row_label", "col_label", "rows", "cols", "cells", "total_cases"} <= set(d)
    assert d["row_label"] == "业务线" and d["col_label"] == "年份"
    assert d["rows"] == ["音乐著作权"]  # 3 案同业务线，按案件数降序
    assert d["cols"] == ["2021"]  # 年份升序字符串化
    assert d["total_cases"] == 3
    cell = d["cells"][0][0]
    assert cell["case_count"] == 3
    assert cell["verdict_count"] == 1  # api01 判赔
    assert cell["verdict_rate"] == pytest.approx(1 / 3, abs=0.0001)
    # causeYear：案由即行
    body = _envelope(client.get("/api/v1/stats/analysis", params={"dim": "causeYear"}))
    assert body["data"]["rows"] == ["著作权权属、侵权纠纷"]
    # payerStatus：支付主体 × 案件状态
    body = _envelope(client.get("/api/v1/stats/analysis", params={"dim": "payerStatus"}))
    assert body["data"]["rows"] == ["雷石"]  # fixture payer 默认
    assert body["data"]["cols"] == ["已结案"]
    assert body["data"]["cells"][0][0]["case_count"] == 3
    # 非法维度 → 422
    assert client.get("/api/v1/stats/analysis", params={"dim": "bad"}).status_code == 422


def test_stats_analysis_drill(client):
    """G6-02 热力下钻：命中明细 + 案由聚合（可二次下钻）+ 被告/法院 JSON 扁平化。"""
    body = _envelope(client.get("/api/v1/stats/analysis/drill",
                                params={"dim": "bizYear", "x": "音乐著作权", "col": "2021"}))
    d = body["data"]
    assert {"x", "dim", "col", "cause", "items", "total", "causes"} <= set(d)
    assert d["x"] == "音乐著作权" and d["col"] == 2021 and d["total"] == 3
    assert d["causes"] == [{"cause": "著作权权属、侵权纠纷", "case_count": 3}]
    ids = {it["record_id"] for it in d["items"]}
    assert ids == {"api01", "api02", "api03"}
    first = d["items"][0]
    assert first["defendant"] == ["被告B"] and first["court"] == ["北京市朝阳区人民法院"]
    assert first["biz_line"] == "音乐著作权" and first["support_rate"] == 0.1
    # 案由二次下钻：命中全部；不存在的案由 → 0 件
    body = _envelope(client.get("/api/v1/stats/analysis/drill",
                                params={"dim": "bizYear", "x": "音乐著作权",
                                        "col": "2021", "cause": "著作权权属、侵权纠纷"}))
    assert body["data"]["total"] == 3
    body = _envelope(client.get("/api/v1/stats/analysis/drill",
                                params={"dim": "bizYear", "x": "音乐著作权", "cause": "不存在案由"}))
    assert body["data"]["total"] == 0
    # causeYear 维度下行即案由 → causes 不再二次聚合
    body = _envelope(client.get("/api/v1/stats/analysis/drill",
                                params={"dim": "causeYear", "x": "著作权权属、侵权纠纷", "col": "2021"}))
    assert body["data"]["causes"] == [] and body["data"]["total"] == 3
    # payerStatus 维度下钻（col=已结案）
    body = _envelope(client.get("/api/v1/stats/analysis/drill",
                                params={"dim": "payerStatus", "x": "雷石", "col": "已结案"}))
    assert body["data"]["total"] == 3


# ---------------------------------------------------------------- ⑥ sync：离线 503 / status / logs

def test_sync_run_offline_503(client):
    r = client.post("/api/v1/sync/run", json={"type": "incremental"})
    assert r.status_code == 503
    assert r.json()["message"] == ("飞书凭证未配置（离线模式）：同步仅可在注入 "
                                   "FEISHU_* 环境变量后执行")
    # type=record 但离线同样 503（凭证检查优先）
    assert client.post("/api/v1/sync/run", json={"type": "record", "id": "x"}).status_code == 503


def test_sync_status_and_logs(client):
    body = _envelope(client.get("/api/v1/sync/status"))
    assert body["data"]["running"] is False
    assert body["data"]["feishu_configured"] is False
    assert body["data"]["jobs"]["clean"] == "clean_all"
    body = _envelope(client.get("/api/v1/sync/logs"))
    assert isinstance(body["data"], list)
    # 参数边界：limit 越界 → 422
    assert client.get("/api/v1/sync/logs", params={"limit": 999}).status_code == 422


# ---------------------------------------------------------------- ⑦ export：CSV BOM + 中文表头 + 脚注 + 审计

def test_export_csv_bom_header_footnote_audit(client, db):
    r = client.post("/api/v1/export", json={
        "scope": "all",
        "columns": ["record_id", "case_no", "plaintiff", "biz_line"],
        "format": "csv",
        "with_footnote": True,
    })
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    text = r.content.decode("utf-8-sig")  # 削 BOM（\ufeff 前缀）
    lines = text.strip().splitlines()
    assert lines[0] == "同步键,案号,原告,业务线"  # CASE_FIELD_META.label 中文表头
    assert lines[-1].startswith("# 口径说明")
    rows = lines[1:-1]
    assert any("api01" in ln for ln in rows)
    assert all(len(ln.split(",")) == 4 for ln in rows)
    # scope=search：q 命中 + columns 白名单过滤
    r = client.post("/api/v1/export", json={
        "scope": "search", "q": "音集协",
        "columns": ["case_no", "plaintiff"], "with_footnote": False})
    text = r.content.decode("utf-8-sig")
    pulls = text.strip().splitlines()
    assert pulls[0] == "案号,原告"
    assert len(pulls) == 2  # 表头 + 1 行（api01），无脚注
    # 422 columns 全非法
    r = client.post("/api/v1/export", json={"columns": ["evil_col"]})
    assert r.status_code == 422 and r.json()["message"] == "columns 为空或全非法"
    # xlsx：openpyxl 为 requirements.txt 正式依赖 → 200 + OOXML zip 魔数 + 附件头
    r = client.post("/api/v1/export", json={"format": "xlsx"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx = ZIP 容器
    assert "spreadsheetml" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    # 审计：op_type=export 已记录
    aud = db.scalar(select(AuditLog).where(AuditLog.op_type == "export",
                                           AuditLog.table_name == "cases"))
    assert aud is not None
    detail = json.loads(aud.detail)
    assert detail["scope"] == "search" or detail["rows"] >= 1


# ---------------------------------------------------------------- ⑧ ai：query 证据命中 + report-templates

def test_ai_query_empty_question(client):
    body = _envelope(client.post("/api/v1/ai/query", json={"question": ""}))
    assert body["data"]["answer"] == "问题为空，无法检索"
    assert body["data"]["evidence"] == []
    assert "AI 检索 v1" in body["meta"]["footnote"]


def test_ai_query_evidence_hit(client, db):
    r = client.post("/api/v1/ai/query", json={"question": "音集协 判赔"})
    body = _envelope(r)
    assert body["meta"]["total"] >= 1
    assert body["data"]["answer"].startswith("本地检索")
    assert len(body["data"]["evidence"]) <= 10
    if body["data"]["evidence"]:
        ev = body["data"]["evidence"][0]
        assert "case_no" in ev and "amount" in ev  # _EVIDENCE_COLUMNS 子集
    assert len(body["data"]["metrics"]) == 8
    # 审计 ai_query（空问题提前 return 不写审计，非空才落 AuditLog）
    aud = db.scalar(select(AuditLog).where(AuditLog.op_type == "ai",
                                           AuditLog.action == "ai_query"))
    assert aud is not None and aud.table_name == "cases"
    assert json.loads(aud.detail)["question"] == "音集协 判赔"


def test_ai_report_templates_t1_t7(client):
    body = _envelope(client.get("/api/v1/ai/report-templates"))
    assert body["meta"]["total"] == 7
    assert {t["key"] for t in body["data"]} == {f"T{i}" for i in range(1, 8)}
    t1 = next(t for t in body["data"] if t["key"] == "T1")
    assert t1["title"] == "案件全景报告"
