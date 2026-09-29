"""Bounded voice-only producer counters; no business identifiers or content."""
import asyncio
import json
import logging
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timezone

_deferred_observations = ContextVar('voice_deferred_observations', default=None)


@contextmanager
def defer_voice_metrics(events):
    """Collect telemetry without I/O inside a business readiness deadline."""
    token = _deferred_observations.set(events)
    try:
        yield
    finally:
        _deferred_observations.reset(token)


logger = logging.getLogger(__name__)
TTL_SECONDS = 172800
SUMMARY_REASONS = frozenset({
    'ineligible', 'source_expired', 'source_unavailable', 'deleted', 'lease_expired',
    'summary_configuration_invalid', 'invalid_or_rejected_output', 'model_unavailable',
    'result_commit_failed',
})
PREFLIGHT_REASONS=frozenset({'invalid_idempotency_key','invalid_request','invalid_device','user_missing','user_banned','IDEMPOTENCY_KEY_REUSED','idempotency_record_incomplete','browser_unsupported','microphone_denied','dial_cooldown','maintenance','soft_stop','disabled','not_allowlisted','quota_empty','provider_unavailable','crisis_config_unavailable','user_busy','capacity_full','internal_unavailable'})
_CALL_STATUSES=frozenset({'deciding','ringing','connected','reconnecting','ending','ended','missed','failed','cancelled'})
_CALL_REASONS=frozenset({'user_hangup','user_cancel','exit_intent','silence_timeout','quota_exhausted','hard_limit','reconnect_timeout','provider_error','system_error','character_missed','none','other'})
MEMORY_JOB_REASONS = frozenset({'deletion_fence','source_expired','retention_expired',
    'recovery_snapshot_required','lease_expired','snapshot_invalid','extract_unavailable',
    'write_unavailable','safety_filtered','invalid_output','dropped_items','skipped','ineligible','other'})
