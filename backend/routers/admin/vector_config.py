# -*- coding: utf-8 -*-
# 向量召回与 Prompt Token 热配置接口（admin_config 发布链路）

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID
from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.prompt_builder import MAX_TOTAL_TOKENS, MODULE_TOKEN_LIMITS
from backend.utils.admin_auth import get_current_admin, require_role

router = APIRouter()

_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")

_KEY_VECTOR = "vector_retrieval_config"
_KEY_PROMPT_TOKEN = "prompt_token_config"

# 与 multi_vector_retrieval_service 默认值对齐（R-L1L3-17）
_VECTOR_DEFAULTS = {"top_k": 3, "threshold": 0.7}
_VECTOR_TOP_K_MAX = 20


class VectorRetrievalPatch(BaseModel):
    """部分更新：仅提交需要修改的字段"""

    model_config = ConfigDict(extra="forbid")

    top_k: int | None = Field(default=None, ge=1, le=_VECTOR_TOP_K_MAX)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


def _vector_effective_from_db_row(raw: Any) -> dict[str, Any]:
    """将库中配置与默认值合并为完整向量召回配置"""
    merged = dict(_VECTOR_DEFAULTS)
    if isinstance(raw, dict):
        try:
            if "top_k" in raw:
                merged["top_k"] = int(raw["top_k"])
            if "threshold" in raw:
                merged["threshold"] = float(raw["threshold"])
        except (TypeError, ValueError):
            pass
    if merged["top_k"] < 1 or merged["top_k"] > _VECTOR_TOP_K_MAX:
        merged["top_k"] = _VECTOR_DEFAULTS["top_k"]
    if not (0.0 <= merged["threshold"] <= 1.0):
        merged["threshold"] = _VECTOR_DEFAULTS["threshold"]
    return merged


def _validate_vector_merged(merged: dict[str, Any]) -> str | None:
    """校验合并后的向量配置，失败返回错误文案"""
    tk = merged.get("top_k")
    th = merged.get("threshold")
    try:
        tk_i = int(tk)
        th_f = float(th)
    except (TypeError, ValueError):
        return "top_k 或 threshold 类型无效"
    if tk_i < 1 or tk_i > _VECTOR_TOP_K_MAX:
        return f"top_k 须在 1–{_VECTOR_TOP_K_MAX} 之间"
    if not (0.0 <= th_f <= 1.0):
        return "threshold 须在 0.0–1.0 之间"
    return None


class PromptTokenPatch(BaseModel):
    """部分更新：仅提交需要修改的模块上限或 max_total"""

    model_config = ConfigDict(extra="forbid")

    max_total: int | None = Field(default=None, ge=1, le=50000)
    system: int | None = Field(default=None, ge=1, le=20000)
    persona: int | None = Field(default=None, ge=1, le=20000)
    character_knowledge: int | None = Field(default=None, ge=1, le=20000)
    relationship: int | None = Field(default=None, ge=1, le=20000)
    memory: int | None = Field(default=None, ge=1, le=20000)
    emotion: int | None = Field(default=None, ge=1, le=20000)
    time_activity: int | None = Field(default=None, ge=1, le=20000)
    recent_chat: int | None = Field(default=None, ge=1, le=20000)
    user_input: int | None = Field(default=None, ge=1, le=20000)


def _prompt_hot_config_keys() -> tuple[str, ...]:
    """参与热配的模块键（user_nickname 固定 50，仅代码侧，C30）"""
    return tuple(k for k in MODULE_TOKEN_LIMITS if k != "user_nickname")


def _prompt_defaults_flat() -> dict[str, int]:
    """完整 Prompt Token 配置（供管理端展示与 PATCH，不含 user_nickname）"""
    out = {"max_total": MAX_TOTAL_TOKENS}
    for key in _prompt_hot_config_keys():
        out[key] = MODULE_TOKEN_LIMITS[key]
    return out


