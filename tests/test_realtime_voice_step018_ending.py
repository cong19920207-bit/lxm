from backend.services.realtime_voice_ending_service import EndingPolicy


def policy():
    return EndingPolicy(connected_at=0, hard_limit=3600, goodbye_timeout=10,
                        silence_confirm=6, silence_hangup=12, time_low=60)


def test_silence_only_when_waiting_with_healthy_unmuted_mic():
    p=policy()
    assert p.tick(now=0,waiting=True,mic_ok=True,remaining=100)==[]
    assert p.tick(now=6,waiting=True,mic_ok=True,remaining=100)==['silence_confirm']
    assert p.tick(now=12,waiting=True,mic_ok=True,remaining=0)==['goodbye:silence_timeout']
    assert p.pending_reason=='silence_timeout'
    assert p.tick(now=15,waiting=True,mic_ok=False,remaining=0)==[]
    assert p.tick(now=22,waiting=False,mic_ok=False,remaining=0)==['end:silence_timeout']


def test_active_mute_thinking_reconnect_never_counts_as_silence():
    p=policy()
    for now in range(30): assert p.tick(now=now,waiting=False,mic_ok=True,remaining=100)==[]
    for now in range(30,60): assert p.tick(now=now,waiting=True,mic_ok=False,remaining=100)==[]
    assert p.tick(now=60,waiting=True,mic_ok=True,remaining=100)==[]
    assert p.tick(now=65,waiting=True,mic_ok=True,remaining=100)==[]


def test_explicit_exit_is_cancellable_and_stale_goodbye_ack_cannot_end():
    p=policy()
    assert p.exit_intent(now=1,explicit=False)==[]
    assert p.exit_intent(now=2,explicit=True)==['goodbye:exit_intent']
    generation=p.generation;p.bind_goodbye('r1',generation)
    assert p.resume(now=3)==['cancel_goodbye']
    assert p.played('r1')==[]
    assert p.exit_intent(now=4,explicit=True)==['goodbye:exit_intent']
    p.bind_goodbye('r2',p.generation)
    assert p.played('r1')==[]
    assert p.played('r2',now=5)==[]
    assert p.tick(now=6.2,waiting=False,mic_ok=True,remaining=100)==['end:exit_intent']
    assert p.tick(now=100,waiting=True,mic_ok=True,remaining=0)==[]


def test_grace_deadline_and_hard_limit_win_once_even_during_reconnect():
    p=policy()
    assert p.tick(now=100,waiting=False,mic_ok=False,remaining=0,grace_deadline=130)==['time_low']
    assert p.tick(now=129,waiting=False,mic_ok=False,remaining=0,grace_deadline=130)==[]
    assert p.tick(now=130,waiting=False,mic_ok=False,remaining=0,grace_deadline=130)==['end:quota_exhausted']
    assert p.tick(now=131,waiting=False,mic_ok=False,remaining=0,grace_deadline=130)==[]
    p=policy();assert p.tick(now=3600,waiting=False,mic_ok=False,remaining=100)==['end:hard_limit']

import pytest

@pytest.mark.asyncio
async def test_control_query_uses_provider_ack_without_fabricating_user_final(monkeypatch):
    from tests.test_realtime_voice_step007_provider import connected, response, api
    adapter, wire=await connected(monkeypatch)
    outcome=await adapter.control_query('只简短告别，不要开启新话题。',kind='goodbye',token='g1')
    assert outcome.mode=='control_requested'
    assert int.from_bytes(wire.sent[-1][4:8], 'big')==501
    event=adapter._normalize(api().decode_frame(response(553,adapter.session_id,{'question_id':'control-question'})))
    assert event.kind=='control_confirmed'
    assert event.payload=={'control_kind':'goodbye','control_token':'g1'}
    assert event.question_id and event.reply_id is None
    assert adapter._normalize(api().decode_frame(response(553,adapter.session_id,{'question_id':'control-question'}))) is None

@pytest.mark.asyncio
async def test_late_control_ack_cannot_replace_new_user_question(monkeypatch):
    from tests.test_realtime_voice_step007_provider import connected,response,api
    adapter,wire=await connected(monkeypatch)
    await adapter.control_query('收尾',kind='time_low',token='t1')
    user=adapter._normalize(api().decode_frame(response(450,adapter.session_id,{'question_id':'new-user'})))
    assert adapter._normalize(api().decode_frame(response(553,adapter.session_id,{'question_id':'old-control'}))) is None
    assert adapter._question==user.question_id

@pytest.mark.asyncio
async def test_closing_guard_rejects_new_topics_invalid_results_and_model_failure():
    from backend.services.realtime_voice_ending_service import ClosingSemanticGate
    seen=[]
    async def model(prompt):
        seen.append(prompt);return '{"allowed": false}'
    gate=ClosingSemanticGate(model=model)
    assert not await gate.allow_reply('工作压力','我们去看一部新电影吧？')
    assert '工作压力' in seen[0] and '不得开启新话题' in seen[0]
    async def bad(_): return '{"allowed": "yes"}'
    assert not await ClosingSemanticGate(model=bad).allow_reply('原主题','新主题')
    async def failing(_): raise RuntimeError('private body')
    assert not await ClosingSemanticGate(model=failing).explicit_exit('我等会要开会')

