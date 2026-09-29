"""Consumer rejects corrupt or sensitive counter payloads, never manufactures zero."""
import json
from datetime import date
import pytest


@pytest.mark.parametrize('payload',[
    {'{"result":"written","user_id":"secret"}':'1'},
    {'{"result":"secret"}':'1'},
    {'{"result":"written"}':'NaN'},
    {'{"result":"written"}':'-1'},
    {'{"result":"written"}':'1.5'},
    {'[]':'1'},
    {'{"result":"written","result":"failure"}':'1'},
])
def test_invalid_counter_input_does_not_expose_raw_payload(payload):
    from backend.services.realtime_voice_metric_read_service import parse_counter
    result=parse_counter('voice.memory_upsert.result',payload)
    assert result=={'status':'invalid','samples':None}
    assert 'secret' not in json.dumps(result)


def test_missing_counter_is_unknown_not_zero_and_known_counts_are_canonical():
    from backend.services.realtime_voice_metric_read_service import parse_counter
    assert parse_counter('voice.memory_upsert.result',{})=={'status':'missing','samples':None}
    assert parse_counter('voice.memory_upsert.result',{'{"result":"written"}':'3'})=={
        'status':'available','samples':[{'dimensions':{'result':'written'},'value':3}]}
    assert parse_counter('llm_stats',{})=={'status':'invalid','samples':None}


@pytest.mark.asyncio
async def test_reader_queries_only_registered_voice_keys_without_writes():
    from backend.services.realtime_voice_metric_read_service import read_counter_day
    class Pipeline:
        def __init__(self):self.keys=[]
        def hgetall(self,key):self.keys.append(key);return self
        async def execute(self):return [{} for key in self.keys]
    class Cache:
        def pipeline(self,transaction):
            assert transaction is False
            self.pipe=Pipeline();return self.pipe
    cache=Cache()
    result=await read_counter_day(cache,date(2026,9,19))
    assert cache.pipe.keys and all(k.startswith('voice.') and k.endswith(':20260919') for k in cache.pipe.keys)
    assert result['bucket_basis']=='observation_sent_utc'
    assert all(row['status']=='missing' and row['samples'] is None for row in result['events'])


@pytest.mark.asyncio
async def test_reader_failure_and_cancellation_are_distinct():
    import asyncio
    from backend.services.realtime_voice_metric_read_service import read_counter_day
    class Cache:
        def __init__(self,error):self.error=error
        def pipeline(self,transaction):return self
        def hgetall(self,key):return self
        async def execute(self):raise self.error
    result=await read_counter_day(Cache(RuntimeError('private-secret')),date(2026,9,19))
    assert all(row['status']=='unavailable' and row['samples'] is None for row in result['events'])
    assert 'private-secret' not in json.dumps(result)
    with pytest.raises(asyncio.CancelledError):
        await read_counter_day(Cache(asyncio.CancelledError()),date(2026,9,19))


def test_dictionary_closed_dimensions_and_ttl():
    from backend.services.realtime_voice_metric_read_service import metric_dictionary
    rows=metric_dictionary()
    assert len({row['name'] for row in rows})==len(rows)
    assert all(row['name'].startswith('voice.') and row['ttl_seconds']==172800 for row in rows)
    source=next(row for row in rows if row['name']=='voice.memory_upsert.source_observation')
    assert source['dimensions']=={'boundary':['prewrite'],'current':['voice'],'previous':['admin','text','unknown','voice']}
    assert source['max_dimension_combinations']==4
