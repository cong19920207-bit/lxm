from datetime import datetime,timezone,date
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoiceMemoryJob,VoicePostprocessJob
from tests.test_realtime_voice_step009_ops import storage,add_call,StateCache


@pytest.mark.asyncio
@pytest.mark.parametrize('target',['ringing','missed','cancelled'])
@pytest.mark.parametrize('fallback',[True,False])
async def test_decision_fact_same_transition_and_replay_immutable(storage,target,fallback):
    from backend.services.realtime_voice_state_service import transition_call
    call=await add_call(storage,'deciding',StateCache())
    async with storage() as db:
        assert await transition_call(db,call_id=call,expected=('deciding',),target=target,
            now=datetime.now(timezone.utc),call01_fallback=fallback)
    async with storage() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        assert row.call01_fallback is fallback and row.status==target
        assert not await transition_call(db,call_id=call,expected=('deciding',),target=target,
            now=datetime.now(timezone.utc),call01_fallback=not fallback)
    async with storage() as db:
        assert (await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))).call01_fallback is fallback


@pytest.mark.asyncio
async def test_failed_commit_leaves_both_state_and_fact_unchanged(storage,monkeypatch):
    from backend.services.realtime_voice_state_service import transition_call
    call=await add_call(storage,'deciding',StateCache())
    async with storage() as db:
        async def fail():raise RuntimeError('commit failed')
        monkeypatch.setattr(db,'commit',fail)
        with pytest.raises(RuntimeError):
            await transition_call(db,call_id=call,expected=('deciding',),target='ringing',
                now=datetime.now(timezone.utc),call01_fallback=True)
        await db.rollback()
    async with storage() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        assert row.status=='deciding' and row.call01_fallback is None


@pytest.mark.asyncio
async def test_fallback_rate_legacy_unknown_and_known_cohort(storage):
    from backend.services.realtime_voice_daily_metric_service import compute_daily_metrics
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMemoryJob.__table__,VoicePostprocessJob.__table__])
    ids=[await add_call(storage,'cancelled',StateCache()) for _ in range(3)]
    async with storage() as db:
        rows=(await db.scalars(select(VoiceCall).where(VoiceCall.call_id.in_(ids)))).all()
        for row,value in zip(rows,[True,False,None]):
            row.created_at=datetime(2026,9,19);row.call01_fallback=value
        await db.commit()
        async def rate():return next(m for m in (await compute_daily_metrics(db,date(2026,9,19)))['metrics'] if m['name']=='call01_fallback_rate')
        assert (await rate())['value'] is None
        assert (await rate())['reason']=='unknown_call01_outcomes'
        rows[2].call01_fallback=False;await db.commit()
        assert (await rate())['value']==pytest.approx(1/3)