RECALL_STATUSES=frozenset({'ready','cancelled','context_unavailable','cache_unavailable','timeout','invalid_output','unavailable','filtered','not_needed','empty'})
EVENT_DIMENSIONS = {
    'voice.recall.trigger': {'result':frozenset({'attempt'})},
    'voice.recall.result': {'result':RECALL_STATUSES},
    'voice.recall.latency_ms': {'result':RECALL_STATUSES},
    'voice.recall.mode': {'mode':frozenset({'current_turn_requested','next_turn_cached','none'})},
    'voice.recall.source': {'source':frozenset({'none','short_term','preamble','topic_cache','long_term'})},
    'voice.recall.timeout': {},
    'voice.recall.cache': {'result':frozenset({'hit','stored','unavailable'})},
    'voice.recall.late': {'reason':frozenset({'text_started','stale_question'})},
    'voice.recall.delivery': {'result':frozenset({'current_turn_requested','next_turn','failure','cancelled'})},
    'voice.recall.double_reply': {'result':frozenset({'detected','prevented'}),'unit':frozenset({'frame','injection'})},
    'voice.recall.reply_observed': {'kind':frozenset({'primary','extra','overflow'}),'evidence':frozenset({'verified','unverified'})},
    'voice.recall.not_measurable': {'reason':frozenset({'adoption','current_turn_capability'})},
    'voice.memory_job.enqueue': {'result':frozenset({'pending','skipped','cancelled'})},
    'voice.memory_job.claim': {'phase':frozenset({'first','retry'})},
    'voice.memory_job.enqueue_to_claim_ms': {'phase':frozenset({'first','retry'}),'capped':frozenset({'true','false'})},
    'voice.memory_job.result': {'result':frozenset({'success','failed','skipped','cancelled'})},
    'voice.memory_job.retry': {'source':frozenset({'automatic','admin'}),'reason':MEMORY_JOB_REASONS},
    'voice.memory_job.drop': {'reason':MEMORY_JOB_REASONS},
    'voice.memory_job.compensate': {'result':frozenset({'repaired','no_change'})},
    'voice.memory_job.compensated_jobs': {},
    'voice.memory_job.fence_cancel': {},
    'voice.memory_extract.enqueue': {'result':frozenset({'pending','skipped','cancelled'})},
    'voice.memory_extract.eligible': {'result':frozenset({'eligible','skipped'})},
    'voice.memory_extract.skip': {'reason':frozenset({'deletion_fence','low_confidence','no_user_text','not_closed','no_effective_text','safety','crisis','no_meaningful_text','invalid_output','all_items_dropped','no_items'})},
    'voice.memory_extract.result': {'result':frozenset({'ready','skipped','invalid_output','unavailable'})},
    'voice.memory_extract.drop': {'reason':frozenset({'invalid_atom','duplicate_key','item_limit','schema_invalid','safety'})},
    'voice.memory_extract.output': {'bucket':frozenset({'0','1','2','3','4','5'})},
    'voice.memory_upsert.source_observation': {'previous':frozenset({'voice','text','admin','unknown'}), 'current':frozenset({'voice'}), 'boundary':frozenset({'prewrite'})},
    'voice.memory_upsert.result': {'result':frozenset({'written','existing','superseded','cancelled','failure'})},
    'voice.memory_upsert.conflict': {'scope':frozenset({'stable_key','cross_channel'}),'result':frozenset({'busy','existing','superseded','not_measurable'})},
    'voice.context_pack.result': {'result':frozenset({'full','minimal','failure','cancelled'})},
    'voice.context_pack.duration_ms': {'result':frozenset({'full','minimal','failure','cancelled'})},
    'voice.context_pack.size_chars': {'section':frozenset({'persona','dynamic'})},
    'voice.context_pack.crop_count': {},
    'voice.context_pack.fallback': {'reason':frozenset({'timeout','source_failed','source_invalid','compile_timeout','unavailable'})},
    'voice.context_pack.failure': {'reason':frozenset({'persona_anchor_invalid','context_config_invalid','persona_empty','minimum_context_budget_invalid','referenced_persona_unavailable','timeout','cancelled','unavailable'})},
    'voice.context_pack.barrier': {'result':frozenset({'released','not_released'})},
    'voice.crisis.assessment': {'direction':frozenset({'user','assistant'}),'result':frozenset({'passed','matched','suspected'})},
    'voice.crisis.hit': {'direction':frozenset({'user','assistant'}),'result':frozenset({'matched','suspected'})},
    'voice.crisis.suspected': {'direction':frozenset({'user','assistant'}),'reason':frozenset({'redis_unavailable','missing','invalid_json','invalid_or_empty','unavailable'})},
    'voice.crisis.redis_error': {'direction':frozenset({'user','assistant'})},
    'voice.crisis.alert': {'result':frozenset({'success','failure'})},
    'voice.crisis.audit': {'action':frozenset({'list','detail'}),'result':frozenset({'success','failure'})},
    'voice.content_safety.result': {'direction':frozenset({'user','assistant'}),'result':frozenset({'passed','matched','error_allowed'})},
    'voice.content_safety.keyword_hit': {'direction':frozenset({'user','assistant'})},
    'voice.content_safety.exception_allowed': {'direction':frozenset({'user','assistant'})},
    'voice.content_safety.deduplicated': {'direction':frozenset({'user','assistant'})},
    'voice.content_safety.dedup_unavailable': {'direction':frozenset({'user','assistant'})},
    'voice.growth.result': {'result':frozenset({'eligible','ineligible'})},
    'voice.growth.eligible_seconds': {},
    'voice.growth.points': {},
    'voice.growth.daily_cap_hit': {},
    'voice.growth.idempotent': {},
    'voice.cross_modal.proactive_reset': {},
    'voice.cross_modal.p0_suppressed': {},
    'voice.cross_modal.diary': {'result':frozenset({'voice_interaction'})},
    'voice.cross_modal.diary_summary': {'result':frozenset({'ready','fallback'})},
    'voice.reconnect.trigger': {'reason':frozenset({'client_disconnect','provider_disconnect'})},
    'voice.reconnect.attempt': {'phase':frozenset({'window','provider'})},
    'voice.reconnect.result': {'result':frozenset({'restored','timeout','failure','cancelled','disconnect_failed'})},
    'voice.reconnect.duration_ms': {'result':frozenset({'restored','timeout','failure','cancelled','disconnect_failed'})},
    'voice.reconnect.timeout': {},
    'voice.reconnect.mode': {'mode':frozenset({'same_session','new_session','unavailable'})},
    'voice.reconnect.no_charge_boundary': {'boundary':frozenset({'pause','resume'})},
    'voice.reconnect.no_charge_ms': {'boundary':frozenset({'meter_observation'})},
    'voice.finalizer.end_reason': {'reason':_CALL_REASONS},
    'voice.finalizer.replay': {},
    'voice.finalizer.policy': {'kind':frozenset({'hard_limit','quota_exhausted','silence_timeout','exit_intent','silence_goodbye','exit_goodbye','native_exit','goodbye_cancelled','grace_started','silence_confirm','time_low'})},
    'voice.barge_in.decision': {'source':frozenset({'filter','classifier'}),'result':frozenset({'candidate','backchannel','escalated'})},
    'voice.barge_in.stop_clear': {'result':frozenset({'requested','send_failed','acknowledged','ack_unavailable'})},
    'voice.barge_in.stop_clear_latency_ms': {'boundary':frozenset({'server_request_to_client_ack'})},
    'voice.barge_in.truncate': {'result':frozenset({'requested','success','failure','not_measurable'}),'reason':frozenset({'request','confirmed','request_failed','capability_unavailable','identity_unavailable','confirmation_unavailable'})},
    'voice.barge_in.false_interrupt': {'result':frozenset({'not_measurable'})},
    'voice.barge_in.truncate_outcome': {'result':frozenset({'success','failure','unknown'}),'evidence':frozenset({'verified','unverified'})},
    'voice.effective_text.evidence': {'level':frozenset({'exact_played','confirmed_sentences','full','none'})},
    'voice.effective_text.observed': {'level':frozenset({'exact_played','confirmed_sentences','full','none'}),'evidence':frozenset({'verified','unverified'})},
    'voice.effective_text.event': {'kind':frozenset({'mapping_unavailable','ack_unavailable','invalid_client_event','duplicate_client_event','out_of_order_client_event'})},
    'voice.turn.event': {'kind':frozenset({'interim','final','duplicate','out_of_order','orphan','incomplete','late','gate_error','isolation_failed','persistence_failed'})},
    'voice.turn.close_duration_ms': {},
    'voice.turn.closed': {},
    'voice.state.transition': {'from':_CALL_STATUSES,'to':_CALL_STATUSES,'reason':_CALL_REASONS},
    'voice.state.invalid_transition': {},
    'voice.state.terminal_replay': {},
    'voice.ws.connection': {'channel':frozenset({'initial','reconnect'}),'result':frozenset({'accepted','disconnected'})},
    'voice.ws.concurrency': {'scope':frozenset({'process_handlers'}),'bucket':frozenset({'0','1','2_5','6_10','over_10'})},
    'voice.ws.rejection': {'channel':frozenset({'initial','reconnect'}),'reason':frozenset({'origin','tls','ticket','connection'})},
    'voice.ws.frame_rejection': {'reason':frozenset({'frame_too_large','frame_rate_exceeded','frame_invalid','invalid'})},
    'voice.ws.heartbeat_timeout': {},
    'voice.ws.close_reason': {'reason':frozenset({'user_hangup','user_cancel','exit_intent','silence_timeout','quota_exhausted','hard_limit','reconnect_timeout','provider_error','system_error','character_missed','other','unavailable'})},
    'voice.call01.decision_duration_ms': {'result':frozenset({'model','fallback'})},
    'voice.call01.output': {'result':frozenset({'valid','invalid','timeout'})},
    'voice.call01.decision': {'result':frozenset({'answer','missed'}),'mode':frozenset({'forced','ordinary'})},
    'voice.call01.fallback': {'reason':frozenset({'timeout','decision_invalid'})},
    'voice.call01.final_latency_ms': {'result':frozenset({'connected','missed','failed','cancelled'})},
    'voice.call01.ringing_result': {'result':frozenset({'connected','missed','failed','cancelled'})},
    'voice.call01.provider_ready': {'order':frozenset({'before_target','after_target','unavailable'})},
    'voice.preflight.result': {'result':frozenset({'created','replay','blocked','cancelled'})},
    'voice.preflight.block_reason': {'reason':PREFLIGHT_REASONS},
    'voice.preflight.idempotency': {'result':frozenset({'replay','conflict'})},
    'voice.lease.acquire': {'result':frozenset({'acquired','user_busy','capacity_full','failure'})},
    'voice.lease.renew': {'result':frozenset({'renewed','owner_mismatch','failure'})},
    'voice.lease.release': {'result':frozenset({'released','owner_mismatch','failure'})},
    'voice.lease.owner_mismatch': {'operation':frozenset({'renew','release','check'})},
    'voice.lease.reconcile': {'result':frozenset({'success','failure'})},
    'voice.lease.reconcile_corrected': {},
    'voice.ops_stop.result': {'operation':frozenset({'soft','hard'}),'result':frozenset({'success','repeated','partial_failure','failure','rejected'})},
    'voice.quota.usage_slice': {'kind':frozenset({'connected','grace'})},
    'voice.quota.usage_seconds': {'kind':frozenset({'connected','grace'})},
    'voice.quota.balance_zero': {},
    'voice.quota.grace': {'result':frozenset({'trigger','end'})},
    'voice.quota.grace_seconds': {},
    'voice.quota.billing_input_seconds': {'source':frozenset({'server'})},
    'voice.quota.deduplicated': {},
    'voice.quota.transaction_conflict': {'reason':frozenset({'checkpoint','balance','database'})},
    'voice.provider.session': {'operation':frozenset({'connect','finish'}),'result':frozenset({'attempt','success','failure','cancelled'})},
    'voice.provider.start': {'result':frozenset({'attempt','success','failure','cancelled'})},
    'voice.provider.error': {'reason':frozenset({'invalid_config','credential_missing','authentication_failed','timeout','upstream_unavailable','protocol_error','evidence_invalid'})},
    'voice.provider.usage': {'result':frozenset({'received','missing','invalid','late'})},
    'voice.provider.capability': {'capability':frozenset({'supports_reply_cancel','supports_context_truncate','supports_current_turn_rag_gate','supports_session_reconnect','supports_playback_text_mapping','supports_sentence_playback_ack'}),'result':frozenset({'enabled','downgraded','not_measurable'})},
    'voice.timeline.insert': {'status':frozenset({'ended','missed'})},
    'voice.timeline.update': {'status':frozenset({'ready','not_applicable','failed'})},
    'voice.timeline.pending_reload': {},
    'voice.timeline.cursor_duplicate': {'scope':frozenset({'page','anchor'})},
    'voice.timeline.cursor_missing': {'scope':frozenset({'anchor'})},
    'voice.summary.eligible': {'result': frozenset({'eligible', 'ineligible'})},
    'voice.summary.result': {'result': frozenset({'ready', 'not_applicable', 'failed', 'cancelled'})},
    'voice.summary.failure': {'reason': SUMMARY_REASONS},
    'voice.summary.static_fallback': {'reason': SUMMARY_REASONS},
    'voice.summary.card_update': {'status': frozenset({'ready', 'not_applicable', 'failed'})},
    'voice.summary.reasoning_expiry': {},
    'voice.followup.branch': {'branch': frozenset({'missed','topic'})},
    'voice.followup.schedule': {'result': frozenset({'pending','cancelled','window_deferred'})},
    'voice.followup.send': {'result': frozenset({'sent'})},
    'voice.followup.cancel': {'reason': frozenset({'source_missing','source_deleted','source_expired',
        'deadline_exceeded','content_unavailable','source_ineligible','user_chatted','topic_continued',
        'already_sent','quota_unavailable','deletion_fence','retention_expired','max_delay_exceeded'})},
    'voice.followup.retry': {'reason': frozenset({'dispatch_unavailable','count_pending','lease_expired'})},
    'voice.followup.failure': {'reason': frozenset({'source_missing','invalid_snapshot','message_missing'})},
    'voice.retention.expiry_scan': {'kind':frozenset({'contents','replays'}),'result':frozenset({'success','failure'})},
    'voice.retention.single_call_delete': {'result':frozenset({'deleted','repeated','failure','rejected'})},
    'voice.retention.fence': {'result':frozenset({'set','existing'})},
    'voice.retention.cancel': {'kind':frozenset({'memory','postprocess','followup'}),
        'reason':frozenset({'deletion_fence','source_expired','retention_expired'})},
    'voice.retention.retry': {'reason':frozenset({'contents_unavailable','replays_unavailable','delete_unavailable'})},
}
_ADMIN_ACTIONS=frozenset({'view','export','debug','retry','delete'})
EVENT_DIMENSIONS.update({
    'voice.admin_record.authorization':{'action':_ADMIN_ACTIONS,'result':frozenset({'authorized','denied'})},
    'voice.admin_record.result':{'action':_ADMIN_ACTIONS,'result':frozenset({'success','rejected','failure'})},
    'voice.admin_record.audit':{'action':_ADMIN_ACTIONS,'result':frozenset({'success','failure'})},
    'voice.admin_record.fixed_snapshot':{'result':frozenset({'valid','projection_mismatch'})},
})
DURATION_METRICS = frozenset(name for name in EVENT_DIMENSIONS if name.endswith('_ms'))
DURATION_PREFIX = 'voice.duration_histogram:'


