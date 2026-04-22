# -*- coding: utf-8 -*-
# Agent管理：Agent规则配置、主动消息规则、凌晨关键词、主动消息历史

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.agent_message import AgentMessage
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID,
    ADMIN_ERR_AGENT_RULE_PARAM_INVALID,
    ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID,
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_VALID_TRIGGER_TYPES = ("P0", "P1", "P2", "P3", "P4")


# ──────────────────── 请求模型 ────────────────────

class AgentRulesRequest(BaseModel):
    """完整的 agent_rules 结构"""
    triggers: dict
    decision_engine: dict


class AgentMessageRuleRequest(BaseModel):
    generation_requirements: str
    examples: list[str] = Field(..., min_length=3, max_length=5)
    max_length: int = Field(..., ge=20, le=100)


class NightKeywordsRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)


# ──────────────────── 1. Agent 规则配置 ────────────────────

@router.get(
    "/agent-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_agent_rules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的 Agent 触发规则"""
    config = await admin_config_service.get_active_config("agent_rules")
    return ApiResponse.ok(data=config)


@router.put(
    "/agent-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_agent_rules(
    body: AgentRulesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新 Agent 触发规则（直接发布）"""
    triggers = body.triggers
    decision = body.decision_engine

    # 校验 P2 规则
    p2 = triggers.get("P2", {})
    accumulation_days = p2.get("accumulation_days")
    habit_days_threshold = p2.get("habit_days_threshold")

    if accumulation_days is not None:
        if not (7 <= accumulation_days <= 30):
            return ApiResponse.fail(ADMIN_ERR_AGENT_RULE_PARAM_INVALID, message="P2 accumulation_days 必须在7-30之间")
    if habit_days_threshold is not None and accumulation_days is not None:
        if not (5 <= habit_days_threshold <= accumulation_days):
            return ApiResponse.fail(
                ADMIN_ERR_AGENT_RULE_PARAM_INVALID,
                message=f"P2 habit_days_threshold 必须在5到accumulation_days({accumulation_days})之间",
            )

    # 校验 decision_engine
    action_threshold = decision.get("action_threshold")
    if action_threshold is not None:
        if not (1 <= action_threshold <= 10):
            return ApiResponse.fail(ADMIN_ERR_AGENT_RULE_PARAM_INVALID, message="action_threshold 必须在1-10之间")

    daily_limit = decision.get("daily_limit")
    if daily_limit is not None:
        if not (1 <= daily_limit <= 5):
            return ApiResponse.fail(ADMIN_ERR_AGENT_RULE_PARAM_INVALID, message="daily_limit 必须在1-5之间")

    interval_hours = decision.get("interval_hours")
    if interval_hours is not None:
        if not (1 <= interval_hours <= 24):
            return ApiResponse.fail(ADMIN_ERR_AGENT_RULE_PARAM_INVALID, message="interval_hours 必须在1-24之间")

    # 获取当前配置作为 before_value
    current = await admin_config_service.get_active_config("agent_rules")
    before_value = json.dumps(current, ensure_ascii=False) if current else None

    config_data = body.model_dump()
    config_value = json.dumps(config_data, ensure_ascii=False)

    result = await admin_config_service.publish_config(
        db=db,
        config_key="agent_rules",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布Agent触发规则配置",
    )

    # 同时更新 Redis
    redis = await get_redis()
    await redis.setex("active_config:agent_rules", 3600, config_value)

    return ApiResponse.ok(data=result)


# ──────────────────── 2. 主动消息模板规则 ────────────────────

@router.get(
    "/agent-message-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_agent_message_rules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取主动消息模板规则"""
    config = await admin_config_service.get_active_config("agent_message_rules")
    return ApiResponse.ok(data=config)


@router.put(
    "/agent-message-rules/{trigger_type}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_agent_message_rule(
    trigger_type: str,
    body: AgentMessageRuleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新指定触发类型的主动消息模板规则"""
    if trigger_type not in _VALID_TRIGGER_TYPES:
        return ApiResponse.fail(ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID, message=f"trigger_type 必须为 {'/'.join(_VALID_TRIGGER_TYPES)} 之一")

    # 校验 examples 长度
    if not (3 <= len(body.examples) <= 5):
        return ApiResponse.fail(ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID, message="examples 数量必须为3-5条")

    # 校验 max_length
    if not (20 <= body.max_length <= 100):
        return ApiResponse.fail(ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID, message="max_length 范围为20-100")

    # 读取完整的 agent_message_rules
    current = await admin_config_service.get_active_config("agent_message_rules")
    if current is None:
        current = {}

    before_value = json.dumps(current, ensure_ascii=False) if current else None

    # 更新对应 trigger_type
    current[trigger_type] = body.model_dump()

    config_value = json.dumps(current, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key="agent_message_rules",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"发布Agent消息模板规则({trigger_type})",
    )
    return ApiResponse.ok(data=result)


# ──────────────────── 3. 凌晨关键词 ────────────────────

@router.get(
    "/agent-night-keywords",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_night_keywords(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取 P3 凌晨在线触发关键词（读 admin_config，不经 Redis）"""
    raw = await admin_config_service.get_active_config(
        "agent_night_keywords", use_cache=False,
    )
    if raw is None:
        data = {"keywords": []}
    elif isinstance(raw, list):
        data = {"keywords": raw}
    elif isinstance(raw, dict) and "keywords" in raw:
        data = {"keywords": raw.get("keywords") or []}
    else:
        data = {"keywords": []}
    return ApiResponse.ok(data=data)


@router.put(
    "/agent-night-keywords",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_night_keywords(
    body: NightKeywordsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新 P3 凌晨在线触发关键词"""
    current = await admin_config_service.get_active_config("agent_night_keywords")
    before_value = json.dumps(current, ensure_ascii=False) if current else None

    config_value = json.dumps(body.keywords, ensure_ascii=False)

    result = await admin_config_service.publish_config(
        db=db,
        config_key="agent_night_keywords",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布Agent凌晨关键词",
    )

    # 同时更新 Redis（agent_service 从此 key 读取）
    redis = await get_redis()
    await redis.setex("active_config:agent_night_keywords", 3600, config_value)
    # 兼容 agent_service 的读取 key
    await redis.set("agent:night_keywords", config_value)

    return ApiResponse.ok(data=result)


# ──────────────────── 4. 主动消息历史（额外开放给 ops_admin） ────────────────────

@router.get(
    "/agent-messages",
    dependencies=[require_role("super_admin", "ops_admin", "ai_trainer")],
)
async def get_agent_messages(
    user_id: Optional[int] = Query(None),
    trigger_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查询主动消息历史（分页）"""
    filters = []

    if user_id is not None:
        filters.append(AgentMessage.user_id == user_id)
    if trigger_type:
        if trigger_type not in _VALID_TRIGGER_TYPES:
            return ApiResponse.fail(ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID, message=f"trigger_type 必须为 {'/'.join(_VALID_TRIGGER_TYPES)} 之一")
        filters.append(AgentMessage.trigger_type == trigger_type)
    if is_read is not None:
        filters.append(AgentMessage.is_read == is_read)
    if start_date:
        try:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            filters.append(AgentMessage.created_at >= dt)
        except ValueError:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID, message="start_date 格式错误，应为 YYYY-MM-DD")
    if end_date:
        try:
            dt = datetime.strptime(end_date, "%Y-%m-%d")
            filters.append(AgentMessage.created_at < dt + timedelta(days=1))
        except ValueError:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID, message="end_date 格式错误，应为 YYYY-MM-DD")

    where_clause = and_(*filters) if filters else True

    # 总数
    count_stmt = select(func.count()).select_from(AgentMessage).where(where_clause)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    list_stmt = (
        select(AgentMessage)
        .where(where_clause)
        .order_by(AgentMessage.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(list_stmt)).scalars().all()

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": [
            {
                "id": msg.id,
                "user_id": msg.user_id,
                "trigger_type": msg.trigger_type,
                "content": msg.content,
                "action_score": msg.action_score,
                "is_read": msg.is_read,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in rows
        ],
    }
    return ApiResponse.ok(data=data)
