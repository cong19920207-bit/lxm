"""Public UTC observations cannot infer capabilities from pooled counters."""
from datetime import date
import pytest


@pytest.mark.asyncio
async def test_mask_sensitive_observations_even_with_nonzero_samples(monkeypatch):
    from backend.services import realtime_voice_observation_service as service
    gated=('voice.barge_in.truncate','voice.effective_text.evidence',
           'voice.recall.double_reply','voice.provider.usage')
    async def counters(cache, day):
        return dict(date=day.isoformat(),bucket_basis='observation_sent_utc',completeness='not_guaranteed',
                    events=[dict(name=name,status='available',samples=[dict(value=987)]) for name in gated]+
                    [dict(name='voice.precheck.result',status='available',samples=[dict(value=5)])])
    async def durations(cache,day):return dict(events=[dict(name='voice.call01.latency_ms',status='available',groups=[])])
    monkeypatch.setattr(service,'read_counter_day',counters)
    monkeypatch.setattr(service,'read_duration_day',durations)
    result=await service.read_observations(None,date(2026,9,19))
    assert '987' not in str(result)
    assert result['bucket_basis']=='observation_sent_utc'
    events={item['name']:item for item in result['events']}
    for name in gated:
        assert events[name]['status']=='not_measurable' and events[name]['samples'] is None
        assert events[name]['reason']=='capability_evidence_unavailable_for_bucket'
    assert events['voice.precheck.result']['samples']==[dict(value=5)]
    assert len(result['capability_metrics'])==4
    assert all(row['value'] is None and row['status']=='not_measurable' for row in result['capability_metrics'])
    assert result['durations'][0]['status']=='available'


@pytest.mark.asyncio
async def test_redis_unavailable_is_not_zero():
    from backend.services.realtime_voice_observation_service import read_observations
    result=await read_observations(None,date(2026,9,19))
    for row in result['events']:
        assert row['samples'] is None and row['status'] in {'unavailable','not_measurable'}
    assert all(row['groups'] is None for row in result['durations'])


@pytest.mark.asyncio
@pytest.mark.parametrize('samples,expected', [
    ([('primary','verified',3),('extra','verified',2)],2),
    ([('primary','verified',3)],0),
    ([('extra','verified',2)],2),
    ([('primary','verified',3),('extra','unverified',1)],None),
    ([('primary','verified',3),('overflow','unverified',1)],None),
    ([],None),
])
async def test_unique_reply_projection_requires_sample_capability(monkeypatch,samples,expected):
    from backend.services import realtime_voice_observation_service as service
    async def counters(cache,day):
        return {'events':[{'name':'voice.recall.reply_observed','status':'available',
            'samples':[{'dimensions':{'kind':kind,'evidence':evidence},'value':value} for kind,evidence,value in samples]}]}
    async def durations(cache,day):return {'events':[]}
    monkeypatch.setattr(service,'read_counter_day',counters)
    monkeypatch.setattr(service,'read_duration_day',durations)
    result=await service.read_observations(None,date(2026,9,19))
    metric=next(row for row in result['capability_metrics'] if row['name']=='double_reply_count')
    assert metric['value']==expected
    assert metric['status']==('measured' if expected is not None else 'not_measurable')
    if expected is None:assert result['events'][0]['samples'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('samples,expected',[
    ([('success','verified',3),('failure','verified',1)],.75),
    ([('failure','verified',1)],0),([('success','verified',1)],1),
    ([('success','verified',1),('unknown','verified',1)],None),
    ([('success','unverified',1)],None),([],None)])
async def test_truncate_rate_only_from_verified_final_outcomes(monkeypatch,samples,expected):
    from backend.services import realtime_voice_observation_service as service
    async def counters(cache,day):
        return {'events':[{'name':'voice.barge_in.truncate_outcome','status':'available',
            'samples':[{'dimensions':{'result':result,'evidence':evidence},'value':value} for result,evidence,value in samples]}]}
    async def durations(cache,day):return {'events':[]}
    monkeypatch.setattr(service,'read_counter_day',counters)
    monkeypatch.setattr(service,'read_duration_day',durations)
    result=await service.read_observations(None,date(2026,9,19))
    metric=next(row for row in result['capability_metrics'] if row['name']=='truncate_success_rate')
    assert metric['value']==expected
    assert metric['status']==('measured' if expected is not None else 'not_measurable')
    if expected is None:assert result['events'][0]['samples'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('unverified',[False,True])
async def test_effective_distribution_is_snapshot_weighted_and_fail_closed(monkeypatch,unverified):
    from backend.services import realtime_voice_observation_service as service
    async def counters(cache,day):
        return {'events':[{'name':'voice.effective_text.observed','status':'available','samples':[
            {'dimensions':{'level':'exact_played','evidence':'verified'},'value':2},
            {'dimensions':{'level':'none','evidence':'unverified' if unverified else 'verified'},'value':1},
            {'dimensions':{'level':'full','evidence':'verified'},'value':1}]}]}
    async def durations(cache,day):return {'events':[]}
    monkeypatch.setattr(service,'read_counter_day',counters)
    monkeypatch.setattr(service,'read_duration_day',durations)
    result=await service.read_observations(None,date(2026,9,19))
    metric=next(row for row in result['capability_metrics'] if row['name']=='effective_text_evidence_distribution')
    if unverified:
        assert metric['value'] is None and result['events'][0]['samples'] is None
    else:
        assert metric['unit']=='text_snapshot' and metric['sample_count']==4
        assert metric['value']=={'exact_played':.5,'confirmed_sentences':0,'full':.25,'none':.25}
