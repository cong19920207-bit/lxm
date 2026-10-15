# -*- coding: utf-8 -*-
"""Versioned hybrid retrieval and Prompt budget configuration."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services import memory_config_publication as publications
from backend.services.memory_config_schema import (
    PROMPT_DEFAULTS, PROMPT_KEYS, PromptTokenPatch, VectorRetrievalPatch,
    merge_prompt, merge_vector, prompt_effective, vector_effective,
)
from backend.utils.admin_auth import get_current_admin, require_role

router = APIRouter()
_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")
_KEY_VECTOR = "vector_retrieval_config"
_KEY_PROMPT_TOKEN = "prompt_token_config"


def _server_time():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prompt_hot_config_keys():
    return tuple(key for key in PROMPT_KEYS if key != "max_total")


def _prompt_defaults_flat():
    return dict(PROMPT_DEFAULTS)


_prompt_effective_from_db_row = prompt_effective
_vector_effective_from_db_row = vector_effective


def _validate_prompt_merged(merged):
    try:
        prompt_effective(merged)
    except ValueError:
        return "Token 预算无效"
    return None


def _validate_vector_merged(merged):
    try:
        vector_effective(merged)
    except ValueError:
        return "混合召回配置无效"
    return None


async def _get_config(db, key, validate):
    try:
        stored = await publications.read(db, key)
        data = validate(stored["raw"])
        data.update(version=stored["version"], source=stored["source"], server_time=_server_time())
        if key == _KEY_VECTOR:
            data.setdefault("legacy", {"top_k": 3, "threshold": 0.7})
        return ApiResponse.ok(data=data)
    except publications.PublicationError as exc:
        return ApiResponse.fail(exc.code, message=exc.reason)
    except ValueError:
        return ApiResponse.fail(ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID, message="已发布配置不完整或无效")


async def _publish_config(body, request, db, admin, key, merge):
    patch = body.model_dump(exclude_unset=True)
    if not patch or (key == _KEY_VECTOR and not any(patch.get("routes", {}).values())):
        return ApiResponse.fail(ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID, message="须至少提交一个可编辑参数")
    try:
        publish_id = publications.get_or_create_publish_id(request.headers.get("Idempotency-Key"))
    except (ValueError, publications.PublicationError):
        raise HTTPException(422, detail="Idempotency-Key 须为规范 UUIDv7") from None
    try:
        result = await publications.publish(
            db, key, patch, admin.id, publish_id, merge,
            source_entry=request.url.path,
        )
        result["server_time"] = _server_time()
        if result["commit_state"] == "committed":
            return ApiResponse.ok(data=result)
        code = {"expired": 20123, "rejected": ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID}.get(result["commit_state"], 20122)
        if result.get("reason") == "publication_revision_conflict":
            code = 20127
        return ApiResponse.fail(code, data=result, message="配置发布未确认" if code == 20122 else "配置未发布")
    except publications.PublicationError as exc:
        return ApiResponse.fail(exc.code, message=exc.reason)
    except ValueError:
        return ApiResponse.fail(ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID, message="配置字段或组合范围无效")


@router.get("/vector_retrieval_config", dependencies=[require_role(*_READ_ROLES)])
async def get_vector_retrieval_config(db: AsyncSession = Depends(get_db)):
    return await _get_config(db, _KEY_VECTOR, vector_effective)


@router.put("/vector_retrieval_config", dependencies=[require_role(*_WRITE_ROLES)])
async def put_vector_retrieval_config(body: VectorRetrievalPatch, request: Request,
                                     db: AsyncSession = Depends(get_db),
                                     admin_user: AdminUser = Depends(get_current_admin)):
    return await _publish_config(body, request, db, admin_user, _KEY_VECTOR, merge_vector)


@router.get("/prompt_token_config", dependencies=[require_role(*_READ_ROLES)])
async def get_prompt_token_config(db: AsyncSession = Depends(get_db)):
    return await _get_config(db, _KEY_PROMPT_TOKEN, prompt_effective)


@router.put("/prompt_token_config", dependencies=[require_role(*_WRITE_ROLES)])
async def put_prompt_token_config(body: PromptTokenPatch, request: Request,
                                 db: AsyncSession = Depends(get_db),
                                 admin_user: AdminUser = Depends(get_current_admin)):
    return await _publish_config(body, request, db, admin_user, _KEY_PROMPT_TOKEN, merge_prompt)


@router.get("/publications/{publish_id}")
async def get_publication(publish_id: str, db: AsyncSession = Depends(get_db),
                          admin_user: AdminUser = Depends(get_current_admin)):
    try:
        publications.get_or_create_publish_id(publish_id)
    except (ValueError, publications.PublicationError):
        raise HTTPException(422, detail="publish_id 须为规范 UUIDv7") from None
    try:
        result = await publications.get_receipt(db, admin_user.id, publish_id)
    except publications.PublicationError as exc:
        return ApiResponse.fail(exc.code, message=exc.reason)
    if result is None:
        return ApiResponse.fail(20125, message="无可核实的本次发布记录", data={"publish_id": publish_id, "server_time": _server_time()})
    entry = result.get("source_entry", "")
    allowed = ("super_admin", "tech_ops", "observer") if "third-party" in entry else _READ_ROLES
    if admin_user.role not in allowed:
        raise HTTPException(403, detail="无原配置入口读取权限")
    result["server_time"] = _server_time()
    if result["commit_state"] == "expired":
        return ApiResponse.fail(20123, message="本次发布回执已过保障期", data=result)
    if result["commit_state"] in {"pending", "unknown"}:
        return ApiResponse.fail(20122, message="本次发布结果待核实", data=result)
    return ApiResponse.ok(data=result)
