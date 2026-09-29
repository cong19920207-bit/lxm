"""Formal adapter contracts; transport fixtures are not capability evidence."""
import asyncio
import gzip
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

MODULE = 'backend.services.realtime_voice_provider_service'


def api():
    assert importlib.util.find_spec(MODULE), 'STEP-007 formal provider adapter is missing'
    from backend.services import realtime_voice_provider_service
    return realtime_voice_provider_service


def config():
    from backend.constants.realtime_voice_config import build_canonical_voice_seed_manifest
    return build_canonical_voice_seed_manifest({'config_key': 'persona', 'version': 1, 'content_sha256': 'sha256:' + 'a' * 64})['voice_call_config']


def response(event, session='', payload=None, audio=False):
    body = gzip.compress(payload if audio else json.dumps(payload or {}).encode())
    sid = session.encode()
    return bytes([0x11, 0xb4 if audio else 0x94, 0x01 if audio else 0x11, 0]) + event.to_bytes(4, 'big') + len(sid).to_bytes(4, 'big') + sid + len(body).to_bytes(4, 'big') + body


class Wire:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.closed = False

    async def send(self, raw):
        self.sent.append(raw)
        event = int.from_bytes(raw[4:8], 'big')
        if event == 1:
            await self.incoming.put(response(50, 'connection'))
        elif event == 100:
            n = int.from_bytes(raw[8:12], 'big')
            session = raw[12:12+n].decode()
            await self.incoming.put(response(150, session, {'dialog_id': 'dialog-1'}))

    async def recv(self):
        return await self.incoming.get()

    async def close(self):
        self.closed = True


async def connected(monkeypatch, cfg=None):
    m = api()
    monkeypatch.setenv('DOUBAO_S2S_APP_ID', 'sentinel-app')
    monkeypatch.setenv('DOUBAO_S2S_APP_KEY', 'sentinel-app-key')
    monkeypatch.setenv('DOUBAO_S2S_ACCESS_KEY', 'sentinel-access')
    wire = Wire()
    async def connect(url, **kwargs):
        assert url.startswith('wss://')
        assert kwargs['additional_headers']['X-Api-Access-Key'] == 'sentinel-access'
        return wire
    adapter = m.VoiceProviderAdapter(call_id=str(uuid4()), config=cfg or config(), transport_factory=connect)
    await adapter.inject_context('人格', '会前上下文')
    await adapter.create_connection()
    await adapter.start_session()
    return adapter, wire


def verified_capability():
    import websockets
    return dict(enabled=True, verification_status='verified', effective_scope='all',
                provider_profile='doubao', model_version='2.2.0.0', protocol_profile='doubao_dialog_v3_pcm',
                adapter_version='voice_adapter_v1', sdk_version=api().SDK_VERSION,
                evidence_suite_version='formal-test/v1', evidence_fingerprint='a'*64,
                evidence_report_id=str(uuid4()), last_test_result='passed',
                expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())


@pytest.mark.asyncio
async def test_verified_truncate_uses_protocol_request_and_never_claims_ack(monkeypatch):
    a, wire = await connected(monkeypatch)
    a._capabilities['supports_context_truncate'] = verified_capability()
    a._reply = 'reply'
    out = await a.truncate_reply_context('reply', 123, item_id='item')
    assert int.from_bytes(wire.sent[-1][4:8], 'big') == 513
    assert out.confirmed is False
    await wire.incoming.put(response(570, a.session_id, {'item_id': 'item', 'audio_end_ms': 123}))
    await a.receive_event()
    event = await a.receive_event()
    assert event.kind == 'context_truncated' and event.payload['item_id'] == 'item'
    await a.finish_session()


