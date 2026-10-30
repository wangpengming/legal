#!/usr/bin/env python3
# =============================================
# case_service.py - 能力服务层
# CLI（bin/extract.py）/ Streamlit UI / 飞书 Bot 三端共享的单一真值。
# 只收敛"业务动作"并返回数据结构；表现层（print / Streamlit / 交互卡片）
# 由各端自行负责。见 docs/SPEC-feishu-bot.md §6。
# =============================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from . import artifact_store
from . import case_matcher
from . import case_recognizer
from . import database as db
from . import extractor
from . import importer
from . import parser
from . import scanner
from . import template_store
from .court_resolver import resolve_court, year_from_case_number
from .document_generator import (
    CaseContext,
    DocumentGenerator,
    GenerationRequest,
)

# 引擎 → artifact.generation_method（唯一真值：CLI / Bot 共用；原散落于 bin/extract.py）
ENGINE_GENERATION_METHOD = {
    "minimax": "llm",
    "ollama": "llm",
    "openai": "llm",
    "basic": "rule-based",
    "mock": "mock",
}

# register_case 接受的字段白名单
REGISTER_FIELDS = (
    "case_name", "case_number", "plaintiff", "defendant", "cause", "court",
    "year", "result", "scene", "plaintiff_auth_level", "defendant_auth_status",
    "quality", "notes", "source_path", "entry_method",
)

# 领域常量转发（单一真值仍在 database.py；UI/Bot 经服务层取用，避免直连 db 只为读常量）
ARTIFACT_TYPES = db.ARTIFACT_TYPES
ARTIFACT_TYPE_NAMES = db.ARTIFACT_TYPE_NAMES
TEMPLATE_CATEGORIES = db.TEMPLATE_CATEGORIES
ENTRY_METHODS = db.ENTRY_METHODS


def _as_int(value) -> Optional[int]:
    try:
        n = int(value)
        return n or None
    except (TypeError, ValueError):
        return None


def _s(value) -> str:
    return (value or "").strip() if isinstance(value, str) else ("" if value is None else str(value).strip())


def _compute_health(case: dict, artifact_count: int) -> dict:
    """健康度口径单一真值在 ui/utils.py（SPEC §6「口径同源」）。

    延迟导入：本层（src）不在导入期强耦合 UI 模块，仅在真正需要时取用。
    """
    from ui.utils import compute_health
    return compute_health(case, artifact_count)


# =============================================
# 查询类（只读）
# =============================================

