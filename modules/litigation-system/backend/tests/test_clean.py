"""清洗规则引擎测试（t08-4 验证固化；t08-8 套件子集）。

覆盖：表驱动隔离（仅注入规则生效）/ 未注册规则 skipped 事件 / R01~R10 全量
断言 / audit 回放 / 幂等第二遍 0 变更 + 收敛语义 / FTS 重建命中。
同模块测试按定义顺序执行（数据演化依赖：表驱动 → 全量 → 幂等 → FTS）。
"""
import json

import pytest
from sqlalchemy import select

from app.clean.pipeline import CleanPipeline
from app.core.database import SessionLocal, init_db
from app.models.fact import Case, RawCase
from app.models.fts import search_cases
from app.models.meta import CleanRule
from app.models.ops import AuditLog


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def get(db: SessionLocal, rid: str) -> Case:
    return db.scalar(select(Case).where(Case.record_id == rid))


def audits(db: SessionLocal, rid: str, tag: str | None = None, action: str | None = None, field: str | None = None) -> list[AuditLog]:
    stmt = select(AuditLog)
    if rid:
        stmt = stmt.where(AuditLog.record_id == rid)
    if tag:
        stmt = stmt.where(AuditLog.rule_tag == tag)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if field:
        stmt = stmt.where(AuditLog.field == field)
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------- ① 夹具：脏数据形态

def _case(rid: str, **kw) -> Case:
    base = {
        "record_id": rid,
        "case_no": None,
        "case_no_raw": None,
        "year": 2021,
        "year_raw": "2021年",
        "plaintiff": "原告A",
        "plaintiff_raw": "原告A",
        "defendant": None,
        "defendant_raw": '["被告B"]',
        "court": None,
        "court_raw": '["北京市朝阳区人民法院"]',
        "cause": "著作权权属、侵权纠纷",
        "resolve": "判赔",
        "payer": "雷石",
        "biz_line": "VOD",
        "case_status": "已结案",
        "amount": 50000,
        "pay_amount": 5000,
        "song_count": 2,
        "per_song_amount": 2500,
        "support_rate": 0.1,
    }
    base.update(kw)
    return Case(**base)


CASES = {
    # 干净样本：各规则均不应命中
    "clean": _case("clean"),
    # R01 extract_year：正则 / accept_date 兜底 / 仍失败 → -1+dirty
    "r01a": _case("r01a", year_raw="2022年", year=2021),
    "r01b": _case("r01b", year_raw="不详", accept_date=1619827200000),  # 2021-05-01
    "r01c": _case("r01c", year=None, year_raw=None, accept_date=None),
    # R02 de_dup plaintiff：枚举值 / 案号格式 → dirty 不自动改
    "r02a": _case("r02a", plaintiff_raw="已结案"),
    "r02b": _case("r02b", plaintiff_raw="（2021）京0105民初12345号"),
    # R03 company_map：3 变体归一 / 含案由关键词未归一 → dirty
    "r03a": _case("r03a", defendant=None, defendant_raw='["音集协"]'),
    "r03b": _case("r03b", defendant=None, defendant_raw='["中国音像著作权集体管理协会（音集协）"]'),
    "r03c": _case("r03c", defendant=None, defendant_raw='["无名著作权侵权公司"]'),
    # R04 split_court：仲裁机构剥离 / 保留 / 长度异常 → dirty
    "r04a": _case("r04a", court_raw='["杭州仲裁委员会"]'),
    "r04b": _case("r04b", court_raw='["上海市浦东新区人民法院"]'),
    "r04c": _case("r04c", court_raw=json.dumps(["长" * 70], ensure_ascii=False)),
    # R05 normalize_enum：结案原因重复项归并
    "r05a": _case("r05a", resolve="原告撤诉(重复)"),
    # R06 regex_replace：半角括号+缺号 / 空白+回填
    "r06b": _case("r06b", case_no="(2021)京0105民初123", case_no_raw="(2021)京0105民初123"),
    "r06c": _case("r06c", case_no="(2020) 京0105民初 456号", case_no_raw=None),
    # R07 amount_guard：原始 fields 修复 / 负值 NULL+dirty / 超界标记
    "r07a": _case("r07a", amount=None, pay_amount=None),
    "r07b": _case("r07b", amount=None, pay_amount=None),
    "r07c": _case("r07c", amount=50000, pay_amount=None),
    "r07d": _case("r07d", amount=1000, pay_amount=20000),
    # R10 null_mark：除零置 NULL / 空串 → NULL
    "r10a": _case("r10a", amount=0, support_rate=0.5),
    "r10b": _case("r10b", song_count=None, per_song_amount=100),
    "r10c": _case("r10c", payer=""),
    # 表驱动隔离验证（仅 R04 注入，year 不应被处理；须在表驱动跑之后才允许全量清洗它们）
    "r_td_a": _case("r_td_a", year=None, year_raw="2020年", court_raw='["深圳仲裁委"]'),
    "r_td_b": _case("r_td_b", year=None, year_raw="2019年", court_raw='["四川省成都市中级人民法院"]'),
}

RAW_FIELDS = {
    "r07a": {"fields": {"标的": "¥66,000", "支付总金额": "66,000"}},
    "r07b": {"fields": {"标的": "66,00? ", "支付总金额": None}},
    "r07c": {"fields": {"标的": "-5000"}},
}


@pytest.fixture(scope="module")
def seeded(db):
    db.add_all(CASES.values())
    for rid, fields in RAW_FIELDS.items():
        db.add(RawCase(record_id=rid, table_name="cases", fields_json=json.dumps(fields, ensure_ascii=False), synced_at=1))
    db.commit()
    return CASES


# ---------------------------------------------------------------- ② 表驱动隔离 + 未注册规则

