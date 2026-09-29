"""Authoritative voice lifecycle transitions; callers own finalization effects."""
import logging
from datetime import timezone

from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall
from backend.models.user import User
from backend.services.realtime_voice_metric_service import stage_voice_metrics

logger = logging.getLogger(__name__)
TERMINAL = frozenset({'ended', 'missed', 'failed', 'cancelled'})
ACTIVE = ('deciding', 'ringing', 'connected', 'reconnecting', 'ending')
TRANSITIONS = {
    'deciding': {'ringing', 'missed', 'failed', 'cancelled'},
    'ringing': {'connected', 'missed', 'failed', 'cancelled'},
    'connected': {'reconnecting', 'ending'},
    'reconnecting': {'connected', 'ending'},
    'ending': {'ended'},
}
REASONS = frozenset({'user_hangup', 'user_cancel', 'exit_intent', 'silence_timeout',
    'quota_exhausted', 'hard_limit', 'reconnect_timeout', 'provider_error',
    'system_error', 'character_missed'})


def utc_naive(now):
    if now.tzinfo is None:
        raise ValueError('server_time_requires_timezone')
    return now.astimezone(timezone.utc).replace(tzinfo=None)


def emit_transition(before, after, reason=None):
    # No identifiers, transcript or unrestricted error strings in dimensions.
    logger.info('voice.state.transition from=%s to=%s reason=%s', before, after,
                reason if reason in REASONS else 'none' if reason is None else 'other')


def stage_transition_metric(db,before,after,reason=None):
    stage_voice_metrics(db,[('voice.state.transition',{'from':before,'to':after,
        'reason':reason if reason in REASONS else 'none' if reason is None else 'other'},1)])


async def lock_call(db, call_id):
    owner = await db.scalar(select(VoiceCall.user_id).where(VoiceCall.call_id == call_id))
    if owner is None:
        return None
    # Same lock order as creation, quota and administrative finalization.
    await db.scalar(select(User.id).where(User.id == owner).with_for_update())
    return await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id)
                           .with_for_update().execution_options(populate_existing=True))


def final_status(row, reason):
    if row.connected_at is not None:
        return 'ended'
    if reason in ('user_cancel', 'user_hangup'):
        return 'cancelled'
    return 'missed' if reason == 'character_missed' else 'failed'


def stage_final_state(row, *, reason, now):
    """Called only in the locked settlement/flush transaction, never commits."""
    if row.status in TERMINAL:
        logger.info('voice.state.terminal_replay=1')
        return False
    if row.status not in ACTIVE:
        raise ValueError('invalid_call_state')
    target = final_status(row, reason)
    row.status = target
    row.end_reason = 'user_cancel' if target == 'cancelled' else reason
    row.ended_at = utc_naive(now)
    if row.connected_at is None:
        row.summary_status = 'not_applicable'
    return True


async def transition_call(db, *, call_id, expected, target, now, metrics=None, call01_fallback=None):
    """Serialize server transitions; an existing terminal state is immutable.

    Terminal transitions here are establishment-only (no charge or turn yet).
    Connected finalization must use VoiceOpsService.end_call for transactional
    flush and settlement rather than bypassing them with a status assignment.
    """
    if call01_fallback is not None and (type(call01_fallback) is not bool or
            tuple(expected) != ('deciding',) or target not in {'ringing','missed','cancelled'}):
        raise ValueError('invalid_call01_fact_transition')
    if (not expected or target == 'ended'
            or any(target not in TRANSITIONS.get(state, set()) for state in expected)):
        logger.info('voice.state.invalid_transition=1')
        if metrics is not None:await metrics.emit_many([('voice.state.invalid_transition',{},1)])
        raise ValueError('invalid_call_transition')
    row = await lock_call(db, call_id)
    if row is None or row.status not in expected:
        if row is not None and row.status in TERMINAL:
            logger.info('voice.state.terminal_replay=1')
            stage_voice_metrics(db,[('voice.state.terminal_replay',{},1)])
        await db.commit()
        from backend.services.realtime_voice_metric_service import flush_voice_metrics
        await flush_voice_metrics(db,metrics)
        return False
    if call01_fallback is not None:
        row.call01_fallback = call01_fallback
    before = row.status
    instant = utc_naive(now)
    if target in TERMINAL:
        if row.connected_at is not None:
            if metrics is not None:await metrics.emit_many([('voice.state.invalid_transition',{},1)])
            raise ValueError('connected_call_requires_finalizer')
        reason = {'missed':'character_missed', 'failed':'system_error', 'cancelled':'user_cancel'}[target]
        stage_final_state(row, reason=reason, now=now)
        from backend.services.realtime_voice_card_service import stage_call_card
        await stage_call_card(db, row)
        if target == 'missed':
            from backend.services.realtime_voice_summary_followup_service import stage_missed_followup
            await stage_missed_followup(db, call=row)
    else:
        row.status = target
        if target == 'connected' and row.connected_at is None:
            row.connected_at = instant
    reason = row.end_reason
    stage_transition_metric(db,before,target,reason)
    await db.commit()
    from backend.services.realtime_voice_metric_service import flush_voice_metrics
    await flush_voice_metrics(db,metrics)
    emit_transition(before, target, reason)
    return True