_INCREMENT = """
-- VOICE_PRODUCER_COUNTERS_V1: validate all key types before any mutation.
for i = 1, #KEYS do
    local reply = redis.call('TYPE', KEYS[i])
    local kind = type(reply) == 'table' and reply.ok or reply
    if kind ~= 'none' and kind ~= 'hash' then return redis.error_reply('invalid_voice_counter_type') end
    local value = redis.call('HGET', KEYS[i], ARGV[(i-1)*2+1])
    if value and (not (value == '0' or string.match(value, '^[1-9]%d*$')) or tonumber(value) > 1000000000000) then
        return redis.error_reply('invalid_voice_counter_value')
    end
end
for i = 1, #KEYS do
    redis.call('HINCRBY', KEYS[i], ARGV[(i-1)*2+1], ARGV[(i-1)*2+2])
    redis.call('EXPIRE', KEYS[i], 172800)
end
return #KEYS
"""


class VoiceMetrics:
    def __init__(self, cache, *, deadline_seconds=0.1):
        self.cache, self.deadline = cache, deadline_seconds

    async def emit_many(self, events):
        """Count committed transitions, not polling calls. Redis loss is observable, not fatal.

        Each event is (registered name, closed dimensions, nonnegative integer amount).
        Buckets use UTC, matching existing voice content-safety/config counters.
        These short-lived counters are not a durable business outbox.
        """
        deferred = _deferred_observations.get()
        if deferred is not None:
            deferred.extend(events)
            return True
        try:
            day = datetime.now(timezone.utc).strftime('%Y%m%d')
            keys, args = [], []
            for name, dimensions, amount in events:
                schema = EVENT_DIMENSIONS.get(name)
                if schema is None or set(dimensions) != set(schema):
                    raise ValueError('invalid_voice_metric')
                if any(type(value) is not str or value not in schema[key] for key, value in dimensions.items()):
                    raise ValueError('invalid_voice_metric')
                if type(amount) is not int or not 0 <= amount <= 1000000000:
                    raise ValueError('invalid_voice_metric')
                if name in DURATION_METRICS:
                    keys.append(DURATION_PREFIX + name + ':' + day)
                    args.extend((json.dumps({'dimensions': dimensions, 'milliseconds': amount},
                        sort_keys=True, separators=(',', ':')), 1))
                if amount:
                    keys.append(name + ':' + day)
                    args.extend((json.dumps(dimensions, sort_keys=True, separators=(',', ':')), amount))
            if keys:
                await asyncio.wait_for(self.cache.eval(_INCREMENT, len(keys), *keys, *args), self.deadline)
            return True
        except Exception:
            logger.warning('voice.metrics.emit_unavailable')
            return False


