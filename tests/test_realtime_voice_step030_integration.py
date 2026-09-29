import asyncio
import gzip
import json

import pytest
from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall
from tests.test_realtime_voice_step028_jobs import memory_env, storage, add_turn
from tests.test_realtime_voice_step030_recall import service, script, Adapter, Context
from tests.test_realtime_voice_step007_provider import connected, verified_capability, response


@pytest.mark.asyncio
async def test_coordinator_reads_safe_final_once_and_cancels_at_end(memory_env):
    from backend.services.realtime_voice_recall_service import VoiceRecallCoordinator
    factory,call=memory_env; await add_turn(factory,call)
    entered=asyncio.Event(); ended=asyncio.Event()
    async def model(prompt):
        entered.set()
        try: await asyncio.Event().wait()
        finally: ended.set()
    a=Adapter(); c=VoiceRecallCoordinator(call_id=call,user_id=1,session_factory=factory,service=service(model=model),adapter=a,script=script())
    c.submit('q1'); c.submit('q1'); assert len(c.tasks)==1
    await asyncio.wait_for(entered.wait(),1)
    await c.close()
    assert ended.is_set() and a.calls==[] and c.tasks=={}


@pytest.mark.asyncio
@pytest.mark.parametrize('change',[{'user_content_safety_status':'matched'},{'user_crisis_status':'matched'}])
async def test_unsafe_stored_final_never_triggers_model(memory_env,change):
    from backend.services.realtime_voice_recall_service import VoiceRecallCoordinator
    factory,call=memory_env; await add_turn(factory,call,**change)
    called=[]
    async def model(prompt): called.append(prompt); return '{}'
    c=VoiceRecallCoordinator(call_id=call,user_id=1,session_factory=factory,service=service(model=model),adapter=Adapter(),script=script())
    c.submit('q1'); await asyncio.gather(*list(c.tasks.values())); await c.close()
    assert not called


@pytest.mark.asyncio
async def test_real_adapter_502_payload_and_single_reply_audio_guard(monkeypatch):
    a,wire=await connected(monkeypatch)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._question='q'; a._questions['vendor-q']='q'
    out=await service().recall(call_id='call',user_id=1,question_id='q',turn_index=1,user_text='记得京都吗',script=script(),preamble='',adapter=a)
    assert out.mode=='current_turn_requested'
    frame=wire.sent[-1]; assert int.from_bytes(frame[4:8],'big')==502
    n=int.from_bytes(frame[8:12],'big'); body=json.loads(gzip.decompress(frame[16+n:]))
    assert json.loads(body['external_rag'])[0]['content']=='计划去京都'
    from backend.services.realtime_voice_provider_service import decode_frame
    def event(number,reply,**payload):
        return a._normalize(decode_frame(response(number,a.session_id,dict(question_id='vendor-q',reply_id=reply,**payload))))
    first=event(350,'r1',text='first',tts_type='external_rag'); assert first is not None
    assert event(550,'r1',content='first') is not None
    assert event(350,'r2',text='second',tts_type='default') is None
    assert a._normalize(decode_frame(response(352,a.session_id,b'\0\0',audio=True))) is None
    assert event(550,'r2',content='second') is None
    assert event(359,'r1') is not None
    assert (await a.inject_rag('q','again')).mode=='next_turn'
    await a.finish_session()


@pytest.mark.asyncio
async def test_gateway_starts_recall_after_durable_asr_without_waiting(storage):
    from tests.test_realtime_voice_step012_gateway import session
    from types import SimpleNamespace
    g=await session(storage)
    events=[]
    class Turns:
        async def consume(self,event): events.append('committed')
    class Recall:
        def submit(self,q): events.append(('recall',q))
    g.turns=Turns(); g.recall=Recall()
    async def forward(*args,**kw): pass
    g.forward_provider_event=forward
    await g._accepted_provider_event(SimpleNamespace(kind='asr_final',question_id='q',reply_id=None,payload='去京都',session_id='s'))
    assert events==['committed',('recall','q')]


@pytest.mark.asyncio
async def test_diagnostic_adapter_keeps_double_reply_evidence(monkeypatch):
    a,wire=await connected(monkeypatch)
    a._purpose='admin_test'
    a._capabilities['supports_current_turn_rag_gate']=verified_capability()
    a._question='q'; a._questions['vendor-q']='q'
    assert (await a.inject_rag('q','memory')).mode=='current_turn_requested'
    from backend.services.realtime_voice_provider_service import decode_frame
    replies=[]
    for rid in ('first','second'):
        event=a._normalize(decode_frame(response(350,a.session_id,dict(question_id='vendor-q',reply_id=rid,text=rid))))
        assert event is not None
        replies.append(event.reply_id)
    assert len(set(replies))==2
    await a.finish_session()


@pytest.mark.asyncio
async def test_concurrent_rag_claim_sends_only_once(monkeypatch):
    a,wire=await connected(monkeypatch)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability(); a._question='q'
    before=len(wire.sent)
    results=await asyncio.gather(*(a.inject_rag('q','memory') for _ in range(100)))
    assert sum(r.mode=='current_turn_requested' for r in results)==1
    assert len(wire.sent)==before+1
    await a.finish_session()


@pytest.mark.asyncio
async def test_terminal_or_empty_event_cannot_claim_rag_reply(monkeypatch):
    a,wire=await connected(monkeypatch)
    a._capabilities['supports_current_turn_rag_gate']=verified_capability(); a._question='q'; a._questions['vendor-q']='q'
    await a.inject_rag('q','memory')
    from backend.services.realtime_voice_provider_service import decode_frame
    def event(n,r,**kw): return a._normalize(decode_frame(response(n,a.session_id,dict(question_id='vendor-q',reply_id=r,**kw))))
    assert event(559,'obsolete') is None
    assert event(550,'empty',content='') is None
    assert event(350,'actual',text='used memory') is not None
    assert event(550,'actual',content='used memory') is not None
    await a.finish_session()
