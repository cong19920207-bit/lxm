"""Controlled protocol fixtures; never operational capability evidence."""
import asyncio,json
from unittest.mock import AsyncMock
import pytest
from tests.test_realtime_voice_step007_provider import Wire,response,config
from backend.services.realtime_voice_provider_service import ProviderAdminTestRunner


class PlaybackWire(Wire):
    async def send(self,raw):
        await super().send(raw)
        if int.from_bytes(raw[4:8],'big')==300:
            size=int.from_bytes(raw[8:12],'big');sid=raw[12:12+size].decode()
            fields={'question_id':'private-question','reply_id':'private-reply','sentence_id':'private-sentence','text':'sentinel-body'}
            for event,payload,audio in [(350,fields,False),(352,b'\0\0'*20,True),(351,fields,False),(359,fields,False)]:
                await self.incoming.put(response(event,sid,payload,audio))

@pytest.mark.asyncio
async def test_builtin_mapping_collects_real_boundaries_and_validates_without_plaintext(monkeypatch):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    from backend.services.realtime_voice_capability_service import _validate_evidence_record
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    wire=PlaybackWire()
    async def transport(*args,**kwargs):return wire
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    result=await runner.run_capability(capability_key='supports_playback_text_mapping',draft_snapshot=config(),secret='sentinel-secret')
    await runner.aclose()
    assert result['status']=='passed'
    record=result['evidence_record']
    _validate_evidence_record(record,expected_source='admin_capability_test',allow_error=True,path='fixture')
    serialized=json.dumps(result)
    assert all(x not in serialized for x in ('sentinel','private-question','private-reply','private-sentence'))
    assert wire.closed and record['source_type']=='admin_capability_test'

@pytest.mark.asyncio
async def test_builtin_connection_failure_is_valid_error_evidence_and_not_false_failure(monkeypatch):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    from backend.services.realtime_voice_capability_service import _validate_evidence_record
    from backend.services.realtime_voice_provider_service import ProviderError
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    async def transport(*args,**kwargs):raise ProviderError('authentication_failed')
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    result=await runner.run_capability(capability_key='supports_playback_text_mapping',draft_snapshot=config(),secret='sentinel-secret')
    assert result['status']=='error' and result['failure_category']=='authentication_failed'
    _validate_evidence_record(result['evidence_record'],expected_source='admin_capability_test',allow_error=True,path='fixture')
    assert result['evidence_record']['verified_at'] is None and 'sentinel' not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('wrong',[False,True])
@pytest.mark.parametrize('key',['supports_sentence_playback_ack','supports_playback_text_mapping'])
async def test_sentence_probe_requires_exact_played_target_and_closes(monkeypatch,wrong,key):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    from backend.services.realtime_voice_capability_service import _validate_evidence_record
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    wire=PlaybackWire();target=AsyncMock()
    async def confirm(**expected):return {**expected,'session_id':'wrong'} if wrong else expected
    target.wait_played.side_effect=confirm
    async def transport(*args,**kwargs):return wire
    probe=BuiltinCapabilityProbe(playback_target=target)
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=probe)
    try:
        result=await runner.run_capability(capability_key=key,draft_snapshot=config(),secret='sentinel-secret')
        assert result['status']==('error' if wrong else 'passed')
        _validate_evidence_record(result['evidence_record'],expected_source='admin_capability_test',allow_error=True,path='fixture')
        target.write_audio.assert_awaited_once()
    finally:await runner.aclose()
    target.aclose.assert_awaited_once()

@pytest.mark.asyncio
async def test_foreign_session_mapping_cannot_authorize_current_test():
    from types import SimpleNamespace
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    probe=BuiltinCapabilityProbe();probe.connected=True
    fields={'question_id':'foreign-q','reply_id':'foreign-r','sentence_id':'foreign-s','text':'private-foreign-body'}
    async def hello(content):
        for event,payload,audio in [(350,fields,False),(352,b'\0\0'*20,True),(351,fields,False)]:
            probe.record_frame(response(event,'foreign-session',payload,audio))
    adapter=SimpleNamespace(session_id='current-session',call_id='current-call',say_hello=hello,
        receive_event=AsyncMock(return_value=SimpleNamespace(kind='tts_finished',reply_id=None)))
    result=await probe(adapter=adapter,capability_key='supports_playback_text_mapping',draft_snapshot=config())
    assert result['status']=='error' and result['evidence_record']['evidence_payload']['event_evidence']==[]

