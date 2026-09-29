import asyncio
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step030_recall import service,recall,Adapter,script
from tests.test_realtime_voice_step007_provider import connected,verified_capability,response


def events(sink):return [e for batch in sink.batches for e in batch]


@pytest.mark.asyncio
async def test_current_request_next_cache_hit_and_no_adoption_claim():
    sink=CounterCache();s=service();s.metrics=VoiceMetrics(sink)
    assert (await recall(s,adapter=Adapter('next_turn'))).mode=='next_turn_cached'
    assert (await recall(s,turn_index=2)).mode=='current_turn_requested'
    got=events(sink)
    assert ('voice.recall.cache',{'result':'stored'},1) in got
    assert ('voice.recall.cache',{'result':'hit'},1) in got
    assert ('voice.recall.not_measurable',{'reason':'adoption'},1) in got
    assert all('京都' not in str(e) for e in got)


@pytest.mark.asyncio
async def test_timeout_and_cancellation_classified():
    sink=CounterCache()
    async def model(_):await asyncio.Event().wait()
    s=service(model=model);s.metrics=VoiceMetrics(sink)
    config=script();config['timeout_ms']=5
    assert (await recall(s,script=config)).status=='timeout'
    task=asyncio.create_task(recall(s));await asyncio.sleep(.01);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert ('voice.recall.timeout',{},1) in events(sink)
    assert ('voice.recall.result',{'result':'cancelled'},1) in events(sink)


@pytest.mark.asyncio
async def test_observation_cannot_consume_injection_deadline():
    entered=asyncio.Event();release=asyncio.Event();sink=CounterCache()
    class SlowCache:
        async def eval(self,*args):
            entered.set();await release.wait();return await sink.eval(*args)
    metrics=VoiceMetrics(SlowCache(),deadline_seconds=2)
    class ObservedAdapter:
        async def inject_rag(self,*args):
            await metrics.emit_many([('voice.recall.delivery',{'result':'current_turn_requested'},1)])
            return type('Outcome',(),{'mode':'current_turn_requested'})()
    s=service();s.metrics=metrics
    task=asyncio.create_task(recall(s,adapter=ObservedAdapter()))
    await entered.wait();await asyncio.sleep(.51);release.set()
    assert (await task).mode=='current_turn_requested'


@pytest.mark.asyncio
async def test_real_adapter_duplicate_frames_and_late_injection(monkeypatch):
    from backend.services.realtime_voice_provider_service import decode_frame
    sink=CounterCache();a,wire=await connected(monkeypatch);a.metrics=VoiceMetrics(sink)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._question='q';a._questions['vendor-q']='q'
    assert (await a.inject_rag('q','memory')).mode=='current_turn_requested'
    def event(n,r,**kw):return a._normalize(decode_frame(response(n,a.session_id,dict(question_id='vendor-q',reply_id=r,**kw))))
    assert event(350,'r1',text='first') is not None
    assert event(350,'r2',text='second') is None
    assert event(550,'r2',content='second') is None
    assert (await a.inject_rag('q','again')).mode=='next_turn'
    a._text_started.add('q')
    assert (await a.inject_rag('q','late')).mode=='next_turn'
    await a.finish_session()
    got=events(sink)
    assert ('voice.recall.double_reply',{'result':'detected','unit':'frame'},2) in got
    assert ('voice.recall.double_reply',{'result':'prevented','unit':'frame'},2) in got
    assert ('voice.recall.late',{'reason':'text_started'},1) in got
    assert ('voice.recall.double_reply',{'result':'prevented','unit':'injection'},1) in got


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel',[False,True])
async def test_adapter_send_failure_and_timeout_keep_delivery_outcome(monkeypatch,cancel):
    sink=CounterCache();a,wire=await connected(monkeypatch);a.metrics=VoiceMetrics(sink)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._question='q';a._questions['vendor-q']='q'
    async def fail(*args,**kwargs):
        if cancel:raise asyncio.CancelledError()
        raise ConnectionError('private error')
    monkeypatch.setattr(a,'_send',fail)
    with pytest.raises(asyncio.CancelledError if cancel else ConnectionError):await a.inject_rag('q','memory')
    assert ('voice.recall.delivery',{'result':'cancelled' if cancel else 'failure'},1) in events(sink)


