"""FTS5 全文检索（docs/03 §6.3；容量兜底 10 万行）。

tokenizer 决策（版本 2，实测修正）：本机 SQLite（Python 内置 3.53.4）与
Docker Debian 的 libsqlite3 编译 tokenizer 集不一致（前者缺 `ngram`），
改选两条环境都稳定的 **unicode61**，中文在**应用层做 2-gram 展开**后索引：

- 写入：中文连续段（CJK）逐字滑窗取 2-gram，空格拼接（unicode61 每个
  bigram 视为一个 token）；英文/数字保持原文 token；
- 查询：同一函数展开，MATCH 空格=AND，任意长度中文查询词均可命中；
- 简称兜底：索引列同时并入原始值（如 plaintiff + plaintiff_raw），
  「音集协」简称可命中 canonical 化后的全称案件。
- 单字符查询 ngram 语义不可用，search_cases 走 LIKE 兜底（含跨列）。
"""
from __future__ import annotations

import json
import re

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

CASES_FTS_TABLE = "cases_fts"

# 参与检索的列（Case 可读字段）＋ case_id 关联主键（UNINDEXED）
# 含 resolve（结案原因）：ai/搜索的高频过滤词（判赔/胜诉/和解），必须可命中
_CASE_FTS_COLS = ("case_no", "plaintiff", "defendant", "court", "cause", "resolve", "notes", "judge_name", "exec_case_no")

