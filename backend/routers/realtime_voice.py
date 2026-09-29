"""M2 user call APIs and single-use authenticated WebSocket entry."""
import os
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, WebSocket, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend.database import get_db, async_session_maker
from backend.redis_client import get_redis
from backend.models.realtime_voice import VoiceCall
from backend.models.user import User
from backend.services.realtime_voice_create_service import VoiceCreateService, VoicePreflightError
from backend.services.realtime_voice_decision_service import transition_call
from backend.services.realtime_voice_gateway_service import (VoiceGatewaySession, socket_credentials,
    ticket_codec_from_environment, provider_preflight)
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_quota_service import VoiceQuotaService
from backend.services.realtime_voice_runtime_config_service import realtime_voice_runtime_config_service
from backend.services.realtime_voice_ticket_service import consume_voice_ticket
from backend.services.realtime_voice_ticket_service import TicketError
from backend.services.realtime_voice_local_runtime import local_voice_calls
from backend.services.realtime_voice_presentation_service import call_presentation
from backend.utils.auth_middleware import get_current_user
from backend.services.realtime_voice_metric_service import VoiceMetrics,ApplicationVoiceMetrics
from backend.services.realtime_voice_ws_metric_service import stream_metrics,observed_stream,observe_ws,ws_rejection

router = APIRouter(prefix='/api/voice', tags=['voice'])
logger = logging.getLogger(__name__)


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source: str
    device_id: str
    browser_supported: bool
    microphone_granted: bool


class EnvironmentTicketCodec:
    def issue(self, **kwargs):
        return ticket_codec_from_environment().issue(**kwargs)


async def get_create_service():
    cache = await get_redis()
    ops = VoiceOpsService(cache=cache, session_factory=async_session_maker)
    return VoiceCreateService(loader=realtime_voice_runtime_config_service, cache=cache,
        leases=VoiceLeaseService(cache, end_call=ops.end_call), ticket_codec=EnvironmentTicketCodec(),
        provider_preflight=provider_preflight)


@router.post('/calls')
async def create_call(body: CreateRequest, idempotency_key: str = Header(..., alias='Idempotency-Key', max_length=64),
                      user_id=Depends(get_current_user), db=Depends(get_db), service=Depends(get_create_service)):
    try:
        return {'code': 0, 'data': await service.create(db, user_id=user_id, idempotency_key=idempotency_key, payload=body.model_dump())}
    except VoicePreflightError as exc:
        return JSONResponse(status_code=exc.status, content={'code': exc.status, 'message': '当前无法发起通话', 'data': {'block_reason': exc.reason}})


@router.get('/quota')
async def quota(user_id=Depends(get_current_user), db=Depends(get_db)):
    bundle = await realtime_voice_runtime_config_service.load_bundle(user_id=user_id)
    snapshot = bundle.build_snapshot(user_id=user_id)
    daily = snapshot.config_snapshot['resolved_config']['quota']['daily_free_seconds']
    balance = await VoiceQuotaService().balance(db, user_id, daily_seconds=daily,
                                                now=datetime.now(timezone.utc), published_config=True)
    return {'code': 0, 'data': {'remaining_seconds': balance.total}}


@router.get('/calls/{call_id}')
async def call_status(call_id: UUID, user_id=Depends(get_current_user), db=Depends(get_db)):
    row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == str(call_id), VoiceCall.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail='通话不存在')
    from fastapi.responses import JSONResponse
    from backend.services.realtime_voice_crisis_presentation_service import crisis_presentations
    data = call_presentation(row)
    data['crisis'] = (await crisis_presentations(db, [row])).get(row.call_id)
    return JSONResponse({'code': 0, 'data': data}, headers={'Cache-Control': 'no-store'})


@router.post('/calls/{call_id}/end')
async def end_call(call_id: UUID, only_if_unconnected: bool = False,
                   user_id=Depends(get_current_user), db=Depends(get_db)):
    row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == str(call_id), VoiceCall.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail='通话不存在')
    events=[]
    class DeferredStateMetrics:
        async def emit_many(self,batch):
            events.extend(batch)
    try:
        if only_if_unconnected or row.status in ('deciding','ringing'):
            # No telemetry I/O between cancellation commit and required cleanup.
            cancelled = await transition_call(db, call_id=str(call_id), expected=('deciding','ringing'),
                target='cancelled', now=datetime.now(timezone.utc), metrics=DeferredStateMetrics())
            if only_if_unconnected and not cancelled:
                # 前端查询可能已过时；锁内取消失败后，只允许重试未接通过的终态清理。
                await db.refresh(row)
                if row.connected_at is not None or row.status not in ('cancelled', 'failed', 'missed', 'ended'):
                    raise HTTPException(status_code=409, detail='通话状态已变化，请重新查询')
        ops = VoiceOpsService(cache=await get_redis(), session_factory=async_session_maker)
        return {'code': 0, 'data': await ops.end_call(call_id=str(call_id), user_id=user_id, reason='user_hangup')}
    finally:
        if events:await ApplicationVoiceMetrics().emit_many(events)



class ReconnectRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    device_id: str = Field(min_length=36, max_length=36)


