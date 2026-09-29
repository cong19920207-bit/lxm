"""Opt-in integration against disposable, fixed local ports; no business DB."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.database import Base
from backend.models.user import User
from backend.models.realtime_voice import VoiceCall, VoiceQuotaAccount, VoiceUsageLedger, VoiceCallTurn, VoiceCrisisRecord
from backend.services.realtime_voice_state_service import transition_call
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from tests.test_realtime_voice_step009_ops import add_call, StateCache

pytestmark = pytest.mark.skipif(os.getenv('VOICE_M3_ISOLATED_RUNTIME') != '1',
                              reason='requires explicitly started disposable M3 containers')


@pytest_asyncio.fixture
async def runtime():
    engine = create_async_engine('mysql+asyncmy://root@127.0.0.1:13316/voice_m3_test', pool_size=16)
    cache = Redis(host='127.0.0.1', port=16386, decode_responses=True)
    async with engine.begin() as conn:
        assert await conn.scalar(text('SELECT DATABASE()')) == 'voice_m3_test'
        await conn.run_sync(Base.metadata.create_all, tables=[m.__table__ for m in
            (User, VoiceCall, VoiceQuotaAccount, VoiceUsageLedger, VoiceCallTurn, VoiceCrisisRecord)])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        if await db.get(User, 1) is None:
            db.add(User(id=1, username='isolated-m3', password_hash='not-a-login'))
            await db.commit()
    try:
        yield factory, cache
    finally:
        await cache.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_mysql_concurrent_terminal_claim_from_old_snapshots_settles_once(runtime):
    factory, cache = runtime
    fake = StateCache()
    call_id = await add_call(factory, 'connected', fake)
    await cache.set('voice:quota:'+call_id, fake.data['voice:quota:'+call_id], ex=60)
    leases = VoiceLeaseService(cache, end_call=VoiceOpsService(cache=cache, session_factory=factory).end_call)
    assert await leases.acquire(user_id=1, call_id=call_id, ttl_ms=60000, global_limit=10) == (True, 'acquired')
    barrier = asyncio.Barrier(12)
    @asynccontextmanager
    async def old_snapshot_factory():
        async with factory() as db:
            await db.scalar(select(func.count()).select_from(VoiceCall))
            await barrier.wait()
            yield db
    service = VoiceOpsService(cache=cache, session_factory=old_snapshot_factory)
    results = await asyncio.gather(*(service.end_call(call_id=call_id, reason='hard_limit') for _ in range(12)))
    assert sum(r['changed'] for r in results) == 1
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert (row.status, row.end_reason, row.free_seconds_used) == ('ended','hard_limit',9)
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger).where(VoiceUsageLedger.call_id == call_id)) == 1
    assert not await cache.exists(leases.user_key(1))
    assert await cache.zscore(leases.active_key, call_id) is None
    assert not any(r['cleanup_pending'] for r in results)


@pytest.mark.asyncio
async def test_mysql_competing_connect_and_preconnection_hard_stop_cannot_resurrect(runtime):
    factory, cache = runtime
    call_id = await add_call(factory, 'ringing', StateCache())
    # End first while another connection already has an old repeatable-read view.
    async with factory() as stale:
        await stale.scalar(select(func.count()).select_from(VoiceCall))
        await VoiceOpsService(cache=cache, session_factory=factory).end_call(call_id=call_id)
        assert not await transition_call(stale, call_id=call_id, expected=('ringing',), target='connected', now=datetime.now(timezone.utc))
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert (row.status,row.connected_at,row.summary_status)==('failed',None,'not_applicable')


@pytest.mark.asyncio
async def test_mysql_concurrent_turn_allocation_and_crisis_transaction(runtime):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    from tests.test_realtime_voice_step015_turns import Gate, event
    factory, _ = runtime
    call_id=await add_call(factory,'connected',StateCache())
    async def consume(index, gate):
        service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate)
        await service.consume(event(call_id,1,'asr_final','fixture-'+str(index),question='q'+str(index)))
    await asyncio.gather(*(consume(i,Gate()) for i in range(12)))
    await asyncio.gather(consume(12,Gate('matched')),consume(12,Gate('matched')))
    await consume(13,Gate('suspected',fail=True))
    async with factory() as db:
        rows=(await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id==call_id).order_by(VoiceCallTurn.turn_index))).all()
        assert [r.turn_index for r in rows]==list(range(1,15))
        isolated=list(await db.scalars(select(VoiceCrisisRecord).where(VoiceCrisisRecord.call_id==call_id)))
        assert len(isolated)==1 and isolated[0].content_plaintext=='fixture-12'
        matched=next(r for r in rows if r.question_id=='q12')
        failed=next(r for r in rows if r.question_id=='q13')
        assert matched.user_text_final is None and matched.user_crisis_status=='matched'
        assert failed.user_text_final is None and failed.user_crisis_status=='isolation_failed'


@pytest.mark.asyncio
async def test_mysql_reconnect_same_call_excludes_real_wall_window_and_preserves_anchor(runtime):
    from datetime import datetime, timezone
    from uuid import uuid4
    from backend.constants.realtime_voice_config import get_default_voice_call_config,get_default_voice_call_script
    from backend.services.realtime_voice_gateway_service import VoiceGatewaySession
    from backend.services.realtime_voice_ticket_service import VoiceTicketCodec
    from backend.services.realtime_voice_local_runtime import LocalVoiceCall,local_voice_calls
    from tests.test_realtime_voice_step019_reconnect import RebuildAdapter,formal_pack,Socket
    factory,cache=runtime
    config=get_default_voice_call_config({'config_key':'persona','version':1,'content_sha256':'sha256:'+'a'*64})
    anchor=datetime.now(timezone.utc).replace(tzinfo=None)
    async with factory() as db:
        row=VoiceCall(call_id=str(uuid4()),user_id=1,initiated_by='user',status='connected',connected_at=anchor,
            summary_status='pending',config_snapshot={'resolved_config':config,'resolved_script':get_default_voice_call_script()},
            capability_snapshot={},transcript_retention_days=180,generated_retention_days=30)
        db.add(row);await db.commit();await db.refresh(row)
        anchor=row.connected_at
    gateway=VoiceGatewaySession(socket=Socket(),call=row,cache=cache,session_factory=factory,
        adapter_factory=RebuildAdapter,context_builder=formal_pack,device_id='device',
        reconnect_codec=VoiceTicketCodec(b'x'*32,purpose='voice_reconnect_v1'))
    assert await gateway.leases.acquire(user_id=1,call_id=row.call_id,ttl_ms=15000,global_limit=10)==(True,'acquired')
    gateway.connected=True
    local_voice_calls[row.call_id]=LocalVoiceCall(gateway.meter,gateway.stop_local,final_flush=gateway.flush_turns)
    try:
        await gateway.observe(True);await asyncio.sleep(1.05)
        await gateway.reconnector.begin(client_lost=True)
        await asyncio.sleep(1.1)
        ticket=await gateway.reconnector.issue(user_id=1,device_id='device')
        await gateway.reconnector.attach(Socket(),ticket=ticket['call_ticket'],device_id='device')
        await gateway.reconnector.task
        assert gateway.connected and not gateway.stopped
        await asyncio.sleep(1.05)
        result=await gateway.ops.end_call(call_id=row.call_id,user_id=1,reason='user_hangup')
        assert result['changed']
        async with factory() as db:
            ended=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==row.call_id))
            assert ended.status=='ended' and ended.connected_at==anchor
            assert ended.free_seconds_used+ended.extra_seconds_used==2
            assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger).where(VoiceUsageLedger.call_id==row.call_id))==1
        assert not await cache.exists(gateway.leases.user_key(1))
    finally:
        local_voice_calls.pop(row.call_id,None)
        await gateway.stop_local()
