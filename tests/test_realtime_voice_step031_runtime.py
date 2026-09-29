"""CALL-SUM transactions on disposable MySQL/Redis, controlled model output."""
import os
import pytest
import pytest_asyncio
from backend.database import Base
from backend.models.conversation_log import ConversationLog
from backend.models.agent_message import AgentMessage
from backend.models.realtime_voice import VoicePostprocessJob,VoiceFollowupJob
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step028_runtime import memory_env
from tests.test_realtime_voice_step031_jobs import (
    summary_env,test_summary_transaction_fixed_card_reasoning_and_idempotency,
    test_model_wait_releases_call_and_fence_rejects_late_result,
    test_followup_storage_failure_rolls_back_summary_and_candidate,
    test_reasoning_expiry_clears_only_internal_content,
    test_reasoning_private_role_projection_and_each_read_audit,
    test_source_expiry_during_model_cannot_leave_pending_card,
    test_real_candidate_storage_shares_summary_commit_and_keeps_future_slot,
    test_manual_summary_retry_roles_preserve_attempt_count,
    test_followup_jitter_honors_nonzero_published_minimum,
    test_reasoning_assessment_timeout_keeps_ready_public_card,
    test_scan_discovers_unqueued_card_and_stops_after_success_or_failure,
    test_production_composition_consumes_frozen_deepseek_prompt_and_compensates,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL/Redis opt-in')

@pytest_asyncio.fixture
async def card_env(memory_env):
    factory,call=memory_env
    tables=[m.__table__ for m in (ConversationLog,AgentMessage,VoicePostprocessJob,VoiceFollowupJob)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    try:
        yield factory,call
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)

@pytest.mark.asyncio
async def test_old_emotion_domains_trace_and_vector_unchanged_and_public_reasoning_absent(summary_env,runtime,monkeypatch):
    import json
    from datetime import datetime
    from sqlalchemy import select
    from backend.models.emotion_log import EmotionLog
    from backend.models.user_short_term_emotion import UserShortTermEmotion
    from backend.models.realtime_voice import VoiceCall,VoiceMemoryTrace
    from backend.services.timeline_read_service import get_timeline
    from backend.services.realtime_voice_presentation_service import call_presentation
    from backend.utils.dashvector_client import dashvector_client
    from tests.test_realtime_voice_step031_jobs import service
    factory,call=summary_env;cache=runtime[2]
    tables=[EmotionLog.__table__,UserShortTermEmotion.__table__]
    async with factory.kw['bind'].begin() as conn:await conn.run_sync(Base.metadata.create_all,tables=tables)
    vector_calls=[]
    async def forbidden_write(*args,**kwargs):vector_calls.append(True);raise AssertionError('CALL-SUM must not write vector')
    monkeypatch.setattr(dashvector_client,'upsert',forbidden_write)
    monkeypatch.setattr(dashvector_client,'delete',forbidden_write)
    try:
        async with factory() as db:
            conv=ConversationLog(user_id=1,role='assistant',content='旧文字',sort_seq=33);db.add(conv);await db.flush()
            db.add(EmotionLog(user_id=1,emotion_label='平静',confidence=.9,conversation_id=conv.id))
            db.add(UserShortTermEmotion(user_id=1,emotion_label='开心',confidence=.8,payload='旧画像'))
            db.add(VoiceMemoryTrace(call_id=call,turn_index=1,doc_id='test-existing-doc',memory_type='user',stable_key='旅行-计划-日本',pipeline_version='voice_mem_v1',written_at=datetime.utcnow()))
            await db.commit()
        await cache.set('ai_emotion:1','旧Redis情绪')
        async def snapshot():
            async with factory() as db:
                return {model.__tablename__:[tuple(row) for row in (await db.execute(select(model.__table__))).all()]
                        for model in (EmotionLog,UserShortTermEmotion,VoiceMemoryTrace)}
        before=await snapshot();worker=service(factory)
        await worker.enqueue(call_id=call);assert await worker.process(call_id=call)=='ready'
        assert await worker.process(call_id=call)=='success'
        assert await snapshot()==before and await cache.get('ai_emotion:1')=='旧Redis情绪' and not vector_calls
        async with factory() as db:
            row=await db.scalar(select(VoiceCall));assert row.summary_reasoning
            surfaces=[call_presentation(row),await get_timeline(1,db,include_calls=True),await get_timeline(1,db)]
            encoded=json.dumps(surfaces,ensure_ascii=False)
            assert 'reasoning' not in encoded and row.summary_reasoning not in encoded
    finally:
        async with factory.kw['bind'].begin() as conn:await conn.run_sync(Base.metadata.drop_all,tables=tables)
