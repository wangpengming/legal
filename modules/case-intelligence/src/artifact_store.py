# =============================================
# artifact_store.py - 提取物存储层
# 负责提取物的文件持久化（data/artifacts/{case_id}/xxx.md）
# 数据库操作委托给 database.py
# =============================================
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import database as db


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_ROOT = PROJECT_ROOT / "data" / "artifacts"


def _artifact_dir(case_id: str) -> Path:
    return ARTIFACTS_ROOT / case_id


def _ensure_dir(case_id: str) -> Path:
    d = _artifact_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(title: str) -> str:
    """将标题转为 safe 文件名（用于 MD 文件名）。"""
    import re
    s = re.sub(r"[^\w\s\u4e00-\u9fff]", "", title)
    s = re.sub(r"[\s_]+", "_", s.strip())
    return s[:40] or "untitled"


def _build_frontmatter(artifact: dict, case_name: str) -> str:
    """生成 Markdown frontmatter。"""
    meta = {
        "artifact_id": artifact["id"],
        "case_id": artifact["case_id"],
        "case_name": case_name,
        "artifact_type": artifact["artifact_type"],
        "title": artifact["title"],
        "version": artifact["version"],
        "extracted_at": artifact["created_at"],
        "source_ref": artifact.get("source_ref", ""),
    }
    lines = ["---"]
    for k, v in meta.items():
        if v is None:
            v = ""
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, str) and '\n' in v else v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def create_artifact(
    case_id: str,
    artifact_type: str,
    title: str,
    content: str = "",
    source_ref: str = "",
    extractor: str = "",
    db_path: Optional[Path] = None,
) -> dict:
    """创建提取物：写 DB + 写 Markdown 文件。"""
    # 入库
    artifact = db.create_artifact(
        case_id=case_id,
        artifact_type=artifact_type,
        title=title,
        content=content,
        source_ref=source_ref,
        db_path=db_path,
    )
    # 获取案件名（用于 frontmatter）
    case = db.get_case(case_id, db_path)
    case_name = case["case_name"] if case else ""

    # 写 MD 文件
    d = _ensure_dir(case_id)
    filename = f"{artifact['id'][:8]}_{_slug(title)}.md"
    filepath = d / filename
    frontmatter = _build_frontmatter(artifact, case_name)
    filepath.write_text(frontmatter + content, encoding="utf-8")

    artifact["file_path"] = str(filepath)
    return artifact


def get_artifact_with_file(
    artifact_id: str, db_path: Optional[Path] = None
) -> Optional[dict]:
    """读取提取物：DB 记录 + Markdown 正文。"""
    artifact = db.get_artifact(artifact_id, db_path)
    if not artifact:
        return None
    d = _artifact_dir(artifact["case_id"])
    if d.exists():
        for f in d.glob(f"{artifact_id[:8]}*.md"):
            artifact["file_path"] = str(f)
            artifact["file_content"] = f.read_text(encoding="utf-8")
            break
    return artifact


def list_artifacts_by_case(
    case_id: str, db_path: Optional[Path] = None
) -> list[dict]:
    """列出案件下所有提取物（含文件路径）。"""
    artifacts = db.list_artifacts_by_case(case_id, db_path)
    d = _artifact_dir(case_id)
    if not d.exists():
        return artifacts
    # 补 file_path
    for a in artifacts:
        prefix = a["id"][:8]
        for f in d.glob(f"{prefix}*.md"):
            a["file_path"] = str(f)
            break
    return artifacts


def update_artifact(
    artifact_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    source_ref: Optional[str] = None,
    extractor: str = "",
    db_path: Optional[Path] = None,
) -> dict:
    """更新提取物：更新 DB + 重写 Markdown 文件。"""
    artifact = db.update_artifact(
        artifact_id=artifact_id,
        title=title,
        content=content,
        source_ref=source_ref,
        db_path=db_path,
    )
    case = db.get_case(artifact["case_id"], db_path)
    case_name = case["case_name"] if case else ""
    d = _ensure_dir(artifact["case_id"])
    # 找旧文件
    prefix = artifact_id[:8]
    old_files = list(d.glob(f"{prefix}*.md"))
    filename = f"{artifact_id[:8]}_{_slug(artifact['title'])}.md"
    filepath = d / filename
    frontmatter = _build_frontmatter(artifact, case_name)
    final_content = content if content is not None else ""
    filepath.write_text(frontmatter + final_content, encoding="utf-8")
    # 删除旧文件名（如果文件名变了）
    for old in old_files:
        if old.name != filename:
            old.unlink()
    artifact["file_path"] = str(filepath)
    return artifact


def delete_artifact(
    artifact_id: str, db_path: Optional[Path] = None
) -> None:
    """删除提取物：删 DB + 删 Markdown 文件。"""
    artifact = db.get_artifact(artifact_id, db_path)
    if artifact:
        d = _artifact_dir(artifact["case_id"])
        for f in d.glob(f"{artifact_id[:8]}*.md"):
            f.unlink()
    db.delete_artifact(artifact_id, db_path)


def export_case_artifacts(
    case_id: str, db_path: Optional[Path] = None
) -> dict:
    """导出某案件所有提取物为合并 Markdown。"""
    artifacts = list_artifacts_by_case(case_id, db_path)
    case = db.get_case(case_id, db_path)
    if not case:
        return {}
    lines = [
        f"# {case['case_name']} 提取物汇总",
        f"",
        f"案号: {case.get('case_number', 'N/A')}",
        f"原告: {case.get('plaintiff', '')}",
        f"被告: {case.get('defendant', '')}",
        f"案由: {case.get('cause', '')}",
        f"结果: {case.get('result', '')}",
        f"",
        "---",
        "",
    ]
    for a in artifacts:
        lines.append(f"## {a['title']}（{a['artifact_type']}）")
        if a.get("source_ref"):
            lines.append(f"> 来源: {a['source_ref']}")
        lines.append("")
        content = a.get("file_content", a.get("content", ""))
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")
    return {
        "case": case,
        "artifacts": artifacts,
        "markdown": "\n".join(lines),
    }
