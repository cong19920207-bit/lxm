import asyncio
from types import SimpleNamespace
import pytest
from backend.services.realtime_voice_barge_in_service import BargeObservations,BargeInController,observe_barge_in
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step017_barge_in import classifier,voice
from tests.test_realtime_voice_step031_metrics import CounterCache


class Adapter:
    session_id='s1'
    def __init__(self,enabled=True,fail=False):self.enabled=enabled;self.fail=fail
    def capability_enabled(self,key):return self.enabled
    def reply_context_item(self,reply):return 'item1'
    async def interrupt_reply(self,reply):return SimpleNamespace(mode='remote_cancel_requested')
    async def truncate_reply_context(self,*args,**kwargs):
        if self.fail:raise RuntimeError('private-error')
        return SimpleNamespace(mode='context_truncate_requested')


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled,fail,confirmed,expected',[
    (False,False,False,('not_measurable','capability_unavailable')),
    (True,True,False,('failure','request_failed')),
    (True,False,False,('not_measurable','confirmation_unavailable')),
    (True,False,True,('success','confirmed'))])
async def test_stop_and_truncate_classification(enabled,fail,confirmed,expected):
    observations=BargeObservations();sink=CounterCache()
    async def send(*a,**k):pass
    c=BargeInController(Adapter(enabled,fail),send,observations)
    await c.upgrade('r1');await c.upgrade('r1');await c.stopped('r1',100)
    if confirmed:
        event=SimpleNamespace(kind='context_truncated',session_id='s1',payload={'item_id':'item1','audio_end_ms':100})
        assert c.confirm(event) and c.confirm(event)
    c.finish_observations();c.finish_observations()
    events=observations.drain()
    assert ('voice.barge_in.truncate',{'reason':expected[1],'result':expected[0]},1) in events
    assert ('voice.barge_in.stop_clear',{'result':'acknowledged'},1) in events
    assert sum(e[2] for e in events if e[0]=='voice.barge_in.truncate' and e[1]['result']=='success')==int(confirmed)
    assert await VoiceMetrics(sink).emit_many(events)
    assert 'private' not in str(events) and 'item1' not in str(events)


@pytest.mark.asyncio
async def test_send_failure_no_ack_and_classifier_decision():
    observations=BargeObservations()
    async def send(*a,**k):raise ConnectionError('private-send')
    c=BargeInController(Adapter(),send,observations)
    with pytest.raises(ConnectionError):await c.upgrade('r1')
    c.finish_observations()
    assert ('voice.barge_in.stop_clear',{'result':'ack_unavailable'},1) in observations.drain()
    policy=classifier();voice(policy)
    assert policy.text('q1','嗯',final=True)=='backchannel'
    assert policy.text('q1','等等',final=True) is None
    assert policy.observations.drain()==[
        ('voice.barge_in.decision',{'result':'candidate','source':'classifier'},1),
        ('voice.barge_in.decision',{'result':'backchannel','source':'classifier'},1)]


@pytest.mark.asyncio
async def test_observer_waits_for_outer_operation_and_filter_lock():
    owner=SimpleNamespace(barge_observations=BargeObservations(),backchannels=SimpleNamespace(lock=asyncio.Lock()))
    sink=CounterCache();owner.metrics=VoiceMetrics(sink)
    @observe_barge_in
    async def inner(self):self.barge_observations('decision',source='filter',result='candidate')
    @observe_barge_in
    async def outer(self):
        before=len(sink.batches)
        async with self.backchannels.lock:
            await inner(self)
            assert len(sink.batches)==before
        assert len(sink.batches)==before
    await outer(owner)
    assert len(sink.batches)==1
    async with owner.backchannels.lock:await inner(owner)
    assert len(sink.batches)==1
    await outer(owner)
    assert sink.batches[-1]==[('voice.barge_in.decision',{'result':'candidate','source':'filter'},2)]

from tests.test_realtime_voice_step012_gateway import storage,session

@pytest.mark.asyncio
async def test_only_actual_user_interrupt_is_unlabelled(storage):
    from backend.services.realtime_voice_playback_service import PlaybackEvidence,Reply
    gateway=await session(storage);sink=CounterCache();gateway.metrics=VoiceMetrics(sink);gateway.connected=True
    gateway.playback=PlaybackEvidence(call_id=gateway.call_id,capability_enabled=lambda _:False)
    gateway.playback.replies['r1']=Reply('q0',audio_bytes=48000,played_ms=100)
    await gateway.handle_barge_in('backchannel')
    await gateway.handle_barge_in('barge_in');await gateway.handle_barge_in('barge_in')
    events=[e for b in sink.batches for e in b]
    assert events.count(('voice.barge_in.false_interrupt',{'result':'not_measurable'},1))==1


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled,fail,confirmed,result,evidence',[
    (True,False,True,'success','verified'),(True,True,False,'failure','verified'),
    (True,False,False,'unknown','verified'),(False,False,False,'unknown','unverified')])
async def test_truncate_terminal_outcome_once(enabled,fail,confirmed,result,evidence):
    observations=BargeObservations()
    async def send(*a,**k):pass
    controller=BargeInController(Adapter(enabled,fail),send,observations)
    await controller.upgrade('reply');await controller.stopped('reply',100)
    event=SimpleNamespace(kind='context_truncated',session_id='s1',payload={'item_id':'item1','audio_end_ms':100})
    if confirmed:controller.confirm(event);controller.confirm(event)
    controller.finish_observations();controller.finish_observations()
    # Late confirmation after the observation window must not emit a second outcome.
    controller.confirm(event)
    outcomes=[e for e in observations.drain() if e[0]=='voice.barge_in.truncate_outcome']
    assert outcomes==[('voice.barge_in.truncate_outcome',{'evidence':evidence,'result':result},1)]
