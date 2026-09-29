"""Cut real MySQL TCP traffic, then retry finalization against the same stores."""
import asyncio
import os
from datetime import datetime, timezone, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger, VoiceQuotaAccount
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_quota_service import VoiceQuotaService, ConnectedMeter
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step037_redis_fault_runtime import RedisLink

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated MySQL link drill')


@pytest.mark.asyncio
async def test_mysql_tcp_loss_preserves_retryable_call_and_no_partial_settlement(runtime):
    factory, call_id, cache = runtime
    direct_engine = factory.kw['bind']
    async with direct_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Relationship.__table__, RelationshipGrowthLog.__table__])
    # The existing raw TCP relay is protocol-neutral; no MySQL messages mocked.
    link = RedisLink(direct_engine.url.port)
    server = await asyncio.start_server(link.accept, '127.0.0.1', 0)
    engine = create_async_engine(direct_engine.url.set(port=server.sockets[0].getsockname()[1]),
        hide_parameters=True, pool_pre_ping=True, connect_args={'connect_timeout': 1})
    proxied = async_sessionmaker(engine, expire_on_commit=False)
    meter = ConnectedMeter(call_id, 1, 300, 30)
    stopped = asyncio.Event()
    async def stop():
        stopped.set()
    service = VoiceOpsService(cache=cache, session_factory=proxied)
    leases = VoiceLeaseService(cache, end_call=service.end_call)
    async def projection():
        async with factory() as db:
            return {model.__tablename__: [{column.name: getattr(row, column.name) for column in model.__table__.columns}
                for row in await db.scalars(sa.select(model).order_by(model.id))]
                for model in (VoiceCall, VoiceUsageLedger, VoiceQuotaAccount, RelationshipGrowthLog)}
    try:
        async with engine.connect() as conn:
            assert await conn.scalar(sa.text('SELECT 1')) == 1
        assert await leases.acquire(user_id=1, call_id=call_id, ttl_ms=60000, global_limit=10) == (True, 'acquired')
        now = datetime.now(timezone.utc)
        async with factory() as db:
            quota = VoiceQuotaService()
            await quota.observe(db, meter, connected=True, monotonic=0, now=now)
            await quota.observe(db, meter, connected=True, monotonic=9, now=now+timedelta(seconds=9))
            await quota.checkpoint(cache, meter)
        local_voice_calls[call_id] = LocalVoiceCall(meter, stop)
        before = await projection()
        link.disconnect()
        with pytest.raises(sa.exc.DBAPIError):
            await asyncio.wait_for(service.end_call(call_id=call_id, user_id=1, reason='system_error'), 10)
        assert stopped.is_set()
        assert await projection() == before
        assert call_id in local_voice_calls  # Retained until the finalizer commits.
        assert await cache.get(leases.user_key(1)) == call_id
        assert await cache.get('voice:quota:' + call_id) is not None
        link.cut = False
        result = await service.end_call(call_id=call_id, user_id=1, reason='system_error')
        assert result == dict(call_id=call_id, changed=True, cleanup_pending=False)
        async with factory() as db:
            row = await db.scalar(sa.select(VoiceCall).where(VoiceCall.call_id == call_id))
            assert (row.status, row.end_reason, row.free_seconds_used) == ('ended', 'system_error', 9)
            assert len(list(await db.scalars(sa.select(VoiceUsageLedger)))) == 1
            assert (await db.scalar(sa.select(VoiceQuotaAccount))).free_remaining_seconds == 291
        settled = await projection()
        assert (await service.end_call(call_id=call_id, user_id=1))['changed'] is False
        assert await projection() == settled
        assert call_id not in local_voice_calls
        assert await cache.get(leases.user_key(1)) is None
        assert await cache.zscore(leases.active_key, call_id) is None
        assert await cache.hget(leases.owners_key, call_id) is None
    finally:
        local_voice_calls.pop(call_id, None)
        await engine.dispose()
        server.close()
        await server.wait_closed()
        link.disconnect()
        await asyncio.gather(*tuple(link.tasks), return_exceptions=True)
