"""Authenticated, request-owned pure playback diagnostic (not capability evidence)."""
import asyncio
import json
import anyio
from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db,async_session_maker
from backend.redis_client import get_redis
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import require_role,log_operation
from backend.services.realtime_voice_admin_test_service import _load_draft_snapshot,_resolve_server_secret
from backend.services.realtime_voice_provider_service import ProviderAdminTestRunner
from backend.services.realtime_voice_admin_playback_transport import RedisPlaybackTarget,PlaybackTargetError,acknowledge_playback

router=APIRouter()
ROLES=('super_admin','tech_ops')

class EmptyPlaybackRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')

class PlaybackAckRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    call_id: str=Field(min_length=1,max_length=255)
    session_id: str=Field(min_length=1,max_length=255)
    reply_id: str=Field(min_length=1,max_length=255)
    audio_bytes: int=Field(gt=0,le=4*1024*1024)


def playback_runner_factory():
    return ProviderAdminTestRunner


def audit_session_factory():
    return async_session_maker


@router.post('/config/test-playback')
async def test_playback(body:EmptyPlaybackRequest,request:Request,
                        admin= require_role(*ROLES),db:AsyncSession=Depends(get_db),
                        cache=Depends(get_redis),runner_type=Depends(playback_runner_factory),
                        audit_factory=Depends(audit_session_factory)):
    if request.url.query:raise HTTPException(400,'播放测试不接受 URL 参数')
    snapshot=await _load_draft_snapshot(db)
    secret,error=_resolve_server_secret(snapshot)
    if error:raise HTTPException(409,detail={'failure_category':error})
    try:target=await RedisPlaybackTarget.open(cache,admin_id=admin.id)
    except PlaybackTargetError:raise HTTPException(409,'已有播放测试或目标不可用') from None
    operator=SimpleNamespace(id=admin.id,username=admin.username)
    try:
        runner=runner_type(playback_target=target)
    except Exception:
        async with asyncio.timeout(3):await target.aclose()
        raise

    async def run():
        result=None
        try:
            result=await runner.run_playback(draft_snapshot=snapshot.config,secret=secret)
        except asyncio.CancelledError:
            result={'status':'error','failure_category':'client_disconnected'}
            raise
        except Exception:
            result={'status':'error','failure_category':'internal_error'}
        finally:
            # Audit is linked to this target and original draft, never the
            # currently displayed capability row; audio/body/secret stay out.
            safe=dict(test_id=target.test_id,tested_draft_revision=snapshot.revision,
                tested_draft_sha256=snapshot.content_sha256,**(result or {}))
            async with asyncio.timeout(3),audit_factory() as audit_db:
                await log_operation(audit_db,operator,'voice_config','test_playback','管理端纯播放诊断',
                                    after_value=json.dumps(safe,ensure_ascii=False),request=request)
                await audit_db.commit()
        return {**result,'test_id':target.test_id,'tested_draft_revision':snapshot.revision}

    return stream_target_result(target,run)


def stream_target_result(target,run):
    async def stream():
        job=asyncio.create_task(run());pending=None
        try:
            while True:
                pending=asyncio.create_task(target.events.get())
                done,_=await asyncio.wait((job,pending),return_when=asyncio.FIRST_COMPLETED)
                if pending in done:
                    yield json.dumps(pending.result(),separators=(',',':'))+'\n'
                    pending=None
                elif job in done:
                    pending.cancel();await asyncio.gather(pending,return_exceptions=True);pending=None
                if job.done() and target.events.empty():
                    try:result=job.result()
                    except Exception:result={'status':'error','failure_category':'audit_or_cleanup_failed','test_id':target.test_id}
                    yield json.dumps(dict(type='result',**result),separators=(',',':'))+'\n'
                    return
        finally:
            # Starlette cancels the response scope on disconnect. Shield the
            # bounded cleanup so its repeated cancellation cannot interrupt
            # Provider closure or the cancellation audit transaction.
            with anyio.CancelScope(shield=True):
                if pending:pending.cancel()
                if not job.done():job.cancel()
                try:
                    async with asyncio.timeout(10):
                        await asyncio.gather(*([pending] if pending else []),job,return_exceptions=True)
                finally:
                    try:
                        async with asyncio.timeout(3):await target.aclose()
                    except Exception:pass
    return StreamingResponse(stream(),media_type='application/x-ndjson',
        headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})


@router.post('/config/test-playback/{test_id}/ack')
async def playback_ack(test_id:UUID,body:PlaybackAckRequest,request:Request,
                       admin=require_role(*ROLES),cache=Depends(get_redis)):
    if request.url.query:raise HTTPException(400,'播放确认不接受 URL 参数')
    try:
        await acknowledge_playback(cache,test_id=str(test_id),admin_id=admin.id,ack=body.model_dump())
    except PlaybackTargetError:raise HTTPException(409,'播放目标、状态或确认不匹配') from None
    return ApiResponse.ok(data={'acknowledged':True})


class PlaybackStopAckRequest(PlaybackAckRequest):
    played_ms: int=Field(gt=0,le=45000)
    stopped: bool

    @field_validator("stopped")
    @classmethod
    def require_stopped(cls,value):
        if value is not True:raise ValueError("停止确认必须为 true")
        return value


@router.post('/config/test-playback/{test_id}/stop-ack')
async def playback_stop_ack(test_id:UUID,body:PlaybackStopAckRequest,request:Request,
                            admin=require_role(*ROLES),cache=Depends(get_redis)):
    if request.url.query:raise HTTPException(400,'播放确认不接受 URL 参数')
    if body.played_ms != body.audio_bytes//48:raise HTTPException(422,'播放时长与 PCM 前缀不匹配')
    try:await acknowledge_playback(cache,test_id=str(test_id),admin_id=admin.id,ack=body.model_dump())
    except PlaybackTargetError:raise HTTPException(409,'播放目标、状态或确认不匹配') from None
    return ApiResponse.ok(data={'acknowledged':True})


async def capability_stream(*,capability_key,request,admin,cache,runner,session_factory):
    from backend.services.realtime_voice_admin_test_service import realtime_voice_admin_test_service
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    if not isinstance(getattr(runner,'_probe',None),BuiltinCapabilityProbe):
        raise HTTPException(409,'当前 runner 未支持管理播放目标')
    try:target=await RedisPlaybackTarget.open(cache,admin_id=admin.id)
    except PlaybackTargetError:raise HTTPException(409,'已有测试或播放目标不可用') from None
    runner._probe.playback_target=target
    runner.test_target_id=target.test_id
    operator=SimpleNamespace(id=admin.id,username=admin.username)
    async def run():
        try:
            # This transaction belongs to the stream job, not a dependency
            # session whose lifetime may end before StreamingResponse runs.
            async with session_factory() as db:
                data=await realtime_voice_admin_test_service.test_capability(db,
                    capability_key=capability_key,runner=runner,admin_user=operator,request=request)
                await db.commit()
                return dict(test_id=target.test_id,**data.model_dump(mode='json'))
        except asyncio.CancelledError:
            async with asyncio.timeout(3),session_factory() as db:
                await log_operation(db,operator,'voice_config','test_capability','实时语音后台能力测试',
                    after_value=json.dumps(dict(test_id=target.test_id,capability_key=capability_key,
                        status='error',failure_category='client_disconnected')),request=request)
                await db.commit()
            raise
        finally:
            await runner.aclose()
    return stream_target_result(target,run)
