import pytest
from tests.test_realtime_voice_step015_turns import event


def reply(mapping=False, sentences=False):
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    engine=PlaybackEvidence(call_id='call1', capability_enabled=lambda key:
        mapping if key=='supports_playback_text_mapping' else sentences)
    seq=0
    def feed(kind,payload):
        nonlocal seq
        seq+=1
        return engine.feed(event('call1',seq,kind,payload,reply='r1'))
    feed('chat_text','第一句。第二句。')
    first=feed('sentence_started',{'text':'第一句。'})['sentence_id']
    feed('tts_audio',b'\0'*4800)
    feed('sentence_finished',{})
    second=feed('sentence_started',{'text':'第二句。'})['sentence_id']
    feed('tts_audio',b'\0'*4800)
    feed('sentence_finished',{})
    feed('text_finished',{})
    feed('tts_finished',{})
    return engine,first,second


def client(kind,seq,**kwargs):
    return dict(type=kind,call_id='call1',reply_id='r1',event_seq=seq,**kwargs)


def test_completed_full_requires_server_finished_audio_and_client_completion():
    engine,_,_=reply()
    assert engine.snapshot('r1').text==''
    result=engine.client(client('client_reply_playback_completed',1))
    assert (result.text,result.evidence,result.completed,result.played_ms)==('第一句。第二句。','full',True,200)
    assert engine.client(client('client_reply_playback_completed',1)) is None


@pytest.mark.parametrize('mapping,sentences,evidence,text',[
    (True,False,'exact_played','第一句。'),
    (False,True,'confirmed_sentences','第一句。'),
    (False,False,'none','')])
def test_interruption_uses_only_verified_boundary_or_confirmed_sentence(mapping,sentences,evidence,text):
    engine,first,_=reply(mapping,sentences)
    engine.client(client('client_sentence_played',1,sentence_id=first))
    result=engine.client(client('client_barge_in',2,played_audio_ms=100))
    assert (result.evidence,result.text,result.interrupted)==(evidence,text,True)


@pytest.mark.parametrize('kwargs',[
    {'played_audio_ms':201}, {'played_audio_ms':-1}, {'played_audio_ms':True},
    {'played_audio_ms':float('nan')}, {'played_audio_ms':100,'text':'伪造正文'}])
def test_invalid_position_or_extra_text_cannot_promote_evidence(kwargs):
    engine,_,_=reply(True,True)
    with pytest.raises(ValueError):engine.client(client('client_playback_progress',1,**kwargs))
    assert engine.snapshot('r1').evidence=='none'


def test_wrong_reply_call_and_backward_position_rejected():
    engine,_,_=reply(True)
    for frame in [dict(client('client_playback_progress',1,played_audio_ms=100),reply_id='other'),
                  dict(client('client_playback_progress',1,played_audio_ms=100),call_id='other')]:
        with pytest.raises(ValueError):engine.client(frame)
    engine.client(client('client_playback_progress',1,played_audio_ms=100))
    with pytest.raises(ValueError):engine.client(client('client_playback_progress',2,played_audio_ms=99))
    assert engine.snapshot('r1').text=='第一句。'


def test_unmapped_partial_sentence_never_interpolates_text():
    engine,_,_=reply(True)
    result=engine.client(client('client_barge_in',1,played_audio_ms=75))
    assert result.text=='' and result.evidence=='none'


def test_no_client_completion_before_provider_end_or_after_barge_in():
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    engine=PlaybackEvidence(call_id='call1',capability_enabled=lambda key:False)
    engine.feed(event('call1',1,'chat_text','没有发完',reply='r1'))
    engine.feed(event('call1',2,'tts_audio',b'\0'*4800,reply='r1'))
    with pytest.raises(ValueError):engine.client(client('client_reply_playback_completed',1))
    engine.client(client('client_barge_in',1,played_audio_ms=0))
    assert engine.client(client('client_reply_playback_completed',2)) is None


def test_sentence_ack_cannot_be_followed_by_contradictory_earlier_position():
    engine,first,_=reply(False,True)
    engine.client(client('client_sentence_played',1,sentence_id=first))
    with pytest.raises(ValueError):engine.client(client('client_barge_in',2,played_audio_ms=50))


