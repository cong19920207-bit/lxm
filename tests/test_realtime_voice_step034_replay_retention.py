"""Exact replay-record expiry, fixed candidate IDs, atomic retry and pagination."""
from datetime import datetime,timedelta
import pytest
import pytest_asyncio
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoiceCallCreateIdempotency
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage


@pytest_asyncio.fixture
async def replay_env(card_env):
    factory,call_id=card_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceCallCreateIdempotency.__table__])
    now=datetime(2026,9,14,4)
    async with factory() as db:
        rows=[]
        for index,offset in enumerate([-1,0,1]):
            row=VoiceCallCreateIdempotency(user_id=1,idempotency_key=f'replay-{index}',
                request_payload_sha256=str(index)*64,replay_expires_at=now+timedelta(seconds=offset),
                created_at=now-timedelta(hours=24))
            db.add(row);rows.append(row)
        await db.commit();ids=[row.id for row in rows]
    try:yield factory,call_id,now,ids
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=[VoiceCallCreateIdempotency.__table__])


@pytest.mark.asyncio
async def test_replay_expiry_exact_ids_and_call_metadata_survive(replay_env):
    from backend.services.realtime_voice_retention_service import VoiceRetentionService
    factory,call_id,now,ids=replay_env
    service=VoiceRetentionService(session_factory=factory)
    result=await service.purge_replays(now=now,limit=1)
    assert result['candidate_ids']==result['deleted_ids']==ids[:1]
    next_result=await service.purge_replays(now=now,after_id=result['next_cursor'],limit=1)
    assert next_result['candidate_ids']==next_result['deleted_ids']==ids[1:2]
    assert (await service.purge_replays(now=now))['deleted_ids']==[]
    async with factory() as db:
        rows=list((await db.scalars(select(VoiceCallCreateIdempotency))).all())
        assert [(r.id,r.replay_expires_at,r.request_payload_sha256) for r in rows]==[(ids[2],now+timedelta(seconds=1),'2'*64)]
        assert await db.scalar(select(VoiceCall.call_id).where(VoiceCall.call_id==call_id))==call_id


@pytest.mark.asyncio
async def test_replay_delete_failure_rolls_back_then_same_batch_retries(replay_env,monkeypatch):
    from backend.services.realtime_voice_retention_service import VoiceRetentionService
    from sqlalchemy.ext.asyncio import AsyncSession
    factory,_,now,ids=replay_env
    original=AsyncSession.delete;calls=[]
    async def fail_second(db,row):
        calls.append(row.id)
        if len(calls)==2:raise RuntimeError('controlled delete failure')
        return await original(db,row)
    monkeypatch.setattr(AsyncSession,'delete',fail_second)
    service=VoiceRetentionService(session_factory=factory)
    with pytest.raises(RuntimeError):await service.purge_replays(now=now)
    async with factory() as db:
        assert list((await db.scalars(select(VoiceCallCreateIdempotency.id).order_by(VoiceCallCreateIdempotency.id))).all())==ids
    monkeypatch.setattr(AsyncSession,'delete',original)
    assert (await service.purge_replays(now=now))['deleted_ids']==ids[:2]
