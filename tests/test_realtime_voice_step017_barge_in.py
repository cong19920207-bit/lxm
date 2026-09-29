from backend.services.realtime_voice_barge_in_service import BargeInClassifier
from backend.constants.realtime_voice_config import get_default_voice_call_config, get_default_voice_call_script
from tests.test_realtime_voice_m2_shared_extension import REF


def classifier():
    return BargeInClassifier(get_default_voice_call_config(REF)['interaction'], get_default_voice_call_script()['barge_in'])


def voice(c, seconds=.2):
    c.start('q1')
    for n in range(round(seconds/.02)):
        c.audio(b'\x00\x20'*320, now=n*.02)


def test_short_weak_ack_remains_backchannel_and_does_not_repeat():
    c=classifier();voice(c)
    assert c.text('q1','嗯',final=True)=='backchannel'
    assert c.text('q1','嗯',final=True) is None


def test_weak_ack_upgrades_when_continued_with_new_semantics():
    c=classifier();voice(c)
    assert c.text('q1','嗯',final=False) is None
    assert c.text('q1','嗯，但是我想说别的',final=False)=='barge_in'
    assert c.text('q1','再说一句',final=True) is None


def test_sustained_pure_ack_does_not_interrupt_story():
    c=classifier();voice(c,.62)
    assert c.text('q1','嗯',final=False) is None
    assert c.text('q1','嗯',final=True)=='backchannel'


def test_noise_or_echo_without_provider_speech_cannot_interrupt():
    c=classifier()
    for n in range(50):
        assert c.audio(b'\xff\x7f'*320, now=n*.02) is None
    assert c.text('unknown','等等',final=True) is None
    c.start('q1')
    for n in range(50):
        c.audio(b'\x00\x00'*320, now=2+n*.02)
    assert c.text('q1','等等',final=True) is None


def test_packet_burst_cannot_forge_sustained_speech_and_new_question_resets():
    c=classifier();c.start('q1')
    for _ in range(100): c.audio(b'\x00\x20'*320, now=0)
    assert c.text('q1','等等',final=False) is None
    c.start('q2')
    assert c.text('q1','等等',final=True) is None


def test_delayed_asr_final_keeps_observed_voice_evidence_after_silence():
    c=classifier();voice(c)
    c.audio(b'\0\0'*320,now=.21)
    assert c.text('q1','等等',final=True)=='barge_in'


import pytest
from types import SimpleNamespace

@pytest.mark.asyncio
async def test_remote_request_is_never_confirmation_and_ack_must_match():
    from backend.services.realtime_voice_barge_in_service import BargeInController
    frames=[]
    class Adapter:
        session_id='s1'
        async def interrupt_reply(self, reply): return SimpleNamespace(mode='remote_cancel_requested')
        async def truncate_reply_context(self, reply, ms, item_id=None): return SimpleNamespace(mode='context_truncate_requested')
        def reply_context_item(self, reply): return 'item1'
        def capability_enabled(self, key): return True
    async def send(kind, **fields): frames.append((kind, fields))
    c=BargeInController(Adapter(),send)
    await c.upgrade('r1')
    await c.upgrade('r1')
    assert len(frames)==1
    assert await c.stopped('r1',100)=='context_truncate_requested'
    assert c.confirmed('r1') is False
    assert not c.confirm(SimpleNamespace(kind='context_truncated',session_id='s1',payload={'item_id':'wrong','audio_end_ms':100}))
    assert not c.confirm(SimpleNamespace(kind='context_truncated',session_id='old',payload={'item_id':'item1','audio_end_ms':100}))
    assert c.confirm(SimpleNamespace(kind='context_truncated',session_id='s1',payload={'item_id':'item1','audio_end_ms':100}))
    assert c.confirmed('r1')


@pytest.mark.asyncio
async def test_unverified_truncate_and_remote_failure_preserve_local_stop():
    from backend.services.realtime_voice_barge_in_service import BargeInController
    class Adapter:
        async def interrupt_reply(self, reply): raise RuntimeError('transport lost')
        def capability_enabled(self, key): return False
        async def truncate_reply_context(self,*args,**kwargs): raise AssertionError('unverified operation')
    frames=[]
    async def send(kind,**fields): frames.append(kind)
    c=BargeInController(Adapter(),send)
    await c.upgrade('r1')
    assert frames==['stop_playback']
    assert await c.stopped('r1',0)=='context_not_truncated'
    assert not c.confirmed('r1')


from tests.test_realtime_voice_step012_gateway import storage, session

@pytest.mark.asyncio
async def test_gateway_requires_rendered_playback_and_keeps_weak_ack_playing(storage):
    from backend.services.realtime_voice_playback_service import PlaybackEvidence, Reply
    gateway=await session(storage)
    gateway.connected=True
    gateway.playback=PlaybackEvidence(call_id=gateway.call.call_id,capability_enabled=lambda _:False)
    gateway.playback.replies['r1']=Reply('q0',audio_bytes=48000)
    await gateway.handle_barge_in('barge_in')
    assert gateway.socket.frames==[]
    gateway.playback.replies['r1'].played_ms=100
    await gateway.handle_barge_in('backchannel')
    assert gateway.socket.frames==[]
    await gateway.handle_barge_in('barge_in')
    assert gateway.socket.frames[-1]['type']=='stop_playback'
    assert gateway.socket.frames[-1]['reply_id']=='r1'
    await gateway.handle_barge_in('barge_in')
    assert len(gateway.socket.frames)==1
