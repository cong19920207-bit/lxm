"""Different-device admission against disposable MySQL/Redis, no Provider I/O."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, func

from backend.database import Base
from backend.models.user import User
from backend.models.realtime_voice import (
    VoiceCall, VoiceCallCreateIdempotency, VoiceQuotaAccount, VoiceUsageLedger,
)
from backend.services.realtime_voice_create_service import VoiceCreateService, VoicePreflightError
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec, consume_voice_ticket
from tests.test_realtime_voice_step010_create import Loader
from tests.test_realtime_voice_m4_runtime import containers, runtime

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='disposable MySQL/Redis opt-in',
)


@pytest.mark.asyncio
async def test_different_devices_and_keys_admit_one_call_without_loser_side_effects(runtime):
    factory, _, cache = runtime
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[VoiceCallCreateIdempotency.__table__])
    async with factory() as db:
        db.add(User(id=2, username='two-devices', password_hash='not-a-login'))
        await db.commit()
    loader = Loader()
    loader.bundle.value['global']['rollout']['user_ids'] = [2]
    async def health(config):
        return True
    async def end(**kwargs):
        pytest.fail('admission must not terminate a call')
    leases = VoiceLeaseService(cache, end_call=end)
    codec = VoiceTicketCodec(b'm8-isolated-ticket-key-material!!')
    service = VoiceCreateService(loader=loader, cache=cache, leases=leases,
        ticket_codec=codec, provider_preflight=health)
    payloads = [dict(source='home', device_id=str(uuid4()),
                    browser_supported=True, microphone_granted=True) for _ in range(2)]
    keys = [str(uuid4()) for _ in range(2)]
    barrier = asyncio.Barrier(2)
    now = datetime.now(timezone.utc)

    async def dial(index):
        async with factory() as db:
            # Both transactions establish a stale repeatable-read view first.
            await db.scalar(select(func.count()).select_from(VoiceCall))
            await asyncio.wait_for(barrier.wait(), 5)
            try:
                result = await service.create(db, user_id=2, idempotency_key=keys[index],
                    payload=payloads[index], now=now)
                return index, result
            except VoicePreflightError as exc:
                assert exc.reason == 'user_busy'
                return index, None

    results = await asyncio.wait_for(asyncio.gather(dial(0), dial(1)), 15)
    winners = [(i, result) for i, result in results if result is not None]
    assert len(winners) == 1
    index, winner = winners[0]
    async with factory() as db:
        calls = list(await db.scalars(select(VoiceCall).where(VoiceCall.user_id == 2)))
        records = list(await db.scalars(select(VoiceCallCreateIdempotency).where(
            VoiceCallCreateIdempotency.user_id == 2)))
        assert len(calls) == len(records) == 1
        assert calls[0].call_id == records[0].call_id == winner['call_id']
        assert calls[0].status == 'deciding' and calls[0].sort_seq is None
        assert records[0].idempotency_key == keys[index]
        assert await db.scalar(select(func.count()).select_from(VoiceQuotaAccount).where(
            VoiceQuotaAccount.user_id == 2)) == 0
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger).where(
            VoiceUsageLedger.call_id == winner['call_id'])) == 0
        consumed = await consume_voice_ticket(db, codec=codec, cache=cache, leases=leases,
            ticket=winner['call_ticket'], call_id=winner['call_id'],
            device_id=payloads[index]['device_id'], now=now)
        assert consumed.call_id == winner['call_id']
    assert await cache.get(leases.user_key(2)) == winner['call_id']
    assert await cache.zrange(leases.active_key, 0, -1) == [winner['call_id']]
    assert await cache.hgetall(leases.owners_key) == {winner['call_id']: '2'}
