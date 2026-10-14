# UI 工具函数
import sys
from pathlib import Path

# 添加项目路径（docstring: 模块根 = ui/ 的父目录）
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import database as db

# 健康度字段（基本信息口径，单一真值：列表页/详情页共用）
HEALTH_FIELDS = (
    ("case_number", "案号"),
    ("plaintiff", "原告"),
    ("defendant", "被告"),
    ("cause", "案由"),
    ("court", "法院"),
)
HEALTH_TOTAL = len(HEALTH_FIELDS) + 1  # + 提取物

# AI 引擎候选（与 bin/extract.py --engine 对齐，去掉飞书）
ENGINE_OPTIONS = ["minimax", "ollama", "openai", "mock", "basic"]
DEFAULT_ENGINE = "minimax"


def compute_health(case: dict, artifact_count: int) -> dict:
    """按 (基本信息 5 字段 + 提取物) 计算健康度（单一真值）。"""
    checks = []
    passed = 0
    for field, label in HEALTH_FIELDS:
        ok = bool(case.get(field))
        checks.append(("✅" if ok else "❌", label))
        passed += 1 if ok else 0
    has_artifacts = artifact_count > 0
    checks.append(("✅" if has_artifacts else "❌", f"提取物({artifact_count}个)" if has_artifacts else "提取物"))
    passed += 1 if has_artifacts else 0
    return {
        "health": int((passed / HEALTH_TOTAL) * 100),
        "passed": passed,
        "total": HEALTH_TOTAL,
        "checks": checks,
    }


def get_case_health(case_id: str) -> dict:
    """计算单个案件健康度。"""
    case = db.get_case(case_id)
    if not case:
        return {"health": 0, "passed": 0, "total": HEALTH_TOTAL, "checks": []}
    count = db.count_artifacts_by_case(case_id)
    return compute_health(case, count)


def get_artifact_counts() -> dict:
    """一次查询返回 {case_id: 提取物数量}，避免逐案查询。"""
    conn = db._get_conn()
    try:
        rows = conn.execute(
            "SELECT case_id, COUNT(*) FROM artifacts GROUP BY case_id"
        ).fetchall()
    finally:
        conn.close()
    return {r[0]: r[1] for r in rows}


def get_cases(search: str = "", page: int = 1, page_size: int = 20):
    """获取案件列表，支持搜索和分页。"""
    cases = db.search_cases(search) if search else db.list_cases()
    total = len(cases)
    start = (page - 1) * page_size
    return cases[start:start + page_size], total


def get_summary():
    """获取统计摘要。"""
    return db.get_summary()


def get_cause_distribution():
    """获取案由分布。"""
    conn = db._get_conn()
    try:
        rows = conn.execute(
            """
            SELECT cause, COUNT(*) as cnt
            FROM cases
            WHERE cause IS NOT NULL AND cause != ''
            GROUP BY cause
            ORDER BY cnt DESC
            LIMIT 10
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


def get_pending_cases(limit: int = 10):
    """获取待提取案件。"""
    return db.list_cases(status="pending")[:limit]