@pytest.mark.asyncio
async def test_probe_permission_is_request_local_and_never_production_enable(monkeypatch):
    from backend.services.realtime_voice_provider_service import VoiceProviderAdapter,ProviderError
    cfg=config()
    with pytest.raises(ProviderError):
        VoiceProviderAdapter(call_id='call',config=cfg,diagnostic_capability='supports_current_turn_rag_gate')
    a=VoiceProviderAdapter(call_id='test',config=cfg,purpose='admin_test',diagnostic_capability='supports_current_turn_rag_gate')
    assert not a.capability_enabled('supports_current_turn_rag_gate')
    assert a._operation_allowed('supports_current_turn_rag_gate')
    assert not a._operation_allowed('supports_reply_cancel')
    assert cfg==config()

@pytest.mark.asyncio
async def test_verified_reconnect_drops_transport_without_finishing_and_preserves_identity(monkeypatch):
    from backend.services.realtime_voice_provider_service import VoiceProviderAdapter
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app');monkeypatch.delenv('DOUBAO_S2S_ACCESS_KEY',raising=False)
    wires=[Wire(),Wire()]
    async def transport(*a,**kw):return wires.pop(0)
    a=VoiceProviderAdapter(call_id='test',config=config(),purpose='admin_test',diagnostic_capability='supports_session_reconnect',transport_factory=transport)
    await a.inject_context('test persona','');await a.create_connection(secret='fixture-secret');await a.start_session()
    old_wire=a._wire;old_session=a.session_id;old_dialog=a.dialog_id
    await a.reconnect_session()
    assert old_wire.closed
    assert [int.from_bytes(x[4:8],'big') for x in old_wire.sent]==[1,100]
    assert a.session_id==old_session and a.dialog_id==old_dialog
    await a.finish_session()

class ProbeWire(PlaybackWire):
    def __init__(self,shared,*,rag=False,recall=False,bad_ack=False):
        super().__init__();self.shared=shared;self.rag=rag;self.recall=recall;self.bad_ack=bad_ack;self.fed=False
    async def send(self,raw):
        import gzip
        await super().send(raw)
        event=int.from_bytes(raw[4:8],'big')
        if event in (1,2):return
        size=int.from_bytes(raw[8:12],'big');sid=raw[12:12+size].decode();offset=12+size
        payload=gzip.decompress(raw[offset+4:])
        if event==510:
            items=json.loads(payload)['items'];self.shared['nonce']=items[0]['text'].split('口令')[1].split('。')[0]
            items=[{**x,'item_id':f'item-{i}','timestamp':1} for i,x in enumerate(items)]
            if self.bad_ack:items[0]['text']='wrong context'
            await self.incoming.put(response(567,sid,{'items':items}))
        if event==200 and not self.fed:
            self.fed=True
            await self.incoming.put(response(450,sid,{'question_id':'recall-q' if self.recall else 'seed-q'}))
            await self.incoming.put(response(451,sid,{'results':[{'text':'private-prompt','is_interim':False}]}))
            if not self.rag:await self.answer(sid,self.shared.get('nonce') if self.recall else '收到')
        if event==502:
            rag=json.loads(json.loads(payload)['external_rag'])[0]['content']
            self.shared['nonce']=rag.split('口令是')[1].split('，')[0]
            await self.answer(sid,self.shared['nonce'] if self.shared.get('match') else '不知道')
    async def answer(self,sid,text):
        fields={'question_id':'recall-q' if self.recall else 'seed-q','reply_id':'recall-r' if self.recall else 'seed-r','content':text}
        await self.incoming.put(response(550,sid,fields))
        await self.incoming.put(response(559,sid,fields))
        await self.incoming.put(response(359,sid,fields))

