"""Standalone voice master switch administration."""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services.realtime_voice_config_service import VoiceConfigError
from backend.services.realtime_voice_master_switch_service import realtime_voice_master_switch_service as service
from backend.utils.admin_auth import require_role

router = APIRouter()
logger = logging.getLogger(__name__)
_READ_ROLES = ('super_admin', 'tech_ops', 'ai_trainer', 'ops_admin', 'observer')
_WRITE_ROLES = ('super_admin', 'tech_ops')

class PublishRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool
    expected_version: Annotated[int, Field(strict=True, ge=1)]


def error_response(exc):
    known = isinstance(exc, VoiceConfigError)
    status = exc.status_code if known else 503
    return JSONResponse(status_code=status, content=ApiResponse.fail(
        status, message=exc.message if known else '总开关操作失败，请刷新确认当前状态',
        data={'error_code': exc.code if known else 'VOICE_MASTER_SWITCH_UNAVAILABLE',
              'errors': exc.errors if known else []},
    ).model_dump(mode='json'))


@router.get('/master-switch')
async def get_master_switch(db=Depends(get_db), admin_user=require_role(*_READ_ROLES)):
    try:
        return ApiResponse.ok(await service.get_state(db))
    except Exception as exc:
        await db.rollback()
        return error_response(exc)


@router.post('/master-switch/publish')
async def publish_master_switch(body: PublishRequest, request: Request, db=Depends(get_db), admin_user=require_role(*_WRITE_ROLES)):
    try:
        return ApiResponse.ok(await service.publish(db, enabled=body.enabled,
            expected_version=body.expected_version, admin_user=admin_user, request=request))
    except Exception as exc:
        return error_response(exc)
