# -*- coding: utf-8 -*-
"""实时语音两套整包配置管理 API（P1 M1 STEP-005）。"""

from __future__ import annotations

import logging
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
    ADMIN_ERR_VOICE_CONFIG_CONFLICT,
    ADMIN_ERR_VOICE_CONFIG_CREDENTIAL_MISSING,
    ADMIN_ERR_VOICE_CONFIG_INVALID,
    ADMIN_ERR_VOICE_CONFIG_NO_DRAFT,
    ADMIN_ERR_VOICE_CONFIG_NOT_FOUND,
    ADMIN_ERR_VOICE_CONFIG_PERSONA_REQUIRED,
    ADMIN_ERR_VOICE_CONFIG_PUBLISH_FAILED,
    ADMIN_ERR_VOICE_CRISIS_KEYWORDS_INVALID,
)
from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    VOICE_CALL_SCRIPT_KEY,
)
from backend.database import get_db
from backend.redis_client import get_redis
from backend.routers.admin.voice_playback import capability_stream,audit_session_factory
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.schemas.realtime_voice_config import (
    VoiceCapabilityTestRequest,
    VoiceConnectionTestRequest,
    VoiceDraftSectionRequest,
    VoiceForceTestRequest,
    VoicePublishRequest,
    VoiceRollbackRequest,
    VoiceValidateRequest,
)
from backend.services.realtime_voice_admin_test_service import (
    VoiceTestRunnerPort,
    get_voice_test_runner,
    realtime_voice_admin_test_service,
)
from backend.services.realtime_voice_capability_service import (
    CAPABILITY_EVIDENCE_NOT_FOUND,
    realtime_voice_capability_service,
)
from backend.services.realtime_voice_config_service import (
    CRISIS_KEYWORDS_EMPTY,
    VOICE_CONFIG_BASE_VERSION_CONFLICT,
    VOICE_CONFIG_CREDENTIAL_MISSING,
    VOICE_CONFIG_NO_DRAFT,
    VOICE_CONFIG_PERSONA_REQUIRED,
    VOICE_CONFIG_REVISION_CONFLICT,
    VOICE_CONFIG_VERSION_NOT_FOUND,
    VoiceConfigError,
    realtime_voice_config_service,
)
from backend.utils.admin_auth import get_current_admin, require_role


logger = logging.getLogger(__name__)

router = APIRouter()

_READ_ROLES = ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer")
_CONFIG_WRITE_ROLES = ("super_admin", "tech_ops")
_SCRIPT_WRITE_ROLES = ("super_admin", "ai_trainer")
_VOICE_CONFIG_TEST_ROLES = ("super_admin", "tech_ops")
_VOICE_CONFIG_FORCE_TEST_ENTRY_ROLES = _READ_ROLES


def _business_error_code(exc: VoiceConfigError) -> int:
    if exc.code in {VOICE_CONFIG_BASE_VERSION_CONFLICT, VOICE_CONFIG_REVISION_CONFLICT}:
        return ADMIN_ERR_VOICE_CONFIG_CONFLICT
    if exc.code == VOICE_CONFIG_NO_DRAFT:
        return ADMIN_ERR_VOICE_CONFIG_NO_DRAFT
    if exc.code == VOICE_CONFIG_VERSION_NOT_FOUND:
        return ADMIN_ERR_VOICE_CONFIG_NOT_FOUND
    if exc.code == VOICE_CONFIG_CREDENTIAL_MISSING:
        return ADMIN_ERR_VOICE_CONFIG_CREDENTIAL_MISSING
    if exc.code == VOICE_CONFIG_PERSONA_REQUIRED:
        return ADMIN_ERR_VOICE_CONFIG_PERSONA_REQUIRED
    if exc.code == CRISIS_KEYWORDS_EMPTY:
        return ADMIN_ERR_VOICE_CRISIS_KEYWORDS_INVALID
    if exc.code == "VOICE_CONFIG_CONFIRM_TEXT_INVALID":
        return ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID
    return ADMIN_ERR_VOICE_CONFIG_INVALID


def _voice_error_response(exc: VoiceConfigError) -> JSONResponse:
    payload = ApiResponse.fail(
        _business_error_code(exc),
        message=exc.message,
        data={"error_code": exc.code, "errors": exc.errors},
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


def _publish_failure_response() -> JSONResponse:
    payload = ApiResponse.fail(ADMIN_ERR_VOICE_CONFIG_PUBLISH_FAILED)
    return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))


