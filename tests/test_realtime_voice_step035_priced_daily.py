from datetime import date, datetime
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceMetricDaily, VoiceMemoryJob, VoicePostprocessJob, VoiceUsageLedger
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache
from tests.test_realtime_voice_step028_jobs import add_turn


@pytest.mark.asyncio
async def test_source_to_ten_materialized_rows_and_isolated_price_history(storage):
    from backend.services.realtime_voice_pricing import SIMULATED_PRICING
    from backend.services.realtime_voice_daily_aggregate_service import aggregate_daily_metrics, daily_dimensions
    from backend.services.realtime_voice_metric_history_service import read_history
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[VoiceMetricDaily.__table__, VoiceMemoryJob.__table__, VoicePostprocessJob.__table__])
    call = await add_call(storage, 'ended', StateCache())
    turn = await add_turn(storage, call)
    day = date(2026,9,19)
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        row.created_at = row.connected_at = datetime(2026,9,18,16)
        row.duration_seconds = 120; row.call01_fallback = True; row.summary_status = 'ready'
        db.add(VoiceUsageLedger(call_id=call, segment_seq=1, usage_type='connected', quota_date=day, free_seconds_used=60, extra_seconds_used=60))
        db.add(VoiceMemoryJob(call_id=call,turn_id=turn,turn_index=1,pipeline_version='voice_memory_v1',status='success',created_at=row.created_at))
        db.add(VoicePostprocessJob(call_id=call,job_type='call_summary',status='success',created_at=row.created_at))
        await db.commit()
    await aggregate_daily_metrics(storage, day)
    for _ in range(2):
        await aggregate_daily_metrics(storage, day, pricing=SIMULATED_PRICING)
    dimensions, digest = daily_dimensions(SIMULATED_PRICING)
    expected = {'daily_call_count':1,'connect_rate':1,'missed_rate':0,'failure_rate':0,
        'avg_duration_seconds':120,'billable_seconds':120,'estimated_cost':.12,
        'call01_fallback_rate':1,'memory_success_rate':1,'summary_success_rate':1}
    async with storage() as db:
        rows = (await db.scalars(select(VoiceMetricDaily).where(VoiceMetricDaily.dimension_hash==digest))).all()
        assert len(rows)==10
        assert all(row.dimension_json==dimensions for row in rows)
        assert {r.metric_name:r.metric_value for r in rows}==pytest.approx(expected)
        history = await read_history(db, day, day, pricing=SIMULATED_PRICING)
        assert history['pricing']['data_source']=='simulated'
        assert {r['name']:r['value'] for r in history['days'][0]['metrics']}==pytest.approx(expected)
        ordinary = await read_history(db, day, day)
        assert next(r for r in ordinary['days'][0]['metrics'] if r['name']=='estimated_cost')['value'] is None


@pytest.mark.asyncio
async def test_price_identity_normalization_and_change_separation(storage):
    from backend.services.realtime_voice_pricing import SimulatedPricing
    from backend.services.realtime_voice_daily_aggregate_service import daily_dimensions
    assert daily_dimensions(SimulatedPricing('0.0600'))==daily_dimensions(SimulatedPricing('0.06'))
    assert daily_dimensions(SimulatedPricing('0.06'))!=daily_dimensions(SimulatedPricing('0.07'))
    assert daily_dimensions(SimulatedPricing('0.06'))!=daily_dimensions(SimulatedPricing('0.06',currency='USD'))
    assert daily_dimensions(SimulatedPricing('999999999999999999.123456789011'))!=daily_dimensions(SimulatedPricing('999999999999999999.123456789012'))
    assert daily_dimensions(SimulatedPricing('-0.00'))==daily_dimensions(SimulatedPricing('0'))
    for kwargs in ({'unit_price':'NaN'}, {'unit_price':'-1'}, {'unit_price':'1','unit':'hour'}, {'unit_price':'1','currency':'cny'}):
        with pytest.raises(ValueError):SimulatedPricing(**kwargs)


@pytest.mark.asyncio
async def test_read_api_can_select_simulated_projection_without_writing(storage):
    from tests.test_realtime_voice_step035_api import build_api
    from backend.utils.admin_auth import get_current_admin
    from types import SimpleNamespace
    from httpx import ASGITransport, AsyncClient
    app=await build_api(storage)
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        for path in ('daily?day=2026-09-19','history?start=2026-09-19&end=2026-09-19'):
            result=await client.get('/api/admin/voice/metrics/'+path+'&simulated_pricing=true')
            assert result.status_code==200
            assert result.json()['data']['pricing']['data_source']=='simulated'
    async with storage() as db:
        assert (await db.scalars(select(VoiceMetricDaily))).all()==[]
