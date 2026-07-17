# -*- coding: utf-8 -*-
# 生活流·她的宇宙后台管理 API（STEP-010）：快照 CRUD + 事件库 CRUD
#
# 前缀 /api/admin（见 main.py），权限 super_admin / ai_trainer；写操作落 operation_log。
# 注：worldview_event 无独立 core_attitude 列（M1 定案：核心态度嵌入 event_view 文本）。
#     本 API 以 "[核心态度：X] " 前缀在 event_view 中往返存取 core_attitude，保证四选项强校验。

import logging
import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_LIFE_PARAM_INVALID,
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
    ADMIN_ERR_WORLDVIEW_ATTITUDE_INVALID,
    ADMIN_ERR_WORLDVIEW_EVENT_NOT_FOUND,
    ADMIN_ERR_WORLDVIEW_SNAPSHOT_NOT_FOUND,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.feed_post import FeedPost
from backend.models.worldview_event import WorldviewEvent
from backend.models.worldview_snapshot import WorldviewSnapshot
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_READ_ROLES = ("super_admin", "ai_trainer", "ops_admin", "observer")
_VALID_ATTITUDES = ("喜欢", "排斥", "矛盾", "无感")
_ATTITUDE_PREFIX_RE = re.compile(r"^\[核心态度：(喜欢|排斥|矛盾|无感)\]\s*")
# 快照默认窗口：近 14 天（含今天）
_SNAPSHOT_DEFAULT_DAYS = 14


def _parse_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _split_attitude(event_view: str) -> tuple[str | None, str]:
    """从 event_view 拆出核心态度前缀。返回 (attitude|None, 去前缀正文)。"""
    m = _ATTITUDE_PREFIX_RE.match(event_view or "")
    if m:
        return m.group(1), _ATTITUDE_PREFIX_RE.sub("", event_view, count=1)
    return None, (event_view or "")


def _compose_view(core_attitude: str, body_text: str) -> str:
    return f"[核心态度：{core_attitude}] {body_text.strip()}"