@router.post('/calls/{call_id}/reconnect')
async def reconnect_ticket(call_id: UUID, body: ReconnectRequest, user_id=Depends(get_current_user), db=Depends(get_db)):
    row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == str(call_id), VoiceCall.user_id == user_id))
    local = local_voice_calls.get(str(call_id))
    if row is None:
        raise HTTPException(status_code=404, detail='通话不存在')
    if row.status != 'reconnecting' or not local or not local.reconnect:
        raise HTTPException(status_code=409, detail='当前无法恢复通话')
    cache = await get_redis()
    if await cache.get(f'user_banned:{user_id}'):
        raise HTTPException(status_code=403, detail='当前无法恢复通话')
    try:
        data = await local.reconnect.issue(user_id=user_id, device_id=body.device_id)
        return {'code': 0, 'data': data}
    except TicketError:
        raise HTTPException(status_code=409, detail='当前无法恢复通话') from None


@router.websocket('/calls/{call_id}/reconnect-stream')
async def reconnect_stream(socket: WebSocket, call_id: str):
    attached = False
    try:
        if str(UUID(call_id)) != call_id:
            raise TicketError("reconnect_call_invalid")
        allowed = {v.strip() for v in os.getenv('VOICE_ALLOWED_ORIGINS', '').split(',') if v.strip()}
        ticket, device = socket_credentials(socket, allowed, os.getenv('VOICE_ALLOW_INSECURE_LOCAL') == '1')
        local = local_voice_calls.get(call_id)
        if local is None or local.reconnect is None:
            raise TicketError('reconnect_owner_unavailable')
        cache = await get_redis()
        user_id = local.reconnect.owner.user_id
        ops = VoiceOpsService(cache=cache, session_factory=async_session_maker)
        leases = VoiceLeaseService(cache, end_call=ops.end_call)
        if await cache.get(f'user_banned:{user_id}') or not await leases.owner_matches(user_id=user_id, call_id=call_id):
            raise TicketError('reconnect_owner_unavailable')
        async with async_session_maker() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id, VoiceCall.user_id == user_id))
            banned = await db.scalar(select(User.is_banned).where(User.id == user_id))
            if banned is not False or row is None or row.status != 'reconnecting' or row.deletion_fence_at is not None:
                raise TicketError('reconnect_not_available')
        await socket.accept(subprotocol='voice.v1')
        async with observed_stream(stream_metrics(socket),'reconnect'):
            await local.reconnect.attach(socket, ticket=ticket, device_id=device)
            attached = True
            await local.closed_event.wait()
    except (Exception, asyncio.CancelledError) as exc:
        # Rejecting an attachment must never terminate the owner's active call.
        logger.info('voice.reconnect.attachment_rejected=1')
        try:
            await socket.close(code=4403)
        except Exception:
            pass
        if not attached and not isinstance(exc,asyncio.CancelledError):
            await observe_ws(stream_metrics(socket),[('voice.ws.rejection',{'channel':'reconnect','reason':ws_rejection(exc)},1)])
        if isinstance(exc, asyncio.CancelledError):
            raise


@router.websocket('/calls/{call_id}/stream')
async def stream(socket: WebSocket, call_id: str):
    call = None
    accepted = False
    ops = None
    try:
        if str(UUID(call_id)) != call_id:
            raise ValueError('invalid_call_id')
        origins = {x.strip() for x in os.getenv('VOICE_ALLOWED_ORIGINS', '').split(',') if x.strip()}
        ticket, device = socket_credentials(socket, origins, os.getenv('VOICE_ALLOW_INSECURE_LOCAL') == '1')
        cache = await get_redis()
        ops = VoiceOpsService(cache=cache, session_factory=async_session_maker)
        leases = VoiceLeaseService(cache, end_call=ops.end_call)
        async with async_session_maker() as db:
            call = await consume_voice_ticket(db, codec=ticket_codec_from_environment(), cache=cache, leases=leases,
                ticket=ticket, call_id=call_id, device_id=device, now=datetime.now(timezone.utc))
        await socket.accept(subprotocol='voice.v1')
        accepted = True
        async with observed_stream(stream_metrics(socket),'initial'):
            await VoiceGatewaySession(socket=socket, call=call, cache=cache, session_factory=async_session_maker, device_id=device).run()
    except (Exception, asyncio.CancelledError) as exc:
        category = ('origin_reject' if isinstance(exc, TicketError) and str(exc)=='socket_origin_or_url_rejected'
                    else 'tls_error' if isinstance(exc, TicketError) and str(exc)=='wss_required'
                    else 'ticket_reject' if isinstance(exc, TicketError) else 'connection_error')
        logger.info('voice.ws.%s=1', category)
        # Deliberately omit URL, ticket, headers and upstream exception details.
        try:
            await socket.close(code=1011 if accepted else 4403)
        except Exception:
            pass
        if call is not None and ops is not None:
            try:
                try:
                    async with async_session_maker() as db:
                        await transition_call(db, call_id=call.call_id, expected=('deciding','ringing'),
                                              target='failed', now=datetime.now(timezone.utc), metrics=VoiceMetrics(cache))
                finally:
                    await ops.end_call(call_id=call.call_id, user_id=call.user_id)
            except Exception:
                pass
        if not accepted and not isinstance(exc,asyncio.CancelledError):
            await observe_ws(stream_metrics(socket),[('voice.ws.rejection',{'channel':'initial','reason':ws_rejection(exc)},1)])
        if isinstance(exc, asyncio.CancelledError):
            raise
