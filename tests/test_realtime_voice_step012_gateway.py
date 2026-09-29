import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from tests.test_realtime_voice_step009_ops import storage, StateCache
from backend.constants.realtime_voice_config import get_default_voice_call_config, get_default_voice_call_script
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_gateway_service import VoiceFrameGuard, socket_credentials, VoiceGatewaySession
from backend.services.realtime_voice_ticket_service import TicketError
from backend.services.realtime_voice_local_runtime import local_voice_calls


@pytest.mark.parametrize('origin,scheme,query,allowed',[
    ('https://app.test','wss','',True), (None,'wss','',False),
    ('https://evil.test','wss','',False), ('https://app.test','ws','',False),
    ('https://app.test','wss','token=secret',False)])
def test_upgrade_origin_tls_and_no_url_credentials(origin,scheme,query,allowed):
    socket=SimpleNamespace(headers={'origin':origin,'sec-websocket-protocol':'voice.v1, ticket.signed.value, device.id'},
        url=SimpleNamespace(scheme=scheme,query=query),client=SimpleNamespace(host='203.0.113.1'))
    if allowed:assert socket_credentials(socket,{'https://app.test'})==('signed.value','id')
    else:
        with pytest.raises(TicketError):socket_credentials(socket,{'https://app.test'},True)


@pytest.mark.parametrize('value',[
    {'v':1,'seq':2,'type':'heartbeat'}, {'v':True,'seq':1,'type':'heartbeat'},
    {'v':1,'seq':1,'type':'heartbeat','token':'private'},
    {'v':1,'seq':1,'type':'audio','pcm_base64':'AA=='},
    {'v':1,'seq':1,'type':'audio','pcm_base64':'%%%'}])
def test_bad_frames_rejected(value):
    with pytest.raises(TicketError):VoiceFrameGuard().parse(json.dumps(value))


def test_frame_sequence_size_and_rate():
    guard=VoiceFrameGuard()
    for seq in range(1,61):guard.parse(json.dumps(dict(v=1,seq=seq,type='heartbeat')))
    with pytest.raises(TicketError,match='frame_rate'):guard.parse(json.dumps(dict(v=1,seq=61,type='heartbeat')))
    with pytest.raises(TicketError,match='frame_too_large'):VoiceFrameGuard().parse('x'*12001)
    with pytest.raises(TicketError):VoiceFrameGuard().parse('[]')


class Socket:
    def __init__(self):self.closed=asyncio.Event();self.frames=[]
    async def receive_text(self):await self.closed.wait();raise RuntimeError('closed')
    async def send_json(self,value):self.frames.append(value)
    async def close(self,**kw):self.closed.set()

class Adapter:
    def __init__(self,**kw):self.finished=0;self.session_id=str(uuid4())
    async def finish_session(self):self.finished+=1


async def session(storage):
    config=get_default_voice_call_config(dict(config_key='persona',version=1,content_sha256='sha256:'+'a'*64))
    async with storage() as db:
        call=VoiceCall(call_id=str(uuid4()),user_id=1,initiated_by='user',status='deciding',summary_status='pending',
            config_snapshot={'resolved_config':config,'resolved_script':get_default_voice_call_script()},capability_snapshot={},
            transcript_retention_days=180,generated_retention_days=30)
        db.add(call);await db.commit()
    return VoiceGatewaySession(socket=Socket(),call=call,cache=StateCache(),session_factory=storage,adapter_factory=Adapter)


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel',[False,True])
async def test_establishment_disconnect_or_cancel_is_distinct_without_charge(storage,cancel,caplog):
    import logging
    caplog.set_level(logging.INFO)
    gateway=await session(storage)
    async def receiver():
        gateway.user_cancelled=cancel
        if not cancel:raise RuntimeError('transport failed')
    async def idle():await asyncio.Event().wait()
    gateway.receiver=receiver;gateway.lifecycle=idle;gateway.heartbeat=idle
    await gateway.run()
    async with storage() as db:
        row=await db.scalar(select(VoiceCall))
        assert row.status==('cancelled' if cancel else 'failed') and row.connected_at is None
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger))==0
    assert gateway.socket.closed.is_set() and gateway.adapter.finished==1
    assert gateway.call.call_id not in local_voice_calls
    assert "voice.ws.close_reason."+("user_cancel" if cancel else "system_error")+"=1" in caplog.text


