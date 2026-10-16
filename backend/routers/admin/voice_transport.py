"""Administrative transport probes: no call, microphone, quota or provider use."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse

from backend.redis_client import get_redis
from backend.schemas.common import ApiResponse
from backend.services.proxy_discovery import utc_now
from backend.services.realtime_voice_gateway_service import socket_credentials, _voice_origin
from backend.services.realtime_voice_metric_read_service import parse_counter
from backend.services.realtime_voice_ticket_service import TicketError
from backend.utils.admin_auth import require_role

router = APIRouter()
socket_router = APIRouter()
READ_ROLES = ('super_admin', 'tech_ops', 'ai_trainer', 'ops_admin', 'observer')
WRITE_ROLES = ('super_admin', 'tech_ops')
PREFIX = 'voice:transport-diagnostic:'


async def cache_dependency():
    try:
        return await get_redis()
    except Exception:
        return None


async def bounded(operation):
    return await asyncio.wait_for(operation, 1)


def response(data):
    return JSONResponse(ApiResponse.ok(data).model_dump(mode='json'), headers={'Cache-Control': 'no-store'})


def ticket_key(token):
    return PREFIX + 'ticket:' + hashlib.sha256(token.encode()).hexdigest()


def discovery(request):
    value = getattr(request.app.state, 'proxy_discovery', None)
    if value is None:
        raise HTTPException(503, '代理自动发现模块未启用')
    return value


@router.get('/master-switch/diagnostics')
async def diagnostics(request: Request, admin=require_role(*READ_ROLES), cache=Depends(cache_dependency)):
    day = datetime.now(timezone.utc).strftime('%Y%m%d')
    recent = {'status': 'unavailable', 'samples': None}
    last, probe_state = None, 'unavailable'
    try:
        raw = await bounded(cache.hgetall('voice.ws.rejection:' + day))
        recent = parse_counter('voice.ws.rejection', raw)
        value = await bounded(cache.get(PREFIX + 'last'))
        last, probe_state = json.loads(value) if value else None, 'available'
    except Exception:
        pass
    return response(dict(proxy=discovery(request).snapshot(), last_probe=last,
                         probe_storage=probe_state, probe_valid_seconds=60,
                         recent_rejections={**recent, 'utc_day': day, 'completeness': 'not_guaranteed'}))


@router.post('/master-switch/diagnostics/probes')
async def start_probe(request: Request, admin=require_role(*WRITE_ROLES), cache=Depends(cache_dependency)):
    host = request.headers.get('host', '')
    try:
        _voice_origin('https://' + host)
    except TicketError:
        raise HTTPException(400, '诊断入口域名无效') from None
    token, probe_id = secrets.token_urlsafe(32), uuid4().hex
    try:
        if not await bounded(cache.set(PREFIX + 'rate:' + str(admin.id), '1', ex=3, nx=True)):
            raise HTTPException(429, '检测过于频繁，请稍后重试')
        await discovery(request).refresh(force=True)
        record = dict(probe_id=probe_id, host=host, status='pending', checked_at=utc_now())
        # Separate short-lived, single-use capability. Never accepts a user call ticket/JWT.
        await bounded(cache.set(ticket_key(token), json.dumps(record), ex=30))
        await bounded(cache.set(PREFIX + 'result:' + probe_id, json.dumps(record), ex=300))
        await bounded(cache.set(PREFIX + 'last', json.dumps(record), ex=300))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, '诊断存储暂不可用，请检查 Redis 后重新检测') from None
    return response(dict(probe_id=probe_id, ticket=token, expires_seconds=30,
                         path='/api/voice/diagnostics/stream', proxy=discovery(request).snapshot()))


@router.get('/master-switch/diagnostics/probes/{probe_id}')
async def probe_result(probe_id: str, admin=require_role(*READ_ROLES), cache=Depends(cache_dependency)):
    if not re.fullmatch('[0-9a-f]{32}', probe_id):
        raise HTTPException(404, '检测不存在或已过期')
    try:
        raw = await bounded(cache.get(PREFIX + 'result:' + probe_id))
    except Exception:
        raise HTTPException(503, '诊断存储暂不可用') from None
    if not raw:
        raise HTTPException(404, '检测不存在或已过期')
    return response(json.loads(raw))


async def save_result(cache, record, **values):
    result = {**record, **values, 'checked_at': utc_now()}
    encoded = json.dumps(result)
    await bounded(cache.set(PREFIX + 'result:' + record['probe_id'], encoded, ex=300))
    # An older overlapping probe must not replace a newer probe's shared status.
    await bounded(cache.eval("""
        local current = redis.call('GET', KEYS[1])
        if current and cjson.decode(current).probe_id == ARGV[1] then
            return redis.call('SET', KEYS[1], ARGV[2], 'EX', 300)
        end
        return 0
    """, 1, PREFIX + 'last', record['probe_id'], encoded))
    return result


@socket_router.websocket('/diagnostics/stream')
async def probe_socket(socket: WebSocket):
    record, cache = None, None
    accepted = False
    try:
        parts = [value.strip() for value in socket.headers.get('sec-websocket-protocol', '').split(',')]
        if (len(parts) != 3 or parts[0] != 'voice.v1' or parts[2] != 'device.diagnostic'
                or not re.fullmatch(r'ticket\.[A-Za-z0-9_-]{43}', parts[1])):
            raise TicketError('diagnostic_ticket_invalid')
        cache = await get_redis()
        raw = await bounded(cache.getdel(ticket_key(parts[1][7:])))
        if not raw:
            raise TicketError('diagnostic_ticket_invalid')
        record = json.loads(raw)
        if socket.headers.get('host') != record['host']:
            raise TicketError('socket_origin_or_url_rejected')
        origins = {value.strip() for value in os.getenv('VOICE_ALLOWED_ORIGINS', '').split(',') if value.strip()}
        socket_credentials(socket, origins, os.getenv('VOICE_ALLOW_INSECURE_LOCAL', '') == '1')
        await socket.accept(subprotocol='voice.v1')
        accepted = True
        await socket.send_json({'type': 'diagnostic.ready'})
        if await asyncio.wait_for(socket.receive_json(), 3) != {'type': 'diagnostic.ack'}:
            raise TicketError('diagnostic_ack_invalid')
        result = await save_result(cache, record, status='passed', reason=None,
                                   scheme=socket.url.scheme, proxy=socket.scope.get('voice_proxy'),
                                   local_insecure=socket.url.scheme != 'wss')
        await socket.send_json({'type': 'diagnostic.result', 'result': result})
    except Exception as exc:
        if record is not None:
            reason = str(exc) if isinstance(exc, TicketError) else 'diagnostic_connection_failed'
            try:
                await save_result(cache, record, status='failed', reason=reason,
                                  scheme=socket.url.scheme, proxy=socket.scope.get('voice_proxy'))
            except Exception:
                pass
        # Synthetic probes never increment business call rejection metrics.
    finally:
        try:
            await socket.close(code=1000 if accepted else 4403)
        except RuntimeError:
            pass
