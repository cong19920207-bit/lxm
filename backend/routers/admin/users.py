# -*- coding: utf-8 -*-
# 后台用户管理：列表/详情/对话/记忆/状态/重置密码

import logging
import random
import string
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.memory import Memory
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.constants import (
    ADMIN_ERR_USER_ALREADY_BANNED,
    ADMIN_ERR_USER_MEMORY_CONTENT_EMPTY,
    ADMIN_ERR_USER_MEMORY_NOT_FOUND,
    ADMIN_ERR_USER_NOT_BANNED,
    ADMIN_ERR_USER_NOT_FOUND,
    ADMIN_ERR_USER_STATUS_ACTION_INVALID,
    MEMORY_TYPE_USER,
)
from backend.redis_client import get_redis
from backend.schemas.common import ApiResponse
from backend.schemas.memory import AdminMemoryUpdateRequest
from backend.services.admin_diary_query import fetch_admin_diary_list_page
from backend.services.embedding_service import embedding_service
from backend.services.vector_service import vector_service
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

# 关系等级映射
_LEVEL_NAMES = {0: "陌生", 1: "朋友", 2: "亲密", 3: "知己"}
_LEVEL_THRESHOLDS = {0: 200, 1: 800, 2: 2000, 3: None}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口一：GET /users 用户列表
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def list_users(
    username: str | None = Query(None, max_length=20),
    relationship_level: int | None = Query(None, ge=0, le=3),
    status: str | None = Query(None, pattern=r"^(normal|banned)$"),
    register_start: str | None = Query(None),
    register_end: str | None = Query(None),
    last_login_start: str | None = Query(None),
    last_login_end: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """用户列表，支持多条件筛选"""
    # 子查询：每个用户的 role='user' 对话条数
    conv_count_sub = (
        select(
            ConversationLog.user_id,
            func.count(ConversationLog.id).label("total_conversation_count"),
        )
        .where(ConversationLog.role == "user")
        .group_by(ConversationLog.user_id)
        .subquery()
    )

    # 主查询：等级/成长值以 relationship 表为准（与 RelationshipService 读法一致：按 user_id 关联，无行视为 0）
    stmt = (
        select(
            User.id,
            User.username,
            User.created_at,
            User.last_login_at,
            func.coalesce(Relationship.level, 0).label("relationship_level"),
            func.coalesce(Relationship.growth_value, 0).label("growth_value"),
            User.is_banned,
            func.coalesce(conv_count_sub.c.total_conversation_count, 0).label(
                "total_conversation_count"
            ),
        )
        .select_from(User)
        .outerjoin(Relationship, User.id == Relationship.user_id)
        .outerjoin(conv_count_sub, User.id == conv_count_sub.c.user_id)
    )

    # 筛选条件
    if username:
        stmt = stmt.where(User.username.like(f"%{username}%"))
    if relationship_level is not None:
        stmt = stmt.where(
            func.coalesce(Relationship.level, 0) == relationship_level
        )
    if status:
        if status == "banned":
            stmt = stmt.where(User.is_banned.is_(True))
        else:
            stmt = stmt.where(User.is_banned.is_(False))
    if register_start:
        stmt = stmt.where(User.created_at >= register_start)
    if register_end:
        stmt = stmt.where(User.created_at <= register_end)
    if last_login_start:
        stmt = stmt.where(User.last_login_at >= last_login_start)
    if last_login_end:
        stmt = stmt.where(User.last_login_at <= last_login_end)

    # last_login_at倒序，NULL排最后
    stmt = stmt.order_by(
        case((User.last_login_at.is_(None), 1), else_=0),
        User.last_login_at.desc(),
    )

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()

    row_list = []
    for row in rows:
        row_list.append(
            {
                "id": row.id,
                "username": row.username,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
                "relationship_level": row.relationship_level,
                "growth_value": row.growth_value,
                "total_conversation_count": row.total_conversation_count,
                "status": "banned" if row.is_banned else "normal",
            }
        )

    return ApiResponse.ok(
        data={"total": total, "page": page, "page_size": page_size, "list": row_list},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口二：GET /users/{user_id} 用户详情
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users/{user_id}",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def get_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """用户详情"""
    # 用户与关系行一并查询（outerjoin：无 relationship 行时等级/成长值按 0，与用户端懒创建前一致）
    detail_stmt = (
        select(
            User,
            func.coalesce(Relationship.level, 0),
            func.coalesce(Relationship.growth_value, 0),
        )
        .select_from(User)
        .outerjoin(Relationship, User.id == Relationship.user_id)
        .where(User.id == user_id)
    )
    detail_result = await db.execute(detail_stmt)
    detail_row = detail_result.first()
    if not detail_row:
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)
    user = detail_row[0]
    level = int(detail_row[1])
    growth_value = int(detail_row[2])

    # 总对话数（role='user'）
    conv_count_stmt = (
        select(func.count(ConversationLog.id))
        .where(ConversationLog.user_id == user_id, ConversationLog.role == "user")
    )
    conv_count_result = await db.execute(conv_count_stmt)
    total_conversation_count = conv_count_result.scalar() or 0

    # 近7天有对话记录的天数
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    seven_days_ago = now_utc - timedelta(days=7)
    active_days_stmt = (
        select(func.count(func.distinct(func.date(ConversationLog.created_at))))
        .where(
            ConversationLog.user_id == user_id,
            ConversationLog.created_at >= seven_days_ago,
        )
    )
    active_days_result = await db.execute(active_days_stmt)
    active_days_last7 = active_days_result.scalar() or 0

    # agent_message中is_read=True的数量
    agent_reply_stmt = (
        select(func.count(AgentMessage.id))
        .where(AgentMessage.user_id == user_id, AgentMessage.is_read.is_(True))
    )
    agent_reply_result = await db.execute(agent_reply_stmt)
    agent_message_reply_count = agent_reply_result.scalar() or 0

    # 关系等级信息（level / growth_value 已来自 relationship 表）
    level_name = _LEVEL_NAMES.get(level, "未知")
    next_threshold = _LEVEL_THRESHOLDS.get(level)
    if next_threshold is not None:
        progress_percent = round(growth_value / next_threshold * 100) if next_threshold > 0 else 0
        progress_percent = min(progress_percent, 100)
    else:
        # 已满级
        progress_percent = 100
        next_threshold = None

    data = {
        "basic": {
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "status": "banned" if user.is_banned else "normal",
            "is_banned": user.is_banned,
        },
        "relationship": {
            "level": level,
            "level_name": level_name,
            "growth_value": growth_value,
            "next_threshold": next_threshold,
            "progress_percent": progress_percent,
        },
        "activity": {
            "total_conversation_count": total_conversation_count,
            "active_days_last7": active_days_last7,
            "agent_message_reply_count": agent_message_reply_count,
        },
    }

    return ApiResponse.ok(data=data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口三：GET /users/{user_id}/conversations 历史对话
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users/{user_id}/conversations",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def get_user_conversations(
    user_id: int,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """查看用户历史对话记录（只读）"""
    # 检查用户是否存在
    user_stmt = select(User.id).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    if not user_result.scalar():
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    stmt = select(ConversationLog).where(ConversationLog.user_id == user_id)

    if start_date:
        stmt = stmt.where(ConversationLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(ConversationLog.created_at <= end_date)

    # 按created_at正序（最早的在前）
    stmt = stmt.order_by(ConversationLog.created_at.asc())

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    row_list = []
    for row in rows:
        if row.role == "assistant":
            delivery_status = None
            skipped_in_prompt = None
        else:
            delivery_status = row.delivery_status
            skipped_in_prompt = bool(row.skipped_in_prompt)

        row_list.append(
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "emotion_label": row.emotion_label if row.role == "user" else None,
                "emotion_confidence": row.emotion_confidence if row.role == "user" else None,
                "persona_risk_flag": row.persona_risk_flag,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "sort_seq": row.sort_seq,
                "delivery_status": delivery_status,
                "skipped_in_prompt": skipped_in_prompt,
            }
        )

    return ApiResponse.ok(
        data={"total": total, "page": page, "page_size": page_size, "list": row_list},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口三·二：GET /users/{user_id}/emotion-rounds 情绪日志（按 round_id 聚合，只读）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users/{user_id}/emotion-rounds",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def get_user_emotion_rounds(
    user_id: int,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """按轮展示 emotion_log（与历史对话 Tab 同鉴权）；批量拉取 conversation_log 避免 N+1。"""
    user_stmt = select(User.id).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    if not user_result.scalar():
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    filters = [EmotionLog.user_id == user_id]
    if start_date:
        filters.append(EmotionLog.created_at >= start_date)
    if end_date:
        filters.append(EmotionLog.created_at <= end_date)

    count_stmt = select(func.count()).select_from(EmotionLog).where(*filters)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    list_stmt = (
        select(EmotionLog)
        .where(*filters)
        .order_by(EmotionLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    list_result = await db.execute(list_stmt)
    emotion_rows = list(list_result.scalars().all())

    round_ids_ordered: list[str] = []
    seen: set[str] = set()
    for e in emotion_rows:
        if e.round_id and e.round_id not in seen:
            seen.add(e.round_id)
            round_ids_ordered.append(e.round_id)

    conv_by_round: dict[str, list[ConversationLog]] = {}
    if round_ids_ordered:
        conv_stmt = (
            select(ConversationLog)
            .where(
                ConversationLog.user_id == user_id,
                ConversationLog.round_id.in_(round_ids_ordered),
            )
            .order_by(ConversationLog.sort_seq.asc())
        )
        conv_result = await db.execute(conv_stmt)
        for row in conv_result.scalars().all():
            rid = row.round_id
            if not rid:
                continue
            conv_by_round.setdefault(rid, []).append(row)

    row_list: list[dict] = []
    for el in emotion_rows:
        user_parts: list[str] = []
        assistant_text = ""
        if el.round_id and el.round_id in conv_by_round:
            for crow in conv_by_round[el.round_id]:
                if crow.role == "user":
                    user_parts.append(crow.content or "")
                elif crow.role == "assistant":
                    assistant_text = crow.content or ""
            user_text = "\n".join(user_parts) if user_parts else ""
        else:
            # V2-B 前：无 round_id，仅展示轮级标签与锚点 conversation_id
            user_text = ""
            assistant_text = ""

        row_list.append(
            {
                "emotion_log_id": el.id,
                "round_id": el.round_id,
                "emotion_label": el.emotion_label,
                "confidence": el.confidence,
                "created_at": el.created_at.isoformat() if el.created_at else None,
                "anchor_conversation_id": el.conversation_id,
                "user_text": user_text,
                "assistant_text": assistant_text,
            }
        )

    return ApiResponse.ok(
        data={"total": total, "page": page, "page_size": page_size, "list": row_list},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口四：GET /users/{user_id}/memories 用户记忆列表
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users/{user_id}/memories",
    dependencies=[require_role("super_admin", "ops_admin", "ai_trainer")],
)
async def list_user_memories(
    user_id: int,
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """用户记忆列表"""
    # 检查用户是否存在
    user_stmt = select(User.id).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    if not user_result.scalar():
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    stmt = select(Memory).where(
        Memory.user_id == user_id,
        Memory.is_deleted.is_(False),
    )

    if keyword:
        stmt = stmt.where(Memory.content.like(f"%{keyword}%"))

    stmt = stmt.order_by(Memory.created_at.desc())

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    row_list = []
    for row in rows:
        row_list.append(
            {
                "id": row.id,
                "content": row.content,
                "importance_score": row.importance_score,
                "source": row.source,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )

    return ApiResponse.ok(
        data={"total": total, "page": page, "page_size": page_size, "list": row_list},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口四（补）：GET /users/{user_id}/diaries 用户 AI 日记列表
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users/{user_id}/diaries",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def list_user_diaries(
    user_id: int,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """用户 AI 日记分页（只读）；与 GET /api/admin/diary-history 共用查询逻辑（同条件结果一致）。"""
    user_stmt = select(User.id).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    if not user_result.scalar():
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    err, data = await fetch_admin_diary_list_page(
        db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    if err:
        return err
    return ApiResponse.ok(data=data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口五：PUT /users/{user_id}/memories/{memory_id} 编辑记忆
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.put(
    "/users/{user_id}/memories/{memory_id}",
    dependencies=[require_role("super_admin", "ops_admin", "ai_trainer")],
)
async def update_memory(
    user_id: int,
    memory_id: int,
    req: AdminMemoryUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑用户记忆内容"""
    new_content = req.content.strip()
    if not new_content:
        return ApiResponse.fail(ADMIN_ERR_USER_MEMORY_CONTENT_EMPTY)

    # 校验memory_id属于该user_id
    stmt = select(Memory).where(
        Memory.id == memory_id,
        Memory.user_id == user_id,
        Memory.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    memory = result.scalars().first()
    if not memory:
        return ApiResponse.fail(ADMIN_ERR_USER_MEMORY_NOT_FOUND)

    old_content = memory.content

    # 更新MySQL
    memory.content = new_content
    memory.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    memory.source = "admin"
    await db.flush()

    # 生成新向量并更新DashVector
    try:
        new_embedding = await embedding_service.get_embedding(new_content)
        if new_embedding:
            await vector_service.upsert(
                memory_id=memory.id,
                embedding=new_embedding,
                metadata={
                    "user_id": user_id,
                    "content": new_content,
                    "importance_score": memory.importance_score,
                    "created_at": memory.created_at.isoformat() if memory.created_at else "",
                },
                memory_type=MEMORY_TYPE_USER,
            )
    except Exception as e:
        logger.error("更新记忆向量失败: memory_id=%d, error=%s", memory_id, str(e))

    # 写入操作日志
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="用户管理",
        action="edit",
        target_description=f"编辑用户{user_id}的记忆(ID:{memory_id})",
        before_value=old_content,
        after_value=new_content,
        request=request,
    )

    return ApiResponse.ok(message="记忆更新成功")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口六：DELETE /users/{user_id}/memories/{memory_id} 删除记忆
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.delete(
    "/users/{user_id}/memories/{memory_id}",
    dependencies=[require_role("super_admin", "ops_admin", "ai_trainer")],
)
async def delete_memory(
    user_id: int,
    memory_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除用户记忆（软删除）"""
    # 校验memory_id属于该user_id
    stmt = select(Memory).where(
        Memory.id == memory_id,
        Memory.user_id == user_id,
        Memory.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    memory = result.scalars().first()
    if not memory:
        return ApiResponse.fail(ADMIN_ERR_USER_MEMORY_NOT_FOUND)

    old_content = memory.content

    # MySQL软删除
    memory.is_deleted = True
    await db.flush()

    # 删除DashVector中的向量
    if memory.dashvector_id:
        try:
            await vector_service.delete(memory.dashvector_id)
        except Exception as e:
            logger.error("删除记忆向量失败: dashvector_id=%s, error=%s", memory.dashvector_id, str(e))

    # 写入操作日志
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="用户管理",
        action="delete",
        target_description=f"删除用户{user_id}的记忆(ID:{memory_id})",
        before_value=old_content,
        request=request,
    )

    return ApiResponse.ok(message="记忆已删除")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口七：PUT /users/{user_id}/status 禁用/启用账号
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.put(
    "/users/{user_id}/status",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def update_user_status(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """禁用/启用用户账号"""
    body = await request.json()
    action = body.get("action", "")
    if action not in ("ban", "unban"):
        return ApiResponse.fail(ADMIN_ERR_USER_STATUS_ACTION_INVALID)

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    redis = await get_redis()
    ban_key = f"user_banned:{user_id}"

    if action == "ban":
        if user.is_banned:
            return ApiResponse.fail(ADMIN_ERR_USER_ALREADY_BANNED)
        user.is_banned = True
        await db.flush()
        # Redis标记，TTL=100年
        await redis.setex(ban_key, 3153600000, "1")
        action_desc = "禁用"
    else:
        if not user.is_banned:
            return ApiResponse.fail(ADMIN_ERR_USER_NOT_BANNED)
        user.is_banned = False
        await db.flush()
        # 删除Redis标记
        await redis.delete(ban_key)
        action_desc = "启用"

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="用户管理",
        action="edit",
        target_description=f"{action_desc}用户{user.username}(ID:{user_id})",
        before_value="banned" if action == "unban" else "normal",
        after_value="normal" if action == "unban" else "banned",
        request=request,
    )

    return ApiResponse.ok(message=f"用户已{action_desc}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接口八：POST /users/{user_id}/reset-password 重置密码
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _generate_random_password(length: int = 8) -> str:
    """生成随机密码：至少含字母和数字"""
    letters = string.ascii_letters
    digits = string.digits
    # 保证至少1个字母和1个数字
    password_chars = [
        random.choice(letters),
        random.choice(digits),
    ]
    remaining = letters + digits
    password_chars.extend(random.choices(remaining, k=length - 2))
    random.shuffle(password_chars)
    return "".join(password_chars)


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def reset_user_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """重置用户密码"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    new_password = _generate_random_password()
    salt = bcrypt.gensalt()
    user.password_hash = bcrypt.hashpw(
        new_password.encode("utf-8"), salt
    ).decode("utf-8")
    await db.flush()

    # 清除该用户的登录Token
    try:
        redis = await get_redis()
        await redis.delete(f"token:{user_id}")
    except Exception as e:
        logger.warning("清除用户Token失败: user_id=%d, error=%s", user_id, str(e))

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="用户管理",
        action="edit",
        target_description=f"重置用户{user.username}(ID:{user_id})的密码",
        request=request,
    )

    return ApiResponse.ok(
        data={"new_password": new_password},
        message="密码重置成功",
    )
