"""Narrow M2 operations endpoints, with explicit role tuples on every route."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from backend.database import get_db, async_session_maker
from backend.redis_client import get_redis
from backend.services.realtime_voice_ops_service import VoiceOpsService, end_failure, log_end_failure
from backend.services.realtime_voice_config_service import VoiceConfigError
from backend.utils.admin_auth import require_role

from backend.services.realtime_voice_record_metric_service import VoiceRecordMetricRoute, record_role

router = APIRouter(route_class=VoiceRecordMetricRoute)
_VOICE_OPS_READ_ROLES = ('super_admin', 'tech_ops', 'observer')
_VOICE_OPS_WRITE_ROLES = ('super_admin', 'tech_ops')


@router.post('/jobs/{job_id}/retry')
async def retry_job(job_id: int, request: Request, admin=record_role('super_admin', 'tech_ops'), db=Depends(get_db)):
    from backend.services.realtime_voice_job_service import retry_memory_job
    try:
        result = await retry_memory_job(db, job_id=job_id, admin=admin, request=request)
        return JSONResponse(content={'code': 0, 'data': result}, headers={'Cache-Control': 'no-store'})
    except VoiceConfigError as exc:
        return error(exc)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm_text: str


async def get_voice_ops():
    return VoiceOpsService(cache=await get_redis(), session_factory=async_session_maker)


def error(exc):
    return JSONResponse(status_code=exc.status_code, content={'code': 400, 'message': exc.message,
                                                            'data': {'error_code': exc.code}})


def end_error(exc, call_id=None):
    detail = end_failure(call_id, exc)
    log_end_failure(call_id, exc, operation='admin')
    status = 503 if detail['retryable'] else 409
    return JSONResponse(status_code=status, content={'code': status, 'message': detail['message'], 'data': detail})


@router.get('/ops/active-calls')
async def active_calls(admin=require_role(*_VOICE_OPS_READ_ROLES), db=Depends(get_db), service=Depends(get_voice_ops)):
    return {'code': 0, 'data': await service.active_calls(db)}


@router.post('/ops/soft-stop')
async def soft_stop(body: ConfirmRequest, request: Request, admin=require_role(*_VOICE_OPS_WRITE_ROLES), db=Depends(get_db), service=Depends(get_voice_ops)):
    try:
        return {'code': 0, 'data': await service.soft_stop(db, confirm_text=body.confirm_text, admin_user=admin, request=request)}
    except VoiceConfigError as exc:
        return error(exc)


@router.post('/ops/hard-stop')
async def hard_stop(body: ConfirmRequest, request: Request, admin=require_role(*_VOICE_OPS_WRITE_ROLES), db=Depends(get_db), service=Depends(get_voice_ops)):
    try:
        result = await service.hard_stop(db, confirm_text=body.confirm_text, admin_user=admin, request=request)
        return JSONResponse(status_code=503 if result['failed'] else 200,
                            content={'code': 503 if result['failed'] else 0, 'data': result})
    except VoiceConfigError as exc:
        return error(exc)
    except Exception as exc:
        return end_error(exc)


@router.post('/calls/{call_id}/force-end')
async def force_end(call_id: str, body: ConfirmRequest, request: Request, admin=require_role(*_VOICE_OPS_WRITE_ROLES), service=Depends(get_voice_ops)):
    try:
        service.confirm(body.confirm_text)
        return {'code': 0, 'data': await service.end_call(call_id=call_id, admin_user=admin, request=request)}
    except VoiceConfigError as exc:
        return error(exc)
    except Exception as exc:
        return end_error(exc, call_id)
