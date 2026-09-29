"""M2 operations: fixed-target termination, metadata-only listing and soft stop."""
from __future__ import annotations

import json
import asyncio
import logging
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from redis.exceptions import RedisError

from backend.models.admin_config import AdminConfig
from backend.models.realtime_voice import VoiceCall
from backend.models.user import User
from backend.services.realtime_voice_config_service import (
    VOICE_CALL_CONFIG_KEY, VoiceConfigError, canonical_json,
    _execute_publish_with_compensation, realtime_voice_config_service,
)
from backend.services.realtime_voice_quota_service import QuotaError, VoiceQuotaService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_local_runtime import local_voice_calls
from backend.services.realtime_voice_state_service import ACTIVE, TERMINAL, stage_final_state, emit_transition, stage_transition_metric
from backend.utils.admin_auth import log_operation

logger = logging.getLogger(__name__)


def end_failure(call_id, exc=None):
    """Bounded operator-facing details; never return SQL/cache/exception text."""
    if exc is None:
        code, message, retryable = ('VOICE_END_CLEANUP_PENDING', '通话已结束，资源清理待完成。', True)
    elif isinstance(exc, VoiceConfigError):
        code, message, retryable = exc.code, exc.message, exc.status_code >= 500
    elif isinstance(exc, QuotaError):
        code, message, retryable = ('VOICE_END_SETTLEMENT_REVIEW_REQUIRED', '结算依据缺失或不一致，需人工核查后重试。', False)
    elif isinstance(exc, ValueError) and exc.args == ('voice_growth_call_not_terminal',):
        code, message, retryable = ('VOICE_END_STATE_INVALID', '通话终态校验未通过，需核查后台日志后重试。', False)
    elif isinstance(exc, DBAPIError):
        code, message, retryable = ('VOICE_END_DATABASE_UNAVAILABLE', '数据库处理未完成，可重试此通话。', True)
    elif isinstance(exc, (RedisError, ConnectionError, TimeoutError)):
        code, message, retryable = ('VOICE_END_DEPENDENCY_UNAVAILABLE', '通话依赖服务暂不可用，可重试此通话。', True)
    else:
        code, message, retryable = ('VOICE_END_FAILED', '通话结束未完成，请重试此通话；持续失败需核查后台日志。', True)
    return dict(call_id=call_id, error_code=code, message=message, retryable=retryable)


def log_end_failure(call_id, exc, *, operation):
    # Correlate with the call without logging prompts, credentials or SQL parameters.
    logger.error('voice.end.failure call_id=%s operation=%s error_code=%s exception_type=%s',
                 call_id, operation, end_failure(call_id, exc)['error_code'], type(exc).__name__)


class _QuotaDeadlock(Exception):
    """A rolled-back MySQL settlement, before consuming final turn buffers."""


