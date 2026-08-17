"""清洗规则实现（docs/03 §4.2 表驱动 dispatch；t08-4）。

设计约定：
- `RULES[rule_type] = fn(ctx, case, rule) -> list[str]`：纯函数式，返回
  「异常字段名列表」（写 dirty_flags；对齐基线 47 处「只标异常/待确认」语义）；
- 正常修复不标 dirty，仅累积 audit 事件（ctx.log → pipeline 批量写 AuditLog，可回放）；
- 输入语义：year/plaintiff/defendant/court 从 *_raw 重建；枚举列、金额、
  case_no 处理当前列（case_no 优先 case_no_raw 并回填）。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.meta import CompanyMap, CleanRule, EnumDict
from app.models.fact import Case

# R05 normalize_enum 作用的字符串枚举列（year 是 INT，由 R01/R05-year 分支处理）
ENUM_STRING_FIELDS = ["case_status", "cause", "biz_line", "payer", "resolve"]

# 案号缺「号」补全的合法格式判定（年份头 + 末尾数字/汉字）
_CASE_NO_PREFIX_RE = re.compile(r"^[（(]?\d{4}[）)]?")
_CASE_NO_TRAIL_RE = re.compile(r"[\d\u4e00-\u9fff]$")

# 案号捏造值甄别（R02）：与 seed R02.pattern 同构，防旧库 pattern 漂移
_CASE_NO_SUSPECT_RE = re.compile(r"^[（(]?\d{4}[）)]?.*号$")


class RuleCtx:
    """规则执行上下文：字典/映射/原始字段缓存 + audit 事件累积。"""

    def __init__(
        self,
        db: Session,
        rule_version: str,
        aliases: dict[str, dict[str, str]],
        enum_keys: dict[str, set[str]],
        company_map: list[CompanyMap],
        raw_fields: dict[str, dict],
        shared_keywords: list[str],
    ) -> None:
        self.db = db
        self.rule_version = rule_version
        self.aliases = aliases  # {字段: {原始选项: 规范值}}
        self.enum_keys = enum_keys  # {字段: set[规范值]}
        self.company_map = company_map  # 仅 enabled
        self.raw_fields = raw_fields  # record_id → 飞书原始 fields dict
        self.shared_keywords = shared_keywords  # 案由关键词（R03/R04 隔离判定）
        self.events: list[dict] = []  # audit 事件（pipeline 批量落库）
        self.rule_hits: Counter[str] = Counter()

    def log(self, rule: CleanRule, action: str, field: str, old: Any, new: Any, detail: Any = None) -> None:
        """累积一条清洗审计事件（action: update / mark_dirty / isolate）。"""
        self.rule_hits[rule.rule_tag] += 1
        self.events.append(
            {
                "op_type": "clean",
                "table_name": "cases",
                "rule_tag": rule.rule_tag,
                "rule_version": self.rule_version,
                "field": field,
                "old_value": None if old is None else json.dumps(old, ensure_ascii=False, default=str),
                "new_value": None if new is None else json.dumps(new, ensure_ascii=False, default=str),
                "action": action,
                "detail": json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
            }
        )


# ---------------------------------------------------------------- 工具函数

def _load_json_list(v: str | None) -> list[str]:
    """TEXT(JSON 数组) → list[str] | []（容错）。"""
    if not v:
        return []
    try:
        r = json.loads(v)
    except (TypeError, ValueError):
        return []
    return r if isinstance(r, list) else []


def _ms_to_year(ms: int | None) -> int | None:
    """epoch_ms → 业务年（UTC+8）。"""
    if ms is None:
        return None
    try:
        return (
            datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
            .astimezone(timezone(timedelta(hours=8)))
            .year
        )
    except (OverflowError, OSError, ValueError):
        return None


def parse_amount(s: Any) -> float | None:
    """金额字符串解析（修复「¥66,00?」/「66,000」等脏形态）。

    清理 ¥/￥/千分位逗号/全半角空白/尾部问号，再 float()；失败 → None。
    """
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if s is None:
        return None
    t = str(s).strip()
    for ch in ("¥", "￥", "，", ",", " ", "\u3000", "\n", "?", "？"):
        t = t.replace(ch, "")
    if not t:
        return None
    try:
        return float(t)
    except (TypeError, ValueError):
        return None


def _norm_case_no(s: str) -> str:
    """案号规范化（R06 内核，与 seed pattern 同步）：去空白/换行 → 括号全角 → 缺号补全。"""
    s = re.sub(r"[\s\u3000]+", "", s or "")
    s = re.sub(r"[(（]([^)）]*)[)）]", lambda m: f"（{m.group(1)}）", s)
    if re.match(r"^[（(]\d{4}[）)]", s) and not s.endswith("号") and _CASE_NO_TRAIL_RE.search(s):
        s += "号"
    return s


# ---------------------------------------------------------------- R01 extract_year

def _rule_extract_year(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """收案年份：正则史 4 位年 → INT；失败走 accept_date.year；仍失败 → -1 + dirty。"""
    year = None
    raw = (case.year_raw or "").strip()
    if raw:
        m = re.search(rule.pattern or r"(19|20)\d{2}", raw)
        if m:
            year = int(m.group(0))
    if year is None:
        year = _ms_to_year(case.accept_date)
    if year is not None:
        if year != case.year:
            ctx.log(rule, "update", "year", case.year, year)
            case.year = year
        return []
    # 仍失败：置 unknown(-1) + dirty（语义对齐需求 4.2「收案年份规范」）
    if case.year != -1:
        ctx.log(rule, "update", "year", case.year, -1, {"fallback": "unknown(-1)"})
        case.year = -1
    ctx.log(rule, "mark_dirty", "year", case.year_raw, None, {"reason": "无法抽取年份"})
    return ["year"]


# ---------------------------------------------------------------- R02/R08 de_dup

def _rule_de_dup_plaintiff(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """原告捏造值甄别：值∈case_status 枚举 或 形如案号 → 待确认 + dirty（不自动改值）。"""
    raw = (case.plaintiff_raw or "").strip()
    if not raw:
        return []
    status_vals = ctx.enum_keys.get("case_status", set())
    if raw in status_vals or _CASE_NO_SUSPECT_RE.match(raw):
        ctx.log(rule, "mark_dirty", "plaintiff", raw, None, {"reason": "疑似捏造值（枚举/案号误填）"})
        return ["plaintiff"]
    return []


def _rule_de_dup_resolve(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """结案原因重复项归并：aliases 命中即替换（历史两值归并显示；R05 亦覆盖，防御性重复）。"""
    if not case.resolve:
        return []
    canonical = (ctx.aliases.get("resolve") or {}).get(case.resolve)
    if canonical and canonical != case.resolve:
        ctx.log(rule, "update", "resolve", case.resolve, canonical, {"reason": "重复枚举项归并"})
        case.resolve = canonical
    return []


def _rule_de_dup(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    if rule.target_field == "plaintiff":
        return _rule_de_dup_plaintiff(ctx, case, rule)
    if rule.target_field == "resolve":
        return _rule_de_dup_resolve(ctx, case, rule)
    return []


# ---------------------------------------------------------------- R03 company_map

def _lookup_company(ctx: RuleCtx, name: str) -> str | None:
    """company_map 命中 → canonical（等值优先，子串兜底；仅 enabled）。"""
    name = name.strip()
    if not name:
        return None
    for cm in ctx.company_map:
        if name == cm.company_raw:
            return cm.canonical
    for cm in ctx.company_map:
        if len(cm.company_raw) >= 2 and cm.company_raw in name:
            return cm.canonical
    return None


def _rule_company_map(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """被告归一：company_map 命中替换 canonical；未命中且含案由关键词 → 隔离 + dirty。"""
    raw_list = _load_json_list(case.defendant_raw)
    if not raw_list:
        return []
    cur_list = _load_json_list(case.defendant) or list(raw_list)  # 规范列空 → 原始透传
    if not case.defendant:  # 首次透传留痕（仅变更时写库）
        case.defendant = json.dumps(cur_list, ensure_ascii=False)
    mapped = rule.mapped or {}
    if isinstance(mapped, str):  # Text 列存储 JSON 字符串（ORM 注解为 dict 但不去序列化）
        try:
            mapped = json.loads(mapped)
        except (TypeError, ValueError):
            mapped = {}
    keywords = mapped.get("keywords") or ctx.shared_keywords
    dirty: list[str] = []
    new_list: list[str] = []
    for item in cur_list:
        name = (item or "").strip()
        if not name:
            continue
        canonical = _lookup_company(ctx, name)
        if canonical and canonical != name:
            ctx.log(rule, "update", "defendant", name, canonical)
            new_list.append(canonical)
        elif canonical is None and any(k in name for k in keywords):
            ctx.log(rule, "isolate", "defendant", name, None, {"reason": "未归一且含案由关键词", "keywords": keywords})
            dirty.append("defendant")
            new_list.append(name)
        else:
            new_list.append(name)
    if new_list != cur_list:
        case.defendant = json.dumps(new_list, ensure_ascii=False)
    return dirty


# ---------------------------------------------------------------- R04 split_court

def _rule_split_court(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """法院/仲裁机构分离：含『仲裁委员会/仲裁委』剥离至 arbitration_org；长度异常/含案由词 → dirty。"""
    raw_list = _load_json_list(case.court_raw)
    if not raw_list:
        return []
    cur_list = _load_json_list(case.court) or list(raw_list)
    if not case.court:
        case.court = json.dumps(cur_list, ensure_ascii=False)
    pattern = rule.pattern or r"仲裁委员会|仲裁委"
    arb_list = _load_json_list(case.arbitration_org)
    new_court: list[str] = []
    new_arb = list(arb_list)
    dirty: list[str] = []
    changed = False
    for item in cur_list:
        name = (item or "").strip()
        if not name:
            continue
        if re.search(pattern, name):
            if name not in new_arb:
                new_arb.append(name)
                changed = True
            # 从 court 剔除（仲裁机构不入法院列）
            changed = True
            continue
        if len(name) > 64 or any(k in name for k in ctx.shared_keywords):
            dirty.append("court")
        new_court.append(name)
    if changed:
        case.court = json.dumps(new_court, ensure_ascii=False) if new_court else None
        case.arbitration_org = json.dumps(new_arb, ensure_ascii=False) if new_arb else None
        ctx.log(
            rule,
            "update",
            "court",
            ";".join(cur_list),
            ";".join(new_court),
            {"arbitration_org": new_arb},
        )
    return dirty


# ---------------------------------------------------------------- R05 normalize_enum

def _rule_normalize_enum(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """枚举别名归一（enum_dicts.aliases 表驱动）；year 由 R01 抽取，此处兜底 year_raw 别名。"""
    for field in ENUM_STRING_FIELDS:
        cur = getattr(case, field)
        if not cur:
            continue
        canonical = (ctx.aliases.get(field) or {}).get(cur)
        if canonical and canonical != cur:
            ctx.log(rule, "update", field, cur, canonical)
            setattr(case, field, canonical)
    # year 兜底：R01 失败（year_raw 非常规格式）但别名命中（如「2021年」）
    if case.year is None and case.year_raw:
        v = (ctx.aliases.get("year") or {}).get(case.year_raw.strip())
        if v and str(v).isdigit():
            case.year = int(v)
            ctx.log(rule, "update", "year", None, case.year, {"source": "year_raw alias"})
    return []


# ---------------------------------------------------------------- R06 regex_replace

def _rule_regex_replace(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """案号规范：优先 case_no_raw（空则回填后处理）；括号全角/去空白/缺号补全。"""
    raw = case.case_no_raw if case.case_no_raw is not None else case.case_no
    if not raw:
        return []
    if case.case_no_raw is None:
        case.case_no_raw = raw  # 原始值回填（engine 不写 case_no_raw，首次清洗补全）
    normed = _norm_case_no(raw.strip())
    if normed and normed != case.case_no:
        ctx.log(rule, "update", "case_no", case.case_no, normed)
        case.case_no = normed
    return []


# ---------------------------------------------------------------- R07 amount_guard

def _rule_amount_guard(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """金额守卫：字符串脏金额按原始 fields 解析修复；负值 → NULL + dirty；pay>amount×10 超界标记。"""
    dirty: list[str] = []
    raw_fields = ctx.raw_fields.get(case.record_id) or {}
    for col, raw_key in (("amount", "标的"), ("pay_amount", "支付总金额")):
        if raw_key in raw_fields:
            parsed = parse_amount(raw_fields[raw_key])
        else:
            parsed = getattr(case, col)
        if parsed is None:
            continue
        if parsed < 0:  # 负值 → NULL + dirty
            ctx.log(rule, "update", col, getattr(case, col), None, {"reason": "负值置空"})
            setattr(case, col, None)
            dirty.append(col)
        elif parsed != getattr(case, col):  # 修复（「¥66,00?」→ 6600 等）
            ctx.log(rule, "update", col, getattr(case, col), parsed, {"source": "raw_fields" if raw_key in raw_fields else "column"})
            setattr(case, col, parsed)
    # 超界标记（不自动改）：pay_amount > amount×10
    if case.amount and case.pay_amount and case.pay_amount > case.amount * 10:
        ctx.log(rule, "mark_dirty", "pay_amount", case.pay_amount, None, {"reason": f"pay_amount>amount×10（{case.pay_amount} vs {case.amount}）"})
        dirty.append("pay_amount")
    return dirty


# ---------------------------------------------------------------- R10 null_mark

def _rule_null_mark(ctx: RuleCtx, case: Case, rule: CleanRule) -> list[str]:
    """空值统一 NULL 不显示 0；support_rate/per_song 除零（分母缺失）→ 置 NULL + 标记。"""
    dirty: list[str] = []
    if case.support_rate is not None and (case.amount is None or case.amount == 0):
        ctx.log(rule, "mark_dirty", "support_rate", case.support_rate, None, {"reason": "标的缺失（分母 0/空），除零置 NULL"})
        case.support_rate = None
        dirty.append("support_rate")
    if case.per_song_amount is not None and (case.song_count is None or case.song_count == 0):
        ctx.log(rule, "mark_dirty", "per_song_amount", case.per_song_amount, None, {"reason": "歌曲数缺失（分母 0/空），除零置 NULL"})
        case.per_song_amount = None
        dirty.append("per_song_amount")
    # 空串 → NULL（文本列统一）
    for field in ("case_no", "plaintiff", "resolve", "payer", "biz_line", "cause"):
        if getattr(case, field) == "":
            setattr(case, field, None)
    return dirty


# ---------------------------------------------------------------- dispatch 表

RULES: dict[str, Callable[[RuleCtx, Case, CleanRule], list[str]]] = {
    "extract_year": _rule_extract_year,
    "de_dup": _rule_de_dup,
    "company_map": _rule_company_map,
    "split_court": _rule_split_court,
    "normalize_enum": _rule_normalize_enum,
    "regex_replace": _rule_regex_replace,
    "amount_guard": _rule_amount_guard,
    "null_mark": _rule_null_mark,
    # R09 infer_fee（律师代理费推断）未注册：Phase 0 阻塞项，seed 默认 enabled=False；
    # pipeline 对未注册 rule_type 记 error 并跳过，避免静默吞掉意外启用的规则。
}


def build_ctx(db: Session) -> RuleCtx:
    """从库加载字典/映射，构造执行上下文（表驱动数据源）。"""
    aliases: dict[str, dict[str, str]] = {}
    enum_keys: dict[str, set[str]] = {}
    for ed in db.query(EnumDict).all():
        enum_keys.setdefault(ed.field, set()).add(ed.enum_key)
        if ed.aliases:
            try:
                data = json.loads(ed.aliases)
            except (TypeError, ValueError):
                data = {}
            if isinstance(data, dict):
                aliases.setdefault(ed.field, {}).update(data)
    company_map = db.query(CompanyMap).filter_by(enabled=True).all()
    return RuleCtx(
        db=db,
        rule_version="v1",
        aliases=aliases,
        enum_keys=enum_keys,
        company_map=company_map,
        raw_fields={},
        shared_keywords=["侵权纠纷", "权属", "许可使用合同", "著作权"],
    )