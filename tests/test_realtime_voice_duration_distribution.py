"""Equal sums can have different quantiles; zeros and repeated samples matter."""
import json
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_barge_in_service import BargeObservations


class Cache:
    def __init__(self):self.rows={}
    async def eval(self,script,n,*args):
        for i in range(n):
            self.rows.setdefault(args[i],{}).setdefault(args[n+2*i],0)
            self.rows[args[i]][args[n+2*i]]+=args[n+2*i+1]


@pytest.mark.asyncio
async def test_raw_zero_and_repeated_durations_are_preserved():
    cache=Cache()
    await VoiceMetrics(cache).emit_many([('voice.call01.decision_duration_ms',{'result':'model'},n) for n in [0,50,50,100]])
    hist=[v for k,v in cache.rows.items() if k.startswith('voice.duration_histogram:')]
    assert len(hist)==1
    parsed={json.loads(k)['milliseconds']:v for k,v in hist[0].items()}
    assert parsed=={0:1,50:2,100:1}
    total=next(v for k,v in cache.rows.items() if k.startswith('voice.call01.decision_duration_ms:'))
    assert total=={'{"result":"model"}':200}


def test_barge_in_preserves_individual_latency_before_drain():
    observations=BargeObservations()
    for n in [0,100]:observations.add('stop_clear_latency_ms',{'boundary':'server_request_to_client_ack'},n)
    assert [e[2] for e in observations.drain()]==[0,100]
    assert observations.drain()==[]


def test_equal_sum_different_distributions_have_different_p90():
    from backend.services.realtime_voice_metric_read_service import parse_duration_histogram
    def raw(values):
        result={}
        for ms in values:
            key=json.dumps({'dimensions':{'result':'model'},'milliseconds':ms})
            result[key]=str(int(result.get(key,'0'))+1)
        return result
    a=parse_duration_histogram('voice.call01.decision_duration_ms',raw([0,100]))
    b=parse_duration_histogram('voice.call01.decision_duration_ms',raw([50,50]))
    assert a['groups'][0]['p90_ms']==100
    assert b['groups'][0]['p90_ms']==50
    assert a['groups'][0]['p50_ms']==0
    assert a['groups'][0]['sample_count']==2


@pytest.mark.parametrize('field,count',[
    ({'dimensions':{'result':'model','secret':'private'},'milliseconds':10},'1'),
    ({'dimensions':{'result':'model'},'milliseconds':True},'1'),
    ({'dimensions':{'result':'model'},'milliseconds':-1},'1'),
    ({'dimensions':{'result':'model'},'milliseconds':10},'0'),
    ({'dimensions':{'result':'model'},'milliseconds':10},'NaN'),
])
def test_histogram_rejects_invalid_payload_without_exposure(field,count):
    from backend.services.realtime_voice_metric_read_service import parse_duration_histogram
    assert parse_duration_histogram('voice.call01.decision_duration_ms',{json.dumps(field):count})=={'status':'invalid','groups':None}


def test_capped_queue_age_and_missing_distribution_never_report_fake_precision():
    from backend.services.realtime_voice_metric_read_service import parse_duration_histogram
    assert parse_duration_histogram('voice.turn.close_duration_ms',{})=={'status':'missing','groups':None}
    raw={json.dumps({'dimensions':{'phase':'retry','capped':'true'},'milliseconds':10**9}):'1'}
    row=parse_duration_histogram('voice.memory_job.enqueue_to_claim_ms',raw)['groups'][0]
    assert row['status']=='not_measurable' and row['p95_ms'] is None


@pytest.mark.asyncio
async def test_deferred_samples_stay_local_until_flush_and_invalid_batch_writes_nothing():
    from backend.services.realtime_voice_metric_service import defer_voice_metrics
    cache=Cache();metrics=VoiceMetrics(cache);pending=[]
    with defer_voice_metrics(pending):
        await metrics.emit_many([('voice.turn.close_duration_ms',{},0)])
    assert not cache.rows
    assert await metrics.emit_many(pending)
    before={key:dict(value) for key,value in cache.rows.items()}
    assert not await metrics.emit_many([('voice.turn.close_duration_ms',{},100),('private',{},1)])
    assert cache.rows==before


def test_deep_corrupt_json_is_invalid_not_parser_crash():
    from backend.services.realtime_voice_metric_read_service import parse_counter,parse_duration_histogram
    raw={'['*1000+'0'+']'*1000:'1'}
    assert parse_counter('voice.turn.close_duration_ms',raw)=={'status':'invalid','samples':None}
    assert parse_duration_histogram('voice.turn.close_duration_ms',raw)=={'status':'invalid','groups':None}
