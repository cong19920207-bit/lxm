"""Real TCP cut/restore to disposable Redis while MySQL remains available."""
import asyncio
import os
from datetime import datetime, timezone, timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger, VoiceQuotaAccount
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.services.realtime_voice_local_runtime import LocalVoiceCall, local_voice_calls
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_quota_service import VoiceQuotaService, ConnectedMeter
from tests.test_realtime_voice_m4_runtime import containers, runtime

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated TCP fault drill')


class RedisLink:
    def __init__(self, port):
        self.port, self.cut, self.writers, self.tasks = port, False, set(), set()

    async def accept(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        upstream = None
        pumps = []
        try:
            self.writers.add(writer)
            if self.cut:
                return
            remote, upstream = await asyncio.open_connection('127.0.0.1', self.port)
            self.writers.add(upstream)
            async def pipe(source, target):
                while data := await source.read(65536):
                    target.write(data)
                    await target.drain()
            pumps = [asyncio.create_task(pipe(reader, upstream)), asyncio.create_task(pipe(remote, writer))]
            await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for pump in pumps:
                pump.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            for connection in (writer, upstream):
                if connection is not None:
                    connection.close()
                    try:
                        await connection.wait_closed()
                    except (ConnectionError, OSError):
                        pass
                    self.writers.discard(connection)
            self.tasks.discard(task)

    def disconnect(self):
        self.cut = True
        for writer in tuple(self.writers):
            writer.close()


@pytest.mark.asyncio
async def test_redis_tcp_loss_stops_local_call_then_reconciles_without_second_charge(runtime):
    factory, call_id, direct = runtime
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Relationship.__table__, RelationshipGrowthLog.__table__])
    link = RedisLink(direct.connection_pool.connection_kwargs['port'])
    server = await asyncio.start_server(link.accept, '127.0.0.1', 0)
    client = Redis(host='127.0.0.1', port=server.sockets[0].getsockname()[1],
        decode_responses=True, socket_timeout=.3, socket_connect_timeout=.3)
    meter = ConnectedMeter(call_id, 1, 300, 30)
    stops, results = [], []
    async def stop():
        stops.append('stopped')
    service = VoiceOpsService(cache=client, session_factory=factory)
    async def terminate(**kwargs):
        results.append(await service.end_call(**kwargs))
    leases = VoiceLeaseService(client, end_call=terminate)
    try:
        assert await client.ping()
        assert await leases.acquire(user_id=1, call_id=call_id, ttl_ms=60000, global_limit=10) == (True, 'acquired')
        now = datetime.now(timezone.utc)
        async with factory() as db:
            quota = VoiceQuotaService()
            await quota.observe(db, meter, connected=True, monotonic=0, now=now)
            await quota.observe(db, meter, connected=True, monotonic=9, now=now + timedelta(seconds=9))
        await client.set('voice:session_context:' + call_id, 'synthetic-private')
        await direct.set('voice:session_context:control', 'preserve')
        local_voice_calls[call_id] = LocalVoiceCall(meter, stop)
        link.disconnect()
        # Allow this client's bounded retry/backoff across all cleanup commands;
        # this guard is not a product recovery-latency acceptance threshold.
        assert await asyncio.wait_for(leases.renew(user_id=1, call_id=call_id, ttl_ms=60000), 45) is False
        assert stops == ['stopped']
        assert results == [dict(call_id=call_id, changed=True, cleanup_pending=True)]
        assert call_id not in local_voice_calls
        # Redis kept its data during the transport fault; cleanup really is pending.
        assert await direct.get(leases.user_key(1)) == call_id
        assert await direct.get('voice:session_context:' + call_id) == 'synthetic-private'

        async def projection():
            async with factory() as db:
                return {model.__tablename__: [{col.name: getattr(row, col.name) for col in model.__table__.columns}
                    for row in await db.scalars(select(model).order_by(model.id))]
                    for model in (VoiceCall, VoiceUsageLedger, VoiceQuotaAccount, RelationshipGrowthLog)}
        before = await projection()
        async with factory() as db:
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            assert (row.status, row.end_reason, row.free_seconds_used) == ('ended', 'system_error', 9)
            assert len(list(await db.scalars(select(VoiceUsageLedger)))) == 1
            assert (await db.scalar(select(VoiceQuotaAccount))).free_remaining_seconds == 291
        link.cut = False
        assert await client.ping()
        await service.reconcile()
        await service.reconcile()
        assert await projection() == before
        assert await direct.get(leases.user_key(1)) is None
        assert await direct.zscore(leases.active_key, call_id) is None
        assert await direct.hget(leases.owners_key, call_id) is None
        assert await direct.get('voice:session_context:' + call_id) is None
        assert await direct.get('voice:session_context:control') == 'preserve'
    finally:
        local_voice_calls.pop(call_id, None)
        await client.aclose()
        server.close()
        await server.wait_closed()
        link.disconnect()
        await asyncio.gather(*tuple(link.tasks), return_exceptions=True)
