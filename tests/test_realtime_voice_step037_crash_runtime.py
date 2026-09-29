"""SIGKILL a real metering worker; recover its committed Redis checkpoint."""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger, VoiceQuotaAccount
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.services.realtime_voice_quota_service import VoiceQuotaService, ConnectedMeter
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from tests.test_realtime_voice_m4_runtime import containers, runtime

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated crash drill')


async def metering_worker():
    engine = create_async_engine(os.environ['VOICE_DRILL_DATABASE'], hide_parameters=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    cache = Redis(host='127.0.0.1', port=int(os.environ['VOICE_DRILL_REDIS_PORT']), decode_responses=True)
    call_id = os.environ['VOICE_DRILL_CALL']
    async def unexpected_end(**kwargs):
        raise AssertionError('worker must be killed before graceful finalization')
    leases = VoiceLeaseService(cache, end_call=unexpected_end)
    assert await leases.acquire(user_id=1, call_id=call_id, ttl_ms=10000, global_limit=10) == (True, 'acquired')
    meter = ConnectedMeter(call_id, 1, 300, 30)
    quota = VoiceQuotaService()
    async with factory() as db:
        await quota.observe(db, meter, connected=True, monotonic=time.monotonic(), now=datetime.now(timezone.utc))
        await asyncio.sleep(1.2)
        await quota.observe(db, meter, connected=True, monotonic=time.monotonic(), now=datetime.now(timezone.utc))
        await quota.checkpoint(cache, meter)
    seconds = sum(s['duration_seconds'] for s in meter.slices)
    print(json.dumps({'checkpoint_ready': True, 'seconds': seconds}), flush=True)
    await asyncio.Event().wait()  # Parent sends SIGKILL; no cleanup/finalizer runs.


@pytest.mark.asyncio
async def test_sigkill_worker_recovers_once_after_real_lease_expiry(runtime):
    factory, call_id, cache = runtime
    engine = factory.kw['bind']
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Relationship.__table__, RelationshipGrowthLog.__table__])
    env = {**os.environ, 'VOICE_DRILL_DATABASE': engine.url.render_as_string(hide_password=False),
        'VOICE_DRILL_REDIS_PORT': str(cache.connection_pool.connection_kwargs['port']), 'VOICE_DRILL_CALL': call_id}
    proc = await asyncio.create_subprocess_exec(sys.executable, '-c',
        'import asyncio; from tests.test_realtime_voice_step037_crash_runtime import metering_worker; asyncio.run(metering_worker())',
        env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        line = await asyncio.wait_for(proc.stdout.readline(), 15)
        ready = json.loads(line)
        assert ready['checkpoint_ready'] and ready['seconds'] >= 1
        checkpoint = await cache.get('voice:quota:' + call_id)
        assert checkpoint is not None
        proc.kill()
        assert await asyncio.wait_for(proc.wait(), 5) == -9
        leases = VoiceLeaseService(cache, end_call=VoiceOpsService(cache=cache, session_factory=factory).end_call)
        async def expiry():
            while await cache.exists(leases.user_key(1)):
                await asyncio.sleep(.1)
        await asyncio.wait_for(expiry(), 12)
        service = VoiceOpsService(cache=cache, session_factory=factory)
        assert await service.reconcile() >= 1

        async def projection():
            async with factory() as db:
                result = {}
                for model in (VoiceCall, VoiceUsageLedger, VoiceQuotaAccount, RelationshipGrowthLog):
                    result[model.__tablename__] = [
                        {col.name: getattr(row, col.name) for col in model.__table__.columns}
                        for row in await db.scalars(select(model).order_by(model.id))]
                return result
        before = await projection()
        async with factory() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            assert (row.status, row.end_reason) == ('ended', 'system_error')
            assert row.free_seconds_used == ready['seconds'] and row.extra_seconds_used == 0
            ledger = list(await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.call_id == call_id)))
            assert len(ledger) == 1 and ledger[0].duration_seconds == ready['seconds']
            account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
            assert account.free_remaining_seconds == 300 - ready['seconds']
        assert await service.reconcile() == 0
        replay = await service.end_call(call_id=call_id, user_id=1, reason='system_error')
        assert replay['changed'] is False
        assert await projection() == before
        assert await cache.get('voice:quota:' + call_id) == checkpoint
        assert await cache.get(leases.user_key(1)) is None
        assert await cache.zscore(leases.active_key, call_id) is None
        assert await cache.hget(leases.owners_key, call_id) is None
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
