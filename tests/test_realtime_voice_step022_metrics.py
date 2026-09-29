from datetime import date,datetime,timedelta
import pytest
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.services.relationship_service import RelationshipService
from backend.services.diary_service import DiaryService
from backend.services.agent_service import AgentService
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step022_growth import growth_env,memory_env,storage
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('rollback',[False,True])
async def test_growth_actual_cap_reset_and_rollback(growth_env,rollback):
    factory,call_id=growth_env;sink=CounterCache();metrics=VoiceMetrics(sink)
    async with factory() as db:
        db.add(RelationshipGrowthLog(user_id=1,action_type='voice_call',points=95,source_type='voice_call',source_id='older',eligible_seconds=570,business_date=date(2026,9,14)))
        await db.commit()
        assert (await RelationshipService(db).add_voice_growth(1,65,call_id))['points']==5
        assert not sink.batches
        if rollback:await db.rollback()
        else:await db.commit()
        await flush_voice_metrics(db,metrics)
        if not rollback:
            await RelationshipService(db).add_voice_growth(1,65,call_id);await db.commit();await flush_voice_metrics(db,metrics)
    events=[e for b in sink.batches for e in b]
    assert events==([] if rollback else [
        ('voice.growth.result',{'result':'eligible'},1),('voice.growth.eligible_seconds',{},65),
        ('voice.growth.points',{},5),('voice.growth.daily_cap_hit',{},1),
        ('voice.cross_modal.proactive_reset',{},1),('voice.growth.idempotent',{},1)])


async def cross_modal(factory,metrics,ready):
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[ConversationLog.__table__,EmotionLog.__table__])
    now=datetime.utcnow()
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.connected_at=now-timedelta(hours=1)
        call.summary_status='ready' if ready else 'failed';call.call_summary='private-summary'
        call.transcript_expires_at=now+timedelta(days=1)
        conv=ConversationLog(user_id=1,role='user',content='old',sort_seq=100,created_at=now-timedelta(days=2))
        db.add(conv);await db.flush()
        db.add(EmotionLog(user_id=1,emotion_label='悲伤',confidence=.9,conversation_id=conv.id,created_at=now-timedelta(days=2)))
        await db.commit()
        active,summary=await DiaryService(db,voice_metrics=metrics)._get_conversation_summary_in_window(1,now-timedelta(days=1),now)
        assert active and bool(summary) and ('private-summary' in summary)==ready
        assert not await AgentService(voice_metrics=metrics)._check_p0(1,db)


@pytest.mark.asyncio
@pytest.mark.parametrize('ready',[False,True])
async def test_cross_modal_observations_are_safe_samples(growth_env,ready):
    sink=CounterCache();await cross_modal(growth_env[0],VoiceMetrics(sink),ready)
    assert [e for b in sink.batches for e in b]==[
        ('voice.cross_modal.diary',{'result':'voice_interaction'},1),
        ('voice.cross_modal.diary_summary',{'result':'ready' if ready else 'fallback'},1),
        ('voice.cross_modal.p0_suppressed',{},1)]