@pytest.mark.asyncio
async def test_quota_end_reason_survives_receiver_completion_and_settles_once(storage):
    gateway=await session(storage)
    connected=asyncio.Event()
    async def lifecycle():
        from datetime import datetime
        async with storage() as db:
            row=await db.scalar(select(VoiceCall));row.status='connected';row.connected_at=datetime.utcnow();await db.commit()
        await gateway.observe(True);gateway.connected=True;connected.set()
        await asyncio.Event().wait()
    async def heartbeat():
        await connected.wait()
        await gateway.request_end(reason='quota_exhausted')
        # Closing the socket wakes receiver before this task completes.
        await asyncio.Event().wait()
    gateway.lifecycle=lifecycle;gateway.heartbeat=heartbeat
    calls=[];original=gateway.ops.end_call
    async def end(**kw):calls.append(kw['reason']);return await original(**kw)
    gateway.ops.end_call=end
    await gateway.run()
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));assert row.status=='ended' and row.end_reason=='quota_exhausted'
    assert calls==['quota_exhausted'] and gateway.call.call_id not in local_voice_calls


@pytest.mark.asyncio
@pytest.mark.parametrize('target,reason',[('cancelled','user_cancel'),('missed','character_missed'),('failed','system_error')])
async def test_establishment_terminal_reason_replay_and_zero_charge(storage,target,reason):
    from datetime import datetime, timezone
    from backend.services.realtime_voice_decision_service import transition_call
    gateway=await session(storage)
    async with storage() as db:
        assert await transition_call(db,call_id=gateway.call.call_id,expected=('deciding',),target=target,now=datetime.now(timezone.utc))
        assert not await transition_call(db,call_id=gateway.call.call_id,expected=('deciding',),target='failed',now=datetime.now(timezone.utc))
        row=await db.scalar(select(VoiceCall))
        assert row.status==target and row.end_reason==reason
        assert row.connected_at is None and row.summary_status=='not_applicable'
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger))==0


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel',[False,True])
async def test_upgrade_failure_after_ticket_consumption_cleans_call(storage,monkeypatch,cancel):
    from backend.routers import realtime_voice as route
    gateway=await session(storage)
    async def consume(*args,**kw):return gateway.call
    async def cache():return gateway.cache
    async def accept(**kw):
        if cancel:raise asyncio.CancelledError()
        raise RuntimeError('upgrade failed')
    gateway.socket.accept=accept
    monkeypatch.setattr(route,'socket_credentials',lambda *args:('opaque','device'))
    monkeypatch.setattr(route,'ticket_codec_from_environment',lambda:None)
    monkeypatch.setattr(route,'consume_voice_ticket',consume)
    monkeypatch.setattr(route,'get_redis',cache)
    monkeypatch.setattr(route,'async_session_maker',storage)
    if cancel:
        with pytest.raises(asyncio.CancelledError):await route.stream(gateway.socket,gateway.call.call_id)
    else:await route.stream(gateway.socket,gateway.call.call_id)
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));assert row.status=='failed' and row.end_reason=='system_error'
    assert gateway.socket.closed.is_set() and gateway.cache.events