@pytest.mark.asyncio
@pytest.mark.parametrize('match',[False,True])
async def test_rag_actual_injection_negative_evidence_or_wait_gate_unverified(monkeypatch,match):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    state={'match':match};wire=ProbeWire(state,rag=True)
    async def transport(*a,**kw):return wire
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    try:result=await runner.run_capability(capability_key='supports_current_turn_rag_gate',draft_snapshot=config(),secret='fixture-secret')
    finally:await runner.aclose()
    assert result['status']==('error' if match else 'failed')
    assert state['nonce'] not in json.dumps(result)
    assert [int.from_bytes(x[4:8],'big') for x in wire.sent].count(502)==1

@pytest.mark.asyncio
@pytest.mark.parametrize('bad_ack',[False,True])
async def test_reconnect_full_hidden_context_chain_or_wrong_context_ack(monkeypatch,bad_ack):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app');monkeypatch.delenv('DOUBAO_S2S_ACCESS_KEY',raising=False)
    shared={};first=ProbeWire(shared,bad_ack=bad_ack);second=ProbeWire(shared,recall=True);wires=[first,second]
    async def transport(*a,**kw):return wires.pop(0)
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    try:result=await runner.run_capability(capability_key='supports_session_reconnect',draft_snapshot=config(),secret='fixture-secret')
    finally:await runner.aclose()
    assert result['status']==('error' if bad_ack else 'passed'), result
    assert shared['nonce'] not in json.dumps(result)
    assert first.closed
    if bad_ack:assert wires==[second]
    else:assert second.closed

@pytest.mark.asyncio
async def test_keep_alive_cancel_diagnostic_never_sends_515_or_claims_failure(monkeypatch):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app');wire=PlaybackWire()
    async def transport(*a,**kw):return wire
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    try:result=await runner.run_capability(capability_key='supports_reply_cancel',draft_snapshot=config(),secret='fixture-secret')
    finally:await runner.aclose()
    assert result['status']=='error'
    assert 'keep_alive' in result['evidence_record']['evidence_payload']['reason_code']
    assert 515 not in [int.from_bytes(x[4:8],'big') for x in wire.sent]

class TruncateWire(Wire):
    def __init__(self,*,shorten=True):super().__init__();self.queries=0;self.shorten=shorten
    async def send(self,raw):
        await super().send(raw)
        event=int.from_bytes(raw[4:8],'big')
        if event in (1,2):return
        size=int.from_bytes(raw[8:12],'big');sid=raw[12:12+size].decode()
        fields={'question_id':'private-q','reply_id':'private-r'}
        if event==300:
            for i,text in enumerate(('第一句。','第二句。')):
                sentence={**fields,'sentence_id':str(i),'text':text}
                for code,payload,audio in ((350,sentence,False),(352,b'\0'*480,True),(351,sentence,False)):
                    await self.incoming.put(response(code,sid,payload,audio))
            await self.incoming.put(response(359,sid,fields))
        if event==512:
            self.queries+=1
            await self.incoming.put(response(569,sid,{'items':[{'item_id':'private-r','role':'assistant','text':'第一句。' if self.queries==2 and self.shorten else '第一句。第二句。'}]}))
        if event==513:await self.incoming.put(response(570,sid,{'item_id':'private-r'}))

@pytest.mark.asyncio
@pytest.mark.parametrize('shorten,wrong_ack',[(True,False),(False,False),(True,True)])
async def test_truncate_requires_real_prefix_stop_and_query_write_readback(monkeypatch,shorten,wrong_ack):
    from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
    from backend.services.realtime_voice_capability_service import _validate_evidence_record
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app');wire=TruncateWire(shorten=shorten);target=AsyncMock()
    async def ack(**expected):return {**expected,'stopped':False} if wrong_ack else expected
    target.wait_stopped.side_effect=ack
    async def transport(*a,**kw):return wire
    runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe(playback_target=target))
    try:result=await runner.run_capability(capability_key='supports_context_truncate',draft_snapshot=config(),secret='fixture-secret')
    finally:await runner.aclose()
    assert result['status']==('error' if wrong_ack else 'passed' if shorten else 'failed'),result
    _validate_evidence_record(result['evidence_record'],expected_source='admin_capability_test',allow_error=True,path='fixture')
    target.aclose.assert_awaited_once()
    assert 'private-' not in json.dumps(result)
    assert wire.queries==(0 if wrong_ack else 2)