@pytest.mark.asyncio
async def test_semantic_gate_accepts_only_strict_boolean_decisions():
    from backend.services.realtime_voice_ending_service import ClosingSemanticGate
    async def model(prompt):
        return '{"explicit": true}' if 'explicit' in prompt else '{"allowed": true}'
    gate=ClosingSemanticGate(model=model)
    assert await gate.explicit_exit('我先去开会，晚点聊')
    assert await gate.allow_reply('工作压力','先歇一歇，我们下次聊。')

@pytest.mark.asyncio
async def test_closing_candidate_audio_is_held_then_rejected_before_playback():
    from types import SimpleNamespace
    from backend.services.realtime_voice_ending_service import ClosingOutputBuffer, ClosingSemanticGate
    async def deny(_): return '{"allowed":false}'
    output=ClosingOutputBuffer(ClosingSemanticGate(model=deny))
    for kind,payload in [('chat_text','我们聊一个新话题吧'),('tts_audio',b'\0'*4800)]:
        assert await output.filter(SimpleNamespace(reply_id='r1',kind=kind,payload=payload),restricted=True,topic='工作')==([],False)
    events,rejected=await output.filter(SimpleNamespace(reply_id='r1',kind='text_finished',payload={}),restricted=True,topic='工作')
    assert events==[] and rejected
    assert await output.filter(SimpleNamespace(reply_id='r1',kind='tts_audio',payload=b'\0'*4800),restricted=True,topic='工作')==([],False)

from tests.test_realtime_voice_step008_quota import db, call, NOW

@pytest.mark.asyncio
async def test_live_remaining_does_not_double_subtract_committed_usage(db):
    from datetime import timedelta
    from backend.services.realtime_voice_quota_service import VoiceQuotaService, ConnectedMeter
    c=await call(db);service=VoiceQuotaService();meter=ConnectedMeter(c.call_id,1,300,30)
    await service.observe(db,meter,connected=True,monotonic=0,now=NOW)
    await service.observe(db,meter,connected=True,monotonic=250,now=NOW+timedelta(seconds=250))
    assert await service.remaining(db,meter,now=NOW+timedelta(seconds=250))==50
    await service.settle(db,meter);await db.commit()
    assert await service.remaining(db,meter,now=NOW+timedelta(seconds=250))==50

from tests.test_realtime_voice_step012_gateway import storage, session

@pytest.mark.asyncio
async def test_gateway_suppresses_new_topic_audio_before_client_and_facts(storage):
    from backend.services.realtime_voice_ending_service import ClosingOutputBuffer, ClosingSemanticGate
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    from backend.services.realtime_voice_provider_service import ProviderEvent
    gateway=await session(storage);gateway.connected=True;gateway.ending=policy();gateway.ending.soft_closing=True
    gateway.closing_topic='工作压力'
    async def deny(_): return '{"allowed":false}'
    gateway.closing_output=ClosingOutputBuffer(ClosingSemanticGate(model=deny))
    gateway.playback=PlaybackEvidence(call_id=gateway.call.call_id,capability_enabled=lambda _:False)
    for seq,(kind,payload) in enumerate([('chat_text','我们来聊新电影吧'),('tts_audio',b'\0'*4800),('text_finished',{})],1):
        await gateway.process_provider_event(ProviderEvent(kind,gateway.call.call_id,'s1',seq,'q1','r1',payload))
    assert gateway.socket.frames==[]
    assert gateway.playback.replies=={}

@pytest.mark.asyncio
async def test_gateway_releases_approved_closing_bytes_once_despite_interleaved_usage(storage):
    from backend.services.realtime_voice_ending_service import ClosingOutputBuffer, ClosingSemanticGate
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    from backend.services.realtime_voice_provider_service import ProviderEvent
    gateway=await session(storage);gateway.connected=True;gateway.ending=policy();gateway.ending.soft_closing=True
    async def allow(_): return '{"allowed":true}'
    gateway.closing_output=ClosingOutputBuffer(ClosingSemanticGate(model=allow))
    gateway.playback=PlaybackEvidence(call_id=gateway.call.call_id,capability_enabled=lambda _:False)
    events=[ProviderEvent(k,gateway.call.call_id,'s1',i,q,r,p) for i,(k,q,r,p) in enumerate([
        ('chat_text','q1','r1','先休息，我们下次聊。'),('tts_audio','q1','r1',b'\0'*4800),
        ('usage',None,None,{}),('text_finished','q1','r1',{})],1)]
    for event in events: await gateway.process_provider_event(event)
    assert gateway.playback.replies['r1'].audio_bytes==4800
    assert len([f for f in gateway.socket.frames if f['type']=='audio'])==1
    await gateway.process_provider_event(events[-1])
    assert gateway.playback.replies['r1'].audio_bytes==4800