@pytest.mark.asyncio
async def test_queued_rag_rechecks_question_and_generation_before_send(monkeypatch):
    a, wire = await connected(monkeypatch)
    a._capabilities['supports_current_turn_rag_gate'] = verified_capability()
    a._question = 'q'
    await a._lock.acquire()
    pending = asyncio.create_task(a.inject_rag('q', 'memory'))
    await asyncio.sleep(0)
    a._text_started.add('q')
    before = len(wire.sent)
    a._lock.release()
    result = await pending
    assert result.mode == 'next_turn' and len(wire.sent) == before
    await a.finish_session()


@pytest.mark.asyncio
async def test_queued_interrupt_cannot_cancel_different_reply(monkeypatch):
    a, wire = await connected(monkeypatch)
    a._capabilities['supports_reply_cancel'] = verified_capability()
    a._reply = 'old'
    await a._lock.acquire()
    pending = asyncio.create_task(a.interrupt_reply('old'))
    await asyncio.sleep(0)
    a._reply = 'new'
    before = len(wire.sent)
    a._lock.release()
    with pytest.raises(api().ProviderError):
        await pending
    assert len(wire.sent) == before
    await a.finish_session()


@pytest.mark.asyncio
async def test_old_question_reply_does_not_steal_current_audio_binding(monkeypatch):
    a, wire = await connected(monkeypatch)
    await a.receive_event()
    for q in ['old', 'new']:
        await wire.incoming.put(response(450, a.session_id, {'question_id': q, 'results': [{'text': q}]}))
        await a.receive_event()
    await wire.incoming.put(response(550, a.session_id, {'question_id': 'old', 'reply_id': 'old-r', 'content': 'late'}))
    await wire.incoming.put(response(550, a.session_id, {'question_id': 'new', 'reply_id': 'new-r', 'content': 'current'}))
    assert (await a.receive_chat_text()).payload == 'current'
    await a.finish_session()


@pytest.mark.asyncio
async def test_default_disabled_branches_never_send_unsupported_operations(monkeypatch):
    a, wire = await connected(monkeypatch)
    await a.receive_event()  # session_ready
    await wire.incoming.put(response(450, a.session_id, {'results': [{'text': '问题', 'is_interim': False}], 'question_id': 'q1'}))
    await a.receive_event()  # 450 ASRInfo supplies question identity
    await wire.incoming.put(response(451, a.session_id, {'results': [{'text': '问题', 'is_interim': False}]}))
    q = await a.receive_asr_final()
    await wire.incoming.put(response(550, a.session_id, {'question_id': 'q1', 'reply_id': 'r1', 'content': '回答'}))
    reply = await a.receive_chat_text()
    before = len(wire.sent)
    assert (await a.interrupt_reply(reply.reply_id)).mode == 'local_stop_only'
    assert (await a.truncate_reply_context(reply.reply_id, 100)).confirmed is False
    assert (await a.inject_rag(q.question_id, '记忆')).mode == 'next_turn'
    assert len(wire.sent) == before
    await a.finish_session()
    assert wire.closed


@pytest.mark.asyncio
async def test_normalization_binds_call_question_reply_and_rejects_foreign_session(monkeypatch):
    a, wire = await connected(monkeypatch)
    assert (await a.receive_event()).kind == 'session_ready'
    await wire.incoming.put(response(550, 'foreign-session', {'reply_id': 'r-old', 'content': '串话'}))
    await wire.incoming.put(response(450, a.session_id, {'question_id': 'q', 'results': [{'text': '你好', 'is_interim': False}]}))
    await a.receive_event()  # 450 ASRInfo supplies question identity
    await wire.incoming.put(response(451, a.session_id, {'results': [{'text': '问题', 'is_interim': False}]}))
    q = await a.receive_asr_final()
    for _ in range(2):
        await wire.incoming.put(response(550, a.session_id, {'question_id': 'q', 'reply_id': 'r', 'content': '你好', 'sequence': 1}))
    first = await a.receive_chat_text()
    await wire.incoming.put(response(559, a.session_id, {'question_id': 'q', 'reply_id': 'r'}))
    end = await a.receive_event()
    assert end.kind == 'text_finished'  # duplicate text suppressed
    assert first.call_id == a.call_id and first.question_id == q.question_id
    assert first.reply_id == end.reply_id
    assert set(first.public_metadata()) == {'kind', 'call_id', 'session_id', 'sequence', 'question_id', 'reply_id'}
    assert first.public_metadata()['kind'] == 'chat_text'
    assert '你好' not in repr(first) and '你好' not in json.dumps(first.public_metadata())
    await a.finish_session()


