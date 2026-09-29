import asyncio
import pytest
from backend.services.realtime_voice_reconnect_service import ReconnectCoordinator
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step019_reconnect import Owner
from tests.test_realtime_voice_step031_metrics import CounterCache


async def exercise(metrics,result):
    class ObservedOwner(Owner):
        async def disconnected(self,client_lost):
            await super().disconnected(client_lost)
            if result=='disconnect_failed':raise RuntimeError('private-disconnect')
            coordinator.boundary('pause')
        async def rebuild(self):
            coordinator.observe('mode',mode='same_session')
            coordinator.observe('attempt',phase='provider')
            if result=='failure':raise RuntimeError('private-rebuild')
            if result=='cancelled':await asyncio.Future()
        async def restored(self):
            await super().restored();coordinator.boundary('resume')
    owner=ObservedOwner();coordinator=ReconnectCoordinator(owner,timeout_ms=30,codec=VoiceTicketCodec(b'r'*32,purpose='voice_reconnect_v1'))
    class Checked:
        async def emit_many(self,events):
            assert not coordinator.lock.locked()
            if result=='restored':assert owner.events[-1]==('restored',)
            if result in ('failure','timeout'):assert owner.events[-1]==('failed',)
            await metrics.emit_many(events)
    owner.metrics=Checked()
    if result=='disconnect_failed':
        with pytest.raises(RuntimeError):await coordinator.begin(client_lost=False)
    else:
        await coordinator.begin(client_lost=result=='timeout')
        if result=='cancelled':
            await asyncio.sleep(0)
            coordinator.cancel()
            with pytest.raises(asyncio.CancelledError):await coordinator.task
        else:await coordinator.task
    return coordinator


@pytest.mark.asyncio
@pytest.mark.parametrize('result',['restored','timeout','failure','cancelled','disconnect_failed'])
async def test_outcomes_outside_business_deadline_and_lock(result):
    sink=CounterCache();c=await exercise(VoiceMetrics(sink),result)
    events=[e for batch in sink.batches for e in batch]
    assert ('voice.reconnect.result',{'result':result},1) in events
    assert sum(e[2] for e in events if e[0]=='voice.reconnect.attempt' and e[1]['phase']=='window')==1
    assert sum(e[2] for e in events if e[0]=='voice.reconnect.timeout')==int(result=='timeout')
    assert ('voice.reconnect.no_charge_boundary',{'boundary':'resume'},1) in events if result=='restored' else True
    assert 'private' not in str(events) and 'call' not in str(events)

from tests.test_realtime_voice_step012_gateway import storage,session

@pytest.mark.asyncio
@pytest.mark.parametrize('actual,expected',[('same_dialog','same_session'),('new_session_with_preamble','new_session')])
async def test_gateway_reports_actual_reconnect_outcome(storage,actual,expected):
    from types import SimpleNamespace
    from tests.test_realtime_voice_step019_reconnect import RebuildAdapter,coordinator
    class Adapter(RebuildAdapter):
        def capability_enabled(self,key):return key=='supports_session_reconnect'
        async def reconnect_session(self):return SimpleNamespace(mode=actual)
    gateway=await session(storage);gateway.adapter=Adapter();gateway.reconnector=coordinator(gateway)
    gateway.reconnector.observation={'events':[]}
    await gateway.rebuild()
    assert ('voice.reconnect.mode',{'mode':expected},1) in gateway.reconnector.observation['events']
