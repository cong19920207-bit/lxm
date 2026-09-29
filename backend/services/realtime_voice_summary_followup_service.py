"""Persist CALL-SUM's candidate in the existing job schema, without sending.

Uses the already verified window resolver; STEP-032 owns due-job dispatch and
its final eligibility checks. Candidate and summary share the caller's commit.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import logging
import secrets
import re
from sqlalchemy import select
from backend.constants.realtime_voice_config import DEFAULT_FOLLOWUP_SCHEDULE, DEFAULT_MISSED_EXPLANATION_TEMPLATE
from backend.models.relationship import Relationship
from backend.models.realtime_voice import VoiceFollowupJob
from backend.services.realtime_voice_config_service import validate_followup_schedule,resolve_followup_preview

logger=logging.getLogger(__name__)
STAGES={0:'stranger',1:'friend',2:'intimate',3:'soulmate'}


async def stage_summary_followup(db,*,call,candidate,jitter_minutes=None):
    """Caller holds user/call locks; this function neither commits nor sends."""
    return await _stage_followup(db,call=call,candidate=candidate,jitter_minutes=jitter_minutes)


def _mapping(value):
    return value if isinstance(value,dict) else {}


async def stage_missed_followup(db,*,call,jitter_minutes=None):
    """Persist deterministic missed explanation in the terminal transaction."""
    if (call.status!='missed' or call.connected_at is not None or call.ended_at is None
            or call.deleted_at is not None or call.deletion_fence_at is not None):
        return None
    script=_mapping(_mapping(call.config_snapshot).get('resolved_script'))
    content=_mapping(script.get('followup')).get('missed_explanation_template')
    if (not isinstance(content,str) or not content.strip()
            or content.strip().upper() in {'TODO','TBD','PLACEHOLDER','待填写','占位文案'}
            or re.search(r'[{}]|<%|%>|%\([^)]+\)[a-z]|%s',content)):
        content=DEFAULT_MISSED_EXPLANATION_TEMPLATE
        logger.warning('voice.followup.missed_template_fallback=1')
    return await _stage_followup(db,call=call,
        candidate={'content_type':'missed_explanation','content':content,'delay_minutes':0},
        jitter_minutes=jitter_minutes,allow_new_relationship=True)


async def _stage_followup(db,*,call,candidate,jitter_minutes=None,allow_new_relationship=False):
    existing=await db.scalar(select(VoiceFollowupJob).where(VoiceFollowupJob.call_id==call.call_id,
        VoiceFollowupJob.content_type==candidate['content_type']).with_for_update())
    if existing is not None:return existing
    relationship=await db.scalar(select(Relationship).where(Relationship.user_id==call.user_id))
    if relationship is None and allow_new_relationship:
        stage=STAGES[0]
    elif relationship is None or relationship.level not in STAGES:
        raise ValueError('summary_relationship_snapshot_missing')
    else:
        stage=STAGES[relationship.level]
    snapshot=_mapping(call.config_snapshot)
    schedule=_mapping(_mapping(snapshot.get('resolved_config')).get('followup')).get('schedule')
    version=str(snapshot.get('config_version','code-default'))
    if validate_followup_schedule(schedule):
        schedule=deepcopy(DEFAULT_FOLLOWUP_SCHEDULE);version='code-default'
        logger.warning('voice.summary.followup_schedule_fallback=1')
    minimum,maximum=schedule['jitter_min_minutes'],schedule['jitter_max_minutes']
    jitter=minimum+secrets.randbelow(maximum-minimum+1) if jitter_minutes is None else jitter_minutes
    if type(jitter) is not int or not minimum<=jitter<=maximum:
        raise ValueError('summary_followup_jitter_out_of_range')
    candidate_at=call.ended_at.replace(tzinfo=timezone.utc)+timedelta(minutes=candidate['delay_minutes'])
    resolution=resolve_followup_preview(schedule,dict(stage=stage,candidate_at=candidate_at.isoformat(),jitter_minutes=jitter))
    due=(datetime.fromisoformat(resolution['resolved_due_at']).astimezone(timezone.utc).replace(tzinfo=None)
         if resolution['resolved_due_at'] else candidate_at.replace(tzinfo=None))
    row=VoiceFollowupJob(call_id=call.call_id,user_id=call.user_id,
        candidate_due_at=candidate_at.replace(tzinfo=None),due_at=due,
        latest_due_at=(candidate_at+timedelta(hours=schedule['max_delay_hours'])).replace(tzinfo=None),
        content=candidate['content'],content_type=candidate['content_type'],
        status='cancelled' if resolution['cancel_reason'] else 'pending',cancel_reason=resolution['cancel_reason'],
        relationship_stage_snapshot=stage,schedule_config_version=version,timezone_snapshot=schedule['timezone'],
        allowed_window_snapshot=deepcopy(schedule['stages'][stage]['windows']),
        jitter_minutes=resolution['jitter_applied_minutes'])
    db.add(row)
    from backend.services.realtime_voice_metric_service import stage_voice_metrics
    events=[('voice.followup.branch',{'branch':'missed' if row.content_type=='missed_explanation' else 'topic'},1),
        ('voice.followup.schedule',{'result':row.status},1)]
    if row.status=='cancelled':events.append(('voice.followup.cancel',{'reason':row.cancel_reason},1))
    stage_voice_metrics(db,events)
    return row