@pytest.mark.asyncio
async def test_reconnect_off_starts_new_session_preserves_call_and_preamble(monkeypatch):
    a, wire = await connected(monkeypatch)
    old, call = a.session_id, a.call_id
    mode = await a.reconnect_session()
    assert mode.mode == 'new_session_with_preamble'
    assert old != a.session_id and call == a.call_id
    starts = [r for r in wire.sent if int.from_bytes(r[4:8], 'big') == 100]
    assert len(starts) == 2
    n = int.from_bytes(starts[-1][8:12], 'big')
    payload = json.loads(gzip.decompress(starts[-1][16+n:]))
    assert '会前上下文' in payload['dialog']['character_manifest']
    await a.finish_session()


@pytest.mark.asyncio
async def test_send_failure_and_cleanup_do_not_expose_secret(monkeypatch, caplog):
    a, wire = await connected(monkeypatch)
    async def fail(_):
        raise RuntimeError('sentinel-access full-private-text')
    wire.send = fail
    with pytest.raises(api().ProviderError) as exc:
        await a.send_audio(b'\x00\x00' * 320)
    assert str(exc.value) == 'upstream_unavailable'
    assert exc.value.__cause__ is None
    await a.finish_session()
    assert wire.closed
    assert 'sentinel' not in caplog.text


@pytest.mark.parametrize('change', ['http', 'wrong_host', 'userinfo', 'query'])
@pytest.mark.asyncio
async def test_credentials_not_sent_to_arbitrary_endpoint(monkeypatch, change):
    cfg = config()
    cfg['s2s']['endpoint'] = {'http': 'ws://openspeech.bytedance.com/api/v3/realtime/dialogue', 'wrong_host': 'wss://evil.invalid/', 'userinfo': 'wss://x@openspeech.bytedance.com/api/v3/realtime/dialogue', 'query': 'wss://openspeech.bytedance.com/api/v3/realtime/dialogue?token=x'}[change]
    with pytest.raises(api().ProviderError, match='invalid_config'):
        await connected(monkeypatch, cfg)


def test_parser_rejects_malformed_or_oversized_frames_without_echo():
    m = api()
    for raw in (b'', b'\x11', b'raw-secret', response(550)[:-1], response(550)+b'extra'):
        with pytest.raises(m.ProviderError, match='protocol_error'):
            m.decode_frame(raw)
    raw = response(352, 's', b'a' * (m.MAX_FRAME_BYTES + 1), audio=True)
    with pytest.raises(m.ProviderError, match='protocol_error'):
        m.decode_frame(raw)


@pytest.mark.asyncio
async def test_admin_factory_is_request_scoped_and_connection_is_real_adapter(monkeypatch):
    m = api()
    from backend.services.realtime_voice_admin_test_service import get_voice_test_runner
    assert isinstance(get_voice_test_runner(), m.ProviderAdminTestRunner)
    assert get_voice_test_runner() is not get_voice_test_runner()
    monkeypatch.setenv('DOUBAO_S2S_APP_ID', 'app')
    monkeypatch.setenv('DOUBAO_S2S_APP_KEY', 'key')
    wire = Wire()
    async def connect(*args, **kwargs):
        return wire
    runner = m.ProviderAdminTestRunner(transport_factory=connect)
    result = await runner.run_connection(draft_snapshot=config(), secret='sentinel-access')
    assert result['status'] == 'passed'
    assert 'sentinel' not in json.dumps(result)
    await runner.aclose()
    assert wire.closed


