# -*- coding: utf-8 -*-
# 生活流·后台点赞/已读感知消息管理 API（STEP-035 · PRD 10.8）
#
# agent_aware_queue LEFT JOIN agent_message 联合视图；手动重试；删除审计（不撤回已送达 IM）；
# 运营重置特殊档计数（仅 super_admin）。前缀 /api/admin，写操作全落 operation_log。

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_AGENT_AWARE_NOT_FOUND,
    ADMIN_ERR_AGENT_AWARE_RETRY_INVALID,
    ADMIN_ERR_LIFE_PARAM_INVALID,
    ADMIN_ERR_RELATIONSHIP_NOT_FOUND,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.agent_aware_queue import AgentAwareQueue
from backend.models.agent_message import AgentMessage
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_READ_ROLES = ("super_admin", "ai_trainer", "ops_admin")
_VALID_TRIGGER = ("LIKE_AWARE", "READ_AWARE")
_VALID_STATUS = ("pending", "generating", "sent", "failed")


def _summary(text: str | None, limit: int = 60) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "…"


def _row_to_dict(q: AgentAwareQueue, username: str | None,
                 msg_content: str | None, *, detail: bool = False) -> dict:
    data = {
        "queue_id": q.id,
        "user_id": q.user_id,
        "user_nickname": username,
        "aware_type": q.trigger_type,
        "status": q.status,
        "due_at": q.due_at.isoformat() if q.due_at else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "relationship_stage": q.relationship_stage,
        "prompt_key": q.prompt_key,
        "related_post_id": q.post_id,
        "agent_message_id": q.agent_message_id,
        "agent_message_content": _summary(msg_content),
        "fail_reason": q.fail_reason,
    }
    if detail:
        data["extra_context"] = q.extra_context
    return data


@router.get("/agent-aware", dependencies=[require_role(*_READ_ROLES)])
async def list_agent_aware(
    user_id: int | None = Query(None),
    trigger_type: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """联合视图（agent_aware_queue LEFT JOIN agent_message）。"""
    if trigger_type and trigger_type not in _VALID_TRIGGER:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                message=f"trigger_type 必须是 {'/'.join(_VALID_TRIGGER)}")
    if status and status not in _VALID_STATUS:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                message=f"status 必须是 {'/'.join(_VALID_STATUS)}")
    cond = []
    if user_id is not None:
        cond.append(AgentAwareQueue.user_id == user_id)
    if trigger_type:
        cond.append(AgentAwareQueue.trigger_type == trigger_type)
    if status:
        cond.append(AgentAwareQueue.status == status)

    total = (await db.execute(
        select(func.count(AgentAwareQueue.id)).where(*cond))).scalar() or 0
    rows = (await db.execute(
        select(AgentAwareQueue).where(*cond)
        .order_by(AgentAwareQueue.created_at.desc())
        .offset((page - 1) * size).limit(size))).scalars().all()

    uid_set = {r.user_id for r in rows}
    name_map = {}
    if uid_set:
        urows = (await db.execute(
            select(User.id, User.username).where(User.id.in_(uid_set)))).all()
        name_map = {u[0]: u[1] for u in urows}

    msg_ids = {r.agent_message_id for r in rows if r.agent_message_id}
    msg_map = {}
    if msg_ids:
        mrows = (await db.execute(
            select(AgentMessage.id, AgentMessage.content)
            .where(AgentMessage.id.in_(msg_ids)))).all()
        msg_map = {m[0]: m[1] for m in mrows}

    return ApiResponse.ok(data={
        "total": total, "page": page, "size": size,
        "list": [_row_to_dict(r, name_map.get(r.user_id),
                              msg_map.get(r.agent_message_id)) for r in rows],
    })


@router.get("/agent-aware/{queue_id}", dependencies=[require_role(*_READ_ROLES)])
async def get_agent_aware(
    queue_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """联合视图详情（含 extra_context JSON）。"""
    row = (await db.execute(
        select(AgentAwareQueue).where(AgentAwareQueue.id == queue_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_AGENT_AWARE_NOT_FOUND)
    username = (await db.execute(
        select(User.username).where(User.id == row.user_id))).scalars().first()
    msg_content = None
    if row.agent_message_id:
        msg_content = (await db.execute(
            select(AgentMessage.content)
            .where(AgentMessage.id == row.agent_message_id))).scalars().first()
    return ApiResponse.ok(data=_row_to_dict(row, username, msg_content, detail=True))


@router.post("/agent-aware/{queue_id}/retry", dependencies=[require_role(*_ALLOWED_ROLES)])
async def retry_agent_aware(
    queue_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """手动重试（failed → pending，due_at 置 NOW，由 STEP-019 轮询消费）。"""
    row = (await db.execute(
        select(AgentAwareQueue).where(AgentAwareQueue.id == queue_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_AGENT_AWARE_NOT_FOUND)
    if row.status != "failed":
        return ApiResponse.fail(ADMIN_ERR_AGENT_AWARE_RETRY_INVALID)
    await db.execute(
        update(AgentAwareQueue)
        .where(AgentAwareQueue.id == queue_id, AgentAwareQueue.status == "failed")
        .values(status="pending", due_at=datetime.utcnow(), fail_reason=None))
    await log_operation(db, admin_user, "agent_aware", "retry",
                        f"手动重试感知队列 id={queue_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data={"queue_id": queue_id, "status": "pending"})


@router.delete("/agent-aware/{queue_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_agent_aware(
    queue_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除队列记录（不撤回已送达 agent_message，PRD 10.8）。"""
    row = (await db.execute(
        select(AgentAwareQueue).where(AgentAwareQueue.id == queue_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_AGENT_AWARE_NOT_FOUND)
    had_msg = row.agent_message_id
    await db.delete(row)
    await log_operation(
        db, admin_user, "agent_aware", "delete",
        f"删除感知队列 id={queue_id}（已送达 IM 不撤回，agent_message_id={had_msg}）",
        request=request)
    await db.commit()
    return ApiResponse.ok(data={"deleted": queue_id, "kept_agent_message_id": had_msg})


@router.post("/users/{user_id}/aware/reset", dependencies=[require_role("super_admin")])
async def reset_aware_counters(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """重置特殊档计数（super_admin，便于测试；PRD 11.4 注释）。"""
    row = (await db.execute(
        select(Relationship).where(Relationship.user_id == user_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_RELATIONSHIP_NOT_FOUND)
    row.like_aware_special_used_count = 0
    row.read_aware_special_used_count = 0
    await log_operation(db, admin_user, "agent_aware", "reset_special_counters",
                        f"重置用户 user_id={user_id} 点赞/已读特殊档计数", request=request)
    await db.commit()
    return ApiResponse.ok(data={
        "user_id": user_id,
        "like_aware_special_used_count": 0,
        "read_aware_special_used_count": 0,
    })
