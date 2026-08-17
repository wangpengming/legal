"""标签体系端点（docs/03 §6.2 / 需求 M4：案件/歌曲/对手方/外部案例打标）。

CRUD：
- GET /tags（列表，kind 过滤）/ POST /tags（创建）/ PATCH /tags/{id}（改名/改色/改描述）
- DELETE /tags/{id}（删除标签并清空其关联）
打标：
- POST /tags/link（打标/取消，tag_id 或 tag_name 二选一，新名自动创建）
- POST /tags/batch（批量打标，02-search 表格进阶批量操作入口）
- POST /tags/merge（标签合并：from 并入 into，重复关联合并去重）
- GET /tags/{id}/objects（标签对象列举，含名称解析与聚合计数）
所有写操作经 audit 记 audit_logs（docs/03 §6.1）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    TagBatchLinkRequest,
    TagLinkRequest,
    TagMergeRequest,
    TagUpdateRequest,
    TagWriteRequest,
    audit,
    ok,
)
from app.core.database import get_db
from app.models.fact import Case, Song
from app.models.ops import ExternalCase, Tag, TagLink

router = APIRouter(tags=["tags"])

TARGET_TYPES = {"case", "song", "party", "external_case"}


def _tag_dict(t: Tag, link_count: int | None = None) -> dict:
    d = {
        "id": t.id,
        "name": t.name,
        "kind": t.kind,
        "color": t.color,
        "description": t.description,
    }
    if link_count is not None:
        d["link_count"] = link_count
    return d


def _get_tag(db: Session, tag_id: int) -> Tag:
    t = db.get(Tag, tag_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"标签不存在：{tag_id}")
    return t


def _resolve_tag(db: Session, tag_id: int | None, tag_name: str | None) -> Tag:
    """tag_id / tag_name 二选一解析；tag_name 不存在自动创建（manual）。"""
    if tag_id is not None:
        return _get_tag(db, tag_id)
    name = (tag_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="tag_id 与 tag_name 至少提供一个")
    t = db.scalar(select(Tag).where(Tag.name == name))
    if t is None:
        t = Tag(name=name, kind="manual")
        db.add(t)
        db.commit()
        db.refresh(t)
    return t


def _link_row(tag: Tag, target_type: str, target_id: str) -> TagLink:
    return TagLink(tag_id=tag.id, target_type=target_type, target_id=target_id)


def _object_name(db: Session, target_type: str, target_id: str) -> str:
    """对象名称解析（party 无独立表，直接返回 target_id）。"""
    if target_type == "case":
        c = db.scalar(select(Case).where(Case.record_id == target_id))
        return c.case_no or target_id if c is not None else target_id
    if target_type == "song":
        s = db.scalar(select(Song).where(Song.record_id == target_id))
        return s.song_name or target_id if s is not None else target_id
    if target_type == "external_case":
        try:
            e = db.scalar(select(ExternalCase).where(ExternalCase.id == int(target_id)))
        except (TypeError, ValueError):
            e = None
        return e.case_no or target_id if e is not None else target_id
    return target_id  # party


# ── CRUD ─────────────────────────────────────────────────────────

@router.get("/tags")
def list_tags(kind: str | None = None, db: Session = Depends(get_db)) -> dict:
    """标签列表（附带各标签关联对象数；kind=manual/derived 可选过滤）。"""
    stmt = select(Tag)
    if kind:
        stmt = stmt.where(Tag.kind == kind.strip())
    tags = db.scalars(stmt.order_by(Tag.id)).all()
    counts = dict(
        db.execute(
            select(TagLink.tag_id, func.count(TagLink.id))
            .group_by(TagLink.tag_id)
        ).all()
    )
    data = [_tag_dict(t, counts.get(t.id, 0)) for t in tags]
    return ok(data, total=len(data),
              footnote="M4 标签体系：manual=人工标签 / derived=派生标签（规则或 AI 生成）")


@router.post("/tags")
def create_tag(payload: TagWriteRequest, db: Session = Depends(get_db)) -> dict:
    """创建标签（name 唯一；重复返回 409）。"""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="标签名不能为空")
    exist = db.scalar(select(Tag).where(Tag.name == name))
    if exist is not None:
        raise HTTPException(status_code=409, detail=f"标签已存在：{name}")
    t = Tag(name=name, kind=payload.kind, color=payload.color, description=payload.description)
    db.add(t)
    db.commit()
    db.refresh(t)
    audit(db, op_type="api", table_name="tags", action="create",
          detail={"name": name, "kind": t.kind}, record_id=str(t.id))
    return ok(_tag_dict(t, 0), footnote="已创建标签")


@router.patch("/tags/{tag_id}")
def update_tag(tag_id: int, payload: TagUpdateRequest, db: Session = Depends(get_db)) -> dict:
    """更新标签（name 唯一冲突返回 409；其余字段按传入覆盖）。"""
    t = _get_tag(db, tag_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="标签名不能为空")
        clash = db.scalar(select(Tag).where(Tag.name == name, Tag.id != tag_id))
        if clash is not None:
            raise HTTPException(status_code=409, detail=f"标签名已被占用：{name}")
        t.name = name
    if payload.color is not None:
        t.color = payload.color
    if payload.description is not None:
        t.description = payload.description
    db.commit()
    audit(db, op_type="api", table_name="tags", action="update",
          detail={"id": tag_id, "name": t.name}, record_id=str(t.id))
    return ok(_tag_dict(t), footnote="已更新标签")


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)) -> dict:
    """删除标签（连坐清空该标签全部关联；关联对象本身不受影响）。"""
    t = _get_tag(db, tag_id)
    db.execute(delete(TagLink).where(TagLink.tag_id == tag_id))
    db.delete(t)
    db.commit()
    audit(db, op_type="api", table_name="tags", action="delete",
          detail={"name": t.name}, record_id=str(tag_id))
    return ok({"id": tag_id, "deleted": True}, footnote="已删除标签及其全部关联")


# ── 打标 / 取消 / 批量 / 合并 ────────────────────────────────────

@router.post("/tags/link")
def toggle_tag_link(payload: TagLinkRequest, db: Session = Depends(get_db)) -> dict:
    """打标或取消（link=true 打标幂等；link=false 取消无则静默）。"""
    if payload.target_type not in TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的对象类型：{payload.target_type}")
    t = _resolve_tag(db, payload.tag_id, payload.tag_name)
    row = db.scalar(
        select(TagLink).where(
            TagLink.tag_id == t.id,
            TagLink.target_type == payload.target_type,
            TagLink.target_id == payload.target_id,
        )
    )
    if payload.link:
        if row is None:
            db.add(_link_row(t, payload.target_type, payload.target_id))
            db.commit()
        action = "link"
    else:
        if row is not None:
            db.delete(row)
            db.commit()
        action = "unlink"
    audit(db, op_type="api", table_name="tag_links", action=action,
          detail={"tag": t.name, "target_type": payload.target_type, "target_id": payload.target_id},
          record_id=str(t.id))
    return ok({"linked": payload.link, "tag_id": t.id, "tag_name": t.name},
              footnote="打标幂等：同一 tag+对象 仅保留一条关联")


@router.post("/tags/batch")
def batch_link(payload: TagBatchLinkRequest, db: Session = Depends(get_db)) -> dict:
    """批量打标（02-search 表格进阶：选区案件/歌曲批量打标签）。"""
    if payload.target_type not in TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的对象类型：{payload.target_type}")
    t = _resolve_tag(db, None, payload.tag_name)
    linked = 0
    for target_id in payload.target_ids:
        exist = db.scalar(
            select(TagLink).where(
                TagLink.tag_id == t.id,
                TagLink.target_type == payload.target_type,
                TagLink.target_id == target_id,
            )
        )
        if exist is None:
            db.add(_link_row(t, payload.target_type, target_id))
            linked += 1
    db.commit()
    audit(db, op_type="api", table_name="tag_links", action="batch_link",
          detail={"tag": t.name, "target_type": payload.target_type, "count": len(payload.target_ids)},
          record_id=str(t.id))
    return ok({"tag_id": t.id, "tag_name": t.name, "targets": len(payload.target_ids), "new_links": linked},
              footnote="批量打标完成（重复对象自动跳过）")


@router.post("/tags/merge")
def merge_tags(payload: TagMergeRequest, db: Session = Depends(get_db)) -> dict:
    """标签合并：from_id 并入 into_id，关联去重后删除 from 标签。"""
    src = _get_tag(db, payload.from_id)
    dst = _get_tag(db, payload.into_id)
    if src.id == dst.id:
        raise HTTPException(status_code=400, detail="不能合并到自身")
    moved = 0
    for row in db.scalars(select(TagLink).where(TagLink.tag_id == src.id)).all():
        exist = db.scalar(
            select(TagLink).where(
                TagLink.tag_id == dst.id,
                TagLink.target_type == row.target_type,
                TagLink.target_id == row.target_id,
            )
        )
        if exist is None:
            db.add(_link_row(dst, row.target_type, row.target_id))
            moved += 1
    # 批量删除源标签关联并先落地，避免 ORM 延迟 flush 导致外键删除顺序不确定
    db.execute(delete(TagLink).where(TagLink.tag_id == src.id))
    db.flush()
    db.delete(src)
    db.commit()
    audit(db, op_type="api", table_name="tags", action="merge",
          detail={"from": src.name, "into": dst.name, "moved": moved}, record_id=str(dst.id))
    return ok({"from_id": src.id, "into_id": dst.id, "into_name": dst.name, "moved_links": moved},
              footnote="合并完成：关联去重后保留目标标签")


# ── 对象列举 ─────────────────────────────────────────────────────

@router.get("/tags/{tag_id}/objects")
def tag_objects(tag_id: int, db: Session = Depends(get_db)) -> dict:
    """标签对象列表（按 target_type 分组，含名称解析与类型计数）。"""
    t = _get_tag(db, tag_id)
    rows = db.scalars(
        select(TagLink).where(TagLink.tag_id == tag_id).order_by(TagLink.target_type, TagLink.id)
    ).all()
    items = [
        {
            "target_type": r.target_type,
            "target_id": r.target_id,
            "name": _object_name(db, r.target_type, r.target_id),
            "linked_at": getattr(r, "created_at", None),
        }
        for r in rows
    ]
    by_type = {}
    for i in items:
        by_type[i["target_type"]] = by_type.get(i["target_type"], 0) + 1
    return ok({"tag": _tag_dict(t, len(items)), "objects": items, "by_type": by_type},
              total=len(items),
              footnote=f"标签「{t.name}」关联对象 {len(items)} 个（party 为被告名称，无独立表）")