def test_submillisecond_boundary_cannot_be_rounded_into_exact_evidence():
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    engine=PlaybackEvidence(call_id='call1',capability_enabled=lambda key:True)
    engine.feed(event('call1',1,'chat_text','句子',reply='r1'))
    engine.feed(event('call1',2,'sentence_started',{'text':'句子'},reply='r1'))
    engine.feed(event('call1',3,'tts_audio',b'\0'*4810,reply='r1'))
    engine.feed(event('call1',4,'sentence_finished',{},reply='r1'))
    assert engine.client(client('client_barge_in',1,played_audio_ms=100)).evidence=='none'


def test_frame_guard_accepts_only_declared_playback_event_fields():
    import json
    from backend.services.realtime_voice_gateway_service import VoiceFrameGuard
    from backend.services.realtime_voice_ticket_service import TicketError
    guard=VoiceFrameGuard()
    frame={'v':1,'seq':1,**client('client_playback_progress',1,played_audio_ms=0)}
    assert guard.parse(json.dumps(frame))['event_seq']==1
    with pytest.raises(TicketError):guard.parse(json.dumps({**frame,'seq':2,'text':'fake'}))


def test_duplicate_provider_audio_does_not_expand_client_report_limit():
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    engine=PlaybackEvidence(call_id='call1',capability_enabled=lambda key:False)
    first=event('call1',1,'tts_audio',b'\0'*4800,reply='r1')
    engine.feed(first);engine.feed(first)
    with pytest.raises(ValueError):engine.client(client('client_playback_progress',1,played_audio_ms=150))


def test_earlier_exact_boundary_remains_proven_after_further_partial_playback():
    engine,_,_=reply(True)
    engine.client(client('client_playback_progress',1,played_audio_ms=100))
    assert engine.client(client('client_barge_in',2,played_audio_ms=150)).text=='第一句。'

def test_audio_completion_is_separate_from_full_text_and_rejects_early_position():
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    engine=PlaybackEvidence(call_id='call1',capability_enabled=lambda _:False)
    engine.feed(event('call1',1,'tts_audio',b'\0'*4800,reply='r1'))
    frame=client('client_audio_playback_completed',1,played_audio_ms=100)
    with pytest.raises(ValueError):engine.client(frame)
    engine.feed(event('call1',2,'tts_finished',{},reply='r1'))
    with pytest.raises(ValueError):engine.client(dict(frame,played_audio_ms=99))
    proof=engine.client(frame)
    assert proof.evidence=='none' and proof.text=='' and not proof.completed
    assert engine.audio_idle()
    assert engine.client(frame) is None
    engine.feed(event('call1',3,'chat_text','你好',reply='r1'))
    engine.feed(event('call1',4,'text_finished',{},reply='r1'))
    assert engine.client(client('client_reply_playback_completed',2)).evidence=='full'

from tests.test_realtime_voice_step012_gateway import storage, session

@pytest.mark.asyncio
@pytest.mark.parametrize('other_audio',[False,True])
async def test_gateway_audio_only_completion_starts_silence_only_when_output_idle(storage,other_audio):
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    from tests.test_realtime_voice_step018_ending import policy
    gateway=await session(storage);gateway.connected=True;gateway.waiting_user=False;gateway.ending=policy()
    gateway.playback=PlaybackEvidence(call_id=gateway.call_id,capability_enabled=lambda _:False)
    proofs=[]
    class Turns:
        async def apply_effective(self,rid,proof):proofs.append(proof)
    gateway.turns=Turns()
    gateway.playback.feed(event(gateway.call_id,1,'tts_audio',b'\0'*4800,reply='r1'))
    gateway.playback.feed(event(gateway.call_id,2,'tts_finished',{},reply='r1'))
    if other_audio:gateway.playback.feed(event(gateway.call_id,3,'tts_audio',b'\0'*4800,reply='r2'))
    await gateway.handle_playback(dict(client('client_audio_playback_completed',1,played_audio_ms=100),call_id=gateway.call_id))
    assert gateway.waiting_user is (not other_audio)
    assert proofs[0].evidence=='none' and not proofs[0].completed
    assert gateway.ending.tick(now=0,waiting=gateway.waiting_user,mic_ok=True,remaining=500)==[]
    expected=[] if other_audio else ['silence_confirm']
    assert gateway.ending.tick(now=6,waiting=gateway.waiting_user,mic_ok=True,remaining=500)==expected
    assert gateway.ending.tick(now=12,waiting=gateway.waiting_user,mic_ok=True,remaining=500)==([] if other_audio else ['goodbye:silence_timeout'])