@pytest.mark.asyncio
async def test_admin_capability_without_real_probe_never_fabricates_support(monkeypatch):
    runner = api().ProviderAdminTestRunner()
    result = await runner.run_capability(capability_key='supports_reply_cancel', draft_snapshot=config(), secret='sentinel')
    assert result['status'] == 'error' and 'evidence_record' not in result


def test_expired_mismatched_and_failed_capabilities_remain_disabled():
    m = api()
    cfg = config()
    for status in ['failed', 'unverified', 'stale', 'verified']:
        cfg['capabilities']['supports_reply_cancel'].update(enabled=True, verification_status=status, effective_scope='all', expires_at=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat())
        a = m.VoiceProviderAdapter(call_id=str(uuid4()), config=cfg, capability_snapshot=cfg['capabilities'])
        assert a.capability_enabled('supports_reply_cancel') is False


def test_missing_question_identity_cannot_be_guessed_from_current_question():
    a = api().VoiceProviderAdapter(call_id=str(uuid4()), config=config())
    a.session_id = 's'
    a._normalize(api().decode_frame(response(450, 's', {'question_id': 'q', 'results': [{'text': 'question'}]})))
    assert a._normalize(api().decode_frame(response(550, 's', {'reply_id': 'unknown', 'content': 'private'}))) is None


@pytest.mark.asyncio
async def test_close_during_connect_does_not_resurrect_transport(monkeypatch):
    monkeypatch.setenv('DOUBAO_S2S_APP_ID', 'app')
    monkeypatch.setenv('DOUBAO_S2S_APP_KEY', 'key')
    started, release = asyncio.Event(), asyncio.Event()
    wire = Wire()
    async def connect(*args, **kwargs):
        started.set()
        await release.wait()
        return wire
    a = api().VoiceProviderAdapter(call_id=str(uuid4()), config=config(), transport_factory=connect)
    pending = asyncio.create_task(a.create_connection(secret='sentinel'))
    await started.wait()
    await a.finish_session()
    release.set()
    with pytest.raises(api().ProviderError):
        await pending
    assert wire.closed and not wire.sent and a._wire is None


@pytest.mark.asyncio
async def test_audio_does_not_borrow_new_text_reply_identity(monkeypatch):
    a, wire = await connected(monkeypatch)
    await a.receive_event()
    await wire.incoming.put(response(450, a.session_id, {'question_id': 'q1', 'results': [{'text': 'one'}]}))
    await a.receive_event()
    await wire.incoming.put(response(350, a.session_id, {'question_id': 'q1', 'reply_id': 'r1'}))
    old = await a.receive_event()
    await wire.incoming.put(response(450, a.session_id, {'question_id': 'q2', 'results': [{'text': 'two'}]}))
    await a.receive_event()
    await wire.incoming.put(response(550, a.session_id, {'question_id': 'q2', 'reply_id': 'r2', 'content': 'new'}))
    new = await a.receive_event()
    await wire.incoming.put(response(352, a.session_id, b'\x01\x00', audio=True))
    audio = await a.receive_event()
    assert audio.reply_id == old.reply_id and audio.reply_id != new.reply_id
    await a.finish_session()


@pytest.mark.asyncio
async def test_old_start_failure_cannot_close_replacement_connection(monkeypatch):
    a, old = await connected(monkeypatch)
    await a.finish_session()
    old_session_started = asyncio.Event()
    original_send = old.send
    async def hold_start(raw):
        if int.from_bytes(raw[4:8], 'big') == 100:
            old_session_started.set()
        else:
            await original_send(raw)
    old.send = hold_start
    await a.create_connection()
    pending = asyncio.create_task(a.start_session())
    await old_session_started.wait()
    sid = a.session_id
    await a.finish_session()
    replacement = Wire()
    async def connect(*args, **kwargs):
        return replacement
    a._factory = connect
    await a.create_connection()
    await a.start_session()
    await old.incoming.put(response(150, sid, {'dialog_id': 'old'}))
    with pytest.raises(api().ProviderError):
        await pending
    assert a._ready and not replacement.closed
    await a.finish_session()


