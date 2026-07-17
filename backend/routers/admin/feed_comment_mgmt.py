# -*- coding: utf-8 -*-
# 生活流·后台评论管理 API（STEP-034 · PRD 10.4）：全量评论列表 + 筛选 + CRUD + 失败补发 + 已读状态展示
#
# 前缀 /api/admin（见 main.py），权限 super_admin / ai_trainer；写操作全落 operation_log。
# DELETE 走软删（is_hidden=1，STEP-034 v6c 迁移新增）；补发调 comment_reply_service.consume_one 异步重跑。

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_FEED_COMMENT_NOT_FOUND, ADMIN_ERR_LIFE_PARAM_INVALID
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.feed_comment import FeedComment
from backend.models.user import User
from backend.schemas.common import ApiResponse
from backend.services.comment_reply_service import comment_reply_service
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_READ_ROLES = ("super_admin", "ai_trainer", "ops_admin", "observer")
# 5 状态筛选（PRD 10.4#1）：pending/generating/ready/failed 走 gen_status；hidden 走 is_hidden=1
_VALID_GEN_STATUS = ("pending", "generating", "ready", "failed", "hidden")


def _summary(text: str | None, limit: int = 60) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "…"


def _comment_to_dict(c: FeedComment, username: str | None = None, *, detail: bool = False) -> dict:
    data = {
        "id": c.id,
        "post_id": c.post_id,
        "user_id": c.user_id,
        "user_nickname": username,
        "user_content": c.content if detail else _summary(c.content),
        "lxm_reply": c.lxm_reply if detail else _summary(c.lxm_reply),
        "gen_status": "hidden" if c.is_hidden else c.gen_status,
        "is_hidden": c.is_hidden,
        "lxm_reply_read_at": c.lxm_reply_read_at.isoformat() if c.lxm_reply_read_at else None,
        "lxm_reply_at": c.lxm_reply_at.isoformat() if c.lxm_reply_at else None,
        "due_at": c.due_at.isoformat() if c.due_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    return data


@router.get("/feed/comments", dependencies=[require_role(*_READ_ROLES)])
async def list_comments(
    post_id: int | None = Query(None),
    user_id: int | None = Query(None),
    gen_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """全量评论列表（多筛选）。"""
    if gen_status and gen_status not in _VALID_GEN_STATUS:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                message=f"gen_status 必须是 {'/'.join(_VALID_GEN_STATUS)}")
    cond = []
    if post_id is not None:
        cond.append(FeedComment.post_id == post_id)
    if user_id is not None:
        cond.append(FeedComment.user_id == user_id)
    if gen_status == "hidden":
        cond.append(FeedComment.is_hidden == 1)
    elif gen_status:
        cond.append(FeedComment.gen_status == gen_status)
        cond.append(FeedComment.is_hidden == 0)

    total = (await db.execute(select(func.count(FeedComment.id)).where(*cond))).scalar() or 0
    rows = (await db.execute(
        select(FeedComment).where(*cond)
        .order_by(FeedComment.created_at.desc())
        .offset((page - 1) * size).limit(size))).scalars().all()

    # 批量取用户名
    uid_set = {r.user_id for r in rows}
    name_map = {}
    if uid_set:
        urows = (await db.execute(
            select(User.id, User.username).where(User.id.in_(uid_set)))).all()
        name_map = {u[0]: u[1] for u in urows}

    return ApiResponse.ok(data={
        "total": total, "page": page, "size": size,
        "list": [_comment_to_dict(r, name_map.get(r.user_id)) for r in rows],
    })


@router.get("/feed/comments/{comment_id}", dependencies=[require_role(*_READ_ROLES)])
async def get_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """评论详情。"""
    row = (await db.execute(
        select(FeedComment).where(FeedComment.id == comment_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_COMMENT_NOT_FOUND)
    username = (await db.execute(
        select(User.username).where(User.id == row.user_id))).scalars().first()
    return ApiResponse.ok(data=_comment_to_dict(row, username, detail=True))


class CommentUpdateBody(BaseModel):
    content: str | None = None
    lxm_reply: str | None = None


@router.put("/feed/comments/{comment_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_comment(
    comment_id: int,
    body: CommentUpdateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑评论（content 保留原文可改 / lxm_reply 覆盖生成）。"""
    row = (await db.execute(
        select(FeedComment).where(FeedComment.id == comment_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_COMMENT_NOT_FOUND)
    if body.content is not None:
        row.content = body.content
    if body.lxm_reply is not None:
        row.lxm_reply = body.lxm_reply
        # 管理员覆盖回复视为 ready，并记发出时间（若之前无）
        row.gen_status = "ready"
        if row.lxm_reply_at is None:
            row.lxm_reply_at = datetime.utcnow()
    await log_operation(db, admin_user, "feed_comment", "update_comment",
                        f"编辑评论 id={comment_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_comment_to_dict(row, detail=True))


@router.delete("/feed/comments/{comment_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_comment(
    comment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """软删（is_hidden=1，DB 保留，用户端不再展示）。"""
    row = (await db.execute(
        select(FeedComment).where(FeedComment.id == comment_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_COMMENT_NOT_FOUND)
    row.is_hidden = 1
    await log_operation(db, admin_user, "feed_comment", "delete_comment",
                        f"隐藏评论 id={comment_id}（软删，DB 保留）", request=request)
    await db.commit()
    return ApiResponse.ok(data={"id": comment_id, "is_hidden": 1})


@router.post("/feed/comments/{comment_id}/regenerate", dependencies=[require_role(*_ALLOWED_ROLES)])
async def regenerate_comment(
    comment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """手动触发 LLM-05 补发：重置为 pending + due_at=NOW，异步 consume_one 立即重跑。"""
    row = (await db.execute(
        select(FeedComment).where(FeedComment.id == comment_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_COMMENT_NOT_FOUND)

    await db.execute(
        update(FeedComment)
        .where(FeedComment.id == comment_id)
        .values(gen_status="pending", due_at=datetime.utcnow(),
                lxm_reply=None, lxm_reply_at=None))
    await log_operation(db, admin_user, "feed_comment", "regenerate_comment",
                        f"手动补发评论回复 id={comment_id}", request=request)
    await db.commit()

    # 异步立即重跑（consume_one 内含 pending→generating 原子抢占，与轮询任务无冲突）
    asyncio.create_task(comment_reply_service.consume_one(comment_id))
    return ApiResponse.ok(data={"status": "queued", "id": comment_id})
