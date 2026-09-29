"""Durable CALL-SUM ownership and voice-call-only result transaction.

Composition supplies the frozen DeepSeek model, safety, compensation and follow-up persistence.
"""
import asyncio
import math
import time
from dataclasses import replace
from datetime import datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import select,update,or_
from backend.models.realtime_voice import VoiceCall,VoiceCallTurn,VoicePostprocessJob
from backend.services.realtime_voice_state_service import lock_call
from backend.services.realtime_voice_card_service import summary_eligible,meaningful_user_text
from backend.services.realtime_voice_summary_service import generate_summary,safe_closed_turn

from backend.services.realtime_voice_safety_service import observe_worker_safety

JOB_TYPE='call_summary'


class VoiceSummaryJobService:
    def __init__(self,*,session_factory,model,permits,prepare,timeout_seconds,stage_followup=None,model_factory=None,metrics=None,safety_gate=None):
        if type(timeout_seconds) not in {int,float} or not math.isfinite(timeout_seconds) or timeout_seconds<=0:
            raise ValueError('invalid_summary_timeout')
        self.factory=session_factory
        self.model,self.permits,self.prepare=model,permits,prepare
        self.timeout=timeout_seconds
        self.stage_followup=stage_followup
        self.model_factory=model_factory
        self.metrics=metrics
        self.safety_gate=safety_gate

    async def _observe(self, outcome, reason=None):
        if self.metrics is None:return
        events=[('voice.summary.result', {'result':outcome}, 1)]
        if outcome in {'ready','not_applicable','failed'}:
            events.append(('voice.summary.card_update', {'status':outcome}, 1))
        elif reason in {'source_expired','source_unavailable'}:
            events.append(('voice.summary.card_update', {'status':'failed'}, 1))
        events.extend(('voice.timeline.update', dimensions.copy(), amount)
            for name,dimensions,amount in list(events) if name=='voice.summary.card_update')
        if outcome=='not_applicable':
            events.append(('voice.summary.eligible', {'result':'ineligible'}, 1))
        if outcome=='failed':events.append(('voice.summary.failure', {'reason':reason}, 1))
        if outcome in {'failed','not_applicable'} or reason in {'source_expired','source_unavailable'}:
            events.append(('voice.summary.static_fallback', {'reason':reason or 'ineligible'}, 1))
        await self.metrics.emit_many(events)

    async def poll(self):
        """Bounded recovery scan; actual scheduling belongs to composition."""
        async with self.factory() as db:
            exists=select(VoicePostprocessJob.id).where(VoicePostprocessJob.call_id==VoiceCall.call_id,
                VoicePostprocessJob.job_type==JOB_TYPE).exists()
            missing=list((await db.scalars(select(VoiceCall.call_id).where(VoiceCall.status=='ended',
                VoiceCall.sort_seq.is_not(None),VoiceCall.deletion_fence_at.is_(None),
                VoiceCall.deleted_at.is_(None),~exists).order_by(VoiceCall.id).limit(8))).all())
        for call_id in missing:await self.enqueue(call_id=call_id)
        async with self.factory() as db:
            calls=list((await db.scalars(select(VoicePostprocessJob.call_id).where(
                VoicePostprocessJob.job_type==JOB_TYPE,or_(VoicePostprocessJob.status=='pending',
                    (VoicePostprocessJob.status=='processing') & or_(VoicePostprocessJob.lease_expires_at.is_(None),
                        VoicePostprocessJob.lease_expires_at<=datetime.utcnow())))
                .order_by(VoicePostprocessJob.id).limit(8))).all())
        return await asyncio.gather(*(self.process(call_id=call_id) for call_id in calls),return_exceptions=True)

    async def enqueue(self,*,call_id):
        async with self.factory() as db:
            call=await lock_call(db,call_id)
            if call is None or call.status not in {'ended','missed','failed','cancelled'}:return 'not_ended'
            if call.deletion_fence_at or call.deleted_at:return 'cancelled'
            job=await db.scalar(select(VoicePostprocessJob).where(
                VoicePostprocessJob.call_id==call_id,VoicePostprocessJob.job_type==JOB_TYPE).with_for_update())
            if job is None:
                job=VoicePostprocessJob(call_id=call_id,job_type=JOB_TYPE,status='pending')
                db.add(job)
            await db.commit()
            return job.status

    @observe_worker_safety
    async def process(self,*,call_id):
        # Finalizer already flushed in its terminal transaction. This dependency
        # checks durable missing memory jobs, without re-running existing ones.
        await self.prepare(call_id=call_id)
        owner=uuid4().hex
        async with self.factory() as db:
            call=await lock_call(db,call_id)
            if call is None:return 'missing'
            job=await db.scalar(select(VoicePostprocessJob).where(
                VoicePostprocessJob.call_id==call_id,VoicePostprocessJob.job_type==JOB_TYPE).with_for_update())
            if job is None:return 'idle'
            if call.deletion_fence_at or call.deleted_at:
                changed=job.status!='cancelled'
                job.status='cancelled';self._release(job);await db.commit()
                if changed:await self._observe('cancelled','deleted')
                return 'cancelled'
            now=datetime.utcnow()
            if job.status=='processing' and (job.lease_expires_at is None or job.lease_expires_at<=now):
                job.status='failed';job.fail_reason='lease_expired';call.summary_status='failed'
                self._release(job);await db.commit();await self._observe('failed','lease_expired');return 'failed'
            if job.status!='pending':return job.status
            if call.status not in {'ended','missed','failed','cancelled'}:return 'not_ended'
            if call.status!='ended' or not await summary_eligible(db,call):
                call.summary_status='not_applicable';job.status='success';self._release(job)
                await db.commit();await self._observe('not_applicable');return 'not_applicable'
            if call.sort_seq is None:return 'card_missing'
            turns=(await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id==call_id)
                .order_by(VoiceCallTurn.turn_index))).all()
            turns=[turn for turn in turns if safe_closed_turn(turn) and turn.effective_text_expires_at
                   and turn.effective_text_expires_at>now]
            if not turns or (call.transcript_expires_at and call.transcript_expires_at<=now):
                job.status='cancelled';job.fail_reason='source_expired';call.summary_status='failed'
                self._release(job);await db.commit();await self._observe('cancelled','source_expired');return 'cancelled'
            if not any(meaningful_user_text(turn.user_text_final) for turn in turns):
                call.summary_status='not_applicable';job.status='success';self._release(job)
                await db.commit();await self._observe('not_applicable');return 'not_applicable'
            source_expiry=min([turn.effective_text_expires_at for turn in turns]+
                              ([call.transcript_expires_at] if call.transcript_expires_at else []))
            fields=('turn_index','user_text_final','assistant_text_effective','turn_status','effective_text_evidence',
                    'user_content_safety_status','assistant_content_safety_status','user_crisis_status','assistant_crisis_status')
            inputs=[SimpleNamespace(**{key:getattr(turn,key) for key in fields}) for turn in turns]
            seconds=call.duration_seconds
            from backend.services.realtime_voice_summary_runtime import summary_settings
            try:
                _,prompt_template=summary_settings(call.config_snapshot)
                selected_model=self.model_factory(call.config_snapshot) if self.model_factory else self.model
            except (ValueError,TypeError,AttributeError):
                job.status='failed';job.fail_reason='summary_configuration_invalid';call.summary_status='failed'
                self._release(job);await db.commit();await self._observe('failed','summary_configuration_invalid');return 'failed'
            job.status='processing';job.attempt_count+=1;job.lease_owner=owner
            job.lease_expires_at=now+timedelta(seconds=self.timeout+1)
            job.fail_reason=None
            await db.commit()
        if self.metrics is not None:
            await self.metrics.emit_many([('voice.summary.eligible', {'result':'eligible'}, 1)])
        async def permits(value):return await self.permits(call_id=call_id,text=value)
        started=time.monotonic()
        try:
            result=await asyncio.wait_for(generate_summary(duration_seconds=seconds,turns=inputs,
                model=selected_model,permits=permits,prompt_template=prompt_template,check_reasoning=False),timeout=self.timeout)
        except ValueError:
            return await self._failure(call_id,owner,'invalid_or_rejected_output')
        except Exception:
            return await self._failure(call_id,owner,'model_unavailable')
        if result.reasoning:
            # Optional tuning data must not consume the public result on timeout.
            try:
                allowed=await asyncio.wait_for(permits(result.reasoning),
                    timeout=max(0,self.timeout-(time.monotonic()-started)))
            except Exception:
                allowed=False
            if not allowed:result=replace(result,reasoning=None)
        try:
            async with self.factory() as db:
                call=await lock_call(db,call_id)
                job=await self._owned_job(db,call_id,owner)
                if call is None or job is None:return 'stale'
                if (call.deletion_fence_at or call.deleted_at or source_expiry<=datetime.utcnow()
                        or (call.transcript_expires_at and call.transcript_expires_at<=datetime.utcnow())):
                    job.status='cancelled';job.fail_reason='source_unavailable';self._release(job)
                    if not call.deletion_fence_at and not call.deleted_at:call.summary_status='failed'
                    deleted=bool(call.deletion_fence_at or call.deleted_at)
                    await db.commit();await self._observe('cancelled','deleted' if deleted else 'source_unavailable');return 'cancelled'
                if result.followup:
                    if self.stage_followup is None:raise RuntimeError('followup_storage_required')
                    await self.stage_followup(db,call=call,candidate=result.followup)
                for key,value in result.call_fields().items():setattr(call,key,value)
                retention=call.config_snapshot.get('resolved_config',{}).get('retention',{})
                days=retention.get('reasoning_days',call.generated_retention_days)
                reasoning_expiry=call.ended_at+timedelta(days=days)
                call.summary_reasoning=result.reasoning if reasoning_expiry>datetime.utcnow() else None
                call.reasoning_expires_at=reasoning_expiry
                call.transcript_expires_at=source_expiry
                call.summary_status='ready';job.status='success';self._release(job)
                await db.commit()
                from backend.services.realtime_voice_metric_service import flush_voice_metrics
                await flush_voice_metrics(db,self.metrics)
                await self._observe('ready')
                return 'ready'
        except Exception:
            return await self._failure(call_id,owner,'result_commit_failed')

    @staticmethod
    def _release(job):
        job.lease_owner=job.lease_expires_at=job.next_retry_at=None

    async def _owned_job(self,db,call_id,owner):
        return await db.scalar(select(VoicePostprocessJob).where(VoicePostprocessJob.call_id==call_id,
            VoicePostprocessJob.job_type==JOB_TYPE,VoicePostprocessJob.status=='processing',
            VoicePostprocessJob.lease_owner==owner,VoicePostprocessJob.lease_expires_at>datetime.utcnow()).with_for_update())

    async def _failure(self,call_id,owner,reason):
        async with self.factory() as db:
            call=await lock_call(db,call_id)
            job=await self._owned_job(db,call_id,owner)
            if call is None or job is None:return 'stale'
            cancelled=bool(call.deletion_fence_at or call.deleted_at)
            job.status='cancelled' if cancelled else 'failed';job.fail_reason=reason
            if not cancelled:call.summary_status='failed'
            self._release(job);await db.commit()
            await self._observe(job.status, 'deleted' if cancelled else reason)
            return job.status

    async def purge_reasoning(self):
        async with self.factory() as db:
            result=await db.execute(update(VoiceCall).where(VoiceCall.reasoning_expires_at<=datetime.utcnow(),
                VoiceCall.summary_reasoning.is_not(None)).values(summary_reasoning=None))
            await db.commit()
            if self.metrics is not None:
                await self.metrics.emit_many([('voice.summary.reasoning_expiry', {}, result.rowcount)])
            return result.rowcount