class VoiceOpsService:
    def __init__(self, *, cache, session_factory, metric=None, metrics=None):
        self.cache = cache
        self.metrics=metrics if metrics is not None else VoiceMetrics(cache)
        self.session_factory = session_factory
        self.metric = metric or (lambda name, value: logger.info('%s=%s', name, value))

    @staticmethod
    def confirm(value):
        if value != 'CONFIRM':
            raise VoiceConfigError('VOICE_CONFIG_CONFIRM_TEXT_INVALID', '必须精确输入 CONFIRM')

    async def active_calls(self, db):
        # Explicit projection: no snapshots, transcript, reasoning or credentials.
        rows = (await db.execute(select(VoiceCall.call_id, VoiceCall.user_id, VoiceCall.status,
                                        VoiceCall.connected_at, VoiceCall.duration_seconds)
                                 .where(VoiceCall.status.in_(ACTIVE)).order_by(VoiceCall.id))).mappings().all()
        return dict(calls=[{**r, 'connected_at': r['connected_at'].isoformat() if r['connected_at'] else None} for r in rows],
                    database_count=len(rows), lease_count=await self.cache.zcard('voice:lease:active'))

    async def soft_stop(self, db, **kwargs):
        return await self._stop('soft',self._soft_stop,db,**kwargs)

    async def hard_stop(self, db, **kwargs):
        return await self._stop('hard',self._hard_stop,db,**kwargs)

    async def _stop(self,kind,operation,db,**kwargs):
        try:
            result=await operation(db,**kwargs)
        except VoiceConfigError as exc:
            await self.metrics.emit_many([('voice.ops_stop.result',{'operation':kind,
                'result':'rejected' if exc.status_code<500 else 'failure'},1)])
            raise
        except Exception:
            await self.metrics.emit_many([('voice.ops_stop.result',{'operation':kind,'result':'failure'},1)])
            raise
        status='partial_failure' if result.get('failed') else 'repeated' if result.get('idempotent') else 'success'
        await self.metrics.emit_many([('voice.ops_stop.result',{'operation':kind,'result':status},1)])
        return result

    async def _soft_stop(self, db, *, confirm_text, admin_user, request=None):
        self.confirm(confirm_text)
        active = await realtime_voice_config_service._active(db, VOICE_CALL_CONFIG_KEY, lock=True)
        if active is None:
            raise VoiceConfigError('VOICE_CONFIG_NOT_FOUND', '缺少生效语音配置', status_code=409)
        config = json.loads(active.config_value)
        before = bool(config['global']['soft_stop'])
        if before:
            await log_operation(db, admin_user, 'voice_ops', 'soft_stop', '语音软停重复请求', after_value='{"idempotent":true}', request=request)
            await db.commit()
            return dict(idempotent=True, version=active.version)
        config = deepcopy(config)
        config['global']['soft_stop'] = True
        version = active.version + 1
        now = datetime.utcnow()
        async def operation():
            # Dedicated soft-stop publishes only this safety bit. Do not publish,
            # delete, rebase or overwrite the administrator's unrelated draft.
            active.is_active = False
            db.add(AdminConfig(config_key=VOICE_CALL_CONFIG_KEY, config_value=canonical_json(config),
                               version=version, is_active=True, is_draft=False,
                               updated_by=admin_user.username, updated_at=now))
            await db.flush()
            await self.cache.setex(f'active_config:{VOICE_CALL_CONFIG_KEY}', 3600, canonical_json(config))
            await log_operation(db, admin_user, 'voice_ops', 'soft_stop', '仅关闭语音新拨打',
                                before_value='{"soft_stop":false}',
                                after_value=json.dumps(dict(soft_stop=True, version=version)), request=request)
            return dict(version=version, published_at=now.isoformat(), idempotent=False)
        result = await _execute_publish_with_compensation(db, VOICE_CALL_CONFIG_KEY, operation,
                                                          published_config=config, published_version=version)
        self.metric('voice.ops_stop.soft_success', 1)
        return result

    async def end_call(self, *, call_id, user_id=None, reason='system_error', admin_user=None, request=None):
        # A disconnected HTTP/WS request must not cancel settlement halfway
        # through. Wait for this owned task; never leave a detached finalizer.
        task = asyncio.create_task(self._end_call(call_id=call_id, user_id=user_id,
            reason=reason, admin_user=admin_user, request=request))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                if task.cancelled():
                    raise
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError()
        return result

    async def _end_call(self, *, call_id, user_id=None, reason='system_error', admin_user=None, request=None):
        for attempt in range(4):
            try:
                return await self._end_call_once(call_id=call_id, user_id=user_id,
                    reason=reason, admin_user=admin_user, request=request)
            except _QuotaDeadlock as exc:
                if attempt == 3:
                    log_end_failure(call_id, exc.__cause__, operation='finalize')
                    raise exc.__cause__
                logger.info('voice.quota.deadlock_retry=1')
                await asyncio.sleep(.05 * (2 ** attempt))
            except Exception as exc:
                log_end_failure(call_id, exc, operation='finalize')
                raise

    async def _end_call_once(self, *, call_id, user_id=None, reason='system_error', admin_user=None, request=None):
        from backend.services.realtime_voice_lease_service import VoiceLeaseService
        from backend.services.realtime_voice_metric_service import VoiceMetrics
        leases = VoiceLeaseService(self.cache, end_call=self.end_call)
        local = local_voice_calls.get(call_id)
        if local is not None:
            if user_id is not None and local.meter.user_id != user_id:
                raise VoiceConfigError('VOICE_CALL_NOT_FOUND', '通话不存在', status_code=404)
            if local.set_end_reason is not None:
                local.set_end_reason(reason)
            # Stop socket/audio/provider first, even when Redis is unavailable.
            await local.stop()
        async with self.session_factory() as db:
            owner = await db.scalar(select(VoiceCall.user_id).where(VoiceCall.call_id == call_id))
            if owner is None or (user_id is not None and owner != user_id):
                raise VoiceConfigError('VOICE_CALL_NOT_FOUND', '通话不存在', status_code=404)
            await db.scalar(select(User.id).where(User.id == owner).with_for_update())
            row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id).with_for_update().execution_options(populate_existing=True))
            changed = row.status in ACTIVE
            before = row.status
            if changed:
                if row.connected_at is not None:
                    # Never guess billable time when the checkpoint is missing.
                    # Caller receives failure and can retry the same fixed target.
                    try:
                        if local is not None:
                            await VoiceQuotaService(metrics=VoiceMetrics(self.cache)).settle(db, local.meter)
                        else:
                            await VoiceQuotaService(metrics=VoiceMetrics(self.cache)).recover(db, self.cache, call_id=call_id, user_id=owner)
                    except DBAPIError as exc:
                        if getattr(exc.orig, 'args', (None,))[0] == 1213:
                            # The session context exits and rolls back before retry.
                            # Other errors and any later hook failure must propagate.
                            raise _QuotaDeadlock() from exc
                        raise
                if local is not None and local.final_flush is not None:
                    await local.final_flush(db)
                stage_final_state(row, reason=reason, now=datetime.now(timezone.utc))
                if local is not None and local.on_finalize is not None:
                    await local.on_finalize(db, row)
                from backend.services.realtime_voice_card_service import stage_call_card
                await stage_call_card(db, row)
                if row.status == 'missed':
                    from backend.services.realtime_voice_summary_followup_service import stage_missed_followup
                    await stage_missed_followup(db, call=row)
                if row.connected_at is not None:
                    from backend.services.relationship_service import RelationshipService
                    # Production sessions disable autoflush. Growth re-reads this
                    # row with populate_existing, so persist the staged terminal
                    # state AND card sequence inside this same transaction first.
                    await db.flush()
                    await RelationshipService(db).add_voice_growth(owner, row.growth_eligible_seconds, call_id)
            else:
                self.metric('voice.state.terminal_replay', 1)
                from backend.services.realtime_voice_metric_service import stage_voice_metrics
                stage_voice_metrics(db,[('voice.state.terminal_replay',{},1)])
            if changed:stage_transition_metric(db,before,row.status,row.end_reason)
            from backend.services.realtime_voice_metric_service import stage_voice_metrics, _CALL_REASONS
            stage_voice_metrics(db, [('voice.finalizer.end_reason',
                {'reason':row.end_reason if row.end_reason in _CALL_REASONS else 'other'},1)] if changed else
                [('voice.finalizer.replay',{},1)])
            ended_at = row.ended_at
            final_state, final_reason = row.status, row.end_reason
            if admin_user:
                await log_operation(db, admin_user, 'voice_ops', 'force_end', f'语音通话 {call_id}',
                                    after_value=json.dumps(dict(changed=changed, end_reason=row.end_reason)), request=request)
            await db.commit()
            from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
            await flush_voice_metrics(db,self.metrics)
        if changed:
            emit_transition(before, final_state, final_reason)
        # DB ended rows are durable cleanup targets. Each action is independently
        # attempted; reconcile retries recent ended rows after cache recovery.
        cleaned = await self._cleanup_ended(leases, call_id, owner, ended_at)
        if local_voice_calls.get(call_id) is local:
            local_voice_calls.pop(call_id, None)
        return dict(call_id=call_id, changed=changed, cleanup_pending=not cleaned)

    async def _cleanup_ended(self, leases, call_id, owner, ended_at):
        failed = False
        from backend.services.realtime_voice_session_context_service import VoiceSessionContext
        async def clear_context():
            result = await VoiceSessionContext(cache=self.cache, session_factory=self.session_factory).cleanup(
                call_id=call_id, user_id=owner)
            if result.status != 'ok':
                raise RuntimeError('voice_context_cleanup_pending')
        actions = [('lease', lambda: leases.release(user_id=owner, call_id=call_id)),
                   ('control', lambda: self.cache.publish('voice:control:end', call_id)),
                   ('context', clear_context)]
        if ended_at is not None:
            actions.insert(0, ('cooldown', lambda: leases.after_end_commit(user_id=owner, call_id=call_id, ended_at=ended_at)))
        for phase, action in actions:
            try:
                await action()
            except Exception as exc:
                failed = True
                logger.warning('voice.end.cleanup_pending call_id=%s phase=%s exception_type=%s',
                               call_id, phase, type(exc).__name__)
        if failed:
            self.metric('voice.lease.cleanup_pending', 1)
        return not failed

    async def _hard_stop(self, db, *, confirm_text, admin_user, request=None):
        self.confirm(confirm_text)
        async with self.session_factory() as listing:
            targets = list((await listing.scalars(select(VoiceCall.call_id).where(VoiceCall.status.in_(ACTIVE)).order_by(VoiceCall.id))).all())
        # Each fixed target gets its own idempotent end. Do not roll back the
        # request session: that would expire its authenticated administrator.
        results, failures, failure_details = [], [], []
        for call_id in targets:
            try:
                result = await self.end_call(call_id=call_id, admin_user=admin_user, request=request)
                results.append(result)
                if result['cleanup_pending']:
                    failures.append(call_id)
                    failure_details.append(end_failure(call_id))
            except Exception as exc:
                failures.append(call_id)
                failure_details.append(end_failure(call_id, exc))
        await log_operation(db, admin_user, 'voice_ops', 'hard_stop', '结束固定进行中通话集合',
                            after_value=json.dumps(dict(targets=targets, failed=failures,
                                                        failure_details=failure_details)), request=request)
        await db.commit()
        self.metric('voice.ops_stop.hard_failed' if failures else 'voice.ops_stop.hard_success', 1)
        return dict(targets=targets, results=results, failed=failures, failure_details=failure_details)

    async def reconcile(self):
        try:
            return await self._reconcile()
        except Exception as exc:
            log_end_failure(None, exc, operation='reconcile')
            await self.metrics.emit_many([('voice.lease.reconcile',{'result':'failure'},1)])
            raise

    async def _reconcile(self):
        from backend.services.realtime_voice_lease_service import VoiceLeaseService, PRUNE_EXPIRED
        leases = VoiceLeaseService(self.cache, end_call=self.end_call)
        pruned = await self.cache.eval(PRUNE_EXPIRED, 2, leases.active_key, leases.owners_key)
        async with self.session_factory() as db:
            rows = (await db.scalars(select(VoiceCall).where(VoiceCall.status.in_(ACTIVE)))).all()
            # Current maximum lease TTL is 60 seconds. The owner gateway checks
            # durable end state each heartbeat; repeat control messages are safe.
            ended = (await db.scalars(select(VoiceCall).where(
                VoiceCall.status.in_(TERMINAL),
                VoiceCall.ended_at >= datetime.utcnow()-timedelta(seconds=180)))).all()
        failures = 0
        for row in ended:
            if not await self._cleanup_ended(leases, row.call_id, row.user_id, row.ended_at):failures += 1
        now = datetime.now(timezone.utc)
        corrected = 0
        for row in rows:
            config = row.config_snapshot.get('resolved_config', {})
            hard_limit = config.get('quota', {}).get('hard_limit_seconds', 3600)
            started = row.connected_at or row.created_at
            started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started
            hard_limit_reached = row.connected_at is not None and (now-started).total_seconds() >= hard_limit
            try:
                if hard_limit_reached or not await leases.owner_matches(user_id=row.user_id, call_id=row.call_id):
                    result=await self.end_call(call_id=row.call_id, user_id=row.user_id,
                                        reason='hard_limit' if hard_limit_reached else 'system_error')
                    corrected += 1
                    if isinstance(result,dict) and result.get("cleanup_pending"):failures += 1
            except Exception as exc:
                # A failed owner lookup is not evidence of an orphaned call.
                log_end_failure(row.call_id, exc, operation='reconcile')
                self.metric('voice.lease.reconcile_failed', 1)
                failures += 1
        self.metric('voice.lease.reconcile_corrected', corrected + pruned)
        await self.metrics.emit_many([('voice.lease.reconcile',{'result':'failure' if failures else 'success'},1),
            ('voice.lease.reconcile_corrected',{},corrected+pruned)])
        return corrected
