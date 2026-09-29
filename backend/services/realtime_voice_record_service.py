"""Explicit record projections; never serialize voice ORM objects wholesale."""
from datetime import datetime


def iso(value):
    return value.isoformat() if value is not None else None


def call_content_available(call, now):
    return (call.deleted_at is None and call.deletion_fence_at is None
        and (call.transcript_expires_at is None or call.transcript_expires_at > now))


def turn_content_reason(call, turn, now):
    if call.deleted_at is not None or call.deletion_fence_at is not None:
        return 'deleted'
    if turn.effective_text_cleared_at is not None:
        return 'cleared'
    if ((call.transcript_expires_at is not None and call.transcript_expires_at <= now)
            or (turn.effective_text_expires_at is not None and turn.effective_text_expires_at <= now)):
        return 'expired'
    statuses = (turn.user_crisis_status, turn.assistant_crisis_status)
    if any(status in {'matched', 'suspected', 'isolation_failed'} for status in statuses):
        return 'crisis_isolated'
    if any(status != 'passed' for status in statuses):
        return 'assessment_incomplete'
    if turn.effective_text_expires_at is None:
        return 'retention_unavailable'
    if not (turn.user_text_final or turn.assistant_text_effective):
        return 'no_effective_text'
    return None


def effective_turn(call, turn, *, now: datetime):
    readable = (call_content_available(call, now)
        and turn.effective_text_cleared_at is None
        and turn.effective_text_expires_at is not None and turn.effective_text_expires_at > now
        and turn.user_crisis_status == 'passed' and turn.assistant_crisis_status == 'passed')
    return dict(call_id=turn.call_id, turn_index=turn.turn_index,
        user_text_final=turn.user_text_final if readable else None,
        assistant_text_effective=turn.assistant_text_effective if readable else None,
        effective_text_expires_at=iso(turn.effective_text_expires_at),
        effective_text_cleared_at=iso(turn.effective_text_cleared_at),
        content_clear_reason=turn.content_clear_reason,
        content_unavailable_reason=turn_content_reason(call, turn, now),
        content_available=readable, effective_text_evidence=turn.effective_text_evidence,
        assistant_interrupted=turn.assistant_interrupted, turn_status=turn.turn_status,
        memory_status=turn.memory_status, user_content_safety_status=turn.user_content_safety_status,
        assistant_content_safety_status=turn.assistant_content_safety_status,
        user_crisis_status=turn.user_crisis_status, assistant_crisis_status=turn.assistant_crisis_status)


def export_turn(projected):
    return {key: projected[key] for key in (
        'call_id', 'turn_index', 'user_text_final', 'assistant_text_effective', 'effective_text_expires_at')}


def overview(call, *, now):
    result = {key: getattr(call, key) for key in (
        'call_id','user_id','initiated_by','status','end_reason','provider','duration_seconds',
        'free_seconds_used','extra_seconds_used','grace_seconds','growth_eligible_seconds',
        'growth_points','summary_status')}
    result.update({key: iso(getattr(call, key)) for key in (
        'created_at','connected_at','ended_at','transcript_expires_at','deleted_at')})
    readable = call_content_available(call, now)
    result['content_available'] = readable
    for key in ('call_summary', 'user_emotion', 'assistant_emotion', 'unfinished_topics'):
        result[key] = getattr(call, key) if readable else None
    config = call.config_snapshot.get('resolved_config', {})
    result.update(model_version=config.get('s2s', {}).get('model_version'),
        voice_id=config.get('voice', {}).get('voice_id'), config_version=call.config_snapshot.get('config_version'),
        remaining_days=max(0, (call.transcript_expires_at-now).days) if call.transcript_expires_at else None)
    return result


async def transcript_statistics(db, call_ids, *, now=None):
    """Count metadata and text presence only; never read isolated plaintext."""
    from sqlalchemy import select, or_
    from backend.models.realtime_voice import VoiceCall, VoiceCallTurn
    now = now or datetime.utcnow()
    stats = {cid:dict(turn_count=0,interrupted_count=0,safety_matched_count=0,
        cleared_turn_count=0,crisis_matched_count=0,crisis_suspected_count=0,
        isolated_turn_count=0,readable_turn_count=0) for cid in call_ids}
    if not stats: return stats
    turns = await db.execute(select(VoiceCallTurn.call_id,VoiceCallTurn.assistant_interrupted,
        VoiceCallTurn.user_content_safety_status,VoiceCallTurn.assistant_content_safety_status,
        VoiceCallTurn.effective_text_cleared_at,VoiceCallTurn.effective_text_expires_at,
        VoiceCallTurn.user_crisis_status,VoiceCallTurn.assistant_crisis_status,
        or_(VoiceCallTurn.user_text_final != '', VoiceCallTurn.assistant_text_effective != '').label('has_text'),
        VoiceCall.deleted_at,VoiceCall.deletion_fence_at,VoiceCall.transcript_expires_at
        ).join(VoiceCall, VoiceCall.call_id == VoiceCallTurn.call_id)
        .where(VoiceCallTurn.call_id.in_(call_ids)))
    for cid, interrupted, user_safety, assistant_safety, cleared, expires, user_crisis, assistant_crisis, has_text, deleted, fence, call_expires in turns:
        value=stats[cid];value['turn_count']+=1;value['interrupted_count']+=int(interrupted)
        value['safety_matched_count']+=int(user_safety=='matched')+int(assistant_safety=='matched')
        value['cleared_turn_count']+=int(cleared is not None)
        statuses=(user_crisis,assistant_crisis)
        value['crisis_matched_count']+=statuses.count('matched')
        value['crisis_suspected_count']+=statuses.count('suspected')
        value['isolated_turn_count']+=int(any(s in {'matched','suspected','isolation_failed'} for s in statuses))
        value['readable_turn_count']+=int(bool(has_text) and deleted is None and fence is None
            and (call_expires is None or call_expires > now) and cleared is None
            and expires is not None and expires > now and statuses == ('passed','passed'))
    return stats


async def record_statistics(db, call_ids):
    from sqlalchemy import select, func
    from backend.models.realtime_voice import VoiceMemoryJob, VoiceMemoryTrace, VoiceFollowupJob
    stats = await transcript_statistics(db, call_ids)
    for value in stats.values():
        value.update(memory_success_count=0,memory_failed_count=0,memory_trace_count=0,
            memory_dropped_count=0,memory_dropped_complete=True,followup_statuses=[])
    if not stats: return stats
    jobs = await db.execute(select(VoiceMemoryJob.call_id,VoiceMemoryJob.status,
        VoiceMemoryJob.extraction_snapshot).where(VoiceMemoryJob.call_id.in_(call_ids)))
    for cid, status, snapshot in jobs:
        value=stats[cid]
        value['memory_success_count']+=int(status=='success')
        value['memory_failed_count']+=int(status=='failed')
        dropped=snapshot.get('dropped') if isinstance(snapshot,dict) else None
        if type(dropped) is int and dropped>=0: value['memory_dropped_count']+=dropped
        else: value['memory_dropped_complete']=False
    traces = await db.execute(select(VoiceMemoryTrace.call_id,func.count()).where(
        VoiceMemoryTrace.call_id.in_(call_ids)).group_by(VoiceMemoryTrace.call_id))
    for cid, count in traces: stats[cid]['memory_trace_count']=count
    followups = await db.execute(select(VoiceFollowupJob.call_id,VoiceFollowupJob.status).where(
        VoiceFollowupJob.call_id.in_(call_ids)).order_by(VoiceFollowupJob.id))
    for cid, status in followups: stats[cid]['followup_statuses'].append(status)
    return stats