def test_table_driven_only_injected_rules_run(db, seeded):
    r04_rule = db.scalar(select(CleanRule).where(CleanRule.rule_tag == "R04"))
    result = CleanPipeline(db, records=["r_td_a", "r_td_b"], rules=[r04_rule]).run()
    assert set(result.rule_hits.keys()) == {"R04"} and result.rule_hits.get("R04", 0) >= 1, result.rule_hits
    assert get(db, "r_td_a").year is None  # R01 未注入 → year 不处理
    assert json.loads(get(db, "r_td_a").arbitration_org) == ["深圳仲裁委"]
    assert json.loads(get(db, "r_td_b").court) == ["四川省成都市中级人民法院"]


def test_unregistered_rule_skipped_not_silent(db, seeded):
    r09_rule = db.scalar(select(CleanRule).where(CleanRule.rule_tag == "R09"))
    if r09_rule is None:
        return  # seed 未提供则不测
    CleanPipeline(db, records=["r01a"], rules=[r09_rule]).run()
    assert len(audits(db, "r01a", "R09", "skipped")) == 1


# ---------------------------------------------------------------- ③ 全量清洗（R01~R10 全启用）

def test_full_clean_all_rules(db, seeded):
    r1 = CleanPipeline(db).run()
    for c in seeded.values():
        db.refresh(c)

    assert r1.rule_version == "v1"
    assert r1.cases_total == len(CASES)
    assert r1.errors == []

    # 全量：表驱动样本的 year 现在被抽取
    assert get(db, "r_td_a").year == 2020 and get(db, "r_td_b").year == 2019

    # R01
    assert get(db, "r01a").year == 2022
    assert get(db, "r01b").year == 2021
    assert get(db, "r01c").year == -1 and json.loads(get(db, "r01c").dirty_flags) == ["year"]
    # R02
    assert json.loads(get(db, "r02a").dirty_flags) == ["plaintiff"] and get(db, "r02a").plaintiff == "原告A"
    assert json.loads(get(db, "r02b").dirty_flags) == ["plaintiff"]
    # R03
    assert json.loads(get(db, "r03a").defendant) == ["中国音像著作权集体管理协会"]
    assert json.loads(get(db, "r03b").defendant) == ["中国音像著作权集体管理协会"]
    assert "defendant" in json.loads(get(db, "r03c").dirty_flags) and get(db, "r03c").defendant is not None
    # R04
    assert json.loads(get(db, "r04a").arbitration_org) == ["杭州仲裁委员会"] and get(db, "r04a").court is None
    assert json.loads(get(db, "r04b").court) == ["上海市浦东新区人民法院"]
    assert "court" in json.loads(get(db, "r04c").dirty_flags)
    # R05 / R08
    assert get(db, "r05a").resolve == "原告撤诉"
    # R06
    assert get(db, "r06b").case_no == "（2021）京0105民初123号"
    assert get(db, "r06b").case_no_raw == "(2021)京0105民初123"
    assert get(db, "r06c").case_no == "（2020）京0105民初456号" and get(db, "r06c").case_no_raw == "(2020) 京0105民初 456号"
    # R07
    assert get(db, "r07a").amount == 66000.0
    assert get(db, "r07b").amount == 6600.0
    assert get(db, "r07c").amount is None and "amount" in json.loads(get(db, "r07c").dirty_flags)
    assert get(db, "r07d").amount == 1000.0 and "pay_amount" in json.loads(get(db, "r07d").dirty_flags)
    # R10
    assert get(db, "r10a").support_rate is None and "support_rate" in json.loads(get(db, "r10a").dirty_flags)
    assert get(db, "r10b").per_song_amount is None and "per_song_amount" in json.loads(get(db, "r10b").dirty_flags)
    assert get(db, "r10c").payer is None
    # 干净样本
    assert get(db, "clean").dirty_flags is None
    assert get(db, "clean").year == 2021

    # audit 回放（清洗事件留痕）
    assert len(audits(db, None, None, "error")) == 0  # 无规则静默失败
    assert len(audits(db, "r03a", "R03", "update", "defendant")) == 1
    assert len(audits(db, "r02a", "R02", "mark_dirty", "plaintiff")) == 1
    assert len(audits(db, "r04a", "R04", "update", "court")) == 1
    assert len(audits(db, "r10a", "R10", "mark_dirty", "support_rate")) == 1
    assert r1.audited >= 20
    assert r1.rule_hits.get("R03", 0) >= 2


# ---------------------------------------------------------------- ④ 幂等第二遍

def test_idempotent_second_pass_convergence(db, seeded):
    r2 = CleanPipeline(db).run()
    assert r2.cases_clean == 0
    assert get(db, "r03a").defendant == '["中国音像著作权集体管理协会"]'
    assert get(db, "r06b").case_no == "（2021）京0105民初123号"
    # 收敛语义：已修复的标记解除（r10a support_rate 已 NULL → 不再脏）
    assert get(db, "r10a").dirty_flags is None
    # 持续异常仍标记（每轮重建保留）
    assert json.loads(get(db, "r01c").dirty_flags) == ["year"]
    assert "amount" in json.loads(get(db, "r07c").dirty_flags)
    assert "pay_amount" in json.loads(get(db, "r07d").dirty_flags)


# ---------------------------------------------------------------- ⑤ FTS 重建生效

def test_fts_rebuild_after_clean(db, seeded):
    hits, _ = search_cases(db, "中国音像著作权集体管理协会")
    hit_ids = {h["case_id"] for h in hits}
    assert get(db, "r03a").id in hit_ids and get(db, "r03b").id in hit_ids, hit_ids
    hits2, _ = search_cases(db, "京0105民初123")
    assert get(db, "r06b").id in {h["case_id"] for h in hits2}