def test_adapter_consumes_existing_immutable_runtime_snapshot():
    from backend.services.realtime_voice_runtime_config_service import VoiceRuntimeSnapshot, _deep_freeze
    c = config()
    snapshot = VoiceRuntimeSnapshot(config_snapshot=_deep_freeze({'resolved_config': c}),
                                    capability_snapshot=_deep_freeze(c['capabilities']))
    a = api().VoiceProviderAdapter.from_snapshot(call_id=str(uuid4()), snapshot=snapshot)
    c['s2s']['model_version'] = 'changed-later'
    assert a._config['s2s']['model_version'] == '2.2.0.0'
    assert not any(a.capability_enabled(k) for k in c['capabilities'])


@pytest.mark.asyncio
async def test_public_app_key_default_needs_only_account_credentials(monkeypatch):
    from backend.services.realtime_voice_gateway_service import provider_preflight
    monkeypatch.setenv('DOUBAO_S2S_APP_ID', 'app')
    monkeypatch.setenv('DOUBAO_S2S_ACCESS_KEY', 'access')
    monkeypatch.delenv('DOUBAO_S2S_APP_KEY', raising=False)
    wire = Wire()
    async def connect(*args, **kwargs):
        assert kwargs['additional_headers']['X-Api-App-Key'] == 'PlgvMymc7f3tQnJ6'
        return wire
    a = api().VoiceProviderAdapter(call_id=str(uuid4()), config=config(), transport_factory=connect)
    assert await provider_preflight(config())
    await a.create_connection()
    await a.finish_session()
    monkeypatch.delenv('DOUBAO_S2S_ACCESS_KEY')
    assert not await provider_preflight(config())


@pytest.mark.asyncio
async def test_opening_is_session_scoped_once_and_not_playback_confirmation(monkeypatch):
    a, wire = await connected(monkeypatch)
    outcomes = await asyncio.gather(a.say_hello('喂，我在。'), a.say_hello('第二次不发'))
    greetings = [raw for raw in wire.sent if int.from_bytes(raw[4:8], 'big') == 300]
    assert len(greetings) == 1
    raw = greetings[0]; size = int.from_bytes(raw[8:12], 'big')
    assert raw[12:12+size].decode() == a.session_id
    assert json.loads(gzip.decompress(raw[16+size:])) == {'content':'喂，我在。'}
    assert all(not out.confirmed for out in outcomes)
    with pytest.raises(api().ProviderError):
        await a.say_hello('x' * 201)
    await a.finish_session()
    with pytest.raises(api().ProviderError):
        await a.say_hello('结束后不发送')


@pytest.mark.asyncio
async def test_real_greeting_shape_binds_only_after_explicit_request(monkeypatch):
    a, wire = await connected(monkeypatch)
    start = response(350, a.session_id, {'question_id':'gq','reply_id':'gr','text':'开场','tts_type':'chat_tts_text'})
    assert a._normalize(api().decode_frame(start)) is None
    await a.say_hello('开场')
    event = a._normalize(api().decode_frame(start))
    assert event.kind == 'sentence_started' and event.question_id and event.reply_id
    audio = a._normalize(api().decode_frame(response(352,a.session_id,b'\x00\x01',audio=True)))
    assert audio.kind == 'tts_audio' and audio.question_id == event.question_id
    assert a._normalize(api().decode_frame(response(350,a.session_id,{'question_id':'unknown','reply_id':'other'}))) is None
    await a.finish_session()


def test_official_asr_450_identity_then_451_text_and_459_end():
    a = api().VoiceProviderAdapter(call_id=str(uuid4()), config=config());a.session_id='s'
    normalize=lambda event,payload:a._normalize(api().decode_frame(response(event,'s',payload)))
    assert normalize(451,{'results':[{'text':'无关联文本'}]}) is None
    start=normalize(450,{'question_id':'q'})
    interim=normalize(451,{'results':[{'text':'你','is_interim':True}]})
    final=normalize(451,{'results':[{'text':'你好','is_interim':False}]})
    end=normalize(459,{})
    assert [e.kind for e in (start,interim,final,end)] == ['user_speech_started','asr_interim','asr_final','user_speech_finished']
    assert len({e.question_id for e in (start,interim,final,end)})==1


