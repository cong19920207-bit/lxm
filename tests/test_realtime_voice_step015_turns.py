"""Final-only voice facts and mandatory pre-persistence isolation boundary."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, func

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceCallTurn, VoiceCrisisRecord
from backend.models.conversation_log import ConversationLog
from backend.services.realtime_voice_provider_service import ProviderEvent
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache


@pytest_asyncio.fixture
async def turn_env(storage):
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[m.__table__ for m in
            (VoiceCallTurn, VoiceCrisisRecord, ConversationLog)])
    call_id = await add_call(storage, 'connected', StateCache())
    return storage, call_id


class Gate:
    def __init__(self, crisis='passed', safety='passed', fail=False):
        self.crisis, self.safety, self.fail = crisis, safety, fail
    async def assess(self, *, call_id, direction, text):
        from backend.services.realtime_voice_turn_service import GateDecision
        return GateDecision(self.safety, self.crisis)
    async def isolate(self, db, *, call, turn, direction, text, decision):
        db.add(VoiceCrisisRecord(call_id=call.call_id, turn_index=turn.turn_index,
            direction=direction, content_plaintext=text, match_status=decision.crisis,
            is_persona_incident=direction=='assistant', expires_at=datetime.utcnow()+timedelta(days=1)))
        await db.flush()
        if self.fail:
            raise RuntimeError('SENTINEL_ISOLATION_ERROR')


def event(call_id, sequence, kind, payload=None, question='q1', reply=None, session='session1'):
    return ProviderEvent(kind, call_id, session, sequence, question, reply, payload)


@pytest.mark.asyncio
async def test_interim_is_not_a_fact_final_persists_immediately_and_no_text_chat_write(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id = turn_env
    service = VoiceTurnService(call_id=call_id, session_id='session1', session_factory=factory, gate=Gate())
    await service.consume(event(call_id,1,'asr_interim','我想'))
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceCallTurn)) == 0
    await service.consume(event(call_id,2,'asr_final','我想去海边'))
    async with factory() as db:
        row = await db.scalar(select(VoiceCallTurn))
        assert (row.turn_index,row.user_text_final,row.assistant_text_effective,row.effective_text_evidence)==(1,'我想去海边',None,'none')
        assert (row.user_crisis_status,row.user_content_safety_status)==('passed','passed')
        assert await db.scalar(select(func.count()).select_from(ConversationLog)) == 0


@pytest.mark.asyncio
async def test_out_of_order_duplicate_cross_call_and_cross_session_do_not_pollute(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id = turn_env
    service = VoiceTurnService(call_id=call_id, session_id='session1', session_factory=factory, gate=Gate())
    await service.consume(event(call_id,2,'asr_final','最终'))
    await service.consume(event(call_id,1,'asr_interim','临时'))
    await service.consume(event(call_id,2,'asr_final','重复污染'))
    for foreign in [event(str(uuid4()),3,'asr_final','跨通'),event(call_id,3,'asr_final','旧会话',session='old')]:
        with pytest.raises(ValueError): await service.consume(foreign)
    await service.consume(event(call_id,3,'asr_final','第二句',question='q2'))
    async with factory() as db:
        rows=(await db.scalars(select(VoiceCallTurn).order_by(VoiceCallTurn.turn_index))).all()
        assert [(r.turn_index,r.user_text_final) for r in rows]==[(1,'最终'),(2,'第二句')]


@pytest.mark.asyncio
@pytest.mark.parametrize('crisis', ['matched','suspected'])
async def test_crisis_gate_isolates_before_turn_has_any_plaintext(turn_env, crisis):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id = turn_env
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate(crisis))
    await service.consume(event(call_id,1,'asr_final','SENTINEL_PRIVATE'))
    async with factory() as db:
        turn=await db.scalar(select(VoiceCallTurn)); isolated=await db.scalar(select(VoiceCrisisRecord))
        assert turn.user_text_final is None and turn.memory_status=='skipped' and turn.user_crisis_status==crisis
        assert isolated.content_plaintext=='SENTINEL_PRIVATE' and isolated.turn_index==turn.turn_index


@pytest.mark.asyncio
async def test_isolation_failure_rolls_back_plaintext_and_drops_memory_reference(turn_env, caplog):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id=turn_env
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate('matched',fail=True))
    await service.consume(event(call_id,1,'asr_final','SENTINEL_PRIVATE'))
    await service.freeze()
    async with factory() as db:
        await service.final_flush(db);await db.commit()
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord))==0
        rows=(await db.scalars(select(VoiceCallTurn))).all()
        assert all(r.user_text_final is None for r in rows)
    assert 'SENTINEL' not in caplog.text and 'SENTINEL_PRIVATE' not in repr(service)


@pytest.mark.asyncio
async def test_generated_and_tts_finished_do_not_invent_effective_or_close_turn(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id=turn_env
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate())
    await service.consume(event(call_id,1,'asr_final','讲个故事'))
    await service.consume(event(call_id,2,'chat_text','没有播放过的故事',reply='r1'))
    await service.consume(event(call_id,3,'tts_finished',{},reply='r1'))
    await service.freeze()
    async with factory() as db:
        await service.final_flush(db);await db.commit()
        row=await db.scalar(select(VoiceCallTurn))
        assert row.assistant_text_effective is None and row.effective_text_evidence=='none'
        assert row.turn_status=='aborted' and row.memory_status=='skipped'


@pytest.mark.asyncio
async def test_missing_gate_never_marks_untested_text_safe(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id=turn_env
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory)
    await service.consume(event(call_id,1,'asr_final','未经判定的正文'))
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn))
        assert row.user_text_final is None and row.user_crisis_status=='pending' and row.memory_status=='skipped'


@pytest.mark.asyncio
async def test_second_service_cannot_overwrite_committed_final_or_duplicate_isolation(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory, call_id=turn_env
    for body in ('原始事实','迟到污染'):
        service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate())
        await service.consume(event(call_id,1,'asr_final',body))
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn))
        assert row.user_text_final=='原始事实'
    for _ in range(2):
        service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate('matched'))
        await service.consume(event(call_id,1,'asr_final','隔离事实',question='q2'))
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.question_id=='q2'))
        assert row.user_crisis_status=='matched'
        assert await db.scalar(select(func.count()).select_from(VoiceCrisisRecord))==1


@pytest.mark.asyncio
async def test_effective_cannot_save_text_with_none_evidence(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService, EffectiveText
    factory, call_id=turn_env
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate())
    await service.consume(event(call_id,1,'asr_final','你好'))
    await service.consume(event(call_id,2,'chat_text','未播文本',reply='r1'))
    with pytest.raises(ValueError):
        await service.apply_effective('r1',EffectiveText('未播文本','none'))
    async with factory() as db:
        assert (await db.scalar(select(VoiceCallTurn))).assistant_text_effective is None


@pytest.mark.asyncio
async def test_gateway_turn_consumption_does_not_forward_ungated_final_text(turn_env):
    from tests.test_realtime_voice_step012_gateway import session
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory,_=turn_env
    gateway=await session(factory)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==gateway.call.call_id))
        row.status='connected';row.connected_at=datetime.utcnow();await db.commit()
    gateway.turns=VoiceTurnService(call_id=gateway.call.call_id,session_id='session1',session_factory=factory,gate=Gate('matched'))
    await gateway.process_provider_event(event(gateway.call.call_id,1,'asr_final','SENTINEL_PRIVATE'))
    assert 'SENTINEL_PRIVATE' not in str(gateway.socket.frames)
    await gateway.stop_local()
    async with factory() as db:
        await gateway.flush_turns(db)
        await db.commit()
        turn=await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.call_id==gateway.call.call_id))
        assert turn.user_text_final is None and turn.turn_status=='aborted'


@pytest.mark.asyncio
@pytest.mark.parametrize('crisis', ['passed','matched','suspected'])
async def test_assistant_effective_gate_controls_both_text_columns_and_memory(turn_env, crisis):
    from backend.services.realtime_voice_turn_service import VoiceTurnService, EffectiveText
    factory, call_id=turn_env
    gate=Gate()
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate)
    await service.consume(event(call_id,1,'asr_final','你好'))
    await service.consume(event(call_id,2,'chat_text','SENTINEL_REPLY',reply='r1'))
    await service.consume(event(call_id,3,'tts_finished',{},reply='r1'))
    gate.crisis=crisis
    await service.apply_effective('r1',EffectiveText('SENTINEL_REPLY','full',200,completed=True))
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn))
        if crisis=='passed':
            assert row.assistant_text_effective==row.assistant_text_generated=='SENTINEL_REPLY'
            assert row.effective_text_evidence=='full' and row.memory_status=='pending'
        else:
            assert row.assistant_text_effective is None and row.assistant_text_generated is None
            assert row.effective_text_evidence=='none' and row.memory_status=='skipped'
            isolated=await db.scalar(select(VoiceCrisisRecord))
            assert isolated.direction=='assistant' and isolated.content_plaintext=='SENTINEL_REPLY'
        assert row.turn_status=='finalized' and row.playback_completed_at is not None


@pytest.mark.asyncio
async def test_conflicting_reply_does_not_create_phantom_turn_on_flush(turn_env):
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    factory,call_id=turn_env
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate())
    await service.consume(event(call_id,1,'chat_text','原回合',reply='r1'))
    with pytest.raises(ValueError):
        await service.consume(event(call_id,2,'chat_text','错误归属',question='q2',reply='r1'))
    await service.freeze()
    async with factory() as db:
        await service.final_flush(db);await db.commit()
        rows=(await db.scalars(select(VoiceCallTurn))).all()
        assert [r.question_id for r in rows]==['q1']


@pytest.mark.asyncio
async def test_gateway_external_terminal_still_stops_audio_when_late_evidence_is_rejected(turn_env):
    from tests.test_realtime_voice_step012_gateway import session
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    factory,_=turn_env
    gateway=await session(factory)
    gateway.turns=VoiceTurnService(call_id=gateway.call.call_id,session_id='session1',session_factory=factory,gate=Gate())
    gateway.playback=PlaybackEvidence(call_id=gateway.call.call_id,capability_enabled=lambda key:False)
    await gateway.process_provider_event(event(gateway.call.call_id,1,'chat_text','没播完',reply='r1'))
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==gateway.call.call_id))
        row.status='ended';row.connected_at=datetime.utcnow();row.ended_at=datetime.utcnow();await db.commit()
    await gateway.stop_local()
    assert gateway.socket.closed.is_set() and gateway.adapter.finished==1


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,want,evidence', [('full','第一句。第二句。','full'),('partial','第一句。','exact_played'),('none',None,'none')])
async def test_gateway_client_evidence_final_flush_only_saves_proven_text(turn_env,mode,want,evidence):
    from tests.test_realtime_voice_step012_gateway import session
    from backend.services.realtime_voice_turn_service import VoiceTurnService
    from backend.services.realtime_voice_playback_service import PlaybackEvidence
    factory,_=turn_env
    gateway=await session(factory);call_id=gateway.call.call_id
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        row.status='connected';row.connected_at=datetime.utcnow();await db.commit()
    gateway.connected=True
    gateway.turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate())
    gateway.playback=PlaybackEvidence(call_id=call_id,capability_enabled=lambda key:mode=='partial')
    events=[('asr_final','讲故事',None),('chat_text','第一句。第二句。','r1'),
        ('sentence_started',{'text':'第一句。'},'r1'),('tts_audio',b'\0'*4800,'r1'),('sentence_finished',{},'r1'),
        ('sentence_started',{'text':'第二句。'},'r1'),('tts_audio',b'\0'*4800,'r1'),('sentence_finished',{},'r1'),
        ('text_finished',{},'r1'),('tts_finished',{},'r1')]
    for i,(kind,payload,rid) in enumerate(events,1):
        await gateway.process_provider_event(event(call_id,i,kind,payload,reply=rid))
    if mode!='none':
        frame=dict(v=1,seq=1,type='client_reply_playback_completed' if mode=='full' else 'client_playback_progress',
                   call_id=call_id,reply_id='r1',event_seq=1)
        if mode=='partial':frame['played_audio_ms']=100
        await gateway.handle_playback(frame)
    await gateway.stop_local()
    async with factory() as db:
        await gateway.flush_turns(db);await db.commit()
        row=await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.call_id==call_id))
        assert (row.assistant_text_effective,row.effective_text_evidence)==(want,evidence)
        assert row.turn_status==('finalized' if mode=='full' else 'aborted')
    assert '第一句' not in str(gateway.socket.frames) and '讲故事' not in str(gateway.socket.frames)