@pytest.mark.asyncio
async def test_unique_reply_observations_bind_capability_and_deduplicate_frames(monkeypatch):
    from backend.services.realtime_voice_provider_service import decode_frame
    sink=CounterCache();a,wire=await connected(monkeypatch);a.metrics=VoiceMetrics(sink)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._question='q';a._questions['vendor-q']='q'
    await a.inject_rag('q','memory')
    for code,rid in [(350,'r1'),(350,'r2'),(550,'r2'),(559,'r2'),(350,'r3')]:
        a._normalize(decode_frame(response(code,a.session_id,dict(question_id='vendor-q',reply_id=rid,text='private',content='private'))))
    await a.finish_session()
    rows=[e for e in events(sink) if e[0]=='voice.recall.reply_observed']
    assert ('voice.recall.reply_observed',{'kind':'primary','evidence':'verified'},1) in rows
    assert ('voice.recall.reply_observed',{'kind':'extra','evidence':'verified'},2) in rows
    assert 'private' not in str(rows) and 'vendor-q' not in str(rows)


@pytest.mark.asyncio
async def test_reply_observation_unverified_and_memory_bound(monkeypatch):
    sink=CounterCache();a,wire=await connected(monkeypatch);a.metrics=VoiceMetrics(sink)
    a._metric_rag_questions.add((a.session_id,'q'))
    a._observe_rag_reply('q','r')
    a._observe_rag_reply('q','r')
    a._metric_rag_replies.update((a.session_id,'q',str(i)) for i in range(4095))
    a._observe_rag_reply('q','overflow1')
    a._observe_rag_reply('q','overflow2')
    await a.finish_session()
    assert len(a._metric_rag_replies)==4096
    rows=[e for e in events(sink) if e[0]=='voice.recall.reply_observed']
    assert rows==[('voice.recall.reply_observed',{'evidence':'unverified','kind':'primary'},1),
                  ('voice.recall.reply_observed',{'evidence':'unverified','kind':'overflow'},1)]


@pytest.mark.asyncio
async def test_reply_observation_primary_is_scoped_to_provider_session(monkeypatch):
    a,wire=await connected(monkeypatch)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._metric_rag_questions.add((a.session_id,'q'))
    a._observe_rag_reply('q','first-session-reply')
    a.session_id='new-session'
    a._observe_rag_reply('q','not-injected')
    assert len(a._metric_rag_replies)==1
    a._metric_rag_questions.add((a.session_id,'q'))
    a._observe_rag_reply('q','new-session-reply')
    a._observe_rag_reply('q','extra')
    rows=[(name,dict(dim),count) for (name,dim),count in a._recall_observations.items() if name=='voice.recall.reply_observed']
    assert ('voice.recall.reply_observed',{'evidence':'verified','kind':'primary'},2) in rows
    assert ('voice.recall.reply_observed',{'evidence':'verified','kind':'extra'},1) in rows


@pytest.mark.asyncio
async def test_actual_reconnect_does_not_count_old_rag_question_in_new_session(monkeypatch):
    from backend.services.realtime_voice_provider_service import decode_frame
    sink=CounterCache();a,wire=await connected(monkeypatch);a.metrics=VoiceMetrics(sink)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._question='q';a._questions['vendor-q']='q'
    await a.inject_rag('q','memory')
    def emit(code,**kw):
        return a._normalize(decode_frame(response(code,a.session_id,dict(question_id='vendor-q',**kw))))
    emit(350,reply_id='old-r',text='old')
    old=a.session_id
    await a.reconnect_session()
    assert a.session_id!=old
    emit(450)
    emit(350,reply_id='new-r',text='new')
    await a.finish_session()
    rows=[e for e in events(sink) if e[0]=='voice.recall.reply_observed']
    assert rows==[('voice.recall.reply_observed',{'evidence':'verified','kind':'primary'},1)]