def test_empty_asr_end_is_deduplicated_per_question_not_session():
    a=api().VoiceProviderAdapter(call_id=str(uuid4()),config=config());a.session_id='s'
    endings=[]
    for qid in ('first','second'):
        a._normalize(api().decode_frame(response(450,'s',{'question_id':qid})))
        end=response(459,'s',{})
        event=a._normalize(api().decode_frame(end))
        assert event is not None and event.kind=='user_speech_finished'
        endings.append(event.question_id)
        assert a._normalize(api().decode_frame(end)) is None
    assert endings[0]!=endings[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('wrong_target', [False, True])
async def test_admin_playback_requires_exact_target_ack_and_closes(monkeypatch, wrong_target):
    m=api();monkeypatch.setenv('DOUBAO_S2S_APP_ID','app')
    class GreetingWire(Wire):
        async def send(self, raw):
            await super().send(raw)
            if int.from_bytes(raw[4:8],'big')==300:
                size=int.from_bytes(raw[8:12],'big');sid=raw[12:12+size].decode()
                for frame in (response(350,sid,{'question_id':'q','reply_id':'r'}),response(352,sid,b'\x00\x01'*8,audio=True),response(359,sid,{'question_id':'q','reply_id':'r'})):
                    await self.incoming.put(frame)
    wire=GreetingWire()
    async def connect(*args,**kwargs):return wire
    class Target:
        def __init__(self):self.events=[];self.closed=False
        async def aclose(self):self.closed=True
        async def write_audio(self,event):self.events.append(event)
        async def wait_played(self,**expected):
            assert self.events and expected['audio_bytes']==16
            assert expected['reply_id']==self.events[0].reply_id
            return {**expected,'session_id':'wrong' if wrong_target else expected['session_id']}
    runner=m.ProviderAdminTestRunner(transport_factory=connect,playback_target=Target())
    result=await runner.run_playback(draft_snapshot=config(),secret='sentinel-access')
    assert result['status']==('error' if wrong_target else 'passed')
    assert 'evidence_record' not in result and 'sentinel' not in json.dumps(result)
    assert wire.closed and runner._adapter is None and runner._playback_target.closed


@pytest.mark.asyncio
async def test_admin_playback_without_target_never_opens_provider():
    async def connect(*args,**kwargs):raise AssertionError('No target; must not connect')
    runner=api().ProviderAdminTestRunner(transport_factory=connect)
    result=await runner.run_playback(draft_snapshot=config(),secret='sentinel')
    assert result['status']=='error' and result['failure_category']=='evidence_invalid'


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_admin_playback_timeout_or_cancel_cleans_without_ack(monkeypatch, cancel):
    m=api();monkeypatch.setenv('DOUBAO_S2S_APP_ID','app')
    monkeypatch.setattr(m,'ADMIN_PLAYBACK_TIMEOUT_SECONDS',.03)
    wire=Wire();waiting=asyncio.Event()
    original_recv=wire.recv
    async def recv():waiting.set();return await original_recv()
    wire.recv=recv
    async def connect(*args,**kwargs):return wire
    class Target:
        closed=False
        async def write_audio(self,event):raise AssertionError('No audio sent')
        async def wait_played(self,**expected):raise AssertionError('No terminal received')
        async def aclose(self):self.closed=True
    target=Target();runner=m.ProviderAdminTestRunner(transport_factory=connect,playback_target=target)
    task=asyncio.create_task(runner.run_playback(draft_snapshot=config(),secret='sentinel'))
    await waiting.wait()
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    else:
        result=await task
        assert result['status']=='error' and result['failure_category']=='timeout'
    assert wire.closed and target.closed and runner._adapter is None