def _prompt_effective_from_db_row(raw: Any) -> dict[str, int]:
    merged = _prompt_defaults_flat()
    if isinstance(raw, dict):
        if "max_total" in raw:
            try:
                mt = int(raw["max_total"])
                if mt > 0:
                    merged["max_total"] = mt
            except (TypeError, ValueError):
                pass
        for key in _prompt_hot_config_keys():
            if key in raw:
                try:
                    v = int(raw[key])
                    if v > 0:
                        merged[key] = v
                except (TypeError, ValueError):
                    pass
    return merged


def _validate_prompt_merged(merged: dict[str, int]) -> str | None:
    if merged.get("max_total", 0) <= 0:
        return "max_total 须为正整数"
    for key in MODULE_TOKEN_LIMITS:
        if merged.get(key, 0) <= 0:
            return f"模块 {key} 的 Token 上限须为正整数"
    return None


def _patch_dict_exclude_none(model: BaseModel) -> dict[str, Any]:
    """提取 PATCH 中显式提供的非 None 字段"""
    raw = model.model_dump(exclude_unset=True)
    return {k: v for k, v in raw.items() if v is not None}


@router.get(
    "/vector_retrieval_config",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_vector_retrieval_config():
    """返回当前生效的向量召回配置（无库记录时与默认值合并后返回）"""
    raw = await admin_config_service.get_active_config(
        _KEY_VECTOR, use_cache=False,
    )
    data = _vector_effective_from_db_row(raw)
    return ApiResponse.ok(data=data)


@router.put(
    "/vector_retrieval_config",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def put_vector_retrieval_config(
    body: VectorRetrievalPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """
    部分字段 PATCH：与库中当前生效配置及默认值合并后整包发布。
    """
    patch = _patch_dict_exclude_none(body)
    if not patch:
        return ApiResponse.fail(
            ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID,
            message="请求体须至少包含一个待更新字段（top_k / threshold）",
        )

    raw = await admin_config_service.get_active_config(
        _KEY_VECTOR, use_cache=False,
    )
    merged = _vector_effective_from_db_row(raw)
    merged.update(patch)

    err = _validate_vector_merged(merged)
    if err:
        return ApiResponse.fail(
            ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID,
            message=err,
        )

    active_stmt = select(AdminConfig).where(
        AdminConfig.config_key == _KEY_VECTOR,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active_record = active_result.scalars().first()
    before_value = active_record.config_value if active_record else None

    config_value = json.dumps(merged, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key=_KEY_VECTOR,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"发布配置 {_KEY_VECTOR}",
    )
    return ApiResponse.ok(data=result)


@router.get(
    "/prompt_token_config",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_prompt_token_config():
    """返回当前生效的 Prompt Token 上限（无库记录时与代码默认合并）"""
    raw = await admin_config_service.get_active_config(
        _KEY_PROMPT_TOKEN, use_cache=False,
    )
    data = _prompt_effective_from_db_row(raw)
    return ApiResponse.ok(data=data)


@router.put(
    "/prompt_token_config",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def put_prompt_token_config(
    body: PromptTokenPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """部分字段 PATCH：与库中当前生效配置及默认值合并后整包发布。"""
    patch = _patch_dict_exclude_none(body)
    if not patch:
        return ApiResponse.fail(
            ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID,
            message="请求体须至少包含一个待更新字段（max_total 或各模块上限）",
        )

    raw = await admin_config_service.get_active_config(
        _KEY_PROMPT_TOKEN, use_cache=False,
    )
    merged = _prompt_effective_from_db_row(raw)
    for k, v in patch.items():
        merged[k] = int(v)

    err = _validate_prompt_merged(merged)
    if err:
        return ApiResponse.fail(
            ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID,
            message=err,
        )

    active_stmt = select(AdminConfig).where(
        AdminConfig.config_key == _KEY_PROMPT_TOKEN,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active_record = active_result.scalars().first()
    before_value = active_record.config_value if active_record else None

    config_value = json.dumps(merged, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key=_KEY_PROMPT_TOKEN,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"发布配置 {_KEY_PROMPT_TOKEN}",
    )
    return ApiResponse.ok(data=result)
