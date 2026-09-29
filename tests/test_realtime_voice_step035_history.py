from datetime import date,datetime
import pytest
from backend.database import Base
from backend.models.realtime_voice import VoiceMetricDaily
from tests.test_realtime_voice_step009_ops import storage


@pytest.mark.asyncio
async def test_history_missing_invalid_and_version_isolation(storage):
    from backend.services.realtime_voice_metric_history_service import read_history
    from backend.services.realtime_voice_daily_aggregate_service import DIMENSIONS,DIMENSION_HASH
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceMetricDaily.__table__])
    async with storage() as db:
        def row(name,value,**kwargs):
            return VoiceMetricDaily(business_date=date(2026,9,19),metric_name=name,metric_value=value,
                dimension_hash=kwargs.get('hash',DIMENSION_HASH),dimension_json=kwargs.get('dimensions',DIMENSIONS),
                updated_at=datetime(2026,9,20,1))
        db.add_all([row('daily_call_count',0),row('connect_rate',.5),row('failure_rate',2),
                    row('missed_rate',.1,dimensions={'secret':'DO_NOT_EXPOSE'}),
                    row('billable_seconds',999,hash='old-version')])
        await db.commit()
        result=await read_history(db,date(2026,9,18),date(2026,9,19))
        assert not db.new and not db.dirty and not db.deleted
    assert result['history_basis']=='materialized_current_durable_state'
    assert len(result['days'])==2 and all(len(day['metrics'])==10 for day in result['days'])
    assert all(item['value'] is None for item in result['days'][0]['metrics'])
    values={item['name']:item for item in result['days'][1]['metrics']}
    assert values['daily_call_count']['value']==0 and values['connect_rate']['value']==.5
    assert values['connect_rate']['computed_at_utc']=='2026-09-20T01:00:00+00:00'
    assert values['failure_rate']['reason']=='invalid_materialized_value'
    assert values['missed_rate']['value'] is None
    assert values['billable_seconds']['value'] is None
    assert 'DO_NOT_EXPOSE' not in str(result) and '999' not in str(result)


@pytest.mark.asyncio
async def test_history_range_bounded_before_sql():
    from backend.services.realtime_voice_metric_history_service import read_history
    for start,end in [(date(2026,9,20),date(2026,9,19)),(date(2026,8,1),date(2026,9,19))]:
        with pytest.raises(ValueError):await read_history(None,start,end)
