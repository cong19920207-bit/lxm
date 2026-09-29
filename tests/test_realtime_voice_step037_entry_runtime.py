"""HTTP create and signed WebSocket entry/reconnect against production routes."""
import asyncio
import json
import os
import socket
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import uvicorn
import websockets
from fastapi import FastAPI
from sqlalchemy import select, func

import backend.config
import backend.routers.realtime_voice as routes
from backend.database import get_db
from backend.models.user import User
from backend.models.realtime_voice import VoiceCall, VoiceCallCreateIdempotency, VoiceUsageLedger
from backend.utils.auth_middleware import get_current_user
from backend.constants.realtime_voice_config import get_default_voice_call_script
from backend.services.realtime_voice_create_service import VoiceCreateService
from backend.services.realtime_voice_gateway_service import VoiceGatewaySession, ticket_codec_from_environment
from backend.services.realtime_voice_provider_service import VoiceProviderAdapter, ENDPOINT
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from tests.test_realtime_voice_step010_create import Loader
from tests.test_realtime_voice_step019_reconnect import formal_pack
from tests.test_realtime_voice_step007_provider import response
from tests.test_realtime_voice_step037_provider_fault_runtime import containers, runtime, full_runtime

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated HTTP/WS entry drill')


@pytest.mark.asyncio
@pytest.mark.parametrize('origin_policy', ['explicit', 'same_site'])
async def test_signed_entry_origin_device_replay_and_same_call_reconnect(full_runtime, monkeypatch, origin_policy):
    factory, _, cache = full_runtime
    async with factory() as db:
        db.add(User(id=2, username='entry-fixture', password_hash='not-a-login'))
        await db.commit()
    monkeypatch.setattr(backend.config, 'get_jwt_secret', lambda: 'isolated-entry-signing-key-32-characters')
    monkeypatch.setattr(routes, 'async_session_maker', factory)
    async def redis():
        return cache
    monkeypatch.setattr(routes, 'get_redis', redis)
    for name in ('DOUBAO_S2S_APP_ID','DOUBAO_S2S_APP_KEY','DOUBAO_S2S_ACCESS_KEY'):
        monkeypatch.setenv(name, 'isolated-provider-fixture')
    loader = Loader()
    loader.bundle.value['global']['rollout']['user_ids'] = [2]
    build = loader.bundle.build_snapshot
    script = get_default_voice_call_script()
    script['call_answer']['prompt_template'] = 'fixture decision'
    def snapshot(**kwargs):
        config, caps = build(**kwargs).persistence_values()
        return SimpleNamespace(persistence_values=lambda: ({**config, 'resolved_script': script}, caps))
    loader.bundle.build_snapshot = snapshot
    async def health(config):
        return True
    ops = VoiceOpsService(cache=cache, session_factory=factory)
    service = VoiceCreateService(loader=loader, cache=cache, leases=VoiceLeaseService(cache,end_call=ops.end_call),
        ticket_codec=ticket_codec_from_environment(), provider_preflight=health)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: 2
    app.dependency_overrides[routes.get_create_service] = lambda: service
    async def db():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    provider_sessions, gateways = [], []
    async def provider(connection):
        try:
            async for raw in connection:
                event = int.from_bytes(raw[4:8], 'big')
                if event == 1:
                    await connection.send(response(50, 'connection'))
                elif event == 100:
                    size = int.from_bytes(raw[8:12], 'big')
                    session = raw[12:12+size].decode()
                    provider_sessions.append(session)
                    await connection.send(response(150, session, {'dialog_id': 'fixture-dialog'}))
        except websockets.ConnectionClosed:
            pass
    async with websockets.serve(provider, '127.0.0.1', 0) as upstream:
        upstream_url = 'ws://127.0.0.1:' + str(upstream.sockets[0].getsockname()[1])
        async def transport(url, **kwargs):
            assert url == ENDPOINT
            return await websockets.connect(upstream_url, **kwargs)
        def adapter(**kwargs):
            return VoiceProviderAdapter(**kwargs, transport_factory=transport)
        async def decision(prompt):
            return '{"answer":true,"delay_seconds":4,"opening_text":""}'
        def gateway(**kwargs):
            result = VoiceGatewaySession(**kwargs, adapter_factory=adapter, context_builder=formal_pack, decision_model=decision)
            gateways.append(result)
            return result
        monkeypatch.setattr(routes, 'VoiceGatewaySession', gateway)
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        monkeypatch.setenv('VOICE_ALLOWED_ORIGINS', origin if origin_policy == 'explicit' else '')
        monkeypatch.setenv('VOICE_ALLOW_INSECURE_LOCAL', '1')
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(100):
                if server.started:
                    break
                if serving.done():
                    await serving
                await asyncio.sleep(.02)
            assert server.started
            async with httpx.AsyncClient(base_url=origin) as http:
                device = str(uuid4())
                created = await http.post('/api/voice/calls', headers={'Idempotency-Key':str(uuid4())},
                    json=dict(source='home',device_id=device,browser_supported=True,microphone_granted=True))
                assert created.status_code == 200
                call_id, ticket = (created.json()['data'][key] for key in ('call_id','call_ticket'))
                url = f'ws://127.0.0.1:{port}/api/voice/calls/{call_id}/stream'
                def protocols(value=ticket, target=device):
                    return ['voice.v1', 'ticket.'+value, 'device.'+target]
                for bad_origin, bad_device in [('https://rejected.invalid', device), (origin, str(uuid4()))]:
                    with pytest.raises(websockets.InvalidStatus):
                        async with websockets.connect(url, origin=bad_origin, subprotocols=protocols(target=bad_device)):
                            pytest.fail('unauthorized entry accepted')
                async with websockets.connect(url, origin=origin, subprotocols=protocols()) as initial:
                    assert initial.subprotocol == 'voice.v1'
                    async with asyncio.timeout(15):
                        while json.loads(await initial.recv()).get('status') != 'connected':
                            pass
                    async with factory() as session:
                        row = await session.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
                        anchor = row.connected_at
                    with pytest.raises(websockets.InvalidStatus):
                        async with websockets.connect(url, origin=origin, subprotocols=protocols()):
                            pytest.fail('consumed ticket reused')
                    await asyncio.sleep(1.1)
                async with asyncio.timeout(10):
                    while True:
                        result = await http.post(f'/api/voice/calls/{call_id}/reconnect', json={'device_id':device})
                        if result.status_code == 200:
                            break
                        assert result.status_code == 409
                        await asyncio.sleep(.05)
                new_ticket = result.json()['data']['call_ticket']
                async with websockets.connect(url.replace('/stream','/reconnect-stream'), origin=origin,
                    subprotocols=protocols(value=new_ticket)) as restored:
                    async with asyncio.timeout(15):
                        while json.loads(await restored.recv()).get('status') != 'connected':
                            pass
                    await asyncio.sleep(1.1)
                    assert (await http.post(f'/api/voice/calls/{call_id}/end')).status_code == 200
                await asyncio.wait_for(gateways[0].closed_event.wait(), 10)
                async with factory() as session:
                    calls = list(await session.scalars(select(VoiceCall).where(VoiceCall.user_id==2)))
                    assert len(calls)==1 and calls[0].call_id==call_id and calls[0].connected_at==anchor
                    assert calls[0].status=='ended'
                    assert await session.scalar(select(func.count()).select_from(VoiceCallCreateIdempotency).where(VoiceCallCreateIdempotency.user_id==2))==1
                    assert await session.scalar(select(func.count()).select_from(VoiceUsageLedger).where(VoiceUsageLedger.call_id==call_id))==1
                assert len(provider_sessions)==2 and len(set(provider_sessions))==2
                assert len(gateways)==1
                assert await cache.get(VoiceLeaseService.user_key(2)) is None
        finally:
            for item in gateways:
                if not item.closed_event.is_set():
                    await item.stop_local()
            server.should_exit = True
            await asyncio.wait_for(serving, 10)
            listener.close()
