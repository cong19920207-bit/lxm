"""Real isolated Redis -> read-only HTTP projection, with capability masking."""
import os
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from httpx import ASGITransport, AsyncClient
from backend.utils.admin_auth import get_current_admin
from backend.routers.admin.voice_metrics import observation_cache
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step035_api import build_api
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores opt-in')


@pytest.mark.asyncio
async def test_real_redis_http_mask_and_distribution(runtime,monkeypatch):
    factory,_,cache=runtime
    app=await build_api(factory)
    app.dependency_overrides[observation_cache]=lambda:cache
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
    await cache.set('llm_stats','unchanged')
    sink=VoiceMetrics(cache,deadline_seconds=1)
    assert await sink.emit_many([
        ('voice.barge_in.truncate',{'result':'success','reason':'confirmed'},37),
        ('voice.effective_text.evidence',{'level':'exact_played'},37),
        ('voice.recall.double_reply',{'result':'detected','unit':'frame'},37),
        ('voice.provider.usage',{'result':'received'},37),
        ('voice.call01.decision_duration_ms',{'result':'model'},10),
        ('voice.call01.decision_duration_ms',{'result':'model'},20),
        ('voice.call01.decision_duration_ms',{'result':'model'},30),
    ])
    before={key:await cache.dump(key) for key in await cache.keys('*')}
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.get('/api/admin/voice/metrics/observations',params={'day':datetime.now(timezone.utc).date().isoformat()})
    assert response.status_code==200
    data=response.json()['data']
    assert all(row['value'] is None for row in data['capability_metrics'])
    for row in data['events']:
        if row['name'] in {'voice.barge_in.truncate','voice.effective_text.evidence','voice.recall.double_reply','voice.provider.usage'}:
            assert row['status']=='not_measurable' and row['samples'] is None
    group=next(row for row in data['durations'] if row['name']=='voice.call01.decision_duration_ms')['groups'][0]
    assert (group['p50_ms'],group['p90_ms'],group['p95_ms'])==(20,30,30)
    assert before=={key:await cache.dump(key) for key in await cache.keys('*')}
    await verify_unique_reply_producer_redis_http(runtime,monkeypatch)


async def verify_unique_reply_producer_redis_http(runtime,monkeypatch):
    from tests.test_realtime_voice_step007_provider import connected,verified_capability,response
    from backend.services.realtime_voice_provider_service import decode_frame
    factory,_,cache=runtime
    adapter,wire=await connected(monkeypatch)
    adapter.metrics=VoiceMetrics(cache,deadline_seconds=1)
    adapter._capabilities['supports_current_turn_rag_gate']=verified_capability()
    adapter._question='q';adapter._questions['vendor-q']='q'
    await adapter.inject_rag('q','private-memory')
    for code,rid in [(350,'r1'),(350,'r2'),(550,'r2')]:
        adapter._normalize(decode_frame(response(code,adapter.session_id,dict(question_id='vendor-q',reply_id=rid,text='private-text',content='private-text'))))
    await adapter.finish_session()
    app=await build_api(factory)
    app.dependency_overrides[observation_cache]=lambda:cache
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result=await client.get('/api/admin/voice/metrics/observations',params={'day':datetime.now(timezone.utc).date().isoformat()})
        await verify_truncate_outcome_redis_http(cache,client)
        await verify_effective_text_redis_http(cache,client)
    assert result.status_code==200
    metric=next(row for row in result.json()['data']['capability_metrics'] if row['name']=='double_reply_count')
    assert metric['value']==1 and metric['status']=='measured'
    assert 'private-text' not in result.text and 'private-memory' not in result.text and 'vendor-q' not in result.text


async def verify_truncate_outcome_redis_http(cache,client):
    from backend.services.realtime_voice_barge_in_service import BargeInController,BargeObservations
    from tests.test_realtime_voice_step017_metrics import Adapter
    observations=BargeObservations()
    async def send(*args,**kwargs):pass
    for failure in (False,True):
        controller=BargeInController(Adapter(fail=failure),send,observations)
        await controller.upgrade('private-reply');await controller.stopped('private-reply',100)
        if not failure:
            event=SimpleNamespace(kind='context_truncated',session_id='s1',payload={'item_id':'item1','audio_end_ms':100})
            assert controller.confirm(event)
        controller.finish_observations();controller.finish_observations()
    assert await VoiceMetrics(cache,deadline_seconds=1).emit_many(observations.drain())
    response=await client.get('/api/admin/voice/metrics/observations',params={'day':datetime.now(timezone.utc).date().isoformat()})
    metric=next(row for row in response.json()['data']['capability_metrics'] if row['name']=='truncate_success_rate')
    assert metric['value']==.5 and metric['status']=='measured'
    assert 'private-reply' not in response.text and 'item1' not in response.text


async def verify_effective_text_redis_http(cache,client):
    from tests.test_realtime_voice_step016_playback import reply,client as playback_frame
    for mapping in (True,False):
        engine,first,_=reply(mapping,True)
        engine.client(playback_frame('client_sentence_played',1,sentence_id=first))
        engine.take_metrics()
        engine.client(playback_frame('client_barge_in',2,played_audio_ms=100))
        assert await VoiceMetrics(cache,deadline_seconds=1).emit_many(engine.take_metrics())
    response=await client.get('/api/admin/voice/metrics/observations',params={'day':datetime.now(timezone.utc).date().isoformat()})
    metric=next(row for row in response.json()['data']['capability_metrics'] if row['name']=='effective_text_evidence_distribution')
    assert metric['value']=={'exact_played':.5,'confirmed_sentences':.5,'full':0,'none':0}
    assert metric['sample_count']==2 and metric['unit']=='text_snapshot'
    assert '第一句' not in response.text and 'call1' not in response.text