async def _connection_test_body(request: Request) -> VoiceConnectionTestRequest:
    """Distinguish an omitted body from explicit JSON null before runner creation."""

    raw = await request.body()
    if not raw:
        return VoiceConnectionTestRequest()
    try:
        value = json.loads(raw)
        return VoiceConnectionTestRequest.model_validate(value)
    except (json.JSONDecodeError, ValidationError) as exc:
        errors = exc.errors() if isinstance(exc, ValidationError) else [
            {
                "type": "json_invalid",
                "loc": ("body",),
                "msg": "JSON body invalid",
                "input": None,
            }
        ]
        raise RequestValidationError(errors, body=raw.decode("utf-8", "replace")) from exc


async def _save_section(
    *,
    config_key: str,
    section: str,
    body: VoiceDraftSectionRequest,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    try:
        result = await realtime_voice_config_service.save_draft_section(
            db,
            config_key=config_key,
            section=section,
            base_version=body.base_version,
            draft_revision=body.draft_revision,
            content=body.content,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


async def _discard_section(
    *,
    config_key: str,
    section: str,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    try:
        result = await realtime_voice_config_service.discard_draft_section(
            db,
            config_key=config_key,
            section=section,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


async def _discard_all(
    *,
    config_key: str,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    try:
        result = await realtime_voice_config_service.discard_draft(
            db,
            config_key=config_key,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


async def _validate(
    *,
    config_key: str,
    body: VoiceValidateRequest,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    preview = body.followup_preview
    if "followup_preview" in body.model_fields_set and preview is None:
        # 显式 null 不是文档定义的可选对象；保留省略字段时的“只校验”语义。
        preview = {}
    try:
        result = await realtime_voice_config_service.validate_current(
            db,
            config_key=config_key,
            preview=preview,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


async def _publish(
    *,
    config_key: str,
    body: VoicePublishRequest,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    try:
        result = await realtime_voice_config_service.publish(
            db,
            config_key=config_key,
            confirm_text=body.confirm_text,
            change_note=body.change_note.strip(),
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    except Exception:
        # 上游异常文本可能夹带 Provider 原文或 Secret；这里只记
        # 固定分类与非敏感 config_key，不记异常对象/堆栈。
        logger.error("发布语音配置失败，已执行补偿: %s", config_key)
        return _publish_failure_response()
    return ApiResponse.ok(data=result)


async def _rollback(
    *,
    config_key: str,
    body: VoiceRollbackRequest,
    request: Request,
    db: AsyncSession,
    admin_user: AdminUser,
):
    try:
        result = await realtime_voice_config_service.rollback(
            db,
            config_key=config_key,
            version=body.version,
            confirm_text=body.confirm_text,
            change_note=body.change_note.strip(),
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    except Exception:
        # 与发布失败保持同一脱敏边界，避免 exception traceback
        # 把凭据或上游敏感原文写入普通日志。
        logger.error("回滚语音配置失败，已执行补偿: %s", config_key)
        return _publish_failure_response()
    return ApiResponse.ok(data=result)


@router.post(
    "/config/test-connection",
    dependencies=[require_role(*_VOICE_CONFIG_TEST_ROLES)],
)
async def test_voice_connection(
    request: Request,
    body: VoiceConnectionTestRequest = Depends(_connection_test_body),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
    runner: VoiceTestRunnerPort = Depends(get_voice_test_runner),
):
    # The empty strict model exists solely to reject caller-side Provider
    # overrides; all test parameters come from the frozen draft snapshot.
    del body
    data = await realtime_voice_admin_test_service.test_connection(
        db,
        runner=runner,
        admin_user=admin_user,
        request=request,
    )
    return ApiResponse.ok(data=data.model_dump(mode="json"))


@router.post(
    "/config/test-capability",
    dependencies=[require_role(*_VOICE_CONFIG_TEST_ROLES)],
)
async def test_voice_capability(
    body: VoiceCapabilityTestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
    runner: VoiceTestRunnerPort = Depends(get_voice_test_runner),
    cache=Depends(get_redis),
    stream_sessions=Depends(audit_session_factory),
):
    if 'application/x-ndjson' in request.headers.get('accept','').split(','):
        return await capability_stream(capability_key=body.capability_key,request=request,
            admin=admin_user,cache=cache,runner=runner,session_factory=stream_sessions)
    data = await realtime_voice_admin_test_service.test_capability(
        db,
        capability_key=body.capability_key,
        runner=runner,
        admin_user=admin_user,
        request=request,
    )
    return ApiResponse.ok(data=data.model_dump(mode="json"))


@router.post(
    "/config/capabilities/{capability_key}/force-test",
    dependencies=[require_role(*_VOICE_CONFIG_FORCE_TEST_ENTRY_ROLES)],
)
async def force_voice_capability_test(
    capability_key: str,
    body: VoiceForceTestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    try:
        result = await realtime_voice_config_service.force_capability_test(
            db,
            capability_key=capability_key,
            effective_scope=body.effective_scope,
            confirm_text=body.confirm_text,
            reason=body.reason,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


@router.get("/config/{key}", dependencies=[require_role(*_READ_ROLES)])
async def get_voice_config(
    key: str,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    try:
        result = await realtime_voice_config_service.get_bundle(db, key, admin_user.role)
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


@router.get(
    "/capability-evidence/{evidence_report_id}",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_voice_capability_evidence(
    evidence_report_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    result = await realtime_voice_capability_service.get_evidence(
        db,
        evidence_report_id=evidence_report_id,
        role=admin_user.role,
    )
    if result is None:
        payload = ApiResponse.fail(
            ADMIN_ERR_VOICE_CONFIG_NOT_FOUND,
            message="能力证据不存在",
            data={"error_code": CAPABILITY_EVIDENCE_NOT_FOUND},
        )
        return JSONResponse(
            status_code=404,
            content=payload.model_dump(mode="json"),
        )
    return ApiResponse.ok(data=result)


@router.patch(
    "/config/config/draft/{section}",
    dependencies=[require_role(*_CONFIG_WRITE_ROLES)],
)
async def save_config_draft_section(
    section: str,
    body: VoiceDraftSectionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _save_section(
        config_key=VOICE_CALL_CONFIG_KEY,
        section=section,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.patch(
    "/config/script/draft/{section}",
    dependencies=[require_role(*_SCRIPT_WRITE_ROLES)],
)
async def save_script_draft_section(
    section: str,
    body: VoiceDraftSectionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _save_section(
        config_key=VOICE_CALL_SCRIPT_KEY,
        section=section,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.delete(
    "/config/config/draft/{section}",
    dependencies=[require_role(*_CONFIG_WRITE_ROLES)],
)
async def discard_config_draft_section(
    section: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _discard_section(
        config_key=VOICE_CALL_CONFIG_KEY,
        section=section,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.delete(
    "/config/script/draft/{section}",
    dependencies=[require_role(*_SCRIPT_WRITE_ROLES)],
)
async def discard_script_draft_section(
    section: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _discard_section(
        config_key=VOICE_CALL_SCRIPT_KEY,
        section=section,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.delete(
    "/config/config/draft",
    dependencies=[require_role(*_CONFIG_WRITE_ROLES)],
)
async def discard_config_draft(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _discard_all(
        config_key=VOICE_CALL_CONFIG_KEY,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.delete(
    "/config/script/draft",
    dependencies=[require_role(*_SCRIPT_WRITE_ROLES)],
)
async def discard_script_draft(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _discard_all(
        config_key=VOICE_CALL_SCRIPT_KEY,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.post(
    "/config/config/validate",
    dependencies=[require_role(*_CONFIG_WRITE_ROLES)],
)
async def validate_config(
    body: VoiceValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _validate(
        config_key=VOICE_CALL_CONFIG_KEY,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.post(
    "/config/script/validate",
    dependencies=[require_role(*_SCRIPT_WRITE_ROLES)],
)
async def validate_script(
    body: VoiceValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _validate(
        config_key=VOICE_CALL_SCRIPT_KEY,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.post(
    "/config/config/publish",
    dependencies=[require_role(*_CONFIG_WRITE_ROLES)],
)
async def publish_config(
    body: VoicePublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _publish(
        config_key=VOICE_CALL_CONFIG_KEY,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.post(
    "/config/script/publish",
    dependencies=[require_role(*_SCRIPT_WRITE_ROLES)],
)
async def publish_script(
    body: VoicePublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _publish(
        config_key=VOICE_CALL_SCRIPT_KEY,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.get(
    "/config/{key}/history",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_voice_config_history(
    key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    try:
        config_key = realtime_voice_config_service.resolve_config_key(key)
        result = await realtime_voice_config_service.get_history(
            db,
            config_key=config_key,
            page=page,
            page_size=page_size,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


@router.get(
    "/config/{key}/history/{version}",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_voice_config_history_detail(
    key: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    try:
        config_key = realtime_voice_config_service.resolve_config_key(key)
        result = await realtime_voice_config_service.get_history_detail(
            db,
            config_key=config_key,
            version=version,
            role=admin_user.role,
        )
    except VoiceConfigError as exc:
        return _voice_error_response(exc)
    return ApiResponse.ok(data=result)


@router.post(
    "/config/config/rollback",
    dependencies=[require_role(*_CONFIG_WRITE_ROLES)],
)
async def rollback_config(
    body: VoiceRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _rollback(
        config_key=VOICE_CALL_CONFIG_KEY,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


@router.post(
    "/config/script/rollback",
    dependencies=[require_role(*_SCRIPT_WRITE_ROLES)],
)
async def rollback_script(
    body: VoiceRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    return await _rollback(
        config_key=VOICE_CALL_SCRIPT_KEY,
        body=body,
        request=request,
        db=db,
        admin_user=admin_user,
    )


__all__ = ["get_voice_test_runner", "router"]
