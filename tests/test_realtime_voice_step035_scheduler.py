"""Bounded cyclic business-day repair includes old jobs and settlement changes."""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
import pytest
from backend.database import Base
from backend.models.realtime_voice import VoiceMetricDaily, VoiceMemoryJob, VoicePostprocessJob
from tests.test_realtime_voice_step009_ops import storage


@pytest.mark.asyncio
async def test_cycle_restart_gap_days_and_old_materialization(storage, monkeypatch):
    from backend.services import realtime_voice_daily_schedule_service as service
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__,VoiceMemoryJob.__table__,VoicePostprocessJob.__table__])
    async with storage() as db:
        db.add(VoiceMetricDaily(business_date=date(2026,9,15),metric_name='daily_call_count',
            dimension_hash='old',dimension_json={},metric_value=0))
        await db.commit()
    aggregate=AsyncMock()
    monkeypatch.setattr(service,'aggregate_daily_metrics',aggregate)
    now=datetime(2026,9,19,16,1,tzinfo=timezone.utc) # Shanghai Sep20, yesterday Sep19
    result=await service.run_daily_batch(storage,now=now,after_day=None,limit=2)
    assert [c.args[1] for c in aggregate.call_args_list]==[date(2026,9,19),date(2026,9,15),date(2026,9,16)]
    assert result['next_day']==date(2026,9,16)
    aggregate.reset_mock()
    result=await service.run_daily_batch(storage,now=now,after_day=result['next_day'],limit=2)
    assert [c.args[1] for c in aggregate.call_args_list]==[date(2026,9,19),date(2026,9,17),date(2026,9,18)]
    assert result['next_day']==date(2026,9,18)
    aggregate.reset_mock()
    result=await service.run_daily_batch(storage,now=now,after_day=result['next_day'],limit=2)
    assert [c.args[1] for c in aggregate.call_args_list]==[date(2026,9,19)]
    assert result['next_day'] is None
    # Restart is safe: repeat the oldest dates, never trust an in-memory watermark for completion.
    assert not any(c.args[1]>=date(2026,9,20) for c in aggregate.call_args_list)


def test_registration(monkeypatch):
    from backend.tasks import scheduler as module
    registrations=[]
    class Scheduler:
        running=False
        def add_job(self,callback,**kw):registrations.append((callback,kw))
        def start(self):pass
        def get_jobs(self):return []
    monkeypatch.setattr(module,'scheduler',Scheduler());module.start_scheduler()
    matches=[(fn,kw) for fn,kw in registrations if kw['id']=='voice_daily_metrics_task']
    assert len(matches)==1 and matches[0][0] is module._run_voice_daily_metrics
    assert matches[0][1]['trigger'].interval.total_seconds()==60
    assert matches[0][1]['max_instances']==1 and matches[0][1]['coalesce']


@pytest.mark.asyncio
async def test_scheduler_failure_keeps_cursor_and_cancellation_propagates(monkeypatch,caplog):
    import asyncio
    from backend.tasks import scheduler as module
    from backend.services import realtime_voice_daily_schedule_service as service
    operation=AsyncMock(side_effect=[RuntimeError('PRIVATE'),{'next_day':None},asyncio.CancelledError()])
    monkeypatch.setattr(service,'run_daily_batch',operation)
    monkeypatch.setattr(module,'_voice_daily_after',date(2026,9,15))
    await module._run_voice_daily_metrics()
    assert module._voice_daily_after==date(2026,9,15)
    assert operation.call_args.kwargs['include_simulated'] is True
    await module._run_voice_daily_metrics()
    assert module._voice_daily_after is None
    with pytest.raises(asyncio.CancelledError):await module._run_voice_daily_metrics()
    assert 'PRIVATE' not in caplog.text


@pytest.mark.asyncio
async def test_late_job_and_ledger_change_recomputed_without_duplicate_rows(storage):
    from sqlalchemy import select, func
    from backend.models.realtime_voice import VoiceUsageLedger
    from backend.services.realtime_voice_daily_schedule_service import run_daily_batch
    from tests.test_realtime_voice_step035_daily import test_shanghai_boundary_unique_tasks_and_cross_day_ledger as seed
    await seed(storage)
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    now=datetime(2026,9,21,16,1,tzinfo=timezone.utc)
    await run_daily_batch(storage,now=now)
    async with storage() as db:
        count=await db.scalar(select(func.count()).select_from(VoiceMetricDaily))
        value=await db.scalar(select(VoiceMetricDaily.metric_value).where(VoiceMetricDaily.business_date==date(2026,9,19),VoiceMetricDaily.metric_name=='memory_success_rate'))
        assert value==1
        job=await db.scalar(select(VoiceMemoryJob))
        job.status='failed';job.next_retry_at=None
        ledger=await db.scalar(select(VoiceUsageLedger).where(VoiceUsageLedger.quota_date==date(2026,9,19)))
        ledger.extra_seconds_used=10
        await db.commit()
    await run_daily_batch(storage,now=now)
    async with storage() as db:
        rows={r.metric_name:r.metric_value for r in (await db.scalars(select(VoiceMetricDaily).where(VoiceMetricDaily.business_date==date(2026,9,19)))).all()}
        assert rows['memory_success_rate']==0 and rows['billable_seconds']==70
        assert await db.scalar(select(func.count()).select_from(VoiceMetricDaily))==count


@pytest.mark.asyncio
async def test_explicit_simulation_batch_materializes_cost_and_keeps_default_isolated(storage):
    from backend.services.realtime_voice_daily_schedule_service import run_daily_batch
    from backend.services.realtime_voice_metric_history_service import read_history
    from backend.services.realtime_voice_pricing import SIMULATED_PRICING
    from tests.test_realtime_voice_step035_priced_daily import test_source_to_ten_materialized_rows_and_isolated_price_history as seed
    from sqlalchemy import delete
    await seed(storage)
    async with storage() as db:
        await db.execute(delete(VoiceMetricDaily));await db.commit()
    now=datetime(2026,9,19,16,1,tzinfo=timezone.utc)
    await run_daily_batch(storage,now=now,include_simulated=True)
    async with storage() as db:
        rows=(await read_history(db,date(2026,9,19),date(2026,9,19),pricing=SIMULATED_PRICING))['days'][0]['metrics']
        assert len(rows)==10 and all(row['status']=='measured' for row in rows)
        assert next(row['value'] for row in rows if row['name']=='estimated_cost')==pytest.approx(.12)
        ordinary=(await read_history(db,date(2026,9,19),date(2026,9,19)))['days'][0]['metrics']
        assert next(row['value'] for row in ordinary if row['name']=='estimated_cost') is None
