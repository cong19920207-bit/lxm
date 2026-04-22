# -*- coding: utf-8 -*-
# 关系成长与日记管理：关系规则配置、日记规则配置、日记历史查看

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_DIARY_RULE_PARAM_INVALID,
    ADMIN_ERR_RELATIONSHIP_RULE_INVALID,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.admin_diary_query import fetch_admin_diary_list_page
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")


# ──────────────────── 请求模型 ────────────────────

class RelationshipRulesRequest(BaseModel):
    """完整的关系规则结构"""
    levels: list[dict]
    growth_rules: list[dict]
    confirmed: bool = False


class DiaryRulesRequest(BaseModel):
    """日记规则：须同时提供双 Prompt，或仅提供旧字段 generation_prompt（二者择一）。"""
    max_length: int = Field(..., ge=50, le=300)
    frequency: str = "daily"
    generation_hour: int = Field(..., ge=0, le=5)
    generation_minute: int = Field(default=0, ge=0, le=59)
    generation_prompt: Optional[str] = None
    prompt_with_interaction: Optional[str] = None
    prompt_without_interaction: Optional[str] = None


# ──────────────────── 1. 关系等级规则 ────────────────────

@router.get(
    "/relationship-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_relationship_rules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的关系等级规则"""
    config = await admin_config_service.get_active_config("relationship_rules")
    return ApiResponse.ok(data=config)


@router.put(
    "/relationship-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_relationship_rules(
    body: RelationshipRulesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """
    更新关系等级规则。
    第一次请求（confirmed=false）：返回影响预览。
    第二次请求（confirmed=true）：正式发布并执行用户等级调整。
    """
    levels = body.levels
    growth_rules = body.growth_rules

    # 校验 levels 的 threshold 严格递增
    if len(levels) < 2:
        return ApiResponse.fail(ADMIN_ERR_RELATIONSHIP_RULE_INVALID, message="至少需要2个等级定义")

    # 第一个等级 threshold 必须为 0
    if levels[0].get("threshold", -1) != 0:
        return ApiResponse.fail(ADMIN_ERR_RELATIONSHIP_RULE_INVALID, message="0级的threshold必须为0")

    for i in range(1, len(levels)):
        prev_threshold = levels[i - 1].get("threshold", 0)
        curr_threshold = levels[i].get("threshold", 0)
        if curr_threshold <= prev_threshold:
            return ApiResponse.fail(
                ADMIN_ERR_RELATIONSHIP_RULE_INVALID,
                message=f"等级{i}的threshold({curr_threshold})必须严格大于等级{i-1}的threshold({prev_threshold})",
            )

    # 校验 growth_rules 的 points 和 daily_limit
    for rule in growth_rules:
        points = rule.get("points")
        daily_limit = rule.get("daily_limit")
        if points is not None and (not isinstance(points, int) or points <= 0):
            return ApiResponse.fail(ADMIN_ERR_RELATIONSHIP_RULE_INVALID, message=f"growth_rules 中 points 必须为正整数，当前值: {points}")
        if daily_limit is not None and (not isinstance(daily_limit, int) or daily_limit <= 0):
            return ApiResponse.fail(ADMIN_ERR_RELATIONSHIP_RULE_INVALID, message=f"growth_rules 中 daily_limit 必须为正整数，当前值: {daily_limit}")

    # 构建等级阈值映射（level_index → threshold）
    level_thresholds = {i: lv.get("threshold", 0) for i, lv in enumerate(levels)}
    max_level = len(levels) - 1

    def _calc_new_level(growth_value: int) -> int:
        """根据新阈值计算应处于的等级"""
        for lv in range(max_level, -1, -1):
            if growth_value >= level_thresholds.get(lv, 0):
                return lv
        return 0

    # 查询所有用户关系状态
    stmt = select(Relationship)
    result = await db.execute(stmt)
    all_relationships = result.scalars().all()

    # 计算影响用户
    upgrade_users = []  # 应升级的用户
    downgrade_users = []  # 应降级的用户

    for rel in all_relationships:
        new_level = _calc_new_level(rel.growth_value)
        if new_level > rel.level:
            upgrade_users.append({"user_id": rel.user_id, "current_level": rel.level, "new_level": new_level})
        elif new_level < rel.level:
            downgrade_users.append({"user_id": rel.user_id, "current_level": rel.level, "new_level": new_level})

    # 第一次请求：只返回预览
    if not body.confirmed:
        return ApiResponse.ok(data={
            "preview": True,
            "affected_upgrade_users": len(upgrade_users),
            "affected_downgrade_users": len(downgrade_users),
            "new_rules": {
                "levels": levels,
                "growth_rules": growth_rules,
            },
        })

    # ─── 第二次请求（confirmed=true）：正式发布 ───
    current = await admin_config_service.get_active_config("relationship_rules")
    before_value = json.dumps(current, ensure_ascii=False) if current else None

    config_data = {"levels": levels, "growth_rules": growth_rules}
    config_value = json.dumps(config_data, ensure_ascii=False)

    # 发布规则
    publish_result = await admin_config_service.publish_config(
        db=db,
        config_key="relationship_rules",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"发布关系等级规则 升级用户:{len(upgrade_users)} 降级用户:{len(downgrade_users)}",
    )

    redis = await get_redis()

    # 立即升级应升级的用户
    for u in upgrade_users:
        rel_stmt = select(Relationship).where(Relationship.user_id == u["user_id"])
        rel_result = await db.execute(rel_stmt)
        rel = rel_result.scalar_one_or_none()
        if rel:
            rel.level = u["new_level"]
            logger.info("规则变更升级用户 %d: %d → %d", u["user_id"], u["current_level"], u["new_level"])

    # 为应降级的用户设置 Redis 过渡期标记（7天）
    for u in downgrade_users:
        transition_key = f"relationship_transition:{u['user_id']}"
        await redis.setex(transition_key, 604800, str(u["new_level"]))
        logger.info("规则变更降级过渡期 用户 %d: %d → %d (7天后生效)", u["user_id"], u["current_level"], u["new_level"])

    await db.flush()

    return ApiResponse.ok(data={
        **publish_result,
        "upgraded_users": len(upgrade_users),
        "downgrade_transition_users": len(downgrade_users),
    })


# ──────────────────── 2. 日记规则 ────────────────────

@router.get(
    "/diary-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_diary_rules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的日记生成规则"""
    config = await admin_config_service.get_active_config("diary_rules")
    return ApiResponse.ok(data=config)


@router.put(
    "/diary-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_diary_rules(
    body: DiaryRulesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新日记生成规则（直接发布）"""
    # 校验 max_length
    if not (50 <= body.max_length <= 300):
        return ApiResponse.fail(ADMIN_ERR_DIARY_RULE_PARAM_INVALID, message="max_length 范围为50-300")

    # 校验 generation_hour
    if not (0 <= body.generation_hour <= 5):
        return ApiResponse.fail(ADMIN_ERR_DIARY_RULE_PARAM_INVALID, message="generation_hour 范围为0-5（凌晨生成）")

    if not (0 <= body.generation_minute <= 59):
        return ApiResponse.fail(ADMIN_ERR_DIARY_RULE_PARAM_INVALID, message="generation_minute 范围为0-59")

    pwi = (body.prompt_with_interaction or "").strip()
    pwo = (body.prompt_without_interaction or "").strip()
    leg = (body.generation_prompt or "").strip()
    if pwi and pwo:
        payload: dict = {
            "prompt_with_interaction": pwi,
            "prompt_without_interaction": pwo,
            "max_length": body.max_length,
            "frequency": body.frequency,
            "generation_hour": body.generation_hour,
            "generation_minute": body.generation_minute,
        }
    elif leg:
        payload = {
            "generation_prompt": leg,
            "prompt_with_interaction": leg,
            "prompt_without_interaction": leg,
            "max_length": body.max_length,
            "frequency": body.frequency,
            "generation_hour": body.generation_hour,
            "generation_minute": body.generation_minute,
        }
    else:
        return ApiResponse.fail(
            ADMIN_ERR_DIARY_RULE_PARAM_INVALID,
            message="须同时填写 prompt_with_interaction 与 prompt_without_interaction，或填写兼容字段 generation_prompt",
        )

    current = await admin_config_service.get_active_config("diary_rules")
    before_value = json.dumps(current, ensure_ascii=False) if current else None

    config_value = json.dumps(payload, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key="diary_rules",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布日记生成规则",
    )
    return ApiResponse.ok(data=result)


# ──────────────────── 3. 日记历史（额外开放给 ops_admin） ────────────────────

@router.get(
    "/diary-history",
    dependencies=[require_role("super_admin", "ops_admin")],
)
async def get_diary_history(
    user_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查看 AI 日记历史（只读）；列表查询与 users/{id}/diaries 共用逻辑"""
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
