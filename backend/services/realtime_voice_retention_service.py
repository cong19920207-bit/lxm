"""Bounded retention batches with frozen time/candidate IDs and retryable commits."""
from datetime import datetime,timedelta
import asyncio
from sqlalchemy import select,or_
from backend.models.realtime_voice import (VoiceCallCreateIdempotency,VoiceCall,VoiceCallTurn,
    VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob,VoiceCrisisRecord)
from backend.models.user import User
from backend.constants.realtime_voice_config import get_default_voice_call_config
from backend.services.realtime_voice_state_service import lock_call


async def build_voice_retention_service():
    from backend.database import async_session_maker
    from backend.redis_client import get_redis
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    cache=await get_redis()
    return VoiceRetentionService(session_factory=async_session_maker,cache=cache,metrics=VoiceMetrics(cache))


class VoiceRetentionService:
    def __init__(self,*,session_factory,cache=None,metrics=None):
        self.factory,self.cache=session_factory,cache
        self.metrics=metrics

    async def _observe(self,events):
        if self.metrics is not None:await self.metrics.emit_many(events)

    async def delete_call(self,*,call_id,admin,request=None):
        from backend.services.realtime_voice_config_service import VoiceConfigError
        try:
            return await self._delete_call(call_id=call_id,admin=admin,request=request)
        except VoiceConfigError as exc:
            result='rejected' if exc.status_code in (403,422) else 'failure'
            await self._observe([('voice.retention.single_call_delete',{'result':result},1)])
            raise
        except Exception:
            await self._observe([('voice.retention.single_call_delete',{'result':'failure'},1),
                ('voice.retention.retry',{'reason':'delete_unavailable'},1)])
            raise

    async def _delete_call(self,*,call_id,admin,request=None):
        from backend.services.realtime_voice_config_service import VoiceConfigError
        from backend.utils.admin_auth import log_operation
        if admin.role!='super_admin':
            raise VoiceConfigError('VOICE_DELETE_FORBIDDEN','无权删除通话',status_code=403)
        if not isinstance(call_id,str) or not 1<=len(call_id)<=64:
            raise VoiceConfigError('VOICE_CALL_INVALID','通话标识无效',status_code=422)
        # A failed/aborted mutation still leaves an attempt audit, without body.
        async with self.factory() as db:
            if request is not None:request.state.voice_record_audit='failure'
            await log_operation(db,admin,'voice_calls','delete_attempt',call_id,request=request)
            await db.commit()
            if request is not None:request.state.voice_record_audit='success'
        if self.cache is None:raise ValueError('retention_cache_required')
        return await self._purge_call(call_id,datetime.utcnow(),admin=admin,request=request)

    async def purge_contents(self,*,now=None,after_id=0,limit=100):
        return await self._scan('contents',self._purge_contents,now=now,after_id=after_id,limit=limit)

    async def _scan(self,kind,operation,**kwargs):
        try:
            result=await operation(**kwargs)
        except Exception:
            await self._observe([('voice.retention.expiry_scan',{'kind':kind,'result':'failure'},1),
                ('voice.retention.retry',{'reason':kind+'_unavailable'},1)])
            raise
        await self._observe([('voice.retention.expiry_scan',{'kind':kind,'result':'success'},1)])
        return result

    async def _purge_contents(self,*,now=None,after_id=0,limit=100):
        """Fixed call-ID page; errors leave its cursor unadvanced for retry."""
        if self.cache is None:raise ValueError('retention_cache_required')
        now=datetime.utcnow() if now is None else now
        if type(after_id) is not int or after_id<0 or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('invalid_retention_page')
        async with self.factory() as db:
            candidates=list((await db.execute(select(VoiceCall.id,VoiceCall.call_id)
                .where(VoiceCall.id>after_id).order_by(VoiceCall.id).limit(limit))).all())
        reports=[]
        for candidate in candidates:
            reports.append(await self._purge_call(candidate.call_id,now))
        return dict(candidate_ids=[row.id for row in candidates],reports=reports,
            next_cursor=candidates[-1].id if candidates else None)

    @staticmethod
    def _due(expiry,now):
        return expiry is not None and expiry<=now

    @staticmethod
    def _job_days(call):
        snapshot=call.config_snapshot if isinstance(call.config_snapshot,dict) else {}
        config=snapshot.get('resolved_config',{});config=config if isinstance(config,dict) else {}
        retention=config.get('retention',{});retention=retention if isinstance(retention,dict) else {}
        default=get_default_voice_call_config({})['retention']['job_log_days']
        days=retention.get('job_log_days',default)
        return days if type(days) is int and days>0 else default

    async def _has_due_content(self,call_id,now):
        # Do not hold User/Call locks while an unrelated live memory writer
        # owns its job lock. A later expiry/new row is picked up on the next
        # cursor sweep; actual cleanup rechecks current state under locks.
        async with self.factory() as db:
            call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
            if call is None:return False
            if call.deletion_fence_at or call.deleted_at:return True
            if any(self._due(expiry,now) for expiry in (call.transcript_expires_at,
                call.generated_text_expires_at,call.reasoning_expires_at)):return True
            if await db.scalar(select(VoiceCallTurn.id).where(VoiceCallTurn.call_id==call_id,
                or_(VoiceCallTurn.effective_text_expires_at<=now,VoiceCallTurn.generated_text_expires_at<=now)).limit(1)) is not None:return True
            if await db.scalar(select(VoiceCrisisRecord.id).where(VoiceCrisisRecord.call_id==call_id,
                VoiceCrisisRecord.expires_at<=now).limit(1)) is not None:return True
            cutoff=now-timedelta(days=self._job_days(call))
            for model in (VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob):
                if await db.scalar(select(model.id).where(model.call_id==call_id,model.created_at<=cutoff).limit(1)) is not None:return True
            return False

    async def _purge_call(self,call_id,now,*,admin=None,request=None):
        if admin is None and not await self._has_due_content(call_id,now):return dict(call_id=call_id,changed=[],cache_keys=[])
        async with self.factory() as db:
            call=await lock_call(db,call_id)
            report=dict(call_id=call_id,changed=[],cache_keys=[])
            if call is None:
                if admin is not None:
                    from backend.services.realtime_voice_config_service import VoiceConfigError
                    raise VoiceConfigError('VOICE_CALL_NOT_FOUND','通话不存在',status_code=404)
                return report
            events=[]
            already_deleted=call.deleted_at is not None
            if admin is not None:
                from backend.services.realtime_voice_memory_service import VoiceMemoryService
                was_fenced=call.deletion_fence_at is not None
                cancelled=await VoiceMemoryService.stage_deletion_fence(db,call_id=call_id)
                events.append(('voice.retention.fence',{'result':'existing' if was_fenced else 'set'},1))
                if cancelled:events.append(('voice.retention.cancel',{'kind':'memory','reason':'deletion_fence'},cancelled))
            days=self._job_days(call)
            # Match memory deletion serialization: in-flight writes finish under
            # their job locks before any source content/snapshot is removed.
            job_groups=[]
            for model in (VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob):
                rows=list((await db.scalars(select(model).where(model.call_id==call_id)
                    .order_by(model.id).with_for_update().execution_options(populate_existing=True))).all())
                job_groups.append((model,rows))
            turns=list((await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id==call_id)
                .order_by(VoiceCallTurn.id).with_for_update().execution_options(populate_existing=True))).all())
            turn_expiry={turn.id:turn.effective_text_expires_at for turn in turns}
            call_expired=self._due(call.transcript_expires_at,now)
            fenced=bool(call.deletion_fence_at or call.deleted_at)
            cache_due=call_expired or fenced
            for turn in turns:
                fields=[]
                if fenced or call_expired or self._due(turn.effective_text_expires_at,now):
                    cache_due=True
                    for field in ('user_text_final','assistant_text_effective'):
                        if getattr(turn,field) is not None:setattr(turn,field,None);fields.append(field)
                    if turn.effective_text_cleared_at is None:turn.effective_text_cleared_at=now
                    turn.content_clear_reason='admin_deleted' if fenced else 'expired'
                if fenced or self._due(call.generated_text_expires_at,now) or self._due(turn.generated_text_expires_at,now):
                    if turn.assistant_text_generated is not None:turn.assistant_text_generated=None;fields.append('assistant_text_generated')
                    if turn.generated_text_cleared_at is None:turn.generated_text_cleared_at=now
                    if turn.content_clear_reason!='admin_deleted':turn.content_clear_reason='admin_deleted' if fenced else 'expired'
                if fields:report['changed'].append(dict(table=VoiceCallTurn.__tablename__,id=turn.id,fields=fields))
            reasoning_expired=not fenced and self._due(call.reasoning_expires_at,now) and call.summary_reasoning is not None
            if (fenced or self._due(call.reasoning_expires_at,now)) and call.summary_reasoning is not None:
                call.summary_reasoning=None
                report['changed'].append(dict(table=VoiceCall.__tablename__,id=call.id,fields=['summary_reasoning']))
            # Summary/emotions have an independent lifecycle; transcript expiry
            # must not remove them or touch successful memory/usage/growth rows.
            for model,rows in job_groups:
                for job in rows:
                    aged=job.created_at+timedelta(days=days)<=now
                    expired=fenced or call_expired or (isinstance(job,VoiceMemoryJob) and self._due(turn_expiry.get(job.turn_id),now))
                    if not (aged or expired):continue
                    fields=[]
                    if isinstance(job,VoiceMemoryJob) and job.extraction_snapshot is not None:
                        job.extraction_snapshot=None;fields.append('extraction_snapshot')
                    if isinstance(job,VoiceFollowupJob) and job.content:
                        job.content='';fields.append('content')
                    if job.status in {'pending','processing','failed'}:
                        job.status='cancelled';job.next_retry_at=job.lease_owner=job.lease_expires_at=None
                        reason='deletion_fence' if fenced else 'source_expired' if expired else 'retention_expired'
                        kind='memory' if model is VoiceMemoryJob else 'followup' if model is VoiceFollowupJob else 'postprocess'
                        events.append(('voice.retention.cancel',{'kind':kind,'reason':reason},1))
                        if model is VoiceFollowupJob:events.append(('voice.followup.cancel',{'reason':reason},1))
                        if isinstance(job,VoiceFollowupJob):job.cancel_reason=reason
                        else:job.fail_reason=reason
                        if isinstance(job,VoiceMemoryJob):
                            from backend.services.realtime_voice_memory_service import stage_memory_job_outcome
                            stage_memory_job_outcome(db,job,reason)
                            turn=next((turn for turn in turns if turn.id==job.turn_id),None)
                            if turn is not None and turn.memory_status!='success':turn.memory_status='cancelled'
                    if fields:report['changed'].append(dict(table=model.__tablename__,id=job.id,fields=fields))
            crisis_rows=list((await db.scalars(select(VoiceCrisisRecord).where(VoiceCrisisRecord.call_id==call_id)
                .order_by(VoiceCrisisRecord.id).with_for_update())).all())
            for row in crisis_rows:
                if not (fenced or self._due(row.expires_at,now)):continue
                fields=[]
                for field in ('content_plaintext','matched_keyword'):
                    if getattr(row,field) is not None:setattr(row,field,None);fields.append(field)
                if row.cleared_at is None:row.cleared_at=now
                if fields:report['changed'].append(dict(table=VoiceCrisisRecord.__tablename__,id=row.id,fields=fields))
            if admin is not None:
                fields=[]
                for field in ('sort_seq','call_summary','summary_reasoning','unfinished_topics','user_emotion','assistant_emotion'):
                    if getattr(call,field) is not None:setattr(call,field,None);fields.append(field)
                if call.deleted_at is None:call.deleted_at=now;call.deleted_by=admin.id
                if fields:report['changed'].append(dict(table=VoiceCall.__tablename__,id=call.id,fields=fields))
            if cache_due:
                key=f'voice:session_context:{call_id}'
                await asyncio.wait_for(self.cache.delete(key),timeout=1)
                report['cache_keys'].append(key)
            if admin is not None:
                from backend.utils.admin_auth import log_operation
                if request is not None:request.state.voice_record_audit='failure'
                await log_operation(db,admin,'voice_calls','delete',call_id,request=request)
                report['deleted_at']=call.deleted_at.isoformat()
            await db.commit()
            if admin is not None and request is not None:request.state.voice_record_audit='success'
            from backend.services.realtime_voice_metric_service import flush_voice_metrics
            await flush_voice_metrics(db,self.metrics)
            if reasoning_expired:events.append(('voice.summary.reasoning_expiry',{},1))
            if admin is not None:events.append(('voice.retention.single_call_delete',{'result':'repeated' if already_deleted else 'deleted'},1))
            await self._observe(events)
            return report

    async def purge_replays(self,*,now=None,after_id=0,limit=100):
        return await self._scan('replays',self._purge_replays,now=now,after_id=after_id,limit=limit)

    async def _purge_replays(self,*,now=None,after_id=0,limit=100):
        """Delete expired replay records, retaining the separate call metadata.

        Lock users before replay rows, matching create-call serialization. A
        create request may refresh a record after the candidate snapshot; the
        current locking read must therefore recheck the frozen deadline.
        Exceptions roll the whole batch back; retry with the same cursor.
        """
        now=datetime.utcnow() if now is None else now
        if type(after_id) is not int or after_id<0 or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('invalid_retention_page')
        async with self.factory() as db:
            candidates=list((await db.execute(select(VoiceCallCreateIdempotency.id,
                VoiceCallCreateIdempotency.user_id).where(VoiceCallCreateIdempotency.id>after_id,
                    VoiceCallCreateIdempotency.replay_expires_at<=now)
                .order_by(VoiceCallCreateIdempotency.id).limit(limit))).all())
            ids=[row.id for row in candidates]
            if not ids:return dict(candidate_ids=[],deleted_ids=[],next_cursor=None)
            await db.scalars(select(User.id).where(User.id.in_({row.user_id for row in candidates}))
                .order_by(User.id).with_for_update())
            rows=list((await db.scalars(select(VoiceCallCreateIdempotency)
                .where(VoiceCallCreateIdempotency.id.in_(ids))
                .order_by(VoiceCallCreateIdempotency.id).with_for_update()
                .execution_options(populate_existing=True))).all())
            deleted=[]
            for row in rows:
                if row.replay_expires_at<=now:
                    deleted.append(row.id)
                    await db.delete(row)
            await db.commit()
            return dict(candidate_ids=ids,deleted_ids=deleted,next_cursor=ids[-1])
