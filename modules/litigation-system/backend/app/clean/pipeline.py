"""清洗管道（docs/03 §4.1 执行模型 + 实现计划 t08-4）。

执行单位：同步完成后的自动阶段（t08-6 cron_clean 接入）或手动「重跑全部」。
流程：读取启用规则按 priority 排序 → 重置目标行 dirty_flags → 逐行逐规则应用
（RULES 表驱动）→ 异常字段聚合写 dirty_flags → audit 事件批量落 AuditLog →
FTS 影子表重建（spec 值变化影响检索）→ 返回 CleanResult 汇总。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clean.rules import RULES, RuleCtx, build_ctx
from app.models.fact import Case, RawCase, _now_ms
from app.models.fts import rebuild_cases_fts
from app.models.meta import CleanRule
from app.models.ops import AuditLog, Setting


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


@dataclass
class CleanResult:
    """清洗结果汇总（API /admin 展示 + 审计留痕）。"""

    rule_version: str
    started_at: int = 0
    finished_at: int = 0
    cases_total: int = 0
    cases_clean: int = 0  # 实际执行的行数（排除空表/未命中记录场景）
    dirty_flags_total: int = 0  # 全部脏标记计数
    rule_hits: dict[str, int] = field(default_factory=dict)  # rule_tag → 命中记录数
    audited: int = 0  # audit 事件数
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rule_version": self.rule_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cases_total": self.cases_total,
            "cases_clean": self.cases_clean,
            "dirty_flags_total": self.dirty_flags_total,
            "rule_hits": self.rule_hits,
            "audited": self.audited,
            "skipped": self.skipped,
            "errors": self.errors,
        }


class CleanPipeline:
    """表驱动清洗管道：规则集 = clean_rules（enabled + priority 排序）。"""

    def __init__(self, db: Session, records: list[str] | None = None, rules: list[CleanRule] | None = None) -> None:
        self.db = db
        self.records = records  # None = 全量；否则仅处理指定 record_id 列表（单条重跑）
        self.rules = rules  # 测试注入；None = 从库读取启用规则

    # ── 运行 ────────────────────────────────────────────────────────────

    def run(self) -> CleanResult:
        version = self._rule_version()
        result = CleanResult(rule_version=version)
        enabled = self._enabled_rules()
        if not enabled:
            result.errors.append("无启用规则（clean_rule_version.enabled_rules 为空或全禁用）")
            return result

        ctx = build_ctx(self.db)
        ctx.rule_version = version
        # 加载原始 fields 缓存（R07 金额解析源；记录级过滤）
        self._load_raw_fields(ctx)

        result.started_at = _now_ms()
        cases = self._iter_cases()
        for case in cases:
            result.cases_total += 1
            if self._apply(case, enabled, ctx):
                result.cases_clean += 1
            result.dirty_flags_total += len(_load_dirty(case))

        # audit 事件批量落库（与 cases 同事务；回放见 docs/03 §4.3）
        if ctx.events:
            now = _now_ms()
            self.db.add_all(
                [AuditLog(created_at=now, **{k: v for k, v in e.items() if k != "_record_id"}) for e in ctx.events]
            )
            result.audited = len(ctx.events)
        result.rule_hits = dict(ctx.rule_hits)
        result.skipped = result.cases_total - result.cases_clean

        # FTS 影子表重建（案号/原告等规范化值变更影响检索；638 行秒级）
        rebuild_cases_fts(self.db)
        self.db.commit()
        result.finished_at = _now_ms()
        return result

    # ── 内部 ────────────────────────────────────────────────────────────

    def _rule_version(self) -> str:
        setting = self.db.scalar(select(Setting).where(Setting.key == "clean_rule_version"))
        if setting is None:
            return "v1"
        try:
            return (json.loads(setting.value) or {}).get("version", "v1")
        except (TypeError, ValueError):
            return "v1"

    def _enabled_rules(self) -> list[CleanRule]:
        # 测试/单次注入优先（records 局部重跑）；否则从库读启用规则
        if self.rules is not None:
            return sorted(self.rules, key=lambda r: (r.priority, r.rule_tag))
        setting = self.db.scalar(select(Setting).where(Setting.key == "clean_rule_version"))
        enabled_tags: set[str] | None = None
        if setting is not None:
            try:
                saved = json.loads(setting.value) or {}
                if saved.get("enabled_rules") is not None and len(saved["enabled_rules"]) > 0:
                    enabled_tags = set(saved["enabled_rules"])
            except (TypeError, ValueError):
                pass
        stmt = select(CleanRule)
        if enabled_tags is not None:
            stmt = stmt.where(CleanRule.rule_tag.in_(enabled_tags))
        stmt = stmt.where(CleanRule.enabled.is_(True)).order_by(CleanRule.priority, CleanRule.rule_tag)
        return list(self.db.scalars(stmt).all())

    def _load_raw_fields(self, ctx: RuleCtx) -> None:
        """raw_cases 整包 fields 载入（R07 从原始值解析脏金额）。"""
        stmt = select(RawCase.record_id, RawCase.fields_json)
        if self.records:
            stmt = stmt.where(RawCase.record_id.in_(self.records))
        for record_id, fields_json in self.db.execute(stmt).all():
            try:
                ctx.raw_fields[record_id] = json.loads(fields_json).get("fields", {})
            except (TypeError, ValueError):
                continue

    def _iter_cases(self) -> list[Case]:
        stmt = select(Case)
        if self.records:
            stmt = stmt.where(Case.record_id.in_(self.records))
        return list(self.db.scalars(stmt).all())

    def _apply(self, case: Case, enabled: list[CleanRule], ctx: RuleCtx) -> bool:
        """单行规则链：重置 dirty_flags → 逐规则 → 异常字段聚合。返回是否发生任何变更。"""
        case.dirty_flags = None  # 重跑语义：重建脏标记（不清 audit，保证回放）
        anomalies: set[str] = set()
        prev_hash = _row_snapshot(case)
        start_idx = len(ctx.events)
        for rule in enabled:
            fn = RULES.get(rule.rule_type)
            if fn is None:
                ctx.events.append(
                    {
                        "op_type": "clean",
                        "table_name": "cases",
                        "rule_tag": rule.rule_tag,
                        "rule_version": ctx.rule_version,
                        "field": rule.target_field,
                        "action": "skipped",
                        "detail": json.dumps({"reason": f"未支持 rule_type: {rule.rule_type}"}, ensure_ascii=False),
                    }
                )
                continue
            try:
                anomalies.update(fn(ctx, case, rule))
            except Exception as exc:  # noqa: BLE001 单规则失败不阻断整行
                ctx.events.append(
                    {
                        "op_type": "clean",
                        "table_name": "cases",
                        "rule_tag": rule.rule_tag,
                        "rule_version": ctx.rule_version,
                        "field": rule.target_field,
                        "action": "error",
                        "detail": json.dumps({"error": str(exc)}, ensure_ascii=False),
                    }
                )
        # 该行产生的全部事件补 record_id（落库时统一注入 created_at）
        for e in ctx.events[start_idx:]:
            if "_record_id" in e:
                e["record_id"] = e.pop("_record_id")
            else:
                e["record_id"] = case.record_id
        if anomalies:
            case.dirty_flags = json.dumps(sorted(anomalies), ensure_ascii=False)
        return prev_hash != _row_snapshot(case)


def _load_dirty(case: Case) -> list[str]:
    if not case.dirty_flags:
        return []
    try:
        r = json.loads(case.dirty_flags)
        return r if isinstance(r, list) else []
    except (TypeError, ValueError):
        return []


def _row_snapshot(case: Case) -> str:
    """清洗相关列快照（变更判定；dirty_flags/hash 不计）。"""
    keys = (
        "case_no", "year", "plaintiff", "defendant", "court", "arbitration_org",
        "cause", "resolve", "payer", "biz_line", "case_status",
        "amount", "pay_amount", "support_rate", "per_song_amount",
    )
    return json.dumps({k: getattr(case, k) for k in keys}, ensure_ascii=False, sort_keys=True, default=str)