def _snapshot_to_dict(s: WorldviewSnapshot) -> dict:
    return {
        "id": s.id,
        "plan_date": s.plan_date.isoformat(),
        "scene_id": s.scene_id,
        "feeling_text": s.feeling_text,
        "emotion_value": s.emotion_value,
        "focus_tag": s.focus_tag,
        "worldview_trigger": s.worldview_trigger,
        "gen_status": s.gen_status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _event_to_dict(e: WorldviewEvent) -> dict:
    attitude, body = _split_attitude(e.event_view)
    return {
        "id": e.id,
        "event_name": e.event_name,
        "event_view": body,
        "core_attitude": attitude,
        "source_scene_id": e.source_scene_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


# ─────────────────────────── 快照 CRUD ───────────────────────────

class SnapshotUpdateBody(BaseModel):
    emotion_value: str | None = None
    focus_tag: str | None = None
    worldview_trigger: str | None = None
    feeling_text: str | None = None


@router.get("/worldview/snapshots", dependencies=[require_role(*_READ_ROLES)])
async def list_snapshots(
    plan_date: str | None = Query(None, description="单日查询（兼容旧行为，返回数组）"),
    start: str | None = Query(None, description="范围起始 YYYY-MM-DD"),
    end: str | None = Query(None, description="范围结束 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """快照列表：单日返回数组；范围/默认近14天返回分页。

    排序：plan_date DESC（跨天最近在前），同日内 scene_id ASC（早→晚）。
    """
    # 兼容：仅 plan_date → 返回当日数组（旧契约）
    if plan_date and not start and not end:
        d = _parse_date(plan_date)
        if d is None:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
        rows = (await db.execute(
            select(WorldviewSnapshot)
            .where(WorldviewSnapshot.plan_date == d)
            .order_by(WorldviewSnapshot.scene_id.asc()))).scalars().all()
        return ApiResponse.ok(data=[_snapshot_to_dict(r) for r in rows])

    # 范围查询；无参时默认近 14 天（含今天）
    today = date.today()
    if start or end:
        ds = _parse_date(start) if start else None
        de = _parse_date(end) if end else None
        if (start and ds is None) or (end and de is None):
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID)
        if ds is None:
            ds = de - timedelta(days=_SNAPSHOT_DEFAULT_DAYS - 1)
        if de is None:
            de = today
    else:
        de = today
        ds = today - timedelta(days=_SNAPSHOT_DEFAULT_DAYS - 1)

    if ds > de:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="start 不能晚于 end")

    cond = [
        WorldviewSnapshot.plan_date >= ds,
        WorldviewSnapshot.plan_date <= de,
    ]
    total = (await db.execute(
        select(func.count(WorldviewSnapshot.id)).where(*cond))).scalar() or 0
    rows = (await db.execute(
        select(WorldviewSnapshot).where(*cond)
        .order_by(
            WorldviewSnapshot.plan_date.desc(),
            WorldviewSnapshot.scene_id.asc(),
        )
        .offset((page - 1) * size).limit(size))).scalars().all()
    return ApiResponse.ok(data={
        "total": total, "page": page, "size": size,
        "start": ds.isoformat(), "end": de.isoformat(),
        "list": [_snapshot_to_dict(r) for r in rows],
    })


@router.get("/worldview/snapshots/{snapshot_id}", dependencies=[require_role(*_READ_ROLES)])
async def get_snapshot(
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """快照详情。"""
    row = (await db.execute(
        select(WorldviewSnapshot).where(WorldviewSnapshot.id == snapshot_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_SNAPSHOT_NOT_FOUND)
    return ApiResponse.ok(data=_snapshot_to_dict(row))


@router.put("/worldview/snapshots/{snapshot_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_snapshot(
    snapshot_id: int,
    body: SnapshotUpdateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑快照（emotion_value 允许自由词；focus_tag/worldview_trigger/feeling_text）。"""
    row = (await db.execute(
        select(WorldviewSnapshot).where(WorldviewSnapshot.id == snapshot_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_SNAPSHOT_NOT_FOUND)
    if body.emotion_value is not None:
        row.emotion_value = body.emotion_value  # 自由词允许，不校验 vocab
    if body.focus_tag is not None:
        row.focus_tag = body.focus_tag
    if body.worldview_trigger is not None:
        row.worldview_trigger = body.worldview_trigger
    if body.feeling_text is not None:
        row.feeling_text = body.feeling_text
    await log_operation(db, admin_user, "worldview", "update_snapshot",
                        f"编辑快照 id={snapshot_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_snapshot_to_dict(row))


@router.delete("/worldview/snapshots/{snapshot_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_snapshot(
    snapshot_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除快照；若对应 feed_post 已生成仅记 WARN 不阻断。"""
    row = (await db.execute(
        select(WorldviewSnapshot).where(WorldviewSnapshot.id == snapshot_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_SNAPSHOT_NOT_FOUND)
    referenced = (await db.execute(
        select(FeedPost.id).where(FeedPost.scene_id == row.scene_id).limit(1))).scalars().first()
    if referenced:
        logger.warning("[后台][她的宇宙] 删除已被 feed_post 引用的快照 scene_id=%s post_id=%s",
                       row.scene_id, referenced)
    await db.delete(row)
    await log_operation(db, admin_user, "worldview", "delete_snapshot",
                        f"删除快照 id={snapshot_id} scene_id={row.scene_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data={"deleted": snapshot_id, "referenced_by_post": referenced})


# ─────────────────────────── 事件库 CRUD ───────────────────────────

class EventCreateBody(BaseModel):
    event_name: str
    event_view: str
    core_attitude: str
    source_scene_id: str | None = None


class EventUpdateBody(BaseModel):
    event_name: str | None = None
    event_view: str | None = None
    core_attitude: str | None = None
    source_scene_id: str | None = None


@router.get("/worldview/events", dependencies=[require_role(*_READ_ROLES)])
async def list_events(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """事件库列表（分页 + event_name 模糊）。"""
    cond = []
    if keyword:
        cond.append(WorldviewEvent.event_name.like(f"%{keyword}%"))
    total = (await db.execute(
        select(func.count(WorldviewEvent.id)).where(*cond))).scalar() or 0
    rows = (await db.execute(
        select(WorldviewEvent).where(*cond)
        .order_by(WorldviewEvent.updated_at.desc())
        .offset((page - 1) * size).limit(size))).scalars().all()
    return ApiResponse.ok(data={
        "total": total, "page": page, "size": size,
        "list": [_event_to_dict(r) for r in rows],
    })


@router.post("/worldview/events", dependencies=[require_role(*_ALLOWED_ROLES)])
async def create_event(
    body: EventCreateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """新增事件（core_attitude 四选项强校验，嵌入 event_view 前缀存储）。"""
    if body.core_attitude not in _VALID_ATTITUDES:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_ATTITUDE_INVALID)
    _, body_text = _split_attitude(body.event_view)
    row = WorldviewEvent(
        event_name=body.event_name.strip(),
        event_view=_compose_view(body.core_attitude, body_text),
        source_scene_id=body.source_scene_id)
    db.add(row)
    await db.flush()
    await log_operation(db, admin_user, "worldview", "create_event",
                        f"新增事件 {body.event_name}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_event_to_dict(row))


@router.put("/worldview/events/{event_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_event(
    event_id: int,
    body: EventUpdateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑事件（允许覆盖，管理员权威）。"""
    row = (await db.execute(
        select(WorldviewEvent).where(WorldviewEvent.id == event_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_EVENT_NOT_FOUND)

    cur_attitude, cur_body = _split_attitude(row.event_view)
    new_attitude = body.core_attitude if body.core_attitude is not None else (cur_attitude or "无感")
    if new_attitude not in _VALID_ATTITUDES:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_ATTITUDE_INVALID)
    new_body = cur_body
    if body.event_view is not None:
        _, new_body = _split_attitude(body.event_view)

    if body.event_name is not None:
        row.event_name = body.event_name.strip()
    if body.source_scene_id is not None:
        row.source_scene_id = body.source_scene_id
    row.event_view = _compose_view(new_attitude, new_body)

    await log_operation(db, admin_user, "worldview", "update_event",
                        f"编辑事件 id={event_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_event_to_dict(row))


@router.delete("/worldview/events/{event_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_event(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除事件。"""
    row = (await db.execute(
        select(WorldviewEvent).where(WorldviewEvent.id == event_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_WORLDVIEW_EVENT_NOT_FOUND)
    await db.delete(row)
    await log_operation(db, admin_user, "worldview", "delete_event",
                        f"删除事件 id={event_id} name={row.event_name}", request=request)
    await db.commit()
    return ApiResponse.ok(data={"deleted": event_id})
