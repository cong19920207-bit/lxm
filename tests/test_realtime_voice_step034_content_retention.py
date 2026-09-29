"""Content expiry compares fixed primary-key projections, never only counts."""
from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import (VoiceCall,VoiceCallTurn,VoiceMemoryJob,
    VoicePostprocessJob,VoiceFollowupJob,VoiceCrisisRecord,VoiceMemoryTrace)
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step028_jobs import add_turn


class Cache:
    def __init__(self):self.values={};self.calls=[]
    async def delete(self,key):self.calls.append(key);return self.values.pop(key,None) is not None


async def seed(factory,call_id,now,expiry):
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceCrisisRecord.__table__])
    turn_id=await add_turn(factory,call_id,assistant_text_generated='generated-private',
        effective_text_expires_at=expiry,generated_text_expires_at=expiry,memory_status='success')
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        call.status='ended';call.ended_at=now-timedelta(days=180);call.sort_seq=7
        call.call_summary='独立生命周期的总结';call.summary_status='ready';call.user_emotion='平静'
        call.summary_reasoning='private-reasoning';call.transcript_expires_at=expiry
        call.generated_text_expires_at=expiry;call.reasoning_expires_at=expiry
        call.config_snapshot={'resolved_config':{'retention':{'job_log_days':90}}}
        jobs=[VoiceMemoryJob(call_id=call_id,turn_id=turn_id,turn_index=1,pipeline_version='retention-test',
                status='success',extraction_snapshot={'items':['private-atom']},created_at=expiry-timedelta(days=90)),
            VoicePostprocessJob(call_id=call_id,job_type='call_summary',status='success',created_at=expiry-timedelta(days=90)),
            VoiceFollowupJob(call_id=call_id,user_id=1,content='private-followup',content_type='topic_continuation',
                status='sent',candidate_due_at=now,due_at=now,latest_due_at=now+timedelta(hours=24),
                relationship_stage_snapshot='stranger',schedule_config_version='snapshot',timezone_snapshot='Asia/Shanghai',
                allowed_window_snapshot=[{'start':'10:00','end':'21:00'}],jitter_minutes=0,created_at=expiry-timedelta(days=90))]
        crisis=VoiceCrisisRecord(call_id=call_id,turn_index=1,direction='user',content_plaintext='crisis-private',
            matched_keyword='private-keyword',match_status='matched',is_persona_incident=False,expires_at=expiry)
        trace=VoiceMemoryTrace(call_id=call_id,turn_index=1,doc_id='retained-doc',memory_type='user',
            stable_key='旅行',pipeline_version='retention-test',written_at=now-timedelta(days=1))
        db.add_all([*jobs,crisis,trace]);await db.commit()
        return turn_id,crisis.id,[job.id for job in jobs],trace.id


@pytest.mark.asyncio
@pytest.mark.parametrize('offset',[-1,0,1])
async def test_content_expiry_exact_object_projection_and_independent_summary(card_env,offset):
    from backend.services.realtime_voice_retention_service import VoiceRetentionService
    factory,call_id=card_env;now=datetime(2026,9,14,4);expiry=now+timedelta(seconds=offset)
    turn_id,crisis_id,job_ids,trace_id=await seed(factory,call_id,now,expiry)
    cache=Cache();key=f'voice:session_context:{call_id}';cache.values[key]='private-context'
    service=VoiceRetentionService(session_factory=factory,cache=cache)
    async with factory() as db:
        trace=await db.get(VoiceMemoryTrace,trace_id)
        retained={col.name:getattr(trace,col.name) for col in trace.__table__.columns}
    report=await service.purge_contents(now=now)
    objects={(item['table'],item['id']) for item in report['reports'][0]['changed']}
    expected={(VoiceCallTurn.__tablename__,turn_id),(VoiceCrisisRecord.__tablename__,crisis_id),
        (VoiceMemoryJob.__tablename__,job_ids[0]),(VoiceFollowupJob.__tablename__,job_ids[2])}
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        if offset<=0:expected.add((VoiceCall.__tablename__,call.id))
        assert objects==(expected if offset<=0 else set())
        assert (call.call_summary,call.sort_seq,call.user_emotion,call.summary_status)==('独立生命周期的总结',7,'平静','ready')
        turn=await db.get(VoiceCallTurn,turn_id)
        assert (turn.effective_text_expires_at,turn.generated_text_expires_at)==(expiry,expiry)
        assert turn.memory_status=='success'
        assert (turn.user_text_final,turn.assistant_text_effective,turn.assistant_text_generated)==(
            (None,None,None) if offset<=0 else ('下月去日本','去看看京都','generated-private'))
        assert turn.effective_text_cleared_at==(now if offset<=0 else None)
        assert turn.generated_text_cleared_at==(now if offset<=0 else None)
        trace=await db.get(VoiceMemoryTrace,trace_id)
        assert {col.name:getattr(trace,col.name) for col in trace.__table__.columns}==retained
    assert (key in cache.values)==(offset>0)
    assert all(not row['changed'] for row in (await service.purge_contents(now=now))['reports'])


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['generated','job'])
async def test_retention_types_do_not_shorten_other_lifecycles(card_env,kind):
    from backend.services.realtime_voice_retention_service import VoiceRetentionService
    factory,call_id=card_env;now=datetime(2026,9,14,4);future=now+timedelta(days=1)
    turn_id,_,jobs,_=await seed(factory,call_id,now,future)
    async with factory() as db:
        if kind=='generated':
            turn=await db.get(VoiceCallTurn,turn_id);turn.generated_text_expires_at=now
        else:
            job=await db.get(VoiceMemoryJob,jobs[0]);job.created_at=now-timedelta(days=90)
        await db.commit()
    await VoiceRetentionService(session_factory=factory,cache=Cache()).purge_contents(now=now)
    async with factory() as db:
        turn=await db.get(VoiceCallTurn,turn_id);job=await db.get(VoiceMemoryJob,jobs[0])
        assert turn.user_text_final=='下月去日本' and turn.assistant_text_effective=='去看看京都'
        assert turn.effective_text_cleared_at is None
        assert (turn.assistant_text_generated is None)==(kind=='generated')
        assert (job.extraction_snapshot is None)==(kind=='job')
