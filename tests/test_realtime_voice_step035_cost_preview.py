from datetime import date,datetime
import pytest
from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoiceUsageLedger
from tests.test_realtime_voice_step009_ops import storage,add_call,StateCache


@pytest.mark.asyncio
async def test_simulated_price_uses_authoritative_ledger_and_reconciles(storage):
    from backend.services.realtime_voice_cost_preview_service import preview_cost
    call=await add_call(storage,'ended',StateCache())
    async with storage() as db:
        db.add(VoiceUsageLedger(call_id=call,segment_seq=1,quota_date=date(2026,9,19),usage_type='connected',
            free_seconds_used=60,extra_seconds_used=60,duration_seconds=120))
        db.add(VoiceUsageLedger(call_id=call,segment_seq=2,quota_date=date(2026,9,19),usage_type='grace',
            free_seconds_used=50,extra_seconds_used=0,duration_seconds=50))
        await db.commit()
        output=await preview_cost(db,start=date(2026,9,19),end=date(2026,9,19),unit_price='0.06',unit='minute',
            currency='CNY',billed_cost='0.10',bill_currency='CNY',bill_start=date(2026,9,19),bill_end=date(2026,9,19))
        assert output['billable_seconds']==120 and output['estimated_cost']=='0.120000'
        assert output['difference_amount']=='0.020000' and output['difference_rate']=='0.2000'
        assert output['data_source']=='simulated_pricing_and_bill'
        assert not db.new and not db.dirty and not db.deleted
        with pytest.raises(ValueError):
            await preview_cost(db,start=date(2026,9,19),end=date(2026,9,19),unit_price='0.06',unit='minute',
                currency='CNY',billed_cost='0.10',bill_currency='USD',bill_start=date(2026,9,19),bill_end=date(2026,9,19))


@pytest.mark.asyncio
async def test_unsettled_seconds_and_legacy_not_estimated(storage):
    from backend.services.realtime_voice_cost_preview_service import preview_cost
    from sqlalchemy import select
    call=await add_call(storage,'connected',StateCache())
    kwargs=dict(start=date(2026,9,19),end=date(2026,9,19),unit_price='0.06',unit='minute',currency='CNY',
                billed_cost='1',bill_currency='CNY',bill_start=date(2026,9,19),bill_end=date(2026,9,19))
    async with storage() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call));row.connected_at=datetime(2026,9,19)
        await db.commit()
        output=await preview_cost(db,**kwargs)
        assert output['estimated_cost'] is None and output['reason']=='settlement_pending'
        row.status='ended'
        db.add(VoiceUsageLedger(call_id=call,segment_seq=1,quota_date=None,usage_type='connected',free_seconds_used=10,extra_seconds_used=0))
        await db.commit()
        output=await preview_cost(db,**kwargs)
        assert output['estimated_cost'] is None and output['reason']=='undated_legacy_usage'


@pytest.mark.asyncio
@pytest.mark.parametrize('unit,price,bill,expected,rate', [
    ('minute','0.1','0','0.001667',None),
    ('second','0.1','0.1','0.100000','0.00000'),
    ('minute','0','0','0.000000','0'),
])
async def test_units_rounding_and_zero_denominator(storage,unit,price,bill,expected,rate):
    from backend.services.realtime_voice_cost_preview_service import preview_cost
    call=await add_call(storage,'ended',StateCache())
    async with storage() as db:
        db.add(VoiceUsageLedger(call_id=call,segment_seq=1,quota_date=date(2026,9,19),
            usage_type='connected',free_seconds_used=1,extra_seconds_used=0))
        await db.commit()
        result=await preview_cost(db,start=date(2026,9,19),end=date(2026,9,19),unit_price=price,unit=unit,
            currency='CNY',billed_cost=bill,bill_currency='CNY',bill_start=date(2026,9,19),bill_end=date(2026,9,19))
        assert result['estimated_cost']==expected and result['difference_rate']==rate
        assert result['status']==('not_measurable' if rate is None else 'measured')


@pytest.mark.asyncio
@pytest.mark.parametrize('override', [
    {'unit':'hour'}, {'unit_price':'-1'}, {'unit_price':'NaN'}, {'billed_cost':'Infinity'},
    {'bill_currency':'USD'}, {'bill_start':date(2026,9,18)}, {'end':date(2026,11,1)},
    {'start':date.min}, {'end':date.max}, {'end':date(2026,9,18)},
])
async def test_bad_parameters_rejected_before_database(override):
    from backend.services.realtime_voice_cost_preview_service import preview_cost
    kwargs=dict(start=date(2026,9,19),end=date(2026,9,19),unit_price='0.06',unit='minute',
        currency='CNY',billed_cost='1',bill_currency='CNY',bill_start=date(2026,9,19),bill_end=date(2026,9,19))
    kwargs.update(override)
    with pytest.raises(ValueError):
        await preview_cost(None,**kwargs)