async def read_summary_reasoning(db,*,call_id,admin,request=None):
    """Private tuning projection for the forthcoming record-detail route."""
    from backend.services.realtime_voice_config_service import VoiceConfigError
    from backend.utils.admin_auth import log_operation
    if admin.role!='super_admin':
        raise VoiceConfigError('VOICE_REASONING_FORBIDDEN','无权查看调优信息',status_code=403)
    call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id,
        VoiceCall.deletion_fence_at.is_(None),VoiceCall.deleted_at.is_(None)))
    if call is None:raise VoiceConfigError('VOICE_CALL_NOT_FOUND','通话不存在',status_code=404)
    readable=call.reasoning_expires_at is not None and call.reasoning_expires_at>datetime.utcnow()
    result=dict(call_id=call_id,reasoning=call.summary_reasoning if readable else None)
    await log_operation(db,admin,'voice_call','view_reasoning',call_id,request=request)
    await db.commit()
    return result


async def retry_summary_job(db,*,job_id,admin,request=None):
    """One explicitly audited attempt; does not create an automatic retry policy."""
    import json
    from backend.services.realtime_voice_config_service import VoiceConfigError
    from backend.utils.admin_auth import log_operation
    if admin.role not in {'super_admin','tech_ops'}:
        raise VoiceConfigError('VOICE_JOB_FORBIDDEN','无权补跑任务',status_code=403)
    call_id=await db.scalar(select(VoicePostprocessJob.call_id).where(
        VoicePostprocessJob.id==job_id,VoicePostprocessJob.job_type==JOB_TYPE))
    if call_id is None:raise VoiceConfigError('VOICE_JOB_NOT_FOUND','任务不存在',status_code=404)
    call=await lock_call(db,call_id)
    job=await db.scalar(select(VoicePostprocessJob).where(VoicePostprocessJob.id==job_id).with_for_update()
        .execution_options(populate_existing=True))
    now=datetime.utcnow()
    source_exists=await db.scalar(select(VoiceCallTurn.id).where(VoiceCallTurn.call_id==call_id,
        VoiceCallTurn.effective_text_expires_at>now).limit(1))
    if (call is None or job is None or call.status!='ended' or call.deletion_fence_at or call.deleted_at
            or source_exists is None or (call.transcript_expires_at and call.transcript_expires_at<=now)
            or job.status!='failed' or job.fail_reason not in {
                'lease_expired','invalid_or_rejected_output','model_unavailable','result_commit_failed'}):
        raise VoiceConfigError('VOICE_JOB_NOT_RETRYABLE','该任务当前不能补跑',status_code=409)
    before=dict(status=job.status,attempt_count=job.attempt_count,fail_reason=job.fail_reason)
    job.status='pending';call.summary_status='pending';VoiceSummaryJobService._release(job)
    result=dict(job_id=job.id,job_type=JOB_TYPE,status='pending',attempt_count=job.attempt_count)
    if request is not None:request.state.voice_record_audit='failure'
    await log_operation(db,admin,'voice_job','retry',call_id,
        before_value=json.dumps(before),after_value=json.dumps(result),request=request)
    await db.commit()
    if request is not None:request.state.voice_record_audit='success'
    return result
