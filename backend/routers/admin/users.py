# -*- coding: utf-8 -*-
# 后台用户管理：列表/详情/对话/记忆/状态/重置密码

import logging
import random
import string
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import bcrypt
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.constants import (
    ADMIN_ERR_USER_ALREADY_BANNED,
    ADMIN_ERR_USER_NOT_BANNED,
    ADMIN_ERR_USER_NOT_FOUND,
    ADMIN_ERR_USER_STATUS_ACTION_INVALID,
    ADMIN_ERROR_MESSAGES,
    MEMORY_TYPE_CHARACTER_PRIVATE,
    MEMORY_TYPE_USER,
)
from backend.redis_client import get_redis
from backend.schemas.common import ApiResponse
from backend.services.admin_date_filter import append_created_at_range, parse_admin_date_range
from backend.services.admin_diary_query import fetch_admin_diary_list_page
from backend.services.open_api_key_service import get_key_status, upsert_api_key
from backend.services.user_vector_memory_service import user_vector_memory_service
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
    """查看用户历史对话记录（只读）：合并 conversation_log 与 agent_message，按 sort_seq 与用户端时间线一致。"""
    # 检查用户是否存在
    user_stmt = select(User.id).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    if not user_result.scalar():
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    start_dt, end_exclusive, date_err = parse_admin_date_range(start_date, end_date)
    if date_err is not None:
        return date_err

    conv_filters = [ConversationLog.user_id == user_id]
    agent_filters = [AgentMessage.user_id == user_id]
    append_created_at_range(conv_filters, ConversationLog.created_at, start_dt, end_exclusive)
    append_created_at_range(agent_filters, AgentMessage.created_at, start_dt, end_exclusive)

    count_conv_stmt = select(func.count()).select_from(ConversationLog).where(*conv_filters)
    count_agent_stmt = select(func.count()).select_from(AgentMessage).where(*agent_filters)
    total = (
        (await db.execute(count_conv_stmt)).scalar() or 0
    ) + ((await db.execute(count_agent_stmt)).scalar() or 0)

    conv_keys = (
        select(
            ConversationLog.sort_seq,
            ConversationLog.id,
            literal("conversation").label("message_source"),
        )
        .where(*conv_filters)
    )
    agent_keys = (
        select(
            AgentMessage.sort_seq,
            AgentMessage.id,
            literal("agent").label("message_source"),
        )
        .where(*agent_filters)
    )
    union_keys = union_all(conv_keys, agent_keys).subquery("admin_timeline_keys")
    page_stmt = (
        select(
            union_keys.c.sort_seq,
            union_keys.c.id,
            union_keys.c.message_source,
        )
        .select_from(union_keys)
        .order_by(union_keys.c.sort_seq.asc(), union_keys.c.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    page_result = await db.execute(page_stmt)
    page_rows = list(page_result.all())

    conv_ids = [r.id for r in page_rows if r.message_source == "conversation"]
    agent_ids = [r.id for r in page_rows if r.message_source == "agent"]

    conv_by_id: dict[int, ConversationLog] = {}
    if conv_ids:
        conv_q = await db.execute(select(ConversationLog).where(ConversationLog.id.in_(conv_ids)))
        for row in conv_q.scalars():
            conv_by_id[row.id] = row

    agent_by_id: dict[int, AgentMessage] = {}
    if agent_ids:
        agent_q = await db.execute(select(AgentMessage).where(AgentMessage.id.in_(agent_ids)))
        for row in agent_q.scalars():
            agent_by_id[row.id] = row

    row_list: list[dict] = []
    for pr in page_rows:
        if pr.message_source == "conversation":
            row = conv_by_id.get(pr.id)
            if row is None:
                continue
            if row.role == "assistant":
                delivery_status = None
                skipped_in_prompt = None
            else:
                delivery_status = row.delivery_status
                skipped_in_prompt = bool(row.skipped_in_prompt)

            row_list.append(
                {
                    "id": row.id,
                    "message_source": "conversation",
                    "role": row.role,
                    "content": row.content,
                    "emotion_label": row.emotion_label if row.role == "user" else None,
                    "emotion_confidence": row.emotion_confidence if row.role == "user" else None,
                    "persona_risk_flag": row.persona_risk_flag,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "sort_seq": row.sort_seq,
                    "delivery_status": delivery_status,
                    "skipped_in_prompt": skipped_in_prompt,
                    "trigger_type": None,
                    "is_read": None,
                }
            )
        else:
            am = agent_by_id.get(pr.id)
            if am is None:
                continue
            row_list.append(
                {
                    "id": am.id,
                    "message_source": "agent",
                    "role": "assistant",
                    "content": am.content,
                    "emotion_label": None,
                    "emotion_confidence": None,
                    "persona_risk_flag": False,
                    "created_at": am.created_at.isoformat() if am.created_at else None,
                    "sort_seq": am.sort_seq,
                    "delivery_status": None,
                    "skipped_in_prompt": None,
                    "trigger_type": am.trigger_type,
                    "is_read": am.is_read,
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

    start_dt, end_exclusive, date_err = parse_admin_date_range(start_date, end_date)
    if date_err is not None:
        return date_err

    filters = [EmotionLog.user_id == user_id]
    append_created_at_range(filters, EmotionLog.created_at, start_dt, end_exclusive)

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
# 接口四：用户记忆（user）/ 私有状态（character_private）DashVector CRUD（C-01/C-09）
# 旧 MySQL `/users/{id}/memories*`（接口四/五/六）已删除，统一改为 Step6 向量读写。
# 权限：super_admin + ops_admin + ai_trainer（P5）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_USER_MEMORY_ROLES = ("super_admin", "ops_admin", "ai_trainer")


class UserMemoryCreateRequest(BaseModel):
    """新增用户记忆 / 私有状态条目（三层 key + value）。"""
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class UserMemoryUpdateRequest(BaseModel):
    """仅改 value（C-03，改 key 走 DELETE + POST）。"""
    value: str = Field(..., min_length=1)


def _fail_from_user_memory_service(result: dict):
    code = result.get("error_code")
    message = result.get("message") or ADMIN_ERROR_MESSAGES.get(code, "操作失败")
    return ApiResponse.fail(code, message=message)


async def _ensure_user_exists(db: AsyncSession, user_id: int) -> bool:
    user_result = await db.execute(select(User.id).where(User.id == user_id))
    return user_result.scalar() is not None


async def _list_user_vectors(
    user_id: int,
    memory_type: str,
    keyword: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
):
    if not await _ensure_user_exists(db, user_id):
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)
    result = await user_vector_memory_service.list_entries(
        memory_type=memory_type,
        user_id=user_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    if "error_code" in result:
        return _fail_from_user_memory_service(result)
    return ApiResponse.ok(data=result)


async def _create_user_vector(
    user_id: int,
    memory_type: str,
    module: str,
    body: UserMemoryCreateRequest,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    result = await user_vector_memory_service.create_entry(
        memory_type=memory_type,
        user_id=user_id,
        key=body.key.strip(),
        value=body.value.strip(),
    )
    if "error_code" in result:
        return _fail_from_user_memory_service(result)
    entry = result["data"]
    await log_operation(
        db=db,
        admin_user=admin_user,
        module=module,
        action="create",
        target_description=f"新增用户{user_id}的{module} key={entry['key']}",
        after_value=entry.get("content"),
        request=request,
    )
    return ApiResponse.ok(data=entry)


async def _update_user_vector(
    user_id: int,
    memory_type: str,
    module: str,
    doc_id: str,
    body: UserMemoryUpdateRequest,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    doc_id = unquote(doc_id)
    result = await user_vector_memory_service.update_entry(
        memory_type=memory_type,
        user_id=user_id,
        doc_id=doc_id,
        value=body.value.strip(),
    )
    if "error_code" in result:
        return _fail_from_user_memory_service(result)
    entry = result["data"]
    await log_operation(
        db=db,
        admin_user=admin_user,
        module=module,
        action="update",
        target_description=f"更新用户{user_id}的{module} key={entry['key']}",
        after_value=entry.get("content"),
        request=request,
    )
    return ApiResponse.ok(data=entry)


async def _delete_user_vector(
    user_id: int,
    memory_type: str,
    module: str,
    doc_id: str,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    doc_id = unquote(doc_id)
    result = await user_vector_memory_service.delete_entry(
        memory_type=memory_type,
        user_id=user_id,
        doc_id=doc_id,
    )
    if "error_code" in result:
        return _fail_from_user_memory_service(result)
    await log_operation(
        db=db,
        admin_user=admin_user,
        module=module,
        action="delete",
        target_description=f"删除用户{user_id}的{module} doc_id={doc_id}",
        request=request,
    )
    return ApiResponse.ok(data=result["data"])


# ---------- user-memories（type=user）----------
@router.get(
    "/users/{user_id}/user-memories",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def list_user_memories(
    user_id: int,
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """用户记忆列表（Step6 user 向量，cap=500）。"""
    return await _list_user_vectors(
        user_id, MEMORY_TYPE_USER, keyword, page, page_size, db,
    )


@router.post(
    "/users/{user_id}/user-memories",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def create_user_memory(
    user_id: int,
    body: UserMemoryCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """新增用户记忆条目（三层 key + value）。"""
    return await _create_user_vector(
        user_id, MEMORY_TYPE_USER, "user_memory", body, request, db, admin_user,
    )


@router.put(
    "/users/{user_id}/user-memories/{doc_id:path}",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def update_user_memory(
    user_id: int,
    doc_id: str,
    body: UserMemoryUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑用户记忆 value（key 不可改）。"""
    return await _update_user_vector(
        user_id, MEMORY_TYPE_USER, "user_memory", doc_id, body, request, db, admin_user,
    )


@router.delete(
    "/users/{user_id}/user-memories/{doc_id:path}",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def delete_user_memory(
    user_id: int,
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除用户记忆条目。"""
    return await _delete_user_vector(
        user_id, MEMORY_TYPE_USER, "user_memory", doc_id, request, db, admin_user,
    )


# ---------- private-settings（type=character_private）----------
@router.get(
    "/users/{user_id}/private-settings",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def list_private_settings(
    user_id: int,
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """私有状态列表（角色对该用户的私有设定，cap=500）。"""
    return await _list_user_vectors(
        user_id, MEMORY_TYPE_CHARACTER_PRIVATE, keyword, page, page_size, db,
    )


@router.post(
    "/users/{user_id}/private-settings",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def create_private_setting(
    user_id: int,
    body: UserMemoryCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """新增私有状态条目（三层 key + value）。"""
    return await _create_user_vector(
        user_id, MEMORY_TYPE_CHARACTER_PRIVATE, "private_setting", body, request, db, admin_user,
    )


@router.put(
    "/users/{user_id}/private-settings/{doc_id:path}",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def update_private_setting(
    user_id: int,
    doc_id: str,
    body: UserMemoryUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑私有状态 value（key 不可改）。"""
    return await _update_user_vector(
        user_id, MEMORY_TYPE_CHARACTER_PRIVATE, "private_setting", doc_id, body, request, db, admin_user,
    )


@router.delete(
    "/users/{user_id}/private-settings/{doc_id:path}",
    dependencies=[require_role(*_USER_MEMORY_ROLES)],
)
async def delete_private_setting(
    user_id: int,
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除私有状态条目。"""
    return await _delete_user_vector(
        user_id, MEMORY_TYPE_CHARACTER_PRIVATE, "private_setting", doc_id, request, db, admin_user,
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
# Open API Key：GET/POST /users/{user_id}/open-api-key
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get(
    "/users/{user_id}/open-api-key",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def get_user_open_api_key(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)
    status = await get_key_status(db, user_id)
    if status is None:
        return ApiResponse.ok(data={"enabled": False})
    return ApiResponse.ok(data=status)


@router.post(
    "/users/{user_id}/open-api-key",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def create_or_regenerate_open_api_key(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    try:
        api_key, is_create, old_prefix = await upsert_api_key(db, user_id, admin_user.id)
    except ValueError:
        return ApiResponse.fail(ADMIN_ERR_USER_NOT_FOUND)

    status = await get_key_status(db, user_id)

    if is_create:
        await log_operation(
            db=db,
            admin_user=admin_user,
            module="用户管理",
            action="create",
            target_description=(
                f"为用户 {user.username}(ID:{user_id}) 生成 Open API Key，前缀 {status['key_prefix']}"
            ),
            request=request,
        )
    else:
        await log_operation(
            db=db,
            admin_user=admin_user,
            module="用户管理",
            action="edit",
            target_description=f"重新生成用户 {user.username}(ID:{user_id}) 的 Open API Key",
            before_value=old_prefix,
            after_value=status["key_prefix"],
            request=request,
        )

    await db.commit()

    return ApiResponse.ok(
        data={
            "api_key": api_key,
            "key_prefix": status["key_prefix"],
            "created_at": status["created_at"],
        },
        message="API Key 已生成，请立即复制保存，关闭后无法再次查看",
    )


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
