"""M2 read-only preflight then single-transaction idempotent call creation."""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.models.user import User
from backend.models.realtime_voice import VoiceCall, VoiceCallCreateIdempotency
from backend.services.realtime_voice_quota_service import VoiceQuotaService
from backend.services.realtime_voice_metric_service import VoiceMetrics,PREFLIGHT_REASONS

logger = logging.getLogger(__name__)


class VoicePreflightError(ValueError):
    def __init__(self, reason, status=409):
        self.reason, self.status = reason, status
        super().__init__(reason)


def canonical_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {'source','device_id','browser_supported','microphone_granted'}:
        raise VoicePreflightError('invalid_request', 422)
    try:
        if str(UUID(payload['device_id'])) != payload['device_id']:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise VoicePreflightError('invalid_device', 422) from None
    if payload['source'] != 'home' or any(type(payload[k]) is not bool for k in ('browser_supported','microphone_granted')):
        raise VoicePreflightError('invalid_request', 422)
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


class VoiceCreateService:
    def __init__(self, *, loader, cache, leases, ticket_codec, provider_preflight, metric=None, metrics=None):
        self.loader, self.cache, self.leases = loader, cache, leases
        self.metrics=metrics if metrics is not None else VoiceMetrics(cache)
        self.ticket_codec, self.provider_preflight = ticket_codec, provider_preflight
        self.metric = metric or (lambda name, value: logger.info('%s=%s', name, value))

    def response(self, record, call, payload, now):
        value = dict(call_id=call.call_id, status=call.status, call_ticket=None)
        if record.ticket_consumed_at is None and record.ticket_expires_at > now.replace(tzinfo=None):
            value['call_ticket'] = self.ticket_codec.issue(user_id=call.user_id, call_id=call.call_id,
                jti=record.ticket_jti, device_id=payload['device_id'],
                expires_ms=int(record.ticket_expires_at.replace(tzinfo=timezone.utc).timestamp()*1000))
        return value

    async def create(self, db, *, user_id, idempotency_key, payload, now=None):
        now = now or datetime.now(timezone.utc)
        call_id = None
        acquired = False
        committed = False
        try:
            try:
                valid_key = isinstance(idempotency_key, str) and len(idempotency_key) <= 64 and str(UUID(idempotency_key)) == idempotency_key
            except (ValueError, TypeError, AttributeError):
                valid_key = False
            if not valid_key:
                raise VoicePreflightError('invalid_idempotency_key', 422)
            normalized = canonical_payload(payload)
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            # User lock also serializes absent idempotency rows across processes.
            user = await db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
            if user is None:
                raise VoicePreflightError('user_missing', 401)
            if user.is_banned or await self.cache.get(f'user_banned:{user_id}'):
                raise VoicePreflightError('user_banned', 403)
            record = await db.scalar(select(VoiceCallCreateIdempotency).where(
                VoiceCallCreateIdempotency.user_id == user_id,
                VoiceCallCreateIdempotency.idempotency_key == idempotency_key).with_for_update().execution_options(populate_existing=True))
            if record is not None and record.replay_expires_at > now.replace(tzinfo=None):
                if record.request_payload_sha256 != digest:
                    raise VoicePreflightError('IDEMPOTENCY_KEY_REUSED')
                call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == record.call_id).with_for_update().execution_options(populate_existing=True))
                if call is None:
                    raise VoicePreflightError('idempotency_record_incomplete', 503)
                result = self.response(record, call, payload, now)
                await db.commit()
                committed = True
                self.metric('voice.preflight.replay', 1)
                await self.metrics.emit_many([('voice.preflight.result',{'result':'replay'},1),
                    ('voice.preflight.idempotency',{'result':'replay'},1)])
                return result
            if record is not None:
                await db.delete(record); await db.flush()
            if not payload['browser_supported']:
                raise VoicePreflightError('browser_unsupported')
            if not payload['microphone_granted']:
                raise VoicePreflightError('microphone_denied')
            if await self.leases.check_new_dial(user_id):
                raise VoicePreflightError('dial_cooldown')
            bundle = await self.loader.load_bundle(user_id=user_id)
            snapshot = bundle.build_snapshot(user_id=user_id, now=now)
            config_snapshot, capability_snapshot = snapshot.persistence_values()
            config = config_snapshot['resolved_config']
            if bundle.should_block_new_call(user_id):
                gate = bundle.fallback_gate_global if bundle.config.technical_fallback else config['global']
                reason = ('disabled' if bundle.master_switch_enabled is not True else
                          'maintenance' if gate and gate.get('maintenance_mode') else
                          'soft_stop' if gate and gate.get('soft_stop') else
                          'not_allowlisted')
                raise VoicePreflightError(reason)
            crisis = await self.loader.load_crisis_keywords(db=db)
            if crisis.suspected_hit or not crisis.keywords:
                raise VoicePreflightError('crisis_config_unavailable', 503)
            quota = VoiceQuotaService()
            balance = await quota.balance(db, user_id, daily_seconds=config['quota']['daily_free_seconds'],
                                          now=now, lock=True, published_config=True)
            if balance.total <= 0:
                raise VoicePreflightError('quota_empty')
            if not await self.provider_preflight(config):
                raise VoicePreflightError('provider_unavailable', 503)
            existing_call = await db.scalar(select(VoiceCall.call_id).where(
                VoiceCall.user_id == user_id,
                VoiceCall.status.in_(('deciding','ringing','connected','reconnecting','ending')))
                .with_for_update().limit(1))
            if existing_call is not None:
                raise VoicePreflightError('user_busy')
            call_id = str(uuid4())
            acquired, reason = await self.leases.acquire(user_id=user_id, call_id=call_id,
                ttl_ms=config['concurrency']['user_lock_ttl_ms'], global_limit=config['concurrency']['global_limit'])
            if not acquired:
                raise VoicePreflightError(reason)
            await quota.apply_published_balance(db, user_id, now=now, free_remaining=balance.free)
            # Millisecond TTL is frozen; database baseline uses second precision.
            # Round the shared expiry down so DB, replay and signed ticket agree.
            expires = (now+timedelta(milliseconds=config['concurrency']['call_ticket_ttl_ms'])).replace(tzinfo=None, microsecond=0)
            call = VoiceCall(call_id=call_id, user_id=user_id, initiated_by='user', status='deciding',
                            summary_status='pending', config_snapshot=config_snapshot, capability_snapshot=capability_snapshot,
                            transcript_retention_days=config['retention']['effective_transcript_days'],
                            generated_retention_days=config['retention']['generated_debug_days'])
            record = VoiceCallCreateIdempotency(user_id=user_id, idempotency_key=idempotency_key,
                request_payload_sha256=digest, call_id=call_id, ticket_jti=str(uuid4()), ticket_expires_at=expires,
                replay_expires_at=(now+timedelta(hours=24)).replace(tzinfo=None, microsecond=0))
            db.add_all([call, record]); await db.flush()
            result = self.response(record, call, payload, now)
            await db.commit()
            committed = True
            self.metric('voice.preflight.created', 1)
            await self.metrics.emit_many([('voice.preflight.result',{'result':'created'},1)])
            return result
        except (Exception, asyncio.CancelledError) as exc:
            if committed:
                raise
            try:
                await db.rollback()
                if acquired:
                    await self.leases.release(user_id=user_id, call_id=call_id)
            finally:
                if isinstance(exc,asyncio.CancelledError):
                    events=[('voice.preflight.result',{'result':'cancelled'},1)]
                else:
                    observed_reason=exc.reason if isinstance(exc,VoicePreflightError) and exc.reason in PREFLIGHT_REASONS else 'internal_unavailable'
                    events=[('voice.preflight.result',{'result':'blocked'},1),
                        ('voice.preflight.block_reason',{'reason':observed_reason},1)]
                    if observed_reason=='IDEMPOTENCY_KEY_REUSED':
                        events.append(('voice.preflight.idempotency',{'result':'conflict'},1))
                await self.metrics.emit_many(events)
            if isinstance(exc, asyncio.CancelledError):
                raise
            reason = exc.reason if isinstance(exc, VoicePreflightError) else 'internal_unavailable'
            self.metric('voice.preflight.block.'+reason, 1)
            if isinstance(exc, VoicePreflightError):
                raise
            raise VoicePreflightError('internal_unavailable', 503) from None
