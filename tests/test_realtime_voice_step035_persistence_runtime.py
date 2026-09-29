"""Actual MySQL first-run locking, concurrent recomputation and rollback."""
import asyncio,os
from datetime import date
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceMetricDaily
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step035_persistence import (
    projection,test_full_ten_rows_exact_projection_and_repeat as full_projection,
    test_unavailable_removes_stale_numeric_and_invalid_snapshot_rolls_back as unknown_and_rollback,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_exact_ten_and_rollback(runtime,monkeypatch):
    await full_projection(runtime[0],monkeypatch)
    await unknown_and_rollback(runtime[0],monkeypatch)


@pytest.mark.asyncio
@pytest.mark.parametrize('provisional',[False,True])
async def test_mysql_concurrent_first_run_serializes_before_snapshot(runtime,monkeypatch,provisional):
    from backend.services import realtime_voice_daily_aggregate_service as service
    factory=runtime[0]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    entered,release,second_entered=asyncio.Event(),asyncio.Event(),asyncio.Event()
    calls=[]
    async def compute(db,day):
        calls.append(1)
        if len(calls)==1:
            entered.set();await release.wait()
            result=projection(day,daily_call_count=4)
            if provisional:result['metrics'][0]['status']='provisional'
            return result
        second_entered.set()
        return projection(day,daily_call_count=5)
    monkeypatch.setattr(service,'compute_daily_metrics',compute)
    day=date(2026,9,21 if provisional else 20)
    first=asyncio.create_task(service.aggregate_daily_metrics(factory,day))
    await asyncio.wait_for(entered.wait(),3)
    second=asyncio.create_task(service.aggregate_daily_metrics(factory,day))
    try:
        with pytest.raises(TimeoutError):await asyncio.wait_for(second_entered.wait(),.1)
    finally:
        release.set()
        await asyncio.gather(first,second)
    async with factory() as db:
        rows=(await db.scalars(select(VoiceMetricDaily).where(VoiceMetricDaily.business_date==day))).all()
    assert len(rows)==10
    assert next(row.metric_value for row in rows if row.metric_name=='daily_call_count')==5