@pytest.mark.asyncio
async def test_external_hard_limit_reason_reaches_gateway_before_socket_closes(storage):
    from contextlib import asynccontextmanager
    from datetime import datetime
    from backend.services.realtime_voice_ops_service import VoiceOpsService
    gateway=await session(storage);connected=asyncio.Event()
    async def lifecycle():
        async with storage() as db:
            row=await db.scalar(select(VoiceCall));row.status='connected';row.connected_at=datetime.utcnow();await db.commit()
        await gateway.observe(True);gateway.connected=True;connected.set()
        await asyncio.Event().wait()
    async def idle():await asyncio.Event().wait()
    gateway.lifecycle=lifecycle;gateway.heartbeat=idle
    @asynccontextmanager
    async def slow_factory():
        await asyncio.sleep(.05)
        async with storage() as db:yield db
    external=VoiceOpsService(cache=gateway.cache,session_factory=slow_factory)
    task=asyncio.create_task(gateway.run());await connected.wait()
    await external.end_call(call_id=gateway.call.call_id,user_id=1,reason='hard_limit')
    await task
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));assert row.status=='ended' and row.end_reason=='hard_limit'


@pytest.mark.asyncio
async def test_warmup_persists_provider_session_and_dialog_after_context_barrier(storage):
    gateway=await session(storage)
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));row.status='ringing';await db.commit()
    order=[]
    async def connect():order.append('connect')
    async def context(**kw):kw['barrier'].set();return SimpleNamespace(persona='人格',dynamic='上下文',degraded=False,metadata={})
    async def inject(persona,dynamic):assert (persona,dynamic)==('人格','上下文');order.append('inject')
    async def start():order.append('start')
    gateway.context_builder=context
    gateway.adapter.create_connection=connect;gateway.adapter.inject_context=inject;gateway.adapter.start_session=start
    gateway.adapter.dialog_id='dialog-test'
    await gateway.warmup()
    async with storage() as db:
        row=await db.scalar(select(VoiceCall))
        assert row.provider_session_id==gateway.adapter.session_id and row.provider_dialog_id=='dialog-test'
    assert order==['connect','inject','start']


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_at_connected', [False, True])
async def test_opening_only_after_connected_and_not_after_cancel(storage, monkeypatch, cancel_at_connected):
    import time
    import backend.services.realtime_voice_gateway_service as module
    from backend.services.realtime_voice_decision_service import CallDecision
    gateway = await session(storage)
    async def decision(**kwargs):
        return CallDecision(True, 4, '喂，我在。', False, None, False)
    async def inputs(*args, **kwargs): return {}
    monkeypatch.setattr(module, 'call_decision_inputs', inputs)
    monkeypatch.setattr(module, 'decide_call', decision)
    async def warmup(): return time.monotonic()
    gateway.warmup = warmup
    greetings = []
    async def hello(content):
        async with storage() as db:
            row = await db.scalar(select(VoiceCall))
            assert row.status == 'connected' and row.connected_at is not None
        assert gateway.connected
        assert gateway.socket.frames[-1]['status'] == 'connected'
        greetings.append(content)
    async def receive():
        gateway.stopped = True
        return SimpleNamespace(kind="usage", payload={}, public_metadata=lambda: {})
    gateway.adapter.say_hello = hello
    gateway.adapter.receive_event = receive
    original_send = gateway.send
    async def send(kind, **kwargs):
        await original_send(kind, **kwargs)
        if cancel_at_connected and kwargs.get('status') == 'connected':
            gateway.cancel.set()
    gateway.send = send
    await gateway.lifecycle()
    assert greetings == ([] if cancel_at_connected else ['喂，我在。'])