_FTS_DDL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {CASES_FTS_TABLE} USING fts5(
    case_id UNINDEXED,
    {', '.join(_CASE_FTS_COLS)},
    tokenize = 'unicode61'
)
"""

_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def _ngramize(text_pos: str) -> str:
    """中文连续段 2-gram 空格展开；非中文原样保留（unicode61 词元化）。"""
    if not text_pos:
        return ""
    parts: list[str] = []
    cursor = 0
    for m in _CJK_RE.finditer(text_pos):
        parts.append(text_pos[cursor : m.start()])
        chunk = m.group()
        parts.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
        cursor = m.end()
    parts.append(text_pos[cursor:])
    return " ".join(p for p in parts if p)


def _join_json(fields_str) -> str:
    """Text(JSON) 列（如 defendant/court）→ 空格拼接的可检索文本。"""
    if not fields_str:
        return ""
    try:
        items = json.loads(fields_str)
    except (TypeError, ValueError):
        return str(fields_str)
    if isinstance(items, list):
        return " ".join(str(x) for x in items if x)
    return str(fields_str)


def _index_row(
    case_id: int,
    case_no=None,
    case_no_raw=None,
    related_case_no=None,
    plaintiff=None,
    plaintiff_raw=None,
    defendant=None,
    defendant_raw=None,
    court=None,
    court_raw=None,
    cause=None,
    resolve=None,
    notes=None,
    judge_name=None,
    exec_case_no=None,
) -> dict:
    """字段值 → FTS 索引行（清洗值 + 原始值双写，别名可命中）。"""
    return {
        "case_id": case_id,
        "case_no": _ngramize(f"{case_no or ''} {case_no_raw or ''} {related_case_no or ''}"),
        "plaintiff": _ngramize(f"{plaintiff or ''}\n{plaintiff_raw or ''}"),
        "defendant": _ngramize(f"{_join_json(defendant)} {_join_json(defendant_raw)}"),
        "court": _ngramize(f"{_join_json(court)} {court_raw or ''}"),
        "cause": _ngramize(cause or ""),
        "resolve": _ngramize(resolve or ""),
        "notes": _ngramize(notes or ""),
        "judge_name": _ngramize(judge_name or ""),
        "exec_case_no": _ngramize(exec_case_no or ""),
    }


def _fts_row(row) -> dict:
    """适配：查询结果是 Row（可属性访问），转为 _index_row。"""
    return _index_row(
        case_id=row.id,
        case_no=row.case_no,
        case_no_raw=row.case_no_raw,
        related_case_no=row.related_case_no,
        plaintiff=row.plaintiff,
        plaintiff_raw=row.plaintiff_raw,
        defendant=row.defendant,
        defendant_raw=row.defendant_raw,
        court=row.court,
        court_raw=row.court_raw,
        cause=row.cause,
        resolve=row.resolve,
        notes=row.notes,
        judge_name=row.judge_name,
        exec_case_no=row.exec_case_no,
    )


def _queryize(q: str) -> str:
    """查询词 → MATCH 表达式（与索引同一 2-gram 展开；空格=AND）。"""
    return _ngramize(q).strip()


def init_fts(bind_engine: Engine) -> None:
    """启动时建索引（影子表；内容由 rebuild_cases_fts / upsert_case_fts 维护）。

    注意：`CREATE VIRTUAL TABLE IF NOT EXISTS` 不会对已存在的影子表做结构升级
    （如代码新增索引列 resolve），因此建表后做一次列对账，与 _CASE_FTS_COLS
    不一致（缺新列/多旧列）则 DROP 重建；数据由调用方（init_db）随后
    rebuild_cases_fts 全量重灌，天然幂等。
    """
    with bind_engine.begin() as conn:
        conn.execute(text(_FTS_DDL))
    with bind_engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({CASES_FTS_TABLE})")).fetchall()
    existing = {r[1] for r in rows}
    expected = {"case_id", *_CASE_FTS_COLS}
    if existing != expected:
        with bind_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {CASES_FTS_TABLE}"))
            conn.execute(text(_FTS_DDL))


def rebuild_cases_fts(db: Session) -> int:
    """全量重建（清空重灌 = 永远幂等；按 case_id 关联 cases.id）。"""
    db.execute(text(f"DELETE FROM {CASES_FTS_TABLE}"))
    rows = db.execute(
        text(
            f"SELECT id, case_no, case_no_raw, related_case_no, plaintiff, plaintiff_raw, "
            f"defendant, defendant_raw, court, court_raw, cause, resolve, notes, judge_name, exec_case_no "
            f"FROM cases"
        )
    ).fetchall()
    if rows:
        cols = ", ".join(_CASE_FTS_COLS)
        params = [{"case_id": r.id, **{c: _fts_row(r)[c] for c in _CASE_FTS_COLS}} for r in rows]
        db.execute(
            text(
                f"INSERT INTO {CASES_FTS_TABLE}(case_id, {cols}) "
                f"VALUES (:case_id, {', '.join(':' + c for c in _CASE_FTS_COLS)})"
            ),
            params,
        )
    return len(rows)


def upsert_case_fts(
    db: Session,
    case_id: int,
    case_no=None,
    case_no_raw=None,
    related_case_no=None,
    plaintiff=None,
    plaintiff_raw=None,
    defendant=None,
    defendant_raw=None,
    court=None,
    court_raw=None,
    cause=None,
    resolve=None,
    notes=None,
    judge_name=None,
    exec_case_no=None,
) -> None:
    """单条 upsert（staging→正式表原子换入后调用，保持影子表同步）。"""
    db.execute(text(f"DELETE FROM {CASES_FTS_TABLE} WHERE case_id = :case_id"), {"case_id": case_id})
    cols = ", ".join(_CASE_FTS_COLS)
    db.execute(
        text(
            f"INSERT INTO {CASES_FTS_TABLE}(case_id, {cols}) "
            f"VALUES (:case_id, {', '.join(':' + c for c in _CASE_FTS_COLS)})"
        ),
        _index_row(
            case_id=case_id,
            case_no=case_no,
            case_no_raw=case_no_raw,
            related_case_no=related_case_no,
            plaintiff=plaintiff,
            plaintiff_raw=plaintiff_raw,
            defendant=defendant,
            defendant_raw=defendant_raw,
            court=court,
            court_raw=court_raw,
            cause=cause,
            resolve=resolve,
            notes=notes,
            judge_name=judge_name,
            exec_case_no=exec_case_no,
        ),
    )


def search_cases(db: Session, q: str, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """检索（命中 case_id + 总数）。

    - q 为空/单字符/含特殊字符（"()(\u00a0)-*）→ LIKE 兜底（跨列）；
    - 其余走 FTS：查询词先 2-gram 展开，词间跨列 AND
      （每个词在任一列命中：列内 OR × 词间 AND）。
    """
    q = q.strip()
    if not q:
        return [], 0

    like_cols = ("case_no", "plaintiff", "court", "cause", "notes")
    if len(q) == 1 or any(ch in q for ch in '"(():-*'):
        pattern = f"%{q}%"
        cond = " OR ".join(f"{c} LIKE :p" for c in like_cols)
        total = db.execute(text(f"SELECT COUNT(*) FROM cases WHERE {cond}"), {"p": pattern}).scalar() or 0
        rows = db.execute(
            text(f"SELECT id FROM cases WHERE {cond} ORDER BY id LIMIT :lim OFFSET :off"),
            {"p": pattern, "lim": limit, "off": offset},
        ).fetchall()
        return [{"case_id": r.id} for r in rows], total

    terms = [t for t in q.split() if t]
    if not terms:
        return [], 0
    # 每个原始词独立 2-gram 展开；FTS5 原生查询串：
    #   列内（词内 bigram 隐式 AND）× 跨列 OR × 词间显式 AND
    #   例：q=「雷石 侵权」 → ({col}: 雷石 OR ...) AND ({col}: 侵权 OR ...)
    #   例：q=「音集协」 → ({col}: 音集 集协 OR ...)
    per_term = [(_queryize(t).split(), t) for t in terms]

    def _col_or(bigrams: list[str]) -> str:
        inner = " ".join(bigrams)
        return "(" + " OR ".join(f"{c}: {inner}" for c in _CASE_FTS_COLS) + ")"

    query_str = " AND ".join(_col_or(b) for b, _ in per_term)
    total = (
        db.execute(
            text(f"SELECT COUNT(*) FROM {CASES_FTS_TABLE} WHERE {CASES_FTS_TABLE} MATCH :q"),
            {"q": query_str},
        ).scalar()
        or 0
    )
    rows = db.execute(
        text(
            f"SELECT case_id FROM {CASES_FTS_TABLE} WHERE {CASES_FTS_TABLE} MATCH :q "
            f"ORDER BY rank LIMIT :lim OFFSET :off"
        ),
        {"q": query_str, "lim": limit, "off": offset},
    ).fetchall()
    return [{"case_id": r.case_id} for r in rows], total