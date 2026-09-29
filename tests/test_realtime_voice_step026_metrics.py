import asyncio
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from backend.services.realtime_voice_context_pack_service import build_context_pack,context_pack_events,ContextPackError
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step026_context_pack import persona,settings,Source
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step012_gateway import storage,session


async def pack_for(source=None):
    raw,ref=persona();cfg=settings();cfg['memory_max_items']=1;cfg['recent_dialog_max_chars']=3
    barrier=asyncio.Event()
    class Cropped(Source):
        async def load(self,section,user_id,now):
            return {'schedule':'','recent_dialog':'abcdef','voice_history':'last','memories':[
                dict(id=str(i),content='x'*401,score=i/10,quality=.8,updated_at=now.isoformat()) for i in range(6)]}[section]
    return await build_context_pack(user_id=1,persona_raw=raw,persona_ref=ref,settings=cfg,
        source=source or Cropped(),salutation='你',relationship='朋友',now=datetime.now(timezone.utc),ready_barrier=barrier),barrier


@pytest.mark.asyncio
async def test_context_sizes_crops_and_fallback_without_content():
    pack,barrier=await pack_for();assert pack.metadata['crop_count']==13
    events=context_pack_events(pack=pack,error=None,elapsed_ms=3,barrier_released=barrier.is_set())
    assert ('voice.context_pack.crop_count',{},13) in events
    assert ('voice.context_pack.result',{'result':'full'},1) in events
    class Broken(Source):
        async def load(self,*a):raise RuntimeError('private-source')
    fallback,barrier=await pack_for(Broken())
    events+=context_pack_events(pack=fallback,error=None,elapsed_ms=4,barrier_released=barrier.is_set())
    assert ('voice.context_pack.fallback',{'reason':'source_failed'},1) in events
    assert 'private' not in str(events) and '稳定人格' not in str(events)
    assert await VoiceMetrics(CounterCache()).emit_many(events)


@pytest.mark.parametrize('error,reason',[(ContextPackError('persona_anchor_invalid'),'persona_anchor_invalid'),(RuntimeError('private'),'unavailable'),(asyncio.CancelledError(),'cancelled')])
def test_context_failures_never_claim_released(error,reason):
    events=context_pack_events(pack=None,error=error,elapsed_ms=1,barrier_released=False)
    assert ('voice.context_pack.failure',{'reason':reason},1) in events
    assert ('voice.context_pack.barrier',{'result':'not_released'},1) in events


@pytest.mark.asyncio
async def test_warmup_ready_does_not_wait_on_metric_storage(storage):
    gateway=await session(storage);pack,_=await pack_for();entered=asyncio.Event();release=asyncio.Event()
    class Slow(CounterCache):
        async def eval(self,*a):entered.set();await release.wait();return await super().eval(*a)
    sink=Slow();gateway.metrics=VoiceMetrics(sink,deadline_seconds=1)
    async def context(**kw):kw['barrier'].set();return pack
    async def noop(*a,**k):pass
    gateway.context_builder=context;gateway.adapter.create_connection=noop;gateway.adapter.inject_context=noop;gateway.adapter.start_session=noop
    await asyncio.wait_for(gateway.warmup(),.5)
    assert not entered.is_set() and gateway._warmup_metrics
    publish=asyncio.create_task(gateway._observe_ringing('connected','before_target',0))
    await entered.wait();release.set();await publish
    assert any(e[0]=='voice.context_pack.result' for b in sink.batches for e in b)


@pytest.mark.asyncio
async def test_recovery_deadline_excludes_all_nested_metric_waits():
    from tests.test_realtime_voice_step019_reconnect import Owner
    from backend.services.realtime_voice_reconnect_service import ReconnectCoordinator
    from backend.services.realtime_voice_ticket_service import VoiceTicketCodec
    entered=asyncio.Event();release=asyncio.Event()
    class Slow(CounterCache):
        async def eval(self,*a):entered.set();await release.wait();return await super().eval(*a)
    sink=Slow();metrics=VoiceMetrics(sink,deadline_seconds=1)
    class Observed(Owner):
        async def rebuild(self):
            await metrics.emit_many([('voice.context_pack.result',{'result':'full'},1)])
            await super().rebuild()
    owner=Observed();owner.metrics=metrics
    c=ReconnectCoordinator(owner,timeout_ms=20,codec=VoiceTicketCodec(b'r'*32,purpose='voice_reconnect_v1'))
    await c.begin(client_lost=False);await entered.wait()
    assert owner.events[-1]==('restored',) and not c.active
    await asyncio.sleep(.03);release.set();await c.task
    assert ('voice.reconnect.result',{'result':'restored'},1) in [e for b in sink.batches for e in b]
