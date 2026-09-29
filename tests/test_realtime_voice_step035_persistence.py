"""Daily rows replace a validated snapshot atomically and idempotently."""
from datetime import date
import hashlib,json
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceMetricDaily
from backend.services.realtime_voice_daily_metric_service import METRIC_NAMES
from tests.test_realtime_voice_step009_ops import storage


def projection(day,**changes):
    values={'daily_call_count':4,'connect_rate':.5,'missed_rate':.25,'failure_rate':.25,
        'avg_duration_seconds':80,'billable_seconds':150,'estimated_cost':1.5,'call01_fallback_rate':.25,
        'memory_success_rate':.75,'summary_success_rate':.5}
    values.update(changes)
    return {'date':day.isoformat(),'timezone':'Asia/Shanghai','formula_version':'voice-daily-v1',
        'metrics':[{'name':name,'value':values[name],'status':'measured','reason':None} for name in METRIC_NAMES]}


@pytest.mark.asyncio
async def test_full_ten_rows_exact_projection_and_repeat(storage,monkeypatch):
    from backend.services import realtime_voice_daily_aggregate_service as service
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    day=date(2026,9,19);expected=projection(day)
    async def compute(db,target):assert target==day;return expected
    monkeypatch.setattr(service,'compute_daily_metrics',compute)
    await service.aggregate_daily_metrics(storage,day)
    await service.aggregate_daily_metrics(storage,day)
    async with storage() as db:
        rows=(await db.scalars(select(VoiceMetricDaily))).all()
    dimensions={'timezone':'Asia/Shanghai','formula_version':'voice-daily-v1'}
    digest=hashlib.sha256(json.dumps(dimensions,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    actual=sorted((r.business_date,r.metric_name,r.dimension_hash,json.dumps(r.dimension_json,sort_keys=True),r.metric_value) for r in rows)
    assert actual==sorted((day,m['name'],digest,json.dumps(dimensions,sort_keys=True),m['value']) for m in expected['metrics'])


@pytest.mark.asyncio
async def test_unavailable_removes_stale_numeric_and_invalid_snapshot_rolls_back(storage,monkeypatch):
    from backend.services import realtime_voice_daily_aggregate_service as service
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    day=date(2026,9,19);current=projection(day)
    async def compute(db,target):return current
    monkeypatch.setattr(service,'compute_daily_metrics',compute)
    await service.aggregate_daily_metrics(storage,day)
    for row in current['metrics']:
        if row['name']=='estimated_cost':row.update(value=None,status='not_measurable',reason='price_unconfigured')
        if row['name']=='billable_seconds':row.update(status='provisional',reason='settlement_pending')
    await service.aggregate_daily_metrics(storage,day)
    async with storage() as db:
        before={r.metric_name:r.metric_value for r in (await db.scalars(select(VoiceMetricDaily))).all()}
    assert len(before)==8 and 'estimated_cost' not in before and 'billable_seconds' not in before
    current['metrics'][0]['value']=float('nan')
    with pytest.raises(ValueError):await service.aggregate_daily_metrics(storage,day)
    async with storage() as db:
        after={r.metric_name:r.metric_value for r in (await db.scalars(select(VoiceMetricDaily))).all()}
    assert before==after


@pytest.mark.asyncio
async def test_lock_conflict_retries_fresh_transaction_and_other_error_does_not(storage,monkeypatch):
    from sqlalchemy.exc import OperationalError
    from backend.services import realtime_voice_daily_aggregate_service as service
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    day=date(2026,9,19);sessions=[]
    async def compute(db,target):
        sessions.append(db)
        if len(sessions)==1:raise OperationalError('synthetic',{},Exception(1213,'deadlock'))
        return projection(day)
    monkeypatch.setattr(service,'compute_daily_metrics',compute)
    await service.aggregate_daily_metrics(storage,day)
    assert len(sessions)==2 and sessions[0] is not sessions[1]
    count=0
    async def unavailable(db,target):
        nonlocal count
        count+=1
        raise OperationalError('synthetic',{},Exception(2006,'disconnected'))
    monkeypatch.setattr(service,'compute_daily_metrics',unavailable)
    with pytest.raises(OperationalError):await service.aggregate_daily_metrics(storage,day)
    assert count==1
    async with storage() as db:
        assert len((await db.scalars(select(VoiceMetricDaily))).all())==10


@pytest.mark.asyncio
async def test_cancellation_rolls_back_first_anchor(storage,monkeypatch):
    import asyncio
    from backend.services import realtime_voice_daily_aggregate_service as service
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    async def cancelled(db,target):raise asyncio.CancelledError
    monkeypatch.setattr(service,'compute_daily_metrics',cancelled)
    with pytest.raises(asyncio.CancelledError):await service.aggregate_daily_metrics(storage,date(2026,9,19))
    async with storage() as db:
        assert (await db.scalars(select(VoiceMetricDaily))).all()==[]
