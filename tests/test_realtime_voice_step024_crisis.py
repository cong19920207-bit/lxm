"""Real pre-persistence gate, privacy boundaries and audited crisis reads."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func, event as sql_event
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database import get_db
from backend.models.realtime_voice import VoiceCallTurn, VoiceCrisisRecord
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_turn_service import VoiceTurnService, EffectiveText
from backend.services.realtime_voice_runtime_config_service import RealtimeVoiceRuntimeConfigService
from backend.utils.admin_auth import get_current_admin
from tests.test_realtime_voice_step009_ops import storage
from tests.test_realtime_voice_step015_turns import turn_env, event
from tests.test_realtime_voice_step023_safety import Cache

SENTINEL = 'PRIVATE_CRISIS_SENTINEL'


class CrisisCache(Cache):
    def __init__(self, crisis='["PRIVATE_CRISIS"]', fail=False):
        super().__init__('[]', fail)
        self.crisis = crisis
    async def get(self, key):
        if self.fail:
            raise RuntimeError(SENTINEL)
        if key == 'active_config:crisis_keywords':
            return self.crisis
        return await super().get(key)


def gate_for(cache, signals=None, session_factory=None):
    from backend.services.realtime_voice_safety_service import VoiceSafetyGate
    from backend.services.realtime_voice_crisis_service import VoiceCrisisGate
    def unavailable_database():
        raise ConnectionError('test database unavailable')
    async def provider():
        return cache
    async def notify(signal):
        signals.append(signal)
    return VoiceSafetyGate(cache=cache, crisis_gate=VoiceCrisisGate(
        loader=RealtimeVoiceRuntimeConfigService(redis_provider=provider,
            session_factory=session_factory or unavailable_database),
        notify=notify if signals is not None else None))


@pytest.mark.asyncio
@pytest.mark.parametrize('redis_unavailable', [False, True])
async def test_published_policy_recovers_crisis_gate_without_bypassing_other_safety(turn_env, redis_unavailable):
    from backend.models.admin_config import AdminConfig
    from backend.models.realtime_voice import VoiceCall
    from backend.services.realtime_voice_card_service import summary_eligible
    factory, call_id = turn_env
    async with factory() as db:
        db.add(AdminConfig(config_key='crisis_keywords', config_value='["fixture-only-keyword"]',
                           version=1, is_active=True, is_draft=False))
        await db.commit()
    gate = gate_for(CrisisCache(None, fail=redis_unavailable), session_factory=factory)
    turns = VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate)
    await turns.consume(event(call_id,1,'asr_final','我下个月准备去日本旅行'))
    await turns.consume(event(call_id,2,'chat_text','可以一起规划行程',reply='r1'))
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    await turns.apply_effective('r1',EffectiveText('可以一起规划行程','full',completed=True))
    async with factory() as db:
        row = await db.scalar(select(VoiceCallTurn))
        assert row.user_crisis_status == row.assistant_crisis_status == 'passed'
        assert row.user_text_final == '我下个月准备去日本旅行'
        assert row.assistant_text_effective == '可以一起规划行程'
        assert row.effective_text_evidence != 'none'
        assert row.user_content_safety_status == ('error_allowed' if redis_unavailable else 'passed')
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord)) == 0
        call = await db.scalar(select(VoiceCall))
        call.duration_seconds = 30
        call.connected_at = datetime.utcnow()-timedelta(seconds=30)
        await db.flush()
        assert await summary_eligible(db, call) is (not redis_unavailable)


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,fail,status', [('["PRIVATE_CRISIS"]',False,'matched'), (None,False,'suspected'), ('[]',False,'suspected'), ('{}',False,'suspected'), ('bad-json',False,'suspected'), ('["safe"]',True,'suspected')])
async def test_crisis_both_sides_isolated_and_single_public_signal(turn_env, raw, fail, status, caplog):
    factory, call_id = turn_env
    signals = []
    gate = gate_for(CrisisCache(raw,fail),signals)
    turns = VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate)
    await turns.consume(event(call_id,1,'asr_final',SENTINEL))
    await turns.consume(event(call_id,2,'chat_text',SENTINEL,reply='r1'))
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    await turns.apply_effective('r1',EffectiveText(SENTINEL,'full',completed=True))
    async with factory() as db:
        row = await db.scalar(select(VoiceCallTurn))
        records = (await db.scalars(select(VoiceCrisisRecord).order_by(VoiceCrisisRecord.direction))).all()
        assert row.user_text_final is row.assistant_text_generated is row.assistant_text_effective is None
        assert row.user_crisis_status == row.assistant_crisis_status == status
        assert row.memory_status == 'skipped'
        assert len(records) == 2 and all(r.content_plaintext == SENTINEL for r in records)
        assert [r.is_persona_incident for r in records] == [True,False]
        assert all(timedelta(days=29) < r.expires_at-datetime.utcnow() <= timedelta(days=30) for r in records)
    assert signals == [{'type':'crisis_detected','call_id':call_id}]
    assert SENTINEL not in caplog.text and 'persona_incident' in caplog.text
    assert all(d.user_final is None and d.generated == '' for d in turns._drafts.values())


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['isolation','turn'])
async def test_failed_transaction_never_leaves_partial_plaintext(turn_env,target,caplog):
    factory, call_id = turn_env
    signals = []
    turns = VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate_for(CrisisCache(),signals))
    def fail(mapper, connection, row):
        raise RuntimeError(SENTINEL)
    model = VoiceCrisisRecord if target == 'isolation' else VoiceCallTurn
    sql_event.listen(model, 'before_insert', fail)
    try:
        await turns.consume(event(call_id,1,'asr_final',SENTINEL))
    finally:
        sql_event.remove(model,'before_insert',fail)
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord)) == 0
        rows = (await db.scalars(select(VoiceCallTurn))).all()
        assert all(r.user_text_final is None and r.user_crisis_status == 'isolation_failed' for r in rows)
    assert signals == [] and SENTINEL not in caplog.text
    assert not turns._pending and all(d.user_final is None for d in turns._drafts.values())


async def seed_record(factory,call_id,expired=False):
    async with factory() as db:
        row=VoiceCrisisRecord(call_id=call_id,turn_index=1,direction='user',content_plaintext=SENTINEL,
            matched_keyword='PRIVATE_CRISIS',match_status='matched',is_persona_incident=False,
            expires_at=datetime.utcnow()+timedelta(days=-1 if expired else 30))
        db.add(row)
        await db.commit()
        return row.id


def app_for(factory,role):
    from backend.routers.admin.voice_crisis import router
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='admin',role=role)
    async def db_override():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db]=db_override
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','tech_ops','ops_admin','observer','ai_trainer'])
async def test_each_read_audited_only_super_admin_can_read(turn_env,role):
    factory,call_id=turn_env
    record_id=await seed_record(factory,call_id)
    app=app_for(factory,role)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        for suffix in ['',f'/{record_id}',f'/{record_id}']:
            response=await client.get('/api/admin/voice/crisis-records'+suffix)
            assert response.status_code == (200 if role=='super_admin' else 403)
            if role!='super_admin':assert SENTINEL not in response.text
        response=await client.post('/api/admin/voice/crisis-records/export')
        assert response.status_code in (404,405)
    async with factory() as db:
        audits=(await db.scalars(select(AdminOperationLog))).all()
        assert len(audits) == (3 if role=='super_admin' else 0)
        assert all(call_id in a.target_description for a in audits)
        assert all(SENTINEL not in str(a.__dict__) for a in audits)


@pytest.mark.asyncio
async def test_expired_text_is_hidden_and_cleanup_clears_only_expired(turn_env):
    from backend.services.realtime_voice_crisis_service import clear_expired_crisis
    factory,call_id=turn_env
    record_id=await seed_record(factory,call_id,expired=True)
    async with AsyncClient(transport=ASGITransport(app=app_for(factory,'super_admin')),base_url='http://test') as client:
        response=await client.get(f'/api/admin/voice/crisis-records/{record_id}')
        assert response.status_code==200 and SENTINEL not in response.text
    async with factory() as db:
        assert await clear_expired_crisis(db)==1
        await db.commit()
        row=await db.get(VoiceCrisisRecord,record_id)
        assert row.content_plaintext is None and row.matched_keyword is None and row.cleared_at is not None


@pytest.mark.asyncio
async def test_production_gateway_default_gate_and_partial_crisis_do_not_stop_playback(turn_env):
    from tests.test_realtime_voice_step012_gateway import session
    factory, call_id=turn_env
    gateway=await session(factory)
    # The runtime must construct a real gate by default; no injected test gate.
    cache=gateway.cache
    cache.data['active_config:crisis_keywords']='["PRIVATE_CRISIS"]'
    decision=await gateway.turn_gate.assess(call_id=call_id,direction='assistant',text=SENTINEL)
    assert decision.crisis=='matched'
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gateway.turn_gate)
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text',SENTINEL,reply='r1'))
    await turns.apply_effective('r1',EffectiveText(SENTINEL,'confirmed_sentences'))
    await turns.consume(event(call_id,3,'chat_text',' tail',reply='r1'))
    await turns.consume(event(call_id,4,'tts_finished',reply='r1'))
    await turns.apply_effective('r1',EffectiveText(SENTINEL+' tail','full',completed=True))
    assert gateway.socket.frames==[{'v':1,'seq':1,'type':'crisis_detected','call_id':call_id,
        'banner':gateway.script['crisis']['in_call_banner']}]
    assert not gateway.closed_event.is_set()
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn))
        assert row.turn_status=='finalized' and row.assistant_text_generated is row.assistant_text_effective is None
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord))==1
        record=await db.scalar(select(VoiceCrisisRecord))
        assert record.content_plaintext==SENTINEL+' tail'


@pytest.mark.asyncio
async def test_audit_failure_never_returns_body(turn_env):
    factory,call_id=turn_env
    record_id=await seed_record(factory,call_id)
    def fail(mapper,connection,row):raise RuntimeError('audit unavailable')
    sql_event.listen(AdminOperationLog,'before_insert',fail)
    try:
        transport=ASGITransport(app=app_for(factory,'super_admin'),raise_app_exceptions=False)
        async with AsyncClient(transport=transport,base_url='http://test') as client:
            result=await client.get(f'/api/admin/voice/crisis-records/{record_id}')
            assert result.status_code==500 and SENTINEL not in result.text
    finally:sql_event.remove(AdminOperationLog,'before_insert',fail)


@pytest.mark.asyncio
async def test_scheduled_expiry_clears_only_due_records(turn_env,monkeypatch):
    # Legacy authentication tests install a scheduler stub in sys.modules at
    # collection. Load the real module under a local name without altering it.
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('m4_scheduler_under_test',
        Path(__file__).resolve().parents[1]/'backend/tasks/scheduler.py')
    scheduler=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scheduler)
    import backend.database as database
    factory,call_id=turn_env
    record_id=await seed_record(factory,call_id,expired=True)
    fresh_id=await seed_record(factory,call_id+'-fresh')
    monkeypatch.setattr(database,'async_session_maker',factory)
    await scheduler._run_voice_crisis_expiry()
    async with factory() as db:
        expired=await db.get(VoiceCrisisRecord,record_id)
        fresh=await db.get(VoiceCrisisRecord,fresh_id)
        assert expired.content_plaintext is None and expired.cleared_at is not None
        assert fresh.content_plaintext==SENTINEL and fresh.cleared_at is None


@pytest.mark.asyncio
async def test_unplayed_generated_crisis_never_enters_ordinary_turn(turn_env):
    factory,call_id=turn_env
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate_for(CrisisCache()))
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text','hello '+SENTINEL,reply='r1'))
    await turns.apply_effective('r1',EffectiveText('hello','confirmed_sentences'))
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn))
        assert row.assistant_text_generated is None
        assert row.assistant_text_effective=='hello' and row.assistant_crisis_status=='passed'
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord))==0


@pytest.mark.asyncio
async def test_full_page_audit_preserves_every_read_identity(turn_env):
    from uuid import uuid4
    factory,call_id=turn_env
    ids=[call_id]+[str(uuid4()) for _ in range(19)]
    for identity in ids:await seed_record(factory,identity)
    transport=ASGITransport(app=app_for(factory,'super_admin'),raise_app_exceptions=False)
    async with AsyncClient(transport=transport,base_url='http://test') as client:
        response=await client.get('/api/admin/voice/crisis-records')
        assert response.status_code==200 and len(response.json()['data']['items'])==20
    async with factory() as db:
        audits=(await db.scalars(select(AdminOperationLog))).all()
        assert all(len(a.target_description)<=500 for a in audits)
        assert all(any(identity in a.target_description for a in audits) for identity in ids)


@pytest.mark.asyncio
async def test_gateway_drops_crisis_context_and_completed_playback_text(turn_env):
    from tests.test_realtime_voice_step012_gateway import session
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    factory,call_id=turn_env
    gateway=await session(factory)
    gateway.call_id=call_id
    gateway.cache.data['active_config:crisis_keywords']='["PRIVATE_CRISIS"]'
    gateway.turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gateway.turn_gate)
    gateway.playback=PlaybackEvidence(call_id=call_id,capability_enabled=lambda _:True)
    gateway.connected=True
    gateway.ending=SimpleNamespace(played=lambda _:[],take_metrics=lambda:[])
    final=event(call_id,1,'asr_final',SENTINEL)
    await gateway.turns.consume(final)
    await gateway.observe_ending_event(final)
    assert gateway.latest_user=='' and gateway.closing_topic==''
    events=[event(call_id,2,'chat_text',SENTINEL,reply='r1'),
            event(call_id,3,'tts_audio',b'\0'*480,reply='r1'),
            event(call_id,4,'text_finished',reply='r1'),
            event(call_id,5,'tts_finished',reply='r1')]
    for item in events:
        await gateway.turns.consume(item)
        gateway.playback.feed(item)
    await gateway.handle_playback({'type':'client_reply_playback_completed','call_id':call_id,'reply_id':'r1','event_seq':1})
    reply=gateway.playback.replies['r1']
    assert reply.completed and reply.audio_bytes==480 and reply.played_ms==10
    assert reply.text=='' and all(s.text=='' for s in reply.sentences.values())


def test_barge_in_retains_only_semantic_flags_after_final():
    from tests.test_realtime_voice_step017_barge_in import classifier
    c=classifier();c.start('q1')
    private_text='机密内容只在内存'
    assert c.text('q1',private_text,final=True) is None
    assert private_text not in str(c.__dict__)
    decisions=[c.audio(b'\x00\x20'*320,now=i*.02) for i in range(20)]
    assert 'barge_in' in decisions


@pytest.mark.asyncio
@pytest.mark.parametrize('interrupted',[False,True])
async def test_full_effective_replaces_nonprefix_sentence_ack_isolation(turn_env,interrupted):
    factory,call_id=turn_env
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate_for(CrisisCache()))
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text','first '+SENTINEL,reply='r1'))
    await turns.apply_effective('r1',EffectiveText(SENTINEL,'confirmed_sentences'))
    async with factory() as db:
        expires=(await db.scalar(select(VoiceCrisisRecord))).expires_at
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    await turns.apply_effective('r1',EffectiveText('first '+SENTINEL,
        'confirmed_sentences' if interrupted else 'full',completed=not interrupted,interrupted=interrupted))
    async with factory() as db:
        row=await db.scalar(select(VoiceCrisisRecord))
        assert row.content_plaintext=='first '+SENTINEL and row.expires_at==expires


@pytest.mark.asyncio
async def test_closing_secondary_model_never_receives_unassessed_crisis(turn_env):
    from tests.test_realtime_voice_step012_gateway import session
    factory,_=turn_env
    gateway=await session(factory)
    gateway.cache.data['active_config:crisis_keywords']='["PRIVATE_CRISIS"]'
    prompts=[]
    async def model(prompt):
        prompts.append(prompt);return '{"allowed":true}'
    gateway.semantic_gate.model=model
    assert await gateway.semantic_gate.allow_reply('ordinary',SENTINEL) is None
    assert prompts==[]
    assert await gateway.semantic_gate.allow_reply('ordinary','goodbye') is True
    assert len(prompts)==1 and SENTINEL not in prompts[0]


@pytest.mark.asyncio
async def test_final_flush_releases_unplayed_draft(turn_env):
    factory,call_id=turn_env
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate_for(CrisisCache()))
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text',SENTINEL,reply='r1'))
    await turns.freeze()
    async with factory() as db:
        await turns.final_flush(db);await db.commit()
    assert all(d.generated=='' and d.user_final is None for d in turns._drafts.values())
    assert not turns._pending_effective


@pytest.mark.asyncio
async def test_unproven_interruption_cannot_erase_existing_isolation(turn_env):
    factory,call_id=turn_env
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate_for(CrisisCache()))
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text',SENTINEL,reply='r1'))
    await turns.apply_effective('r1',EffectiveText(SENTINEL,'confirmed_sentences'))
    await turns.apply_effective('r1',EffectiveText('','none',interrupted=True))
    async with factory() as db:
        assert (await db.scalar(select(VoiceCrisisRecord))).content_plaintext==SENTINEL


@pytest.mark.asyncio
async def test_turn_update_failure_after_isolation_insert_rolls_back_both(turn_env,caplog):
    factory,call_id=turn_env
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate_for(CrisisCache()))
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text',SENTINEL,reply='r1'))
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    inserted=[]
    def saw_insert(mapper,connection,row):inserted.append(row.id)
    def fail_final_update(mapper,connection,row):
        if row.assistant_crisis_status=='matched' and row.turn_status=='finalized':
            raise RuntimeError(SENTINEL)
    sql_event.listen(VoiceCrisisRecord,'after_insert',saw_insert)
    sql_event.listen(VoiceCallTurn,'before_update',fail_final_update)
    try:await turns.apply_effective('r1',EffectiveText(SENTINEL,'full',completed=True))
    finally:
        sql_event.remove(VoiceCrisisRecord,'after_insert',saw_insert)
        sql_event.remove(VoiceCallTurn,'before_update',fail_final_update)
    assert inserted
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord))==0
        row=await db.scalar(select(VoiceCallTurn))
        assert row.assistant_text_generated is row.assistant_text_effective is None
    assert SENTINEL not in caplog.text
    assert not turns._pending_effective and turns._drafts['q1'].generated==''
