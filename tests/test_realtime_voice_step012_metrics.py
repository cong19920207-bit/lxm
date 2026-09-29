import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_ws_metric_service import observed_stream
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step012_gateway import session,storage


@pytest.mark.asyncio
async def test_stream_concurrency_balanced_on_error_and_cancellation():
    sink=CounterCache();metrics=VoiceMetrics(sink)
    with pytest.raises(RuntimeError):
        async with observed_stream(metrics,'initial'):
            async with observed_stream(metrics,'reconnect'):raise RuntimeError('private')
    events=[e for b in sink.batches for e in b]
    assert [e[1]['bucket'] for e in events if e[0]=='voice.ws.concurrency']==['1','2_5','1','0']
    entered=asyncio.Event()
    class Blocking:
        async def emit_many(self,events):
            if events[0][1]['result']=='accepted':entered.set();await asyncio.Future()
    async def run():
        async with observed_stream(Blocking(),'initial'):pass
    task=asyncio.create_task(run());await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    import backend.services.realtime_voice_ws_metric_service as module
    assert module._active_streams==0


@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['origin','tls','ticket'])
@pytest.mark.parametrize('channel',['initial','reconnect'])
async def test_ws_route_rejections_are_closed_and_safe(monkeypatch,reason,channel):
    from backend.routers import realtime_voice as route
    sink=CounterCache();closed=[]
    async def close(**kwargs):closed.append(kwargs)
    socket=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(voice_metrics=VoiceMetrics(sink))),
        headers={'origin':'https://evil.test' if reason=='origin' else 'https://voice.test',
            'sec-websocket-protocol':'wrong-secret' if reason=='ticket' else 'voice.v1, ticket.private-ticket, device.private-device'},
        url=SimpleNamespace(scheme='ws' if reason=='tls' else 'wss',query=''),client=SimpleNamespace(host='203.0.113.1'),close=close)
    monkeypatch.setenv('VOICE_ALLOWED_ORIGINS','https://voice.test');monkeypatch.delenv('VOICE_ALLOW_INSECURE_LOCAL',raising=False)
    await (route.stream if channel=='initial' else route.reconnect_stream)(socket,str(uuid4()))
    assert closed
    assert [e for b in sink.batches for e in b]==[('voice.ws.rejection',{'channel':channel,'reason':reason},1)]


@pytest.mark.asyncio
async def test_gateway_frame_rejection_and_close_reason(storage):
    from backend.services.realtime_voice_ticket_service import TicketError
    gateway=await session(storage);sink=CounterCache();gateway.metrics=VoiceMetrics(sink)
    async def invalid():return 'private-invalid-json'
    gateway.socket.receive_text=invalid
    with pytest.raises(TicketError):await gateway.receiver()
    assert [e for b in sink.batches for e in b]==[('voice.ws.frame_rejection',{'reason':'frame_invalid'},1)]
    async def idle():await asyncio.Future()
    gateway.lifecycle=gateway.heartbeat=gateway.ending_clock=idle
    await gateway.run()
    assert ('voice.ws.close_reason',{'reason':'system_error'},1) in [e for b in sink.batches for e in b]


@pytest.mark.asyncio
async def test_heartbeat_timeout_observes_after_ending(storage,monkeypatch):
    import backend.services.realtime_voice_gateway_service as module
    gateway=await session(storage);sink=CounterCache();gateway.metrics=VoiceMetrics(sink)
    async def immediate(*args):pass
    monkeypatch.setattr(module,'asyncio',SimpleNamespace(sleep=immediate))
    gateway.last_client_heartbeat=-1e9
    ended=[]
    async def end(**kwargs):
        assert sink.batches==[];ended.append(True)
    gateway.request_end=end
    await gateway.heartbeat()
    assert ended==[True] and sink.batches==[[('voice.ws.heartbeat_timeout',{},1)]]


@pytest.mark.asyncio
@pytest.mark.parametrize('status,reason',[('missed','character_missed'),('cancelled','user_cancel')])
async def test_close_reason_uses_committed_terminal_fact(storage,status,reason):
    from sqlalchemy import update
    from backend.models.realtime_voice import VoiceCall
    gateway=await session(storage);sink=CounterCache();gateway.metrics=VoiceMetrics(sink)
    async with storage() as db:
        await db.execute(update(VoiceCall).values(status=status,end_reason=reason));await db.commit()
    assert gateway.end_reason=='system_error'
    await gateway._observe_close_reason()
    assert sink.batches==[[('voice.ws.close_reason',{'reason':reason},1)]]
