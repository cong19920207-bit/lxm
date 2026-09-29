import asyncio
from unittest.mock import AsyncMock
import pytest
from backend.services.realtime_voice_backchannel_service import BackchannelFilter, pure_ack
from backend.services.realtime_voice_provider_service import ProviderEvent

@pytest.mark.asyncio
async def test_selective_filter_preserves_sequence_and_deletes_only_completed_ack():
    sent,drop,delete=AsyncMock(),AsyncMock(),AsyncMock()
    gate=BackchannelFilter({'weak_acknowledgements':['a','b']},sent,drop,delete)
    def e(n,k,q='ack',r=None,p=None):return ProviderEvent(k,'c','s',n,q,r,p)
    await gate.consume(e(1,'user_speech_started'),playing='story')
    await gate.consume(e(2,'sentence_started',r='extra',p={}))
    await gate.consume(e(3,'asr_final',p='a b'))
    await gate.consume(e(4,'tts_finished',r='extra',p={}))
    await asyncio.sleep(0)
    assert delete.await_args.args==('ack',)
    assert {c.args[0].sequence for c in drop.await_args_list}=={2,3,4}
    await gate.consume(e(5,'chat_text','story','original','continued'))
    assert sent.await_args.args[0].question_id=='story'
    await gate.close()

@pytest.mark.asyncio
async def test_valid_speech_and_post_story_ack_pass():
    sent=AsyncMock();g=BackchannelFilter({'weak_acknowledgements':['a']},sent,AsyncMock(),AsyncMock())
    await g.consume(ProviderEvent('user_speech_started','c','s',1,'q'),playing='story')
    await g.consume(ProviderEvent('asr_final','c','s',2,'q',payload='a but wait'))
    assert sent.await_count==2
    await g.consume(ProviderEvent('user_speech_started','c','s',3,'next'),playing=None)
    await g.consume(ProviderEvent('asr_final','c','s',4,'next',payload='a'))
    assert sent.await_count==4
    await g.close()

from tests.test_realtime_voice_step007_provider import connected, response, api
from tests.test_realtime_voice_step012_gateway import storage, session

@pytest.mark.asyncio
async def test_adapter_preserves_explicit_playing_story_and_maps_delete_ack(monkeypatch):
    import gzip,json
    a,wire=await connected(monkeypatch)
    def event(n,p):return a._normalize(api().decode_frame(response(n,a.session_id,p)))
    story=event(450,{'question_id':'story'}).question_id
    event(350,{'question_id':'story','reply_id':'original'})
    event(450,{'question_id':'ack'})
    a.preserve_playing_question(story)
    assert event(550,{'question_id':'story','reply_id':'original','content':'continues'}).question_id==story
    done=event(359,{'question_id':'ack','reply_id':'extra'})
    await a.delete_backchannel(done.question_id)
    raw=wire.sent[-1];assert int.from_bytes(raw[4:8],'big')==514
    n=int.from_bytes(raw[8:12],'big');body=json.loads(gzip.decompress(raw[16+n:]))
    assert body=={'items':[{'item_id':'ack'}]}
    ack=event(571,{'items':[{'item_id':'extra'},{'item_id':'ack'}]})
    assert ack.payload=={'question_ids':[done.question_id]}
    await a.finish_session()

@pytest.mark.asyncio
async def test_gateway_filtered_content_never_reaches_turns_or_playback(storage):
    from backend.services.realtime_voice_playback_service import PlaybackEvidence,Reply
    g=await session(storage);g.connected=True
    g.playback=PlaybackEvidence(call_id=g.call_id,capability_enabled=lambda _:False)
    g.playback.replies['original']=Reply('story',audio_bytes=48000,played_ms=100,last_progress_at=__import__('time').monotonic())
    g.turns=AsyncMock();g.adapter.delete_backchannel=AsyncMock()
    words=g.script['barge_in']['weak_acknowledgements']
    frames=[('user_speech_started',None,None),('sentence_started','extra',{}),
            ('asr_final',None,words[0]+words[0]),('tts_audio','extra',b'\0'*480),
            ('tts_finished','extra',{})]
    for n,(kind,r,p) in enumerate(frames,1):
        await g.process_provider_event(ProviderEvent(kind,g.call_id,'s',n,'ack',r,p))
    await asyncio.sleep(0)
    consumed=[c.args[0] for c in g.turns.consume.await_args_list]
    assert sorted(x.sequence for x in consumed)==[1,2,3,4,5]
    assert not any(x.kind in ('asr_final','tts_audio','sentence_started','tts_finished') for x in consumed)
    assert 'extra' not in g.playback.replies
    assert g.latest_user==''
    await g.backchannels.close()
