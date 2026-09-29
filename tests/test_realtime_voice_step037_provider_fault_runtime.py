"""Real client and controlled Provider WebSockets through the production gateway."""
import asyncio
import json
import os

import pytest
import pytest_asyncio
import websockets
from sqlalchemy import select

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.constants.realtime_voice_config import get_default_voice_call_config, get_default_voice_call_script
from backend.services.realtime_voice_gateway_service import VoiceGatewaySession
from backend.services.realtime_voice_provider_service import VoiceProviderAdapter, ENDPOINT
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_local_runtime import local_voice_calls
from tests.test_realtime_voice_m4_runtime import containers, runtime, TABLES
from tests.test_realtime_voice_step019_reconnect import formal_pack
from tests.test_realtime_voice_step007_provider import response

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated WebSocket fault drill')


@pytest_asyncio.fixture
async def full_runtime(runtime):
    factory, _, _ = runtime
    extra = [table for table in Base.metadata.sorted_tables if table not in TABLES]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=extra)
    try:
        yield runtime
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=extra)


class ClientSocket:
    def __init__(self, connection):
        self.connection = connection
    async def receive_text(self):
        return await self.connection.recv()
    async def send_json(self, value):
        await self.connection.send(json.dumps(value))
    async def close(self, **kwargs):
        await self.connection.close(**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize('phase', ['connection', 'connected'])
async def test_provider_wire_failure_gateway_cleanup_and_no_duplicate_charge(full_runtime, monkeypatch, phase):
    factory, call_id, cache = full_runtime
    config = get_default_voice_call_config({'config_key':'persona','version':1,'content_sha256':'sha256:'+'a'*64})
    script = get_default_voice_call_script()
    script['call_answer']['prompt_template'] = 'fixture decision'
    async with factory() as db:
        call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        call.status, call.connected_at = 'deciding', None
        call.config_snapshot = {'resolved_config': config, 'resolved_script': script}
        await db.commit()
    for name in ('DOUBAO_S2S_APP_ID','DOUBAO_S2S_APP_KEY','DOUBAO_S2S_ACCESS_KEY'):
        monkeypatch.setenv(name, 'isolated-provider-fixture')
    connected, finished = asyncio.Event(), asyncio.Event()
    gateways, failures, upstream_events = [], [], []

    async def provider(socket):
        try:
            async for raw in socket:
                event = int.from_bytes(raw[4:8], 'big')
                upstream_events.append(event)
                if event == 1:
                    if phase == 'connection':
                        await socket.close(code=1011, reason='controlled transport failure')
                        return
                    await socket.send(response(50, 'connection'))
                elif event == 100:
                    size = int.from_bytes(raw[8:12], 'big')
                    await socket.send(response(150, raw[12:12+size].decode(), {'dialog_id':'controlled-dialog'}))
                    await asyncio.wait_for(connected.wait(), 10)
                    await asyncio.sleep(1.1)
                    await socket.close(code=1011, reason='controlled connected failure')
                    return
        except websockets.ConnectionClosed:
            pass

    async with websockets.serve(provider, '127.0.0.1', 0) as upstream:
        endpoint = 'ws://127.0.0.1:' + str(upstream.sockets[0].getsockname()[1])
        async def transport(url, **kwargs):
            assert url == ENDPOINT
            return await websockets.connect(endpoint, **kwargs)
        def adapter(**kwargs):
            return VoiceProviderAdapter(**kwargs, transport_factory=transport)
        async def decision(prompt):
            return '{"answer":true,"delay_seconds":4,"opening_text":""}'
        async def gateway_route(socket):
            gateway = VoiceGatewaySession(socket=ClientSocket(socket), call=call, cache=cache,
                session_factory=factory, adapter_factory=adapter, context_builder=formal_pack, decision_model=decision)
            gateways.append(gateway)
            try:
                assert await gateway.leases.acquire(user_id=1, call_id=call_id, ttl_ms=60000, global_limit=10) == (True, 'acquired')
                await gateway.run()
            except Exception as exc:
                failures.append(type(exc).__name__)
            finally:
                finished.set()
        async with websockets.serve(gateway_route, '127.0.0.1', 0) as server:
            states = []
            async with websockets.connect('ws://127.0.0.1:' + str(server.sockets[0].getsockname()[1])) as client:
                async with asyncio.timeout(20):
                    async for message in client:
                        frame = json.loads(message)
                        if frame['type'] == 'state':
                            states.append(frame['status'])
                            if frame['status'] == 'connected':
                                connected.set()
            await asyncio.wait_for(finished.wait(), 10)
    assert failures == [] and len(gateways) == 1
    assert 1 in upstream_events
    assert ('connected' in states) == (phase == 'connected')
    gateway = gateways[0]
    assert gateway.stopped and gateway.closed_event.is_set() and call_id not in local_voice_calls
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        ledger = list(await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.call_id == call_id)))
        if phase == 'connection':
            assert row.status == 'failed' and row.connected_at is None
            assert ledger == [] and row.free_seconds_used == 0
        else:
            assert row.status == 'ended' and row.connected_at is not None
            assert len(ledger) == 1 and row.free_seconds_used >= 1
        before = [{column.name: getattr(item, column.name) for column in item.__table__.columns} for item in [row, *ledger]]
    assert (await gateway.ops.end_call(call_id=call_id, user_id=1))['changed'] is False
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        ledger = list(await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.call_id == call_id)))
        assert [{column.name: getattr(item, column.name) for column in item.__table__.columns} for item in [row, *ledger]] == before
    assert await cache.get(VoiceLeaseService.user_key(1)) is None
    assert await cache.zscore(VoiceLeaseService.active_key, call_id) is None