def query_cases(
    filters: Optional[dict] = None,
    search: str = "",
    limit: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """案件列表：search 非空走模糊搜索，否则按 filters(status/year/quality/cause) 精确过滤。"""
    filters = filters or {}
    if search:
        cases = db.search_cases(search, db_path)
    else:
        cases = db.list_cases(
            status=filters.get("status") or None,
            year=_as_int(filters.get("year")),
            quality=filters.get("quality") or None,
            cause=filters.get("cause") or None,
            db_path=db_path,
        )
    return cases[:limit] if limit else cases


def get_case_detail(case_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    """案件详情：{case, artifacts, health}；案件不存在返回 None。

    health 与 UI 列表/详情页共用同一口径（compute_health）。
    """
    case = db.get_case(case_id, db_path)
    if not case:
        return None
    artifacts = artifact_store.list_artifacts_by_case(case_id, db_path)
    return {
        "case": case,
        "artifacts": artifacts,
        "health": _compute_health(case, len(artifacts)),
    }


def resolve_case(ref: str, db_path: Optional[Path] = None) -> Optional[dict]:
    """按 案件 ID 或（模糊）案号 定位案件，返回 Case dict 或 None。"""
    if not ref:
        return None
    ref = ref.strip()
    case = db.get_case(ref, db_path)
    if case:
        return case
    return db.get_case_by_number(ref, db_path)


def list_artifacts(case_id: str, db_path: Optional[Path] = None) -> list[dict]:
    """某案件下的提取物列表（含 file_path）。"""
    return artifact_store.list_artifacts_by_case(case_id, db_path)


# 证据包里的案件字段（顺序即展示顺序）
_BUNDLE_FIELDS = (
    ("case_name", "案件名称"), ("case_number", "案号"), ("plaintiff", "原告"),
    ("defendant", "被告"), ("cause", "案由"), ("court", "法院"),
    ("year", "年份"), ("scene", "场景"), ("result", "结果"), ("notes", "备注"),
)


def _bundle_text(case: dict, artifacts: list[dict], max_chars: int) -> str:
    lines = ["【案件信息】"]
    for key, label in _BUNDLE_FIELDS:
        value = _s(case.get(key))
        if value:
            lines.append(f"{label}：{value}")
    if artifacts:
        lines.append(f"\n【提取物】共 {len(artifacts)} 份")
        for a in artifacts:
            name = ARTIFACT_TYPE_NAMES.get(a["type"]) or a["type"] or "提取物"
            lines.append(f"\n## {name} · {a['title'] or name}")
            lines.append(a["content"] or "（空）")
    else:
        lines.append("\n【提取物】暂无（尚未提取）")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n…（已截断）"
    return text


def case_bundle(
    case_id: str, max_chars: int = 6000, db_path: Optional[Path] = None
) -> Optional[dict]:
    """案件证据包：案件基础字段 + 各提取物正文 → {case, artifacts, text}。

    LLM 做案件分析时的**唯一事实来源**（只喂这里的内容，防模型按常识补全）。
    案件不存在 → None；text 超过 max_chars 截断并标注。
    """
    case = db.get_case(case_id, db_path)
    if not case:
        return None
    artifacts = [
        {
            "type": a.get("artifact_type") or "",
            "title": a.get("title") or "",
            "content": _s(a.get("content")),
        }
        for a in artifact_store.list_artifacts_by_case(case_id, db_path)
    ]
    return {"case": case, "artifacts": artifacts,
            "text": _bundle_text(case, artifacts, max_chars)}


# 缺失维度的补充建议（规则摘要用；用户侧只显示中文维度名，不露 D1-D5 代码）
_DIM_HINTS = {
    "D1": "事实认定：补充起诉状 / 证据清单等材料后重跑提取",
    "D2": "法律依据：补充请求权基础与适用法条",
    "D3": "攻防策略：补充对方主张与我方抗辩点",
    "D4": "证据体系：补充证据目录与质证要点（对胜负判断影响最大）",
    "D5": "赔偿裁量：补充诉请金额与计算依据",
}
_BASIC_MISSING = (("case_number", "案号"), ("plaintiff", "原告"),
                  ("defendant", "被告"), ("court", "法院"))


def case_insight(case_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    """案件要点（规则版，离线可用）：五维完整度 + 缺失维度建议 + 基础信息待补。

    返回 {case_id, case_name, cause, dims{"D1".."D5"}, missing, hints, basic_missing, text}；
    案件不存在 → None。LLM 增强由调用方在 text 之上叠加（见 lark_intent.insight_llm）。
    """
    case = db.get_case(case_id, db_path)
    if not case:
        return None
    present = {
        a.get("artifact_type") for a in artifact_store.list_artifacts_by_case(case_id, db_path)
        if _s(a.get("content"))
    }
    dims = {dim: db.DIMENSION_ARTIFACT_TYPES[dim] in present for dim in db.DIMENSIONS}
    missing = [dim for dim in db.DIMENSIONS if not dims[dim]]
    hints = [_DIM_HINTS[dim] for dim in missing]
    basic_missing = [label for key, label in _BASIC_MISSING if not _s(case.get(key))]

    filled = sum(1 for v in dims.values() if v)
    lines = [f"案由：{_s(case.get('cause')) or '未登记'}", f"五维完整度：{filled}/5"]
    if hints:
        lines.append("建议补充：")
        lines += [f"· {h}" for h in hints]
    else:
        lines.append("五维信息齐备，可继续出文书或做深入分析。")
    if basic_missing:
        lines.append(f"基础信息待补：{'、'.join(basic_missing)}")
    return {
        "case_id": case_id,
        "case_name": _s(case.get("case_name")),
        "cause": _s(case.get("cause")),
        "dims": dims,
        "missing": missing,
        "hints": hints,
        "basic_missing": basic_missing,
        "text": "\n".join(lines),
    }


def list_all_artifacts(db_path: Optional[Path] = None) -> list[dict]:
    """全部提取物（按写入时间倒序；统计看板「最近写入」用）。"""
    return db.list_all_artifacts(db_path)


def match_cases(
    case_id: str, limit: int = 5, db_path: Optional[Path] = None
) -> list[dict]:
    """与 case_id 最相似的 Top-N（含 score / reasons）。"""
    return case_matcher.match_cases(case_id, limit=limit, db_path=db_path)


def summary(db_path: Optional[Path] = None) -> dict:
    """统计摘要 + 年度/案由分布（Bot /case report 卡用）。"""
    result = dict(db.get_summary(db_path))
    conn = db._get_conn(db_path)
    try:
        year_rows = conn.execute(
            "SELECT year, COUNT(*) FROM cases WHERE year IS NOT NULL "
            "GROUP BY year ORDER BY year DESC"
        ).fetchall()
        cause_rows = conn.execute(
            "SELECT cause, COUNT(*) FROM cases WHERE cause IS NOT NULL AND cause != '' "
            "GROUP BY cause ORDER BY COUNT(*) DESC LIMIT 10"
        ).fetchall()
    finally:
        conn.close()
    result["by_year"] = [{"year": r[0], "count": r[1]} for r in year_rows]
    result["by_cause"] = [{"cause": r[0], "count": r[1]} for r in cause_rows]
    return result


# 视为「未登记案号」的空值口径
_NO_NUMBER_TOKENS = ("", "无案号", "无", "未知", "-", "待补", "null", "none")

# 可用的统计维度（Bot「聚合问法」用）
STATS_DIMS = ("year", "no_number", "extracted", "pending", "status", "cause", "court", "quality")


def stats(dim: str = "year", db_path: Optional[Path] = None) -> dict:
    """维度化统计（回答「案件都有哪些年份」「有多少没案号」这类**聚合**问法）。

    返回 {dim, title, total, rows:[{label,count}], note}；rows 已按计数/年份排序。
    口径写在 note 里——统计数字必须能被追问核对。
    """
    dim = (dim or "year").strip().lower()
    if dim not in STATS_DIMS:
        dim = "year"
    conn = db._get_conn(db_path)
    try:
        total = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
        rows: list[dict] = []
        if dim == "year":
            raw = conn.execute(
                "SELECT year, COUNT(*) FROM cases GROUP BY year ORDER BY year DESC"
            ).fetchall()
            rows = [{"label": (f"{r[0]} 年" if r[0] else "年份未登记"), "count": int(r[1])}
                    for r in raw]
            title = "📅 案件年份分布"
            note = "口径：按案件登记年份分组；「年份未登记」= 库内未填写年份的案件"
        elif dim == "no_number":
            ph = ",".join("?" for _ in _NO_NUMBER_TOKENS)
            no_num = int(conn.execute(
                f"SELECT COUNT(*) FROM cases WHERE case_number IS NULL "
                f"OR TRIM(case_number) IN ({ph})", _NO_NUMBER_TOKENS
            ).fetchone()[0])
            rows = [{"label": "已登记案号", "count": total - no_num},
                    {"label": "未登记案号", "count": no_num}]
            title = "🔢 案号登记情况"
            note = "口径：案号为空 / 「无案号」/「未知」的案件计为「未登记案号」"
        elif dim in ("extracted", "pending"):
            raw = conn.execute(
                "SELECT status, COUNT(*) FROM cases GROUP BY status"
            ).fetchall()
            by_status = {(r[0] or "pending"): int(r[1]) for r in raw}
            extracted = by_status.get("extracted", 0)
            pending = by_status.get("pending", 0)
            other = total - extracted - pending
            rows = [{"label": "已提取（五维已落库）", "count": extracted},
                    {"label": "待提取", "count": pending}]
            if other > 0:
                rows.append({"label": "其他状态", "count": other})
            title = "🧩 提取进度"
            note = "口径：status=extracted 计为已提取；status=pending 计为待提取"
        elif dim == "status":
            raw = conn.execute(
                "SELECT status, COUNT(*) FROM cases GROUP BY status ORDER BY COUNT(*) DESC"
            ).fetchall()
            labels = {"extracted": "已提取", "pending": "待提取"}
            rows = [{"label": labels.get(r[0] or "", (r[0] or "未标注状态")), "count": int(r[1])}
                    for r in raw]
            title = "🧩 案件状态分布"
            note = "口径：按案件 status 分组（已提取 / 待提取 / 其他）"
        elif dim == "cause":
            raw = conn.execute(
                "SELECT cause, COUNT(*) FROM cases WHERE cause IS NOT NULL AND TRIM(cause) != '' "
                "GROUP BY cause ORDER BY COUNT(*) DESC LIMIT 10"
            ).fetchall()
            rows = [{"label": (r[0] or "未知")[:24], "count": int(r[1])} for r in raw]
            title = "⚖️ 案由分布 Top 10"
            note = "口径：按案件登记案由分组，仅统计前 10 项"
        elif dim == "court":
            raw = conn.execute(
                "SELECT court, COUNT(*) FROM cases WHERE court IS NOT NULL AND TRIM(court) != '' "
                "GROUP BY court ORDER BY COUNT(*) DESC LIMIT 10"
            ).fetchall()
            rows = [{"label": (r[0] or "未知")[:24], "count": int(r[1])} for r in raw]
            title = "🏛️ 法院分布 Top 10"
            note = "口径：按案件登记法院分组，仅统计前 10 项"
        else:  # quality
            raw = conn.execute(
                "SELECT quality, COUNT(*) FROM cases WHERE quality IS NOT NULL AND TRIM(quality) != '' "
                "GROUP BY quality ORDER BY COUNT(*) DESC"
            ).fetchall()
            rows = [{"label": f"{r[0]} 级", "count": int(r[1])} for r in raw]
            title = "📋 提取质量分布"
            note = "口径：A=五维齐全，B=≥3 维或有案号，C=其余"
    finally:
        conn.close()
    return {"dim": dim, "title": title, "total": total, "rows": rows, "note": note}


def years(db_path: Optional[Path] = None) -> list:
    """已入库案件的年份列表（倒序，去空）。"""
    conn = db._get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT year FROM cases WHERE year IS NOT NULL ORDER BY year DESC"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def cause_distribution(db_path: Optional[Path] = None) -> list[dict]:
    """案由分布 Top-10：[{cause, count}, ...]（倒序）。"""
    return summary(db_path)["by_cause"]


def artifact_counts(db_path: Optional[Path] = None) -> dict:
    """{case_id: 提取物数量} 一次聚合（列表页健康度批量计算用）。"""
    conn = db._get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT case_id, COUNT(*) FROM artifacts GROUP BY case_id"
        ).fetchall()
    finally:
        conn.close()
    return {r[0]: r[1] for r in rows}


# =============================================
# 模板类（只读）
# =============================================

def list_templates(category: Optional[str] = None, db_path: Optional[Path] = None) -> list[dict]:
    return template_store.list_templates_by_category(category, db_path)


def search_templates(query: str, db_path: Optional[Path] = None) -> list[dict]:
    return template_store.search_templates(query, db_path)


def get_template(template_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    return db.get_template(template_id, db_path)


def create_template(
    name: str,
    content: str = "",
    category: str = "其他",
    source_artifacts: Optional[list[str]] = None,
    source_case_ids: Optional[list[str]] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """新建模板（admin 权限；UI 模板管理 / Bot 模板命令共用）。"""
    return template_store.create_template(
        name=name,
        content=content,
        category=category,
        source_artifacts=source_artifacts,
        source_case_ids=source_case_ids,
        db_path=db_path,
    )


def update_template(
    template_id: str,
    name: Optional[str] = None,
    category: Optional[str] = None,
    content: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[dict]:
    return template_store.update_template(
        template_id, name=name, category=category, content=content, db_path=db_path
    )


def delete_template(template_id: str, db_path: Optional[Path] = None) -> None:
    template_store.delete_template(template_id, db_path)


# =============================================
# 写入类
# =============================================

def check_duplicate(fields: dict, db_path: Optional[Path] = None) -> dict:
    """查重：案号精确 → 当事人精确 → 案由模糊（委托 case_recognizer）。"""
    fields = fields or {}
    return case_recognizer.recognize_case(
        case_number=fields.get("case_number") or None,
        plaintiff=fields.get("plaintiff") or "",
        defendant=fields.get("defendant") or "",
        cause=fields.get("cause") or "",
        db_path=db_path,
    )


def register_case(fields: dict, db_path: Optional[Path] = None) -> dict:
    """登记案件，返回新 Case dict。

    与 UI/CLI 手工登记同口径：
      - court 为空 → 从案号派生；year 为空 → 从案号派生（同 importer.import_case）
      - 不派生 quality（手工登记不推断；quality 仅 AI 提取路径由 extractor.derive_quality 生成）
    案号冲突由 db.create_case 抛 ValueError。
    """
    fields = fields or {}
    case_name = _s(fields.get("case_name"))
    if not case_name:
        raise ValueError("案件名称（case_name）必填")
    case_number = _s(fields.get("case_number")) or None
    court = _s(fields.get("court")) or resolve_court(case_number)
    year = _as_int(fields.get("year")) or year_from_case_number(case_number)
    return db.create_case(
        case_name=case_name,
        case_number=case_number,
        plaintiff=_s(fields.get("plaintiff")),
        defendant=_s(fields.get("defendant")),
        cause=_s(fields.get("cause")),
        court=court,
        year=year,
        result=_s(fields.get("result")),
        source_path=_s(fields.get("source_path")),
        notes=_s(fields.get("notes")),
        entry_method=_s(fields.get("entry_method")) or "CLI",
        scene=_s(fields.get("scene")),
        plaintiff_auth_level=_s(fields.get("plaintiff_auth_level")),
        defendant_auth_status=_s(fields.get("defendant_auth_status")),
        quality=_s(fields.get("quality")),
        db_path=db_path,
    )


def update_case_status(case_id: str, status: str, db_path: Optional[Path] = None) -> None:
    db.update_case_status(case_id, status, db_path)


def update_case(case_id: str, fields: dict, db_path: Optional[Path] = None) -> Optional[dict]:
    """按白名单更新案件字段（UI 编辑 / Bot admin）。空 dict 原样返回。"""
    return db.update_case(case_id, db_path=db_path, **(fields or {}))


def delete_case(
    case_id: str, purge_files: bool = True, db_path: Optional[Path] = None
) -> None:
    """删除案件（级联 DB 记录）；purge_files=True 时同时清理 artifact 文件目录。"""
    db.delete_case(case_id, db_path)
    if purge_files:
        artifact_store.purge_case_dir(case_id)


def create_artifact(
    case_id: str,
    artifact_type: str,
    title: str,
    content: str = "",
    source_ref: str = "",
    generation_method: Optional[str] = None,
    model_version: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """创建提取物（写 DB + 写 Markdown 文件）。"""
    return artifact_store.create_artifact(
        case_id=case_id,
        artifact_type=artifact_type,
        title=title,
        content=content,
        source_ref=source_ref,
        db_path=db_path,
        generation_method=generation_method,
        model_version=model_version,
    )


def generate_document(
    case_id: str,
    doc_type: str,
    engine: Optional[str] = None,
    use_template: bool = True,
    db_path: Optional[Path] = None,
):
    """文书生成（三级降级：模板 → 模板+LLM → LLM → fallback），返回 GenerationResult。

    与 UI 文书生成页同口径：参考模板取自 DocumentGenerator.get_reference_templates(doc_type)；
    use_template=False 时不注入参考模板（UI「使用参考模板」开关）。
    """
    case = db.get_case(case_id, db_path)
    if not case:
        raise ValueError(f"案件不存在: {case_id}")
    gen = DocumentGenerator(db_path=db_path, engine=engine)
    artifacts = artifact_store.list_artifacts_by_case(case_id, db_path)
    art_map = {a["artifact_type"]: a.get("content", "") for a in artifacts}
    ctx = CaseContext(
        case_id=case_id,
        case_number=case.get("case_number") or "",
        case_name=case.get("case_name") or "",
        plaintiff=case.get("plaintiff") or "",
        defendant=case.get("defendant") or "",
        cause=case.get("cause") or "",
        court=case.get("court") or "",
        scene=case.get("scene") or "",
        artifacts=art_map,
    )
    templates = gen.get_reference_templates(doc_type) if use_template else []
    return gen.generate(
        GenerationRequest(doc_type=doc_type, case_context=ctx, reference_templates=templates)
    )


def import_scan(
    path,
    engine: str = "minimax",
    case_name: Optional[str] = None,
    import_result: bool = True,
    recursive: bool = True,
    max_depth: int = 3,
    db_path: Optional[Path] = None,
) -> dict:
    """目录扫描 → 解析 → AI 提取 →（可选）入库，返回 JSON 友好 dict。

    返回：
      {case_name, case_number, file_count, parsed_count,
       dims: {"D1".."D5": bool}, imported, case_id, artifact_ids,
       skipped, reason}
    """
    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise ValueError(f"目录不存在或不是目录: {path}")

    scan = scanner.scan_directory(p, recursive=recursive, max_depth=max_depth)
    parsed = parser.parse_files(scan.files)
    extracted = extractor.extract_case(
        contents=parsed,
        case_name=case_name or scan.case_name,
        engine_type=engine,
    )

    report = {
        "case_name": extracted.case_name,
        "case_number": extracted.case_number or "",
        "file_count": len(scan.files),
        "parsed_count": len(parsed),
        "dims": extractor.dim_flags(extracted),
        "imported": False,
        "case_id": "",
        "artifact_ids": [],
        "skipped": False,
        "reason": "",
    }

    if not import_result:
        report["reason"] = "仅提取未入库（import_result=False）"
        return report

    # 空壳提取（五维全无、无案号）→ 不入库，如实回报（避免建出「0 提取物」的空案件）
    if extractor.extraction_is_empty(extracted):
        report["reason"] = "AI 未返回有效五维内容（材料不完整或模型响应异常）；未建案，可稍后重试"
        return report

    if extracted.case_number:
        existing = db.get_case_by_number(extracted.case_number, db_path)
        if existing:
            report["skipped"] = True
            report["reason"] = f"案号已存在：{existing['case_name']}（{existing['id']}）"
            return report

    gen_method = ENGINE_GENERATION_METHOD.get(engine, "llm")
    model_version = os.environ.get("MINIMAX_MODEL", "") if engine == "minimax" else ""
    result = importer.CaseImporter(db_path).import_full(
        extracted, generation_method=gen_method, model_version=model_version
    )
    report["imported"] = True
    report["case_id"] = result["case_id"]
    report["artifact_ids"] = result["artifact_ids"]
    return report


def extract_into_case(
    case_id: str,
    engine: str = "minimax",
    recursive: bool = True,
    max_depth: int = 3,
    db_path: Optional[Path] = None,
) -> dict:
    """对**已存在案件**的 source_path 目录重跑五维提取，写入该案（不新建案件）。

    与 import_scan 的区别：import_scan 面向"目录 = 新案件"；本函数面向"案件已有 ID，
    补充/刷新其提取物"（Bot `/case extract` 卡片按钮、UI 重提取共用）。

    返回：{case_id, file_count, parsed_count, dims{D1..D5}, artifact_ids}
    """
    case = db.get_case(case_id, db_path)
    if not case:
        raise ValueError(f"案件不存在: {case_id}")
    src = _s(case.get("source_path"))
    if not src:
        raise ValueError("该案件未登记 source_path（原始材料目录），无法重跑提取")
    p = Path(src)
    if not p.is_dir():
        raise ValueError(f"source_path 不是目录: {src}")

    scan = scanner.scan_directory(p, recursive=recursive, max_depth=max_depth)
    if not scan.files:
        raise ValueError(f"目录中无可解析文件: {src}")
    parsed = parser.parse_files(scan.files)
    extracted = extractor.extract_case(
        contents=parsed,
        case_name=case.get("case_name") or scan.case_name,
        engine_type=engine,
    )
    # 空壳提取（五维全无、无案号）→ 如实报错，不写入空提取物
    if extractor.extraction_is_empty(extracted):
        raise extractor.ExtractionError("AI 未返回有效五维内容（材料不完整或模型响应异常），可稍后重试")
    artifact_ids = importer.CaseImporter(db_path).import_artifacts(
        case_id,
        extracted,
        generation_method=ENGINE_GENERATION_METHOD.get(engine, "llm"),
        model_version=os.environ.get("MINIMAX_MODEL", "") if engine == "minimax" else "",
    )
    db.update_case_status(case_id, "extracted", db_path)
    return {
        "case_id": case_id,
        "file_count": len(scan.files),
        "parsed_count": len(parsed),
        "dims": extractor.dim_flags(extracted),
        "artifact_ids": artifact_ids,
    }


__all__ = [
    "ENGINE_GENERATION_METHOD",
    "REGISTER_FIELDS",
    "ARTIFACT_TYPES",
    "ARTIFACT_TYPE_NAMES",
    "TEMPLATE_CATEGORIES",
    "ENTRY_METHODS",
    "query_cases",
    "get_case_detail",
    "resolve_case",
    "list_artifacts",
    "case_bundle",
    "case_insight",
    "list_all_artifacts",
    "match_cases",
    "summary",
    "years",
    "cause_distribution",
    "artifact_counts",
    "list_templates",
    "search_templates",
    "get_template",
    "create_template",
    "update_template",
    "delete_template",
    "check_duplicate",
    "register_case",
    "update_case_status",
    "update_case",
    "delete_case",
    "create_artifact",
    "generate_document",
    "import_scan",
    "extract_into_case",
]