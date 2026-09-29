"""Follow-up admission, frozen windows and missed terminal integration."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, func

from backend.constants.realtime_voice_config import DEFAULT_FOLLOWUP_SCHEDULE
from backend.models.realtime_voice import VoiceCall, VoiceFollowupJob, VoicePostprocessJob
from backend.models.relationship import Relationship
from tests.test_realtime_voice_step021_cards import card_env, memory_env, storage


@pytest.mark.asyncio
@pytest.mark.parametrize('script,expected,fallback',[
    ({'followup':{'missed_explanation_template':'现在没接到，晚一点再聊。'}},'现在没接到，晚一点再聊。',False),
    (None,'刚刚没接到你的电话，晚一点我们再聊呀。',True),
    ('invalid','刚刚没接到你的电话，晚一点我们再聊呀。',True),
    ({'followup':None},'刚刚没接到你的电话，晚一点我们再聊呀。',True),
    ({'followup':{'missed_explanation_template':''}},'刚刚没接到你的电话，晚一点我们再聊呀。',True),
    ({'followup':{'missed_explanation_template':'稍后联系{name}'}},'刚刚没接到你的电话，晚一点我们再聊呀。',True),
    ({'followup':{'missed_explanation_template':'TODO'}},'刚刚没接到你的电话，晚一点我们再聊呀。',True),
])
async def test_missed_transition_stages_exact_message_without_summary(card_env,script,expected,fallback,caplog):
    from backend.services.realtime_voice_state_service import transition_call
    factory,call_id=card_env
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='deciding';row.connected_at=None
        row.config_snapshot={**row.config_snapshot,'resolved_script':script,'config_version':8,
            'resolved_config':{'followup':{'schedule':deepcopy(DEFAULT_FOLLOWUP_SCHEDULE)}}}
        db.add(Relationship(user_id=1,level=1,growth_value=20,future_timestamp=999,future_action='原有安排'))
        await db.commit()
    instant=datetime(2026,9,13,2,tzinfo=timezone.utc)
    async with factory() as db:
        assert await transition_call(db,call_id=call_id,expected=('deciding',),target='missed',now=instant)
        assert not await transition_call(db,call_id=call_id,expected=('deciding',),target='missed',now=instant)
    async with factory() as db:
        job=await db.scalar(select(VoiceFollowupJob))
        assert job is not None
        assert (job.content,job.content_type,job.status)==(expected,'missed_explanation','pending')
        assert (job.candidate_due_at,job.due_at,job.jitter_minutes)==(instant.replace(tzinfo=None),instant.replace(tzinfo=None),0)
        assert (job.relationship_stage_snapshot,job.schedule_config_version)==('friend','8')
        relation=await db.scalar(select(Relationship))
        assert (relation.future_timestamp,relation.future_action)==(999,'原有安排')
        assert await db.scalar(select(func.count()).select_from(VoiceFollowupJob))==1
        assert await db.scalar(select(func.count()).select_from(VoicePostprocessJob))==0
    assert ('voice.followup.missed_template_fallback=1' in caplog.text) is fallback


@pytest.mark.asyncio
@pytest.mark.parametrize('level,start',[(0,(2,0)),(1,(1,30)),(2,(1,0)),(3,(1,0))])
@pytest.mark.parametrize('jitter',[0,20])
async def test_missed_frozen_window_and_same_call_idempotency(card_env,level,start,jitter):
    from backend.services.realtime_voice_summary_followup_service import stage_missed_followup
    factory,call_id=card_env
    async with factory() as db:
        db.add(Relationship(user_id=1,level=level,growth_value=0))
        call=await db.scalar(select(VoiceCall));call.status='missed';call.connected_at=None
        call.ended_at=datetime(2026,9,13,0)
        # Invalid nested config must take the same canonical fallback, not fail the terminal transaction.
        call.config_snapshot={'resolved_config':'broken','resolved_script':None}
        job=await stage_missed_followup(db,call=call,jitter_minutes=jitter)
        await db.commit()
        projection=(job.due_at,deepcopy(job.allowed_window_snapshot),job.relationship_stage_snapshot,job.schedule_config_version,job.jitter_minutes)
        assert job.due_at==datetime(2026,9,13,start[0],start[1]+jitter)
        assert job.schedule_config_version=='code-default'
        relation=await db.scalar(select(Relationship));relation.level=(level+1)%4
        call.config_snapshot={}
        assert await stage_missed_followup(db,call=call,jitter_minutes=20-jitter) is job
        assert projection==(job.due_at,job.allowed_window_snapshot,job.relationship_stage_snapshot,job.schedule_config_version,job.jitter_minutes)


@pytest.mark.asyncio
@pytest.mark.parametrize('status',['failed','cancelled','ended','connected'])
async def test_non_missed_never_gets_deterministic_explanation(card_env,status):
    from backend.services.realtime_voice_summary_followup_service import stage_missed_followup
    factory,_=card_env
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status=status
        assert await stage_missed_followup(db,call=call) is None
        assert await db.scalar(select(func.count()).select_from(VoiceFollowupJob))==0


@pytest.mark.asyncio
async def test_missed_finalizer_and_first_user_default_stage(card_env):
    from backend.services.realtime_voice_ops_service import VoiceOpsService
    from tests.test_realtime_voice_step009_ops import StateCache
    factory,call_id=card_env
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ringing';call.connected_at=None
        await db.commit()
    worker=VoiceOpsService(cache=StateCache(),session_factory=factory)
    await worker.end_call(call_id=call_id,reason='character_missed')
    await worker.end_call(call_id=call_id,reason='character_missed')
    async with factory() as db:
        job=await db.scalar(select(VoiceFollowupJob))
        assert job.relationship_stage_snapshot=='stranger'
        assert await db.scalar(select(func.count()).select_from(VoiceFollowupJob))==1
        assert await db.scalar(select(Relationship)) is None


@pytest.mark.asyncio
async def test_missed_failure_rolls_back_terminal_card_and_job(card_env,monkeypatch):
    import backend.services.realtime_voice_summary_followup_service as module
    from backend.services.realtime_voice_state_service import transition_call
    from backend.models.user_timeline_seq import UserTimelineSeq
    factory,call_id=card_env
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='deciding';call.connected_at=None
        await db.commit()
    original=module.stage_missed_followup
    async def fail_after_stage(db,**kw):
        await original(db,**kw);await db.flush()
        raise RuntimeError('controlled enqueue failure')
    monkeypatch.setattr(module,'stage_missed_followup',fail_after_stage)
    async with factory() as db:
        with pytest.raises(RuntimeError,match='controlled enqueue failure'):
            await transition_call(db,call_id=call_id,expected=('deciding',),target='missed',now=datetime.now(timezone.utc))
        await db.rollback()
    async with factory() as db:
        call=await db.scalar(select(VoiceCall))
        assert call.status=='deciding' and call.sort_seq is None
        assert await db.scalar(select(VoiceFollowupJob)) is None
        assert await db.scalar(select(UserTimelineSeq)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('level,start,end',[(0,(10,0),(21,0)),(1,(9,30),(22,0)),(2,(9,0),(22,30)),(3,(9,0),(23,0))])
@pytest.mark.parametrize('boundary',['start','before_end','end','after_end'])
@pytest.mark.parametrize('jitter',[0,20])
async def test_four_stage_window_edges(card_env,level,start,end,boundary,jitter):
    from backend.services.realtime_voice_summary_followup_service import stage_missed_followup
    factory,_=card_env
    local_start=datetime(2026,9,13,*start)
    local_end=datetime(2026,9,13,*end)
    local_candidate={'start':local_start,'before_end':local_end-timedelta(minutes=1),
        'end':local_end,'after_end':local_end+timedelta(minutes=1)}[boundary]
    candidate=local_candidate-timedelta(hours=8)
    inside=boundary in {'start','before_end'}
    expected=candidate if inside else local_start+timedelta(days=1,minutes=jitter,hours=-8)
    async with factory() as db:
        db.add(Relationship(user_id=1,level=level,growth_value=0))
        call=await db.scalar(select(VoiceCall));call.status='missed';call.connected_at=None;call.ended_at=candidate
        call.config_snapshot={'config_version':9,'resolved_config':{'followup':{'schedule':deepcopy(DEFAULT_FOLLOWUP_SCHEDULE)}}}
        job=await stage_missed_followup(db,call=call,jitter_minutes=jitter)
        await db.flush()
        assert job.candidate_due_at==candidate and job.due_at==expected
        assert job.jitter_minutes==(0 if inside else jitter)
        assert job.latest_due_at==candidate+timedelta(hours=24)
        assert job.status=='pending' and job.timezone_snapshot=='Asia/Shanghai'
