# =============================================
# template_store.py - 模板存储层
# 管理通用模板（templates/）和已归档模板（templates_extracted/）
# 数据库操作委托给 database.py
# =============================================
import json
import shutil
from pathlib import Path
from typing import Optional

from . import database as db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = PROJECT_ROOT / "templates"
EXTRACTED_ROOT = PROJECT_ROOT / "templates_extracted"


def _ensure_dir(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(name: str) -> str:
    import re
    s = re.sub(r"[^\w\s\u4e00-\u9fff]", "", name)
    s = re.sub(r"[\s_]+", "_", s.strip())
    return s[:50] or "untitled"


def create_template(
    name: str,
    content: str = "",
    category: str = "其他",
    source_artifacts: Optional[list[str]] = None,
    source_case_ids: Optional[list[str]] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """创建模板：写 DB + 写 Markdown 文件到 templates/。"""
    template = db.create_template(
        name=name,
        content=content,
        category=category,
        source_artifacts=source_artifacts,
        source_case_ids=source_case_ids,
        db_path=db_path,
    )
    # 写入文件
    d = _ensure_dir(TEMPLATES_ROOT / category)
    filename = f"{template['id'][:8]}_{_slug(name)}.md"
    filepath = d / filename
    text = _build_template_md(template)
    filepath.write_text(text, encoding="utf-8")
    template["file_path"] = str(filepath)
    return template


def _build_template_md(template: dict) -> str:
    """生成模板 Markdown（含 frontmatter）。"""
    meta = {
        "template_id": template["id"],
        "name": template["name"],
        "category": template["category"],
        "source_artifacts": json.loads(template.get("source_artifacts", "[]")),
        "source_case_ids": json.loads(template.get("source_case_ids", "[]")),
        "version": template["version"],
        "usage_count": template["usage_count"],
    }
    lines = ["---"]
    for k, v in meta.items():
        if v is None:
            v = ""
        if isinstance(v, (list, dict)):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(template.get("content", ""))
    return "\n".join(lines)


def get_template_file_path(template: dict) -> Optional[Path]:
    """根据模板 category 和 name 推算文件路径。"""
    cat = template.get("category", "其他")
    name = template.get("name", "")
    slug = _slug(name)
    expected = TEMPLATES_ROOT / cat / f"{template['id'][:8]}_{slug}.md"
    if expected.exists():
        return expected
    # 搜索
    for f in (TEMPLATES_ROOT / cat).glob(f"{template['id'][:8]}*.md"):
        return f
    return None


def list_templates_by_category(
    category: Optional[str] = None, db_path: Optional[Path] = None
) -> list[dict]:
    """列出模板（含文件路径）。"""
    templates = db.list_templates(category=category, db_path=db_path)
    for t in templates:
        fp = get_template_file_path(t)
        if fp:
            t["file_path"] = str(fp)
    return templates


def archive_case_templates(
    case_id: str,
    case_name: str,
    artifacts: list[dict],
    db_path: Optional[Path] = None,
) -> Path:
    """
    将某案件的提取物归档为 case_name/ 目录（templates_extracted/）。
    用于 Phase 2 迁移腾讯案/广电案提取物。
    """
    d = _ensure_dir(EXTRACTED_ROOT / _slug(case_name))
    # 写案件信息
    meta = {
        "case_id": case_id,
        "case_name": case_name,
        "artifacts": [
            {
                "id": a["id"],
                "artifact_type": a["artifact_type"],
                "title": a["title"],
                "source_ref": a.get("source_ref", ""),
                "version": a["version"],
            }
            for a in artifacts
        ],
    }
    import json
    (d / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 逐个写提取物 MD
    for a in artifacts:
        from . import artifact_store
        full = artifact_store.get_artifact_with_file(a["id"], db_path)
        if full and full.get("file_content"):
            slug = _slug(full["title"])
            (d / f"{a['id'][:8]}_{slug}.md").write_text(
                full["file_content"], encoding="utf-8"
            )
    return d


def increment_usage(
    template_id: str, db_path: Optional[Path] = None
) -> None:
    """模板被引用 +1。"""
    db.increment_usage(template_id, db_path)


def search_templates(
    query: str, db_path: Optional[Path] = None
) -> list[dict]:
    """在模板名/分类/内容中模糊搜索。"""
    import sqlite3
    conn = db._get_conn(db_path)
    q = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM templates
        WHERE name LIKE ? OR category LIKE ? OR content LIKE ?
        ORDER BY usage_count DESC, created_at DESC
        LIMIT 20
        """,
        (q, q, q),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
