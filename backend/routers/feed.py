# -*- coding: utf-8 -*-
# 生活流·朋友圈用户端 API（STEP-015 列表/enter/badge、STEP-016 点赞、STEP-017 评论）
#
# 前缀 /api/feed，全部接口 JWT 鉴权。业务逻辑在 backend/services/feed_service.py。

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services.feed_service import FeedError, feed_service
from backend.services.feed_sse_service import feed_sse_service
from backend.utils.auth_middleware import get_current_user
from backend.utils.jwt_handler import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feed", tags=["朋友圈"])

# SSE 无事件心跳间隔（秒）：超时未取到事件即发送注释行保活
_SSE_HEARTBEAT_SEC = 15


class CommentBody(BaseModel):
    content: str = ""
    # 点击林小梦回复后发评时传 true；默认 false（💬 普通发评）
    reply_to_lxm: bool = False


@router.get("/list", response_model=ApiResponse)
async def get_feed_list(
    cursor: str | None = Query(None, description="游标：上一页最后一条 scheduled_publish_time"),
    size: int = Query(20, ge=1, le=50, description="每页数量，默认 20 上限 50"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Feed 列表（游标分页，仅返回已到点+可见+ready 的帖子，评论私有过滤）。"""
    data = await feed_service.list_feed(db, user_id, cursor, size)
    return ApiResponse.ok(data=data)


@router.get("/config/header", response_model=ApiResponse)
async def get_feed_header_config(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """朋友圈页 Header 配置（背景图/头像/签名/昵称），缺失回落默认。"""
    data = await feed_service.get_header_config()
    return ApiResponse.ok(data=data)


@router.post("/enter", response_model=ApiResponse)
async def enter_feed(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """进入朋友圈页：写 last_feed_entered_at，返回未读回复锚点。"""
    data = await feed_service.enter_feed(db, user_id)
    return ApiResponse.ok(data=data)


@router.get("/badge", response_model=ApiResponse)
async def get_feed_badge(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """首页朋友圈入口：has_new + new_post_count + unread_reply_count。"""
    data = await feed_service.get_badge(db, user_id)
    return ApiResponse.ok(data=data)


@router.post("/{post_id}/like", response_model=ApiResponse)
async def like_post(
    post_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """点赞（幂等）。"""
    try:
        data = await feed_service.like_post(db, user_id, post_id)
    except FeedError as e:
        return ApiResponse.fail(code=e.code)
    return ApiResponse.ok(data=data)


@router.delete("/{post_id}/like", response_model=ApiResponse)
async def unlike_post(
    post_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消点赞（幂等，不撤回已触发的点赞 IM）。"""
    try:
        data = await feed_service.unlike_post(db, user_id, post_id)
    except FeedError as e:
        return ApiResponse.fail(code=e.code)
    return ApiResponse.ok(data=data)


@router.post("/{post_id}/comments", response_model=ApiResponse)
async def create_comment(
    post_id: int,
    body: CommentBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发评（含长度/频控/内容安全三层校验 + 首次评论 30s override）。"""
    try:
        data = await feed_service.create_comment(
            db, user_id, post_id, body.content, reply_to_lxm=body.reply_to_lxm)

    except FeedError as e:
        return ApiResponse.fail(code=e.code)
    return ApiResponse.ok(data=data)


# ─────────────────────────── STEP-026 SSE 新帖推送 ───────────────────────────

@router.get("/events")
async def feed_events(request: Request, token: str = Query(..., description="JWT（EventSource 无法自定义 header，走 query）")):
    """
    朋友圈新帖 SSE 长连接（text/event-stream）。
    浏览器 EventSource 不支持自定义 header，token 通过 query 传入并在此端点独立校验。
    """
    try:
        user_id = verify_token(token)["user_id"]
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效或已过期")

    async def event_generator():
        q = feed_sse_service.register(user_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_SSE_HEARTBEAT_SEC)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 心跳（SSE 注释行，不被前端解析）
                    yield ": heartbeat\n\n"
        finally:
            feed_sse_service.unregister(user_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────── STEP-029 已读上报 ───────────────────────────

@router.post("/comments/{comment_id}/read", response_model=ApiResponse)
async def read_comment_reply(
    comment_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """单条评论回复已读上报：写 lxm_reply_read_at（幂等，越权 403）。"""
    try:
        data = await feed_service.mark_comment_reply_read(db, user_id, comment_id)
    except FeedError as e:
        return ApiResponse.fail(code=e.code)
    return ApiResponse.ok(data=data)


@router.post("/{post_id}/read", response_model=ApiResponse)
async def read_feed_post(
    post_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """单帖已读上报：校验可见+到点后触发已读感知 IM 判定（STEP-021）。"""
    try:
        data = await feed_service.mark_feed_post_read(db, user_id, post_id)
    except FeedError as e:
        return ApiResponse.fail(code=e.code)
    return ApiResponse.ok(data=data)
