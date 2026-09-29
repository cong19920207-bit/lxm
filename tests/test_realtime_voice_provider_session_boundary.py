"""Provider-owned IDs and suppression guards belong to the provider session."""
import pytest
from backend.services.realtime_voice_provider_service import decode_frame
from tests.test_realtime_voice_step007_provider import connected, verified_capability, response


def event(adapter, code, **payload):
    return adapter._normalize(decode_frame(response(code, adapter.session_id, payload)))


@pytest.mark.asyncio
@pytest.mark.parametrize('resume', [False, True])
async def test_reconnect_identity_scope_preserves_only_resumed_session(monkeypatch, resume):
    adapter, wire = await connected(monkeypatch)
    adapter._capabilities['supports_current_turn_rag_gate'] = verified_capability()
    if resume:
        adapter._capabilities['supports_session_reconnect'] = verified_capability()
    old_session = adapter.session_id
    question = event(adapter,450,question_id='vendor-q',sequence=1).question_id
    assert (await adapter.inject_rag(question,'memory')).mode=='current_turn_requested'
    first = event(adapter,350,question_id='vendor-q',reply_id='vendor-r',text='first',sequence=1)
    event(adapter,550,question_id='vendor-q',reply_id='vendor-r',content='first',sequence=1)
    event(adapter,559,question_id='vendor-q',reply_id='vendor-r',sequence=1)
    event(adapter,359,question_id='vendor-q',reply_id='vendor-r',sequence=1)
    event(adapter,154,input_tokens=3)
    assert adapter.get_usage()=={'input_tokens':3}
    await adapter.reconnect_session()
    if resume:
        assert adapter.get_usage()=={'input_tokens':3}
        assert adapter.session_id==old_session
        assert event(adapter,450,question_id='vendor-q',sequence=1) is None
        repeated=event(adapter,450,question_id='vendor-q',sequence=2)
        assert repeated.question_id==question
        assert (await adapter.inject_rag(question,'memory')).mode=='next_turn'
        assert event(adapter,350,question_id='vendor-q',reply_id='vendor-r',text='first',sequence=1) is None
    else:
        assert adapter.get_usage() is None
        assert adapter.session_id!=old_session
        fresh=event(adapter,450,question_id='vendor-q',sequence=1)
        assert fresh is not None and fresh.question_id!=question
        assert (await adapter.inject_rag(fresh.question_id,'memory')).mode=='current_turn_requested'
        reply=event(adapter,350,question_id='vendor-q',reply_id='vendor-r',text='second',sequence=1)
        assert reply is not None and reply.reply_id!=first.reply_id
        assert event(adapter,550,question_id='vendor-q',reply_id='vendor-r',content='second',sequence=1) is not None
        assert event(adapter,559,question_id='vendor-q',reply_id='vendor-r',sequence=1) is not None
        assert event(adapter,359,question_id='vendor-q',reply_id='vendor-r',sequence=1) is not None
        assert adapter._normalize(decode_frame(response(450,old_session,{'question_id':'late'}))) is None
    await adapter.finish_session()
