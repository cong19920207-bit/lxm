"""Business-day cohorts are computed from durable rows, never UTC telemetry totals."""
from datetime import date,datetime
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoiceMemoryJob,VoicePostprocessJob,VoiceUsageLedger
from tests.test_realtime_voice_step009_ops import storage,add_call,StateCache
from tests.test_realtime_voice_step028_jobs import add_turn


@pytest.mark.asyncio
async def test_shanghai_boundary_unique_tasks_and_cross_day_ledger(storage):
    from backend.services.realtime_voice_daily_metric_service import compute_daily_metrics
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMemoryJob.__table__,VoicePostprocessJob.__table__])
    ids=[await add_call(storage,state,StateCache()) for state in ('ended','missed','failed','ended')]
    async with storage() as db:
        calls=(await db.scalars(select(VoiceCall).where(VoiceCall.call_id.in_(ids)).order_by(VoiceCall.id))).all()
        for row in calls:row.created_at=datetime(2026,9,18,16)
        calls[0].connected_at=datetime(2026,9,18,16,1);calls[0].duration_seconds=80
        calls[0].summary_status='ready'
        calls[3].created_at=datetime(2026,9,18,15,59,59)  # previous Shanghai day
        calls[3].connected_at=datetime(2026,9,18,15);calls[3].duration_seconds=999
        db.add_all([VoiceUsageLedger(call_id=ids[0],segment_seq=1,free_seconds_used=60,extra_seconds_used=0,
            usage_type='connected',duration_seconds=60,quota_date=date(2026,9,19)),
            VoiceUsageLedger(call_id=ids[0],segment_seq=2,free_seconds_used=20,extra_seconds_used=0,
            usage_type='connected',duration_seconds=20,quota_date=date(2026,9,20))])
        await db.commit()
    turn=await add_turn(storage,ids[0])
    async with storage() as db:
        db.add(VoiceMemoryJob(call_id=ids[0],turn_id=turn,turn_index=1,pipeline_version='voice_memory_v1',
            status='success',attempt_count=3,created_at=datetime(2026,9,18,16)))
        db.add(VoicePostprocessJob(call_id=ids[0],job_type='call_summary',status='success',attempt_count=2,
            created_at=datetime(2026,9,18,16)))
        db.add(VoicePostprocessJob(call_id=ids[0],job_type='memory_compensation',status='failed',
            created_at=datetime(2026,9,18,16)))
        await db.commit()
        output=await compute_daily_metrics(db,date(2026,9,19))
        assert not db.new and not db.dirty and not db.deleted
    metrics={row['name']:row for row in output['metrics']}
    assert set(metrics)=={'daily_call_count','connect_rate','missed_rate','failure_rate','avg_duration_seconds',
        'billable_seconds','estimated_cost','call01_fallback_rate','memory_success_rate','summary_success_rate'}
    for name,value in {'daily_call_count':3,'connect_rate':1/3,'missed_rate':1/3,'failure_rate':1/3,
        'avg_duration_seconds':80,'billable_seconds':60,'memory_success_rate':1,'summary_success_rate':1}.items():
        assert metrics[name]['value']==pytest.approx(value)
    assert metrics['estimated_cost']['value'] is None and metrics['estimated_cost']['reason']=='price_unconfigured'
    assert metrics['call01_fallback_rate']['value'] is None
    assert output['timezone']=='Asia/Shanghai'


@pytest.mark.asyncio
async def test_empty_day_unknown_rates_and_legacy_usage(storage):
    from backend.services.realtime_voice_daily_metric_service import compute_daily_metrics
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMemoryJob.__table__,VoicePostprocessJob.__table__])
    async with storage() as db:
        result=await compute_daily_metrics(db,date(2026,9,19))
        rows={row['name']:row for row in result['metrics']}
        assert rows['daily_call_count']['value']==0
        for name in ('connect_rate','missed_rate','failure_rate','avg_duration_seconds','memory_success_rate','summary_success_rate'):
            assert rows[name]['value'] is None and rows[name]['reason']=='no_eligible_samples'
        db.add(VoiceUsageLedger(call_id='legacy',segment_seq=1,free_seconds_used=20,extra_seconds_used=0,usage_type='connected'))
        await db.commit()
        rows={row['name']:row for row in (await compute_daily_metrics(db,date(2026,9,19)))['metrics']}
        assert rows['billable_seconds']['value'] is None and rows['billable_seconds']['reason']=='undated_legacy_usage'


@pytest.mark.asyncio
async def test_retry_pending_and_summary_ineligible_are_not_failure_or_success_samples(storage):
    from backend.services.realtime_voice_daily_metric_service import compute_daily_metrics
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMemoryJob.__table__,VoicePostprocessJob.__table__])
    call=await add_call(storage,'ringing',StateCache())
    turn=await add_turn(storage,call)
    async with storage() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        row.created_at=datetime(2026,9,18,16);row.summary_status='not_applicable'
        memory=VoiceMemoryJob(call_id=call,turn_id=turn,turn_index=1,pipeline_version='voice_memory_v1',status='failed',
            attempt_count=2,next_retry_at=datetime(2026,9,20),created_at=datetime(2026,9,18,16))
        db.add(memory)
        db.add(VoicePostprocessJob(call_id=call,job_type='call_summary',status='success',created_at=datetime(2026,9,18,16)))
        await db.commit()
        output=await compute_daily_metrics(db,date(2026,9,19))
        rows={row['name']:row for row in output['metrics']}
        assert output['pending_calls']==1 and rows['connect_rate']['status']=='provisional'
        assert output['pending_memory_jobs']==1 and rows['memory_success_rate']['value'] is None
        assert rows['summary_success_rate']['value'] is None
        memory.status='success';memory.next_retry_at=None;memory.attempt_count=3
        await db.commit()
        rows={row['name']:row for row in (await compute_daily_metrics(db,date(2026,9,19)))['metrics']}
        assert rows['memory_success_rate']['value']==1  # one durable task, not 1/3 attempts


@pytest.mark.asyncio
async def test_previous_day_active_call_marks_current_day_usage_provisional(storage):
    from backend.services.realtime_voice_daily_metric_service import compute_daily_metrics
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMemoryJob.__table__,VoicePostprocessJob.__table__])
    call=await add_call(storage,'connected',StateCache())
    async with storage() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        row.created_at=row.connected_at=datetime(2026,9,18,15,59)
        await db.commit()
        result=await compute_daily_metrics(db,date(2026,9,19))
    usage=next(row for row in result['metrics'] if row['name']=='billable_seconds')
    assert result['pending_calls']==0 and result['settlement_pending_calls']==1
    assert usage['value']==0 and usage['status']=='provisional' and usage['reason']=='settlement_pending'
