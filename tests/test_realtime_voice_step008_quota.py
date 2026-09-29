"""STEP-008 server quota acceptance."""
import importlib.util
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

import backend.models
from backend.database import Base
from backend.models.user import User
from backend.models.realtime_voice import VoiceCall, VoiceQuotaAccount, VoiceUsageLedger

NOW = datetime(2026, 9, 9, 6, tzinfo=timezone.utc)


def api():
    name = 'backend.services.realtime_voice_quota_service'
    assert importlib.util.find_spec(name), 'STEP-008 quota implementation missing'
    from backend.services import realtime_voice_quota_service
    return realtime_voice_quota_service


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[User.__table__, VoiceCall.__table__, VoiceQuotaAccount.__table__, VoiceUsageLedger.__table__])
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id=1, username='quota', password_hash='unused'))
        await session.commit()
        yield session
    await engine.dispose()


async def call(db):
    row = VoiceCall(call_id=str(uuid4()), user_id=1, initiated_by='user', status='connected',
                    summary_status='pending', config_snapshot={}, capability_snapshot={},
                    transcript_retention_days=180, generated_retention_days=30)
    db.add(row)
    await db.commit()
    return row


class Cache:
    def __init__(self): self.data = {}
    async def set(self, k, v, **kwargs): self.data[k] = v; return True
    async def get(self, k): return self.data.get(k)
    async def delete(self, k): return self.data.pop(k, None)
    async def eval(self, script, count, key, value):
        import json
        old = json.loads(self.data[key]) if key in self.data else None
        new = json.loads(value)
        if old:
            if old['user_id'] != new['user_id']: return -1
            if old['last_monotonic'] > new['last_monotonic']: return 0
            if old['last_monotonic'] == new['last_monotonic'] and self.data[key] != value: return -1
        self.data[key] = value
        return 1


@pytest.mark.asyncio
async def test_preflight_balance_is_read_only_even_on_new_day(db):
    s = api().VoiceQuotaService()
    assert (await s.balance(db, 1, daily_seconds=300, now=NOW)).total == 300
    assert await db.scalar(select(func.count()).select_from(VoiceQuotaAccount)) == 0
    assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0


@pytest.mark.asyncio
async def test_only_connected_time_charged_once_free_then_extra(db):
    m = api()
    row = await call(db)
    db.add(VoiceQuotaAccount(user_id=1, free_quota_date=NOW.date(), free_remaining_seconds=50, extra_remaining_seconds=30, version=1))
    await db.commit()
    meter = m.ConnectedMeter(call_id=row.call_id, user_id=1, daily_seconds=300, grace_limit=30)
    s = m.VoiceQuotaService()
    await s.observe(db, meter, connected=False, monotonic=0, now=NOW)
    await s.observe(db, meter, connected=True, monotonic=10, now=NOW+timedelta(seconds=10))
    await s.observe(db, meter, connected=False, monotonic=75, now=NOW+timedelta(seconds=75))
    await s.observe(db, meter, connected=True, monotonic=95, now=NOW+timedelta(seconds=95))
    assert (await s.balance(db, 1, daily_seconds=300, now=NOW)).total == 80  # no pre-debit
    first = await s.settle(db, meter)
    await db.commit()
    assert first['free_seconds_used'] == 50 and first['extra_seconds_used'] == 15
    assert (await s.balance(db, 1, daily_seconds=300, now=NOW)).total == 15
    repeated = await s.settle(db, meter)
    await db.commit()
    assert repeated['idempotent']
    assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1
    assert row.growth_eligible_seconds == 65


