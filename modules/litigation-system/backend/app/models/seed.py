"""幂等种子数据（docs/03 §2.3~2.4 + 需求 4.1/4.3 实测真值）。

只在对应唯一键不存在时插入，绝不覆盖人工修改；运行期 schema 同步
（docs/03 §3.2 步骤 2）会在飞书侧字段枚举变化时增量补录 enum_dicts。
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fact import _now_ms
from app.models.meta import CleanRule, CompanyMap, EnumDict, MetricDef
from app.models.ops import Setting

# ---------------------------------------------------------------- 枚举字典

_ENUM_DICTS: list[dict] = [
    # 案件状态（seed 15 项已知；完整 21 项运行期 schema 同步补全）
    {"field": "case_status", "enum_key": k, "color": c, "sort": i}
    for i, (k, c) in enumerate(
        [
            ("已结案", "green"),
            ("一审待判决", "blue"),
            ("二审待判决", "blue"),
            ("强制执行中", "orange"),
            ("执行终本", "orange"),
            ("已撤诉", "gray"),
            ("已和解", "teal"),
            ("破产重整中", "purple"),
            ("协助执行", "amber"),
            ("审理中", "blue"),
            ("待立案", "gray"),
            ("执行异议", "orange"),
            ("管辖权异议", "amber"),
            ("撤诉", "gray"),
            ("等待开庭", "blue"),
        ]
    )
]
# 业务线（需求 4.1 表 8 项）
_ENUM_DICTS += [
    {"field": "biz_line", "enum_key": k, "sort": i}
    for i, k in enumerate(["VOD", "IPTV·OTT", "车载", "雷客", "人力", "哇屋", "研发", "默霆"])
]
# 案由（需求 4.1 表 12 项）
_ENUM_DICTS += [
    {"field": "cause", "enum_key": k, "sort": i}
    for i, k in enumerate(
        [
            "著作权权属、侵权纠纷",
            "侵害作品信息网络传播权纠纷",
            "计算机软件著作权许可使用合同纠纷",
            "劳动争议",
            "服务合同纠纷",
            "合同纠纷",
            "不正当竞争",
            "租赁",
            "执行异议",
            "肖像权",
            "追偿权",
            "破产程序案件",
        ]
    )
]
# 结案原因（15 项实测去重 → 14 规范值；「原告撤诉(重复)」别名并入「原告撤诉」）
_RESOLVE_ALIASES = {"原告撤诉(重复)": "原告撤诉"}
_ENUM_DICTS += [
    {"field": "resolve", "enum_key": k, "aliases": (_RESOLVE_ALIASES if k == "原告撤诉" else None), "sort": i}
    for i, k in enumerate(
        [
            "原告撤诉",
            "双方和解",
            "判决驳回原告的诉讼请求",
            "判赔",
            "裁定驳回对雷石的诉讼请求",
            "驳回上诉维持原判",
            "胜诉",
            "终本",
            "一审驳回对雷石的起诉",
            "按撤回起诉处理",
            "裁定驳回追加请求",
            "撤回上诉",
            "判决驳回对雷石的诉求",
            "裁定驳回雷石的诉讼请求",
        ]
    )
]
# 支付主体
_ENUM_DICTS += [
    {"field": "payer", "enum_key": k, "sort": i}
    for i, k in enumerate(["雷石", "雷客", "诉讼相对方"])
]
# 收案年份（飞书实测含 14 混乱选项：仅 seed 合法规范值 2019~2026 + unknown，
# 乱值映射由 R01 抽取/兜底处理并标记 dirty，不在这里列脏选项）
_YEAR_ALIASES = {f"{y}年": str(y) for y in range(2017, 2027)}
_YEAR_ALIASES.update({f"{y}": str(y) for y in range(2017, 2027)})
_ENUM_DICTS += [
    {"field": "year", "enum_key": str(y), "aliases": _YEAR_ALIASES, "sort": y}
    for y in range(2019, 2027)
]
_ENUM_DICTS.append({"field": "year", "enum_key": "unknown", "label": "未知", "sort": 99, "color": "red"})

# ---------------------------------------------------------------- 清洗规则 R01~R10

_CLEAN_RULES: list[dict] = [
    {
        "rule_tag": "R01",
        "target_field": "year",
        "rule_type": "extract_year",
        "pattern": r"(19|20)\d{2}",
        "priority": 10,
        "description": "收案年份抽取：4 位数字年（容忍带年/空格）；失败走收案时间兜底；仍失败置 unknown(-1) + dirty",
    },
    {
        "rule_tag": "R02",
        "target_field": "plaintiff",
        "rule_type": "de_dup",
        "pattern": r"^[（(]?\d{4}[）)]?.*号$",
        "priority": 20,
        "description": "原告捏造值甄别：命中案件状态枚举或案号格式 → 置待确认（不自动改值）+ dirty",
    },
    {
        "rule_tag": "R03",
        "target_field": "defendant",
        "rule_type": "company_map",
        "mapped": {
            "keywords": ["侵权纠纷", "权属", "许可使用合同", "著作权"],
            "action": "isolate",
        },
        "priority": 30,
        "description": "被告归一：company_map 命中替换 canonical；未命中含案由关键词 → 隔离 + dirty",
    },
    {
        "rule_tag": "R04",
        "target_field": "court",
        "rule_type": "split_court",
        "pattern": r"仲裁委员会|仲裁委",
        "priority": 40,
        "description": "法院/仲裁机构分离：含『仲裁委员会/仲裁委』剥离至 arbitration_org（derived）；长度异常/含案由词 → dirty",
    },
    {
        "rule_tag": "R05",
        "target_field": "*",
        "rule_type": "normalize_enum",
        "priority": 50,
        "description": "枚举别名归一（enum_dicts.aliases 表驱动）：结案原因重复项并入、收案年份 14 选项 → 4 位年、字段枚举统一",
    },
    {
        "rule_tag": "R06",
        "target_field": "case_no",
        "rule_type": "regex_replace",
        "pattern": r"[(（]([^)）]*)[)）]",
        "replacement": r"（\1）",
        "priority": 60,
        "description": "案号规范：（1）括号统一为全角「（）」；（2）去首尾空白与换行；（3）合法格式缺『号』补全（derived）",
    },
    {
        "rule_tag": "R07",
        "target_field": "amount",
        "rule_type": "amount_guard",
        "priority": 70,
        "description": "金额守卫：负值 → NULL + dirty；pay_amount > amount×10 超界标记（不自动改）",
    },
    {
        "rule_tag": "R08",
        "target_field": "resolve",
        "rule_type": "de_dup",
        "priority": 80,
        "description": "结案原因重复项归并：『原告撤诉(重复)』→『原告撤诉』（历史两值归并显示）",
    },
    {
        "rule_tag": "R09",
        "target_field": "lawyer_fee",
        "rule_type": "infer_fee",
        "priority": 90,
        "enabled": False,
        "description": "律师代理费枚举错配：推断 fee_nature（诉讼费/律师费/和解金/判赔金）入 derived；飞书侧字段改造完成前停用",
    },
    {
        "rule_tag": "R10",
        "target_field": "*",
        "rule_type": "null_mark",
        "priority": 100,
        "description": "空值统一 NULL 不显示 0；support_rate 除零 → NULL + 『标的缺失』标记",
    },
]

# ---------------------------------------------------------------- 公司名归一

_COMPANY_MAP: list[dict] = [
    {
        "company_raw": "音集协",
        "canonical": "中国音像著作权集体管理协会",
        "source": "seed",
    },
    {
        "company_raw": "中国音像著作权集体管理协会（音集协）",
        "canonical": "中国音像著作权集体管理协会",
        "source": "seed",
    },
    {
        # docs/03 §2.3 示例：飞书侧确认后启用（首版内置但关）
        "company_raw": "北京雷是天地电子技术股份有限公司",
        "canonical": "北京雷石天地电子技术有限公司",
        "source": "seed",
        "enabled": False,
    },
    {
        "company_raw": "北京雷是天地电子技术有限公司",
        "canonical": "北京雷石天地电子技术有限公司",
        "source": "seed",
        "enabled": False,
    },
]

# ---------------------------------------------------------------- 指标口径 v1.0（需求 4.3）

_METRIC_DEFS: list[dict] = [
    {
        "key": "win_rate_a",
        "title": "胜诉率（口径A·胜败二级）",
        "definition": "胜=结案原因∈{胜诉,驳回上诉维持原判,判决驳回对雷石的诉求,裁定驳回雷石的诉讼请求,裁定驳回对雷石的诉讼请求}; 败=结案原因∈{判赔}; 待定=其余（和解/撤诉/执行类）; 胜诉率=胜/(胜+败)",
        "formula_sql": (
            "WITH t AS (SELECT resolve FROM cases WHERE {filters} AND resolve IS NOT NULL) "
            "SELECT CAST((SELECT COUNT(*) FROM t WHERE resolve IN ("
            "'胜诉','驳回上诉维持原判','判决驳回对雷石的诉求',"
            "'裁定驳回雷石的诉讼请求','裁定驳回对雷石的诉讼请求')) AS REAL) "
            "/ NULLIF((SELECT COUNT(*) FROM t WHERE resolve IN ("
            "'胜诉','驳回上诉维持原判','判决驳回对雷石的诉求',"
            "'裁定驳回雷石的诉讼请求','裁定驳回对雷石的诉讼请求','判赔')),0) AS value"
        ),
        "affected_pages": ["01-overview", "08-metrics"],
        "footnote": "口径A：胜败二级，执行类与调解不计入分母",
    },
    {
        "key": "win_rate_b",
        "title": "胜诉率（口径B·含和解）",
        "definition": "（胜+双方和解）/（胜+败+双方和解）",
        "formula_sql": (
            "WITH t AS (SELECT resolve FROM cases WHERE {filters} AND resolve IS NOT NULL) "
            "SELECT CAST((SELECT COUNT(*) FROM t WHERE resolve IN ("
            "'胜诉','驳回上诉维持原判','判决驳回对雷石的诉求',"
            "'裁定驳回雷石的诉讼请求','裁定驳回对雷石的诉讼请求','双方和解')) AS REAL) "
            "/ NULLIF((SELECT COUNT(*) FROM t WHERE resolve IN ("
            "'胜诉','驳回上诉维持原判','判决驳回对雷石的诉求',"
            "'裁定驳回雷石的诉讼请求','裁定驳回对雷石的诉讼请求','判赔','双方和解')),0) AS value"
        ),
        "affected_pages": ["01-overview", "08-metrics"],
        "footnote": "口径B：含和解，对外宽松口径",
    },
    {
        "key": "support_rate",
        "title": "对方诉求支持率",
        "definition": "支付总金额/标的（均值、中位数、P75）；标的=0 时置 NULL 并标注『标的缺失』",
        "formula_sql": "SELECT SUM(pay_amount)/NULLIF(SUM(amount),0) AS value FROM cases WHERE {filters} AND amount>0 AND pay_amount IS NOT NULL",
        "affected_pages": ["01-overview", "02-search", "07-fees", "08-metrics"],
        "footnote": "支持率=支付总金额/标的；标的缺失样本已排除",
    },
    {
        "key": "verdict_rate",
        "title": "判赔率",
        "definition": "支付总金额/标的，仅对结案原因=判赔 的子集",
        "formula_sql": "SELECT AVG(pay_amount/amount) AS value FROM cases WHERE {filters} AND resolve='判赔' AND amount>0",
        "affected_pages": ["07-fees", "08-metrics"],
        "footnote": "判赔率=Σ(支付总金额/标的)/N，仅统计结案原因=判赔 且标的>0",
    },
    {
        "key": "per_song",
        "title": "单曲判赔（和解金额）",
        "definition": "支付总金额/涉案歌曲数量（均值/中位数）；分母=0 置 NULL",
        "formula_sql": "SELECT AVG(per_song_amount) AS value FROM cases WHERE {filters} AND song_count>0",
        "affected_pages": ["06-songs", "08-metrics"],
        "footnote": "单曲判赔=支付总金额/涉案歌曲数量，均值口径；无歌曲记录已排除",
    },
    {
        "key": "cycle",
        "title": "结案周期",
        "definition": "结案日期−收案时间（天，中位数/均值）；排除空值并标注覆盖量",
        "formula_sql": "SELECT AVG((close_date-accept_date)/86400000.0) AS value FROM cases WHERE {filters} AND accept_date IS NOT NULL AND close_date IS NOT NULL",
        "affected_pages": ["01-overview", "08-metrics"],
        "footnote": "结案周期=结案日期−收案时间（天，均值）；无起止日期样本已排除",
    },
    {
        "key": "series_coef",
        "title": "系列案系数",
        "definition": "合并案件数均值/分布（批量诉讼规模特征）",
        "formula_sql": "SELECT AVG(merged_count) AS value FROM cases WHERE {filters}",
        "affected_pages": ["01-overview", "08-metrics"],
        "footnote": "系列案系数=合并案件数均值",
    },
    {
        "key": "open_count",
        "title": "在办案件数",
        "definition": "案件状态∉{已结案} 的计数",
        "formula_sql": "SELECT COUNT(*) AS value FROM cases WHERE {filters} AND (case_status IS NULL OR case_status NOT IN ('已结案'))",
        "affected_pages": ["01-overview", "08-metrics"],
        "footnote": "在办=案件状态非『已结案』（含状态缺失）",
    },
]

# ---------------------------------------------------------------- 版本指针 KV

_SETTINGS: list[tuple[str, dict]] = [
    ("current_metric_versions", {k: "v1" for k in ["win_rate_a", "win_rate_b", "support_rate", "verdict_rate", "per_song", "cycle", "series_coef", "open_count"]}),
    ("clean_rule_version", {"version": "v1", "enabled_rules": ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R10"]}),
    ("schema_version", {"version": "v1"}),
    ("baseline", {"total": 638, "yi_xie_ji": 312, "open": 42, "verdict_amount": 1284600.0, "dirty_flags": 47}),
]


def seed_meta(db: Session) -> None:
    """幂等种子：仅插入不存在的唯一键（不覆盖人工修改）。"""
    now = _now_ms()

    def _upsert(model, unique: dict, values: dict) -> None:
        exists = db.scalar(select(model).filter_by(**unique))
        if exists is None:
            db.add(model(**values))

    for e in _ENUM_DICTS:
        _upsert(
            EnumDict,
            {"field": e["field"], "enum_key": e["enum_key"]},
            {
                **e,
                "aliases": json.dumps(e["aliases"], ensure_ascii=False) if e.get("aliases") else None,
                "label": e.get("label"),
                "color": e.get("color"),
                "sort": e.get("sort", 0),
            },
        )
    # 注意：clean_rules 是「整包版本快照」，v1 由本文件权威定义（pattern/映射修正随代码
    # 同步，不视为人工修改）；UI（11-dicts 页）改动一律发新版本，回滚=切回旧版本快照。
    for r in _CLEAN_RULES:
        existing = db.scalar(select(CleanRule).filter_by(rule_tag=r["rule_tag"], version="v1"))
        values = {
            **r,
            "version": "v1",
            "mapped": json.dumps(r["mapped"], ensure_ascii=False) if r.get("mapped") else None,
            "enabled": r.get("enabled", True),
        }
        if existing is not None:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(CleanRule(**values))
    for c in _COMPANY_MAP:
        _upsert(
            CompanyMap,
            {"company_raw": c["company_raw"]},
            {
                "company_raw": c["company_raw"],
                "source": c.get("source", "seed"),
                "enabled": c.get("enabled", True),
                "canonical": c["canonical"],
            },
        )
    for m in _METRIC_DEFS:
        # 与 clean_rules 同策略：v1 口径由本文件权威定义（SQL 方言/公式修正随代码同步），
        # 不视为人工修改；UI（08-metrics 页）改动一律发新版本，回滚=切回旧版本快照。
        existing = db.scalar(select(MetricDef).filter_by(key=m["key"], version="v1"))
        values = {
            **m,
            "version": "v1",
            "affected_pages": json.dumps(m["affected_pages"], ensure_ascii=False),
        }
        if existing is not None:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(MetricDef(**values))
    for key, value in _SETTINGS:
        if db.scalar(select(Setting).where(Setting.key == key)) is None:
            db.add(Setting(key=key, value=json.dumps(value, ensure_ascii=False), updated_at=now))

    db.commit()