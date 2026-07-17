# -*- coding: utf-8 -*-
# 生活流·通用 admin_config 读写 API（后台 UI STEP-030/032/033/036 的配置后端支撑）
#
# 面向生活流 config_key 白名单，提供：批量读（active+draft）、保存草稿、发布（三卡点之发布环节）、丢弃草稿。
# 前缀 /api/admin，权限 super_admin / ai_trainer；发布/草稿写操作全落 operation_log。
# 说明：白名单动态汇总自 life_feed_config / life_feed_prompts / DEEPSEEK_MODEL_* / 动态延迟键，
#       防止越权写入非生活流配置项。

import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
    ADMIN_ERR_LIFE_PARAM_INVALID,
    DEEPSEEK_NODE_MODEL_CONFIG_KEYS,
)
from backend.constants import life_feed_config as lfc
from backend.constants.life_feed_config import RELATIONSHIP_STAGES
from backend.constants.life_feed_prompts import IMAGE_MAP_SEED, PROMPT_SEED
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_READ_ROLES = ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer")  # ops/observer 只读


def _build_whitelist() -> set[str]:
    """动态汇总生活流可写 config_key 白名单。"""
    keys: set[str] = set()
    # 1. life_feed_config 内所有 CONFIG_* 字符串常量
    for name in dir(lfc):
        if name.startswith("CONFIG_"):
            val = getattr(lfc, name)
            if isinstance(val, str):
                keys.add(val)
    # 2. 生活节奏比例（life_plan_mgmt 使用）
    keys.update({"life_ratio_local", "life_ratio_short_trip", "life_ratio_long_trip"})
    # 3. 四关系档动态延迟键
    for stage in RELATIONSHIP_STAGES:
        for bound in ("min", "max"):
            keys.add(lfc.comment_reply_delay_key(stage, bound))
            keys.add(lfc.like_regular_delay_key(stage, bound))
            keys.add(lfc.read_regular_delay_key(stage, bound))
    # 4. Prompt 模板 + 图像映射表
    keys.update(PROMPT_SEED.keys())
    keys.update(IMAGE_MAP_SEED.keys())
    # 5. DeepSeek 各节点模型版本
    keys.update(DEEPSEEK_NODE_MODEL_CONFIG_KEYS.values())
    return keys


_WHITELIST = _build_whitelist()


def _serialize(value) -> str:
    """将任意 JSON 值序列化为库存字符串；纯字符串按原样存（与 get_active_config 解析约定一致）。"""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


@router.get("/life-config", dependencies=[require_role(*_READ_ROLES)])
async def get_life_configs(
    keys: str = Query(..., description="逗号分隔的 config_key 列表"),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """批量读取生效值 + 草稿（供 UI 展示）。返回 {key: {active, draft, has_draft}}。"""
    key_list = [k.strip() for k in keys.split(",") if k.strip()]
    invalid = [k for k in key_list if k not in _WHITELIST]
    if invalid:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                message=f"非法 config_key：{', '.join(invalid[:5])}")
    result = {}
    for k in key_list:
        active = await admin_config_service.get_active_config(k, use_cache=False)
        draft = await admin_config_service.get_draft(k)
        result[k] = {
            "active": active,
            "draft": draft.get("config_value") if draft else None,
            "has_draft": draft is not None,
        }
    return ApiResponse.ok(data=result)


class DraftBody(BaseModel):
    config_key: str
    config_value: object


@router.put("/life-config/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def save_life_config_draft(
    body: DraftBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """保存草稿（不发布，不更新 Redis）。"""
    if body.config_key not in _WHITELIST:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="非法 config_key")
    stored = _serialize(body.config_value)
    res = await admin_config_service.save_draft(db, body.config_key, stored, admin_user.username)
    await log_operation(db, admin_user, "life_config", "save_draft",
                        f"保存草稿 {body.config_key}", request=request)
    await db.commit()
    return ApiResponse.ok(data=res)


@router.delete("/life-config/draft/{config_key}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def discard_life_config_draft(
    config_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """丢弃草稿。"""
    if config_key not in _WHITELIST:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="非法 config_key")
    ok = await admin_config_service.discard_draft(db, config_key)
    await log_operation(db, admin_user, "life_config", "discard_draft",
                        f"丢弃草稿 {config_key}", request=request)
    await db.commit()
    return ApiResponse.ok(data={"discarded": ok})


class PublishBody(BaseModel):
    config_key: str
    config_value: object
    confirm_text: str | None = None


@router.post("/life-config/publish", dependencies=[require_role(*_ALLOWED_ROLES)])
async def publish_life_config(
    body: PublishBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """发布配置（旧版本失活→新活跃版本→删草稿→更新 Redis→5min 监控标记；含 operation_log）。"""
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID)
    if body.config_key not in _WHITELIST:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="非法 config_key")
    stored = _serialize(body.config_value)
    before = await admin_config_service.get_active_config(body.config_key, use_cache=False)
    before_str = _serialize(before) if before is not None else None
    res = await admin_config_service.publish_config(
        db, body.config_key, stored, admin_user,
        before_value=before_str, request=request,
        target_description=f"发布生活流配置 {body.config_key}")
    await db.commit()
    return ApiResponse.ok(data=res)
