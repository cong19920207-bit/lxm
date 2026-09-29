from datetime import timedelta
import pytest
from backend.services.realtime_voice_quota_service import VoiceQuotaService,ConnectedMeter,QuotaError
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step008_quota import db,call,NOW
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('rollback',[False,True])
async def test_quota_committed_slices_grace_and_replay(db,rollback):
    row=await call(db);call_id=row.call_id;sink=CounterCache();metrics=VoiceMetrics(sink)
    quota=VoiceQuotaService(metrics=metrics)
    meter=ConnectedMeter(call_id=call_id,user_id=1,daily_seconds=3,grace_limit=5)
    await quota.observe(db,meter,connected=True,monotonic=0,now=NOW)
    await quota.observe(db,meter,connected=True,monotonic=8,now=NOW+timedelta(seconds=8))
    await quota.observe(db,meter,connected=True,monotonic=9,now=NOW+timedelta(seconds=9))
    await quota.settle(db,meter)
    assert not any(e[0]=='voice.quota.usage_slice' for b in sink.batches for e in b)
    if rollback:await db.rollback()
    else:await db.commit()
    await flush_voice_metrics(db,metrics)
    events=[e for b in sink.batches for e in b]
    assert events.count(('voice.quota.balance_zero',{},1))==1
    assert events.count(('voice.quota.grace',{'result':'trigger'},1))==1
    assert events.count(('voice.quota.grace',{'result':'end'},1))==1
    if rollback:assert not any(e[0]=='voice.quota.usage_slice' for e in events)
    else:
        assert ('voice.quota.billing_input_seconds',{'source':'server'},3) in events
        assert ('voice.quota.grace_seconds',{},5) in events
        assert ('voice.quota.usage_slice',{'kind':'connected'},1) in events
        assert ('voice.quota.usage_slice',{'kind':'grace'},1) in events
        before=list(events);await quota.settle(db,meter);await db.commit();await flush_voice_metrics(db,metrics)
        assert [e for b in sink.batches for e in b]==before+[('voice.quota.deduplicated',{},1)]


@pytest.mark.asyncio
async def test_quota_conflict_is_classified_without_success(db):
    row=await call(db);sink=CounterCache();quota=VoiceQuotaService(metrics=VoiceMetrics(sink))
    meter=ConnectedMeter(call_id=row.call_id,user_id=1,daily_seconds=3,grace_limit=5)
    await quota.observe(db,meter,connected=True,monotonic=0,now=NOW)
    await quota.observe(db,meter,connected=False,monotonic=2,now=NOW+timedelta(seconds=2))
    await quota.settle(db,meter);await db.commit();await flush_voice_metrics(db,quota.metrics)
    meter.slices[0]['duration_seconds']=0
    with pytest.raises(QuotaError,match='settlement_checkpoint_conflict'):await quota.settle(db,meter)
    assert sink.batches[-1]==[('voice.quota.transaction_conflict',{'reason':'checkpoint'},1)]


@pytest.mark.asyncio
@pytest.mark.parametrize('code,expected',[(1213,True),(2006,False)])
async def test_database_conflict_is_not_a_generic_storage_outage(db,code,expected):
    from sqlalchemy.exc import DBAPIError
    sink=CounterCache();quota=VoiceQuotaService(metrics=VoiceMetrics(sink))
    async def fail(*args):raise DBAPIError(None,None,Exception(code,'private-error'))
    quota._settle=fail
    with pytest.raises(DBAPIError):await quota.settle(db,None)
    assert [e for b in sink.batches for e in b]==([('voice.quota.transaction_conflict',{'reason':'database'},1)] if expected else [])