def stage_voice_metrics(db, events):
    """Attach content-free observations to the caller-owned transaction.

    Callers must explicitly flush after commit; rollback discards queued events.
    No background task or Redis I/O runs under transaction locks.
    """
    from sqlalchemy import event
    if not db.info.get('_voice_metric_rollback_hook'):
        def discard_rolled_back(session, previous):
            # Flush may report an internal transaction underneath a SAVEPOINT.
            while not previous.nested and previous.parent is not None:
                previous = previous.parent
            if not previous.nested:
                session.info.pop('_voice_metric_events', None)
                session.info.pop('_voice_metric_owners', None)
                return
            def belongs_to_rollback(owner):
                while owner is not None:
                    if owner is previous:
                        return True
                    owner = owner.parent
                return False
            pairs = zip(session.info.get('_voice_metric_events', []),
                        session.info.get('_voice_metric_owners', []))
            kept = [(value, owner) for value, owner in pairs
                    if not belongs_to_rollback(owner)]
            session.info['_voice_metric_events'] = [value for value, _ in kept]
            session.info['_voice_metric_owners'] = [owner for _, owner in kept]
        event.listen(db.sync_session, 'after_soft_rollback', discard_rolled_back)
        db.info['_voice_metric_rollback_hook'] = True
    events = list(events)
    owner = db.sync_session.get_nested_transaction() or db.sync_session.get_transaction()
    db.info.setdefault('_voice_metric_events', []).extend(events)
    db.info.setdefault('_voice_metric_owners', []).extend([owner] * len(events))


async def flush_voice_metrics(db, metrics):
    events = db.info.pop('_voice_metric_events', [])
    db.info.pop('_voice_metric_owners', None)
    if events and metrics is not None:
        await metrics.emit_many(events)


class ApplicationVoiceMetrics:
    """Lazy application-owned adapter; constructing the app never opens Redis."""
    async def emit_many(self,events):
        try:
            from backend.redis_client import get_redis
            return await VoiceMetrics(await get_redis()).emit_many(events)
        except Exception:
            logger.warning('voice.metrics.emit_unavailable')
            return False