@pytest.mark.asyncio
async def test_grace_once_wall_clock_continues_while_reconnecting(db):
    m = api(); row = await call(db)
    meter = m.ConnectedMeter(call_id=row.call_id, user_id=1, daily_seconds=5, grace_limit=30)
    s = m.VoiceQuotaService()
    await s.observe(db, meter, connected=True, monotonic=0, now=NOW)
    state = await s.observe(db, meter, connected=False, monotonic=8, now=NOW+timedelta(seconds=8))
    assert state['in_grace'] and state['grace_seconds'] == 3
    state = await s.observe(db, meter, connected=True, monotonic=35, now=NOW+timedelta(seconds=35))
    assert state['must_end'] and state['grace_seconds'] == 30
    await s.settle(db, meter)
    await db.commit()
    assert (await s.balance(db, 1, daily_seconds=5, now=NOW)).total == 0
    assert row.grace_seconds == 30 and row.growth_eligible_seconds == 5
    grace = (await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.usage_type == 'grace'))).all()
    assert sum(r.duration_seconds for r in grace) == 30
    assert all(r.free_seconds_used == r.extra_seconds_used == 0 for r in grace)


@pytest.mark.asyncio
async def test_checkpoint_crash_recovery_uses_last_server_observation(db):
    m = api(); row = await call(db); cache = Cache()
    s = m.VoiceQuotaService()
    meter = m.ConnectedMeter(call_id=row.call_id, user_id=1, daily_seconds=300, grace_limit=30)
    await s.observe(db, meter, connected=True, monotonic=100, now=NOW)
    await s.observe(db, meter, connected=True, monotonic=117, now=NOW+timedelta(seconds=17))
    await s.checkpoint(cache, meter)
    result = await s.recover(db, cache, call_id=row.call_id, user_id=1)
    await db.commit()
    assert result['free_seconds_used'] == 17
    assert (await s.recover(db, cache, call_id=row.call_id, user_id=1))['idempotent']
    assert all(k.startswith('voice:quota:') for k in cache.data)


@pytest.mark.asyncio
async def test_midnight_splits_usage_without_carrying_free_pool(db):
    m = api(); row = await call(db); s = m.VoiceQuotaService()
    before = datetime(2026,9,9,15,59,58,tzinfo=timezone.utc)
    meter = m.ConnectedMeter(call_id=row.call_id, user_id=1, daily_seconds=300, grace_limit=30)
    await s.observe(db, meter, connected=True, monotonic=0, now=before)
    await s.observe(db, meter, connected=False, monotonic=5, now=before+timedelta(seconds=5))
    await s.settle(db, meter)
    await db.commit()
    balance = await s.balance(db, 1, daily_seconds=300, now=before+timedelta(seconds=5))
    assert balance.free == 297
    rows = (await db.scalars(select(VoiceUsageLedger).order_by(VoiceUsageLedger.segment_seq))).all()
    assert [x.free_seconds_used for x in rows] == [2,3]


@pytest.mark.asyncio
async def test_settlement_rollback_restores_all_money_and_rows(db):
    m = api(); row = await call(db); s = m.VoiceQuotaService()
    meter = m.ConnectedMeter(call_id=row.call_id,user_id=1,daily_seconds=300,grace_limit=30)
    await s.observe(db,meter,connected=True,monotonic=0,now=NOW)
    await s.observe(db,meter,connected=False,monotonic=9,now=NOW+timedelta(seconds=9))
    await s.settle(db,meter)
    await db.rollback()
    assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0
    assert (await s.balance(db,1,daily_seconds=300,now=NOW)).total == 300


@pytest.mark.asyncio
async def test_final_difference_after_committed_checkpoint_does_not_reserve_twice(db):
    m = api(); row = await call(db); s = m.VoiceQuotaService()
    meter = m.ConnectedMeter(row.call_id, 1, 10, 30)
    await s.observe(db, meter, connected=True, monotonic=0, now=NOW)
    await s.observe(db, meter, connected=True, monotonic=4, now=NOW+timedelta(seconds=4))
    await s.settle(db, meter); await db.commit()
    state = await s.observe(db, meter, connected=True, monotonic=6, now=NOW+timedelta(seconds=6))
    assert not state['in_grace']
    await s.settle(db, meter); await db.commit()
    assert (await s.balance(db, 1, daily_seconds=10, now=NOW)).free == 4
    assert row.growth_eligible_seconds == 6