@pytest.mark.asyncio
@pytest.mark.parametrize('first',[True,False])
@pytest.mark.parametrize('outcome',['connected','missed','cancelled','failed','cancelled_deciding'])
async def test_real_lifecycle_result_meter_replay_and_scoped_metrics(storage,monkeypatch,caplog,first,outcome):
    import logging
    import backend.services.realtime_voice_gateway_service as module
    gateway=await session(storage);clock=[0.0];prompts=[]
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    async def inputs(*args,**kwargs):return {'is_first_call':first,'missed_last_5_minutes':0,'private_input':'sentinel-personal-body'}
    monkeypatch.setattr(module,'call_decision_inputs',inputs)
    async def model(prompt):
        prompts.append(prompt)
        if outcome=='cancelled_deciding':gateway.cancel.set()
        return json.dumps({'answer':outcome!='missed','delay_seconds':6,'opening_text':'sentinel-opening'})
    gateway.script['call_answer']['prompt_template']='common-template'
    gateway.decision_model=model
    async def warmup():
        if outcome=='cancelled':gateway.cancel.set();return 0.0
        clock[0]=13.0 if outcome=='failed' else 6.0
        return 13.0 if outcome=='failed' else 3.0
    gateway.warmup=warmup
    async def hello(text):pass
    async def receive():gateway.cancel.set();return SimpleNamespace(kind="usage",payload={},session_id="test",question_id=None,public_metadata=lambda:{})
    gateway.adapter.say_hello=hello;gateway.adapter.receive_event=receive
    observations=[];observe=gateway.observe
    async def tracked(connected):observations.append(connected);return await observe(connected)
    gateway.observe=tracked
    caplog.set_level(logging.INFO)
    await gateway.lifecycle()
    expected='cancelled' if outcome=='cancelled_deciding' else outcome
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));at=row.connected_at
        assert row.status==expected
        assert row.call01_fallback is False  # Normal CALL-01 result persisted through the real lifecycle.
        assert (at is not None)==(outcome=='connected')
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger))==0
    # A second establishment callback cannot alter the terminal/connected row or restart metering.
    await gateway.lifecycle()
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));assert row.status==expected and row.connected_at==at
    assert observations==([True] if outcome=='connected' else [])
    assert all(p.startswith('common-template') for p in prompts)
    messages=[r.getMessage() for r in caplog.records if r.name.startswith('backend.services.realtime_voice')]
    assert sum(m==f'voice.call01.ringing_result.{expected}=1' for m in messages)==1
    assert any(m.startswith('voice.call01.provider_ready_order.') for m in messages)
    assert any(m.startswith('voice.call01.decision.') for m in messages)
    assert any(m.startswith('voice.call01.audit ') for m in messages)
    metrics=[m for m in messages if not m.startswith('voice.call01.audit ')]
    assert all(m.startswith(('voice.call01.', 'voice.state.')) and gateway.call.call_id not in m for m in metrics)
    assert all('sentinel' not in m for m in messages)

@pytest.mark.asyncio
@pytest.mark.parametrize('reason,category',[('socket_origin_or_url_rejected','origin_reject'),('wss_required','tls_error'),('sentinel-private-ticket','ticket_reject')])
async def test_upgrade_rejection_metrics_omit_sensitive_details(monkeypatch,caplog,reason,category):
    import logging
    from backend.routers import realtime_voice as route
    def rejected(*args):raise TicketError(reason)
    monkeypatch.setattr(route,'socket_credentials',rejected)
    sock=Socket();caplog.set_level(logging.INFO)
    await route.stream(sock,str(uuid4()))
    messages=[r.getMessage() for r in caplog.records]
    assert messages==[f'voice.ws.{category}=1'] and sock.closed.is_set()
    assert 'sentinel' not in str(messages)

@pytest.mark.asyncio
async def test_receiver_frame_reject_has_only_scoped_metric(storage,caplog):
    import logging
    gateway=await session(storage)
    async def bad():return 'sentinel-private-body'
    gateway.socket.receive_text=bad;caplog.set_level(logging.INFO)
    with pytest.raises(TicketError):await gateway.receiver()
    assert [r.getMessage() for r in caplog.records]==['voice.ws.frame_reject reason=frame_invalid']

@pytest.mark.asyncio
async def test_heartbeat_timeout_metric_and_end_request_are_scoped(storage,monkeypatch,caplog):
    import logging
    import backend.services.realtime_voice_gateway_service as module
    gateway=await session(storage);gateway.config['concurrency']['heartbeat_interval_ms']=1
    gateway.last_client_heartbeat=0
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:1000))
    ended=[]
    async def end(**kwargs):ended.append(kwargs)
    gateway.request_end=end;caplog.set_level(logging.INFO)
    await gateway.heartbeat()
    assert ended==[{}]
    assert [r.getMessage() for r in caplog.records]==['voice.ws.heartbeat_timeout=1']
