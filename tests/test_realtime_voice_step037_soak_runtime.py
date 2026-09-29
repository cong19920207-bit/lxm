"""Opt-in wall-clock muted-call soak; no external Provider or raw audio storage."""
import asyncio
import json
import os
import time
import traceback
from pathlib import Path
from uuid import uuid4

import psutil
import pytest
import websockets
from sqlalchemy import select, text

from backend.constants.realtime_voice_config import get_default_voice_call_config, get_default_voice_call_script
from backend.models.user import User
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_gateway_service import VoiceGatewaySession
from backend.services.realtime_voice_provider_service import VoiceProviderAdapter, ENDPOINT
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_local_runtime import local_voice_calls
from tests.test_realtime_voice_step007_provider import response
from tests.test_realtime_voice_step019_reconnect import formal_pack
from tests.test_realtime_voice_step037_provider_fault_runtime import containers, runtime, full_runtime, ClientSocket

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_SOAK') != '1', reason='explicit wall-clock soak')


@pytest.mark.asyncio
async def test_three_muted_calls_wall_clock_hard_limit_and_resources(full_runtime, monkeypatch):
    factory, _, cache = full_runtime
    duration = int(os.getenv('VOICE_SOAK_SECONDS', '480'))
    assert 10 <= duration <= 3600
    output = Path(os.environ['VOICE_SOAK_REPORT'])
    assert not output.exists(), 'keep previous run receipts immutable'
    config = get_default_voice_call_config({'config_key':'persona','version':1,'content_sha256':'sha256:'+'a'*64})
    config['quota'].update(daily_free_seconds=7200, hard_limit_seconds=duration)
    script = get_default_voice_call_script()
    script['call_answer']['prompt_template'] = 'fixture decision'
    calls = []
    async with factory() as db:
        for user_id in range(2, 5):
            db.add(User(id=user_id, username=f'soak-{user_id}', password_hash='no-login'))
        await db.flush()
        for user_id in range(2, 5):
            call = VoiceCall(call_id=str(uuid4()), user_id=user_id, initiated_by='user', status='deciding',
                summary_status='pending', config_snapshot={'resolved_config':config,'resolved_script':script},
                capability_snapshot={}, transcript_retention_days=180, generated_retention_days=30)
            db.add(call)
            calls.append(call)
        await db.commit()
    for name in ('DOUBAO_S2S_APP_ID','DOUBAO_S2S_APP_KEY','DOUBAO_S2S_ACCESS_KEY'):
        monkeypatch.setenv(name, 'isolated-provider-fixture')
    gateways, failures, connected_at, closed_at = {}, [], {}, {}
    counters = {'provider_received_bytes':0, 'client_sent_bytes':0, 'client_received_bytes':0}
    started = time.monotonic()
    process = psutil.Process()
    process.cpu_percent()
    report = {'kind':'three muted calls; local protocol Provider; gateway, clients and Provider share process',
        'hard_limit_seconds':duration, 'samples':[], 'result':'running'}
    def save():
        output.write_text(json.dumps(report, indent=2))
    async def sample():
        while True:
            info = await cache.info('memory')
            report['samples'].append({'elapsed_seconds':round(time.monotonic()-started,3),
                'rss_bytes':process.memory_info().rss, 'process_cpu_percent':process.cpu_percent(),
                'fds':process.num_fds(), 'pool_checked_out':factory.kw['bind'].pool.checkedout(),
                'local_calls':sum(call.call_id in local_voice_calls for call in calls),
                'redis_used_memory':info['used_memory'], **counters})
            save()
            await asyncio.sleep(10)
    async def provider(connection):
        try:
            async for raw in connection:
                counters['provider_received_bytes'] += len(raw)
                event = int.from_bytes(raw[4:8], 'big')
                if event == 1:
                    await connection.send(response(50, 'connection'))
                elif event == 100:
                    size = int.from_bytes(raw[8:12], 'big')
                    await connection.send(response(150, raw[12:12+size].decode(), {'dialog_id':'soak-fixture'}))
        except websockets.ConnectionClosed:
            pass
    sampler = asyncio.create_task(sample())
    try:
        async with websockets.serve(provider, '127.0.0.1', 0) as upstream:
            endpoint = 'ws://127.0.0.1:' + str(upstream.sockets[0].getsockname()[1])
            async def transport(url, **kwargs):
                assert url == ENDPOINT
                return await websockets.connect(endpoint, **kwargs)
            def adapter(**kwargs):
                return VoiceProviderAdapter(**kwargs, transport_factory=transport)
            async def decision(prompt):
                return '{"answer":true,"delay_seconds":4,"opening_text":""}'
            async def route(connection):
                call = next(item for item in calls if connection.request.path == '/' + item.call_id)
                gateway = VoiceGatewaySession(socket=ClientSocket(connection), call=call, cache=cache,
                    session_factory=factory, adapter_factory=adapter, context_builder=formal_pack, decision_model=decision)
                gateways[call.call_id] = gateway
                try:
                    assert await gateway.leases.acquire(user_id=call.user_id,call_id=call.call_id,
                        ttl_ms=config['concurrency']['user_lock_ttl_ms'],global_limit=3) == (True,'acquired')
                    await gateway.run()
                except Exception as exc:
                    failures.append({'type':type(exc).__name__,
                        'db_code':getattr(getattr(exc, 'orig', None), 'args', [None])[0],
                        'frames':traceback.format_tb(exc.__traceback__)})
                    async with factory() as diagnostic:
                        status = (await diagnostic.execute(text('SHOW ENGINE INNODB STATUS'))).first()[2]
                        # Only lock/index descriptions; exclude queries, row bytes and identities.
                        report['deadlock_locks'] = [line for line in status.splitlines()
                            if ('RECORD LOCKS' in line or 'HOLDS THE LOCK' in line
                                or 'WAITING FOR THIS LOCK' in line or 'ROLL BACK TRANSACTION' in line)]
            async with websockets.serve(route, '127.0.0.1', 0) as server:
                root = 'ws://127.0.0.1:' + str(server.sockets[0].getsockname()[1])
                async def client(call):
                    async with websockets.connect(root+'/'+call.call_id) as connection:
                        async def transmit():
                            seq = 0
                            while True:
                                seq += 1
                                frame = {'v':1,'seq':seq,'type':'microphone_state','muted':True,'available':True} if seq == 1 else {'v':1,'seq':seq,'type':'heartbeat'}
                                raw = json.dumps(frame)
                                await connection.send(raw)
                                counters['client_sent_bytes'] += len(raw.encode())
                                await asyncio.sleep(2)
                        sending = asyncio.create_task(transmit())
                        try:
                            async for raw in connection:
                                counters['client_received_bytes'] += len(raw.encode())
                                frame = json.loads(raw)
                                if frame.get('type') == 'state' and frame.get('status') == 'connected':
                                    connected_at[call.call_id] = time.monotonic()
                        finally:
                            closed_at[call.call_id] = time.monotonic()
                            sending.cancel()
                            await asyncio.gather(sending, return_exceptions=True)
                await asyncio.wait_for(asyncio.gather(*(client(call) for call in calls)), duration+45)
                await asyncio.wait_for(asyncio.gather(*(g.closed_event.wait() for g in gateways.values())), 15)
        assert failures == [] and len(gateways) == len(connected_at) == 3
        outcomes = []
        async with factory() as db:
            for call in calls:
                row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call.call_id))
                ledgers = list(await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.call_id == call.call_id)))
                assert row.status == 'ended' and row.end_reason == 'hard_limit'
                elapsed = closed_at[call.call_id]-connected_at[call.call_id]
                assert duration-1 <= elapsed <= duration+15
                assert len(ledgers) == 1 and duration-1 <= row.free_seconds_used <= duration+2
                assert await cache.get(VoiceLeaseService.user_key(call.user_id)) is None
                assert call.call_id not in local_voice_calls
                outcomes.append({'status':row.status,'end_reason':row.end_reason,'free_seconds_used':row.free_seconds_used,
                    'wall_seconds':elapsed,'ledger_count':len(ledgers)})
        assert factory.kw['bind'].pool.checkedout() == 0
        report.update(result='passed', outcomes=outcomes, counters=counters,
            final_pool_checked_out=0, elapsed_seconds=time.monotonic()-started)
    except BaseException as exc:
        report.update(result='failed',error_type=type(exc).__name__)
        raise
    finally:
        report['gateway_failures'] = failures
        sampler.cancel()
        await asyncio.gather(sampler,return_exceptions=True)
        for gateway in gateways.values():
            if not gateway.closed_event.is_set():
                await gateway.stop_local()
        save()