@pytest.mark.asyncio
async def test_exact_midnight_exhaustion_uses_new_pool_before_grace(db):
    m = api(); row = await call(db); s = m.VoiceQuotaService()
    before = datetime(2026, 9, 9, 15, 59, 58, tzinfo=timezone.utc)
    meter = m.ConnectedMeter(row.call_id, 1, 2, 30)
    await s.observe(db, meter, connected=True, monotonic=0, now=before)
    state = await s.observe(db, meter, connected=True, monotonic=3, now=before+timedelta(seconds=3))
    assert not state['in_grace']
    await s.settle(db, meter); await db.commit()
    assert row.free_seconds_used == 3 and row.grace_seconds == 0
    assert (await s.balance(db, 1, daily_seconds=2, now=before+timedelta(seconds=3))).free == 1


@pytest.mark.asyncio
async def test_fractional_heartbeats_duplicate_and_out_of_order_do_not_inflate_usage(db):
    from dataclasses import asdict
    m = api(); row = await call(db); s = m.VoiceQuotaService()
    meter = m.ConnectedMeter(row.call_id, 1, 300, 30)
    for n in range(21):
        await s.observe(db, meter, connected=True, monotonic=n/10, now=NOW+timedelta(seconds=n/10))
    before = asdict(meter)
    with pytest.raises(m.QuotaError, match='out_of_order'):
        await s.observe(db, meter, connected=True, monotonic=1.9, now=NOW+timedelta(seconds=1.9))
    assert asdict(meter) == before
    await s.observe(db, meter, connected=True, monotonic=2, now=NOW+timedelta(seconds=2))
    await s.settle(db, meter); await db.commit()
    assert row.free_seconds_used == 2


@pytest.mark.asyncio
async def test_grace_already_started_does_not_restart_at_midnight(db):
    m = api(); row = await call(db); s = m.VoiceQuotaService()
    before = datetime(2026, 9, 9, 15, 59, 58, tzinfo=timezone.utc)
    meter = m.ConnectedMeter(row.call_id, 1, 1, 30)
    await s.observe(db, meter, connected=True, monotonic=0, now=before)
    state = await s.observe(db, meter, connected=True, monotonic=40, now=before+timedelta(seconds=40))
    assert state['must_end'] and state['grace_seconds'] == 30
    await s.settle(db, meter); await db.commit()
    assert row.free_seconds_used == 1 and row.grace_seconds == 30


@pytest.mark.asyncio
async def test_recovery_rollback_keeps_checkpoint_and_time_domain_is_isolated(db):
    from sqlalchemy import event
    m = api(); row = await call(db); cache = Cache(); metrics = []; sql = []
    engine = db.bind.sync_engine
    def observed(conn, cursor, statement, parameters, context, many): sql.append(statement.lower())
    event.listen(engine, 'before_cursor_execute', observed)
    try:
        s = m.VoiceQuotaService(metric=lambda name, value: metrics.append((name, value)))
        meter = m.ConnectedMeter(row.call_id, 1, 300, 30)
        await s.observe(db, meter, connected=True, monotonic=0, now=NOW)
        await s.observe(db, meter, connected=True, monotonic=7, now=NOW+timedelta(seconds=7))
        await s.checkpoint(cache, meter)
        call_id = meter.call_id
        await s.recover(db, cache, call_id=call_id, user_id=1); await db.rollback()
        result = await s.recover(db, cache, call_id=call_id, user_id=1); await db.commit()
        assert result['free_seconds_used'] == 7
        import re
        tables = set(re.findall(r'\b(?:from|join|update|into)\s+([a-z_]+)', '\n'.join(sql)))
        assert tables <= {'users', 'voice_call', 'voice_quota_account', 'voice_usage_ledger'}
        assert metrics and all(name.startswith('voice.quota.') for name, _ in metrics)
    finally:
        event.remove(engine, 'before_cursor_execute', observed)
