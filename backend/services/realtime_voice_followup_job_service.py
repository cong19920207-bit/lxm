"""Durable follow-up dispatch; composition supplies quota and idempotent counting.

No default quota policy is inferred here. count_sent must atomically deduplicate
its idempotency_key, using occurred_at for the original message's counting day.
quota_available must be a read-only check and must not upgrade the User lock.
Message delivery is the existing AgentMessage transaction, not an external send.
"""
from datetime import datetime,timedelta
import asyncio
import hashlib
import json
import re
from uuid import uuid4
from sqlalchemy import select,or_,and_
from backend.constants.realtime_voice_config import get_default_voice_call_config

from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.realtime_voice import VoiceCall,VoiceCallTurn,VoiceFollowupJob
from backend.models.user import User
from backend.services.realtime_voice_card_service import meaningful_user_text
from backend.services.timeline_seq_service import allocate_sort_seq

DEFAULT_MINIMUM_SECONDS=get_default_voice_call_config({})['followup']['summary_min_effective_seconds']
DEFAULT_JOB_RETENTION_DAYS=get_default_voice_call_config({})['retention']['job_log_days']


class VoiceFollowupJobService:
    def __init__(self,*,session_factory,quota_available,count_sent,lease_seconds,retry_seconds,topic_continued=None,clock=datetime.utcnow,metrics=None):
        if not all(type(v) is int and v>0 for v in (lease_seconds,retry_seconds)):
            raise ValueError('invalid_followup_worker_timing')
        self.factory=session_factory
        self.quota_available,self.count_sent=quota_available,count_sent
        self.topic_continued=topic_continued
        self.lease_seconds,self.retry_seconds=lease_seconds,retry_seconds
        self.clock=clock
        self.metrics=metrics

    async def _observe(self,event,dimensions):
        if self.metrics is not None:await self.metrics.emit_many([('voice.followup.'+event,dimensions,1)])

    async def poll(self):
        now=self.clock()
        retry_due=or_(VoiceFollowupJob.next_retry_at.is_(None),VoiceFollowupJob.next_retry_at<=now)
        lease_free=or_(VoiceFollowupJob.lease_expires_at.is_(None),VoiceFollowupJob.lease_expires_at<=now)
        async with self.factory() as db:
            ids=list((await db.scalars(select(VoiceFollowupJob.id).where(retry_due,or_(
                and_(VoiceFollowupJob.status=='pending',VoiceFollowupJob.due_at<=now),
                and_(VoiceFollowupJob.status=='processing',lease_free),
                and_(VoiceFollowupJob.status=='sent',VoiceFollowupJob.fail_reason=='count_pending',lease_free)
            )).order_by(VoiceFollowupJob.due_at,VoiceFollowupJob.id).limit(8))).all())
        return [await self.process(job_id=job_id) for job_id in ids]

    async def _locked(self,db,job_id):
        call_id=await db.scalar(select(VoiceFollowupJob.call_id).where(VoiceFollowupJob.id==job_id))
        if call_id is None:return None,None
        user_id=await db.scalar(select(VoiceCall.user_id).where(VoiceCall.call_id==call_id))
        if user_id is not None:
            # Read-only consumer needs a shared parent lock. User X locks would
            # block concurrent ConversationLog FK checks while holding the call,
            # and invert text's timeline→User(shared) ordering during insertion.
            await db.scalar(select(User.id).where(User.id==user_id).with_for_update(read=True))
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id)
            .with_for_update().execution_options(populate_existing=True))
        job=await db.scalar(select(VoiceFollowupJob).where(VoiceFollowupJob.id==job_id)
            .with_for_update().execution_options(populate_existing=True))
        return call,job

    @staticmethod
    def _release(job):
        job.lease_owner=job.lease_expires_at=None

    async def process(self,*,job_id):
        owner=uuid4().hex
        async with self.factory() as db:
            call,job=await self._locked(db,job_id)
            if job is None:return 'missing'
            accounting=job.status=='sent' and job.fail_reason=='count_pending'
            accounting=accounting or (job.status in {'pending','processing'} and job.agent_message_id is not None)
            if job.status not in {'pending','processing'} and not accounting:return job.status
            now=self.clock()
            if job.lease_owner and job.lease_expires_at and job.lease_expires_at>now:return 'busy'
            if job.next_retry_at and job.next_retry_at>now:return 'not_due'
            if not accounting and job.due_at>now:return 'not_due'
            if call is None:
                job.status='failed';job.fail_reason='source_missing';self._release(job)
                await db.commit();await self._observe('failure',{'reason':'source_missing'});return 'failed'
            recovered=job.status=='processing'
            if accounting:job.status='sent';job.fail_reason='count_pending'
            else:job.status='processing'
            job.attempt_count+=1;job.lease_owner=owner;job.lease_expires_at=now+timedelta(seconds=self.lease_seconds)
            job.next_retry_at=None
            await db.commit()
            if recovered:await self._observe('retry',{'reason':'lease_expired'})
        if accounting:return await self._account(job_id,owner)
        try:
            topic_result=await self._prepare_topic(job_id,owner)
            async with self.factory() as db:
                call,job=await self._locked(db,job_id)
                if job is None or job.status!='processing' or job.lease_owner!=owner:return 'stale'
                now=self.clock()
                if job.lease_expires_at<=now:raise RuntimeError('lease_expired')
                reason=await self._ineligible(db,call,job,now,topic_result=topic_result)
                if reason:return await self._cancel(db,job,reason)
                next_window=self._next_window(job,now)
                if next_window is not None:
                    if next_window>job.latest_due_at:return await self._cancel(db,job,'deadline_exceeded')
                    job.status='pending';job.next_retry_at=next_window;job.fail_reason=None;self._release(job)
                    await db.commit();await self._observe('schedule',{'result':'window_deferred'});return 'pending'
                allowed=await asyncio.wait_for(
                    self.quota_available(db=db,user_id=job.user_id,call=call,job=job),
                    timeout=max(0,(job.lease_expires_at-self.clock()).total_seconds()))
                if type(allowed) is not bool:raise RuntimeError('quota_check_unavailable')
                if not allowed:return await self._cancel(db,job,'quota_unavailable')
                # A slow dependency cannot carry a job across its lease/window/deadline.
                now=self.clock()
                if job.lease_expires_at<=now:raise RuntimeError('lease_expired')
                reason=await self._ineligible(db,call,job,now,topic_result=topic_result)
                if reason:return await self._cancel(db,job,reason)
                if self._next_window(job,now) is not None:raise RuntimeError('window_changed')
                reason=await self._stage_message(db,call,job,now,topic_result=topic_result)
                if reason:return await self._cancel(db,job,reason)
                await db.commit()
                await self._observe('send',{'result':'sent'})
        except ValueError:
            return await self._failure(job_id,owner,'invalid_snapshot',retryable=False)
        except Exception:
            return await self._failure(job_id,owner,'dispatch_unavailable',retryable=True)
        return await self._account(job_id,owner)

    async def _ineligible(self,db,call,job,now,*,lock_chat=False,topic_result=None):
        if call is None or call.user_id!=job.user_id:return 'source_missing'
        if call.deleted_at or call.deletion_fence_at:return 'source_deleted'
        if call.transcript_expires_at and call.transcript_expires_at<=now:return 'source_expired'
        if now>job.latest_due_at:return 'deadline_exceeded'
        if not isinstance(job.content,str) or not job.content.strip():return 'content_unavailable'
        if job.content_type=='missed_explanation':
            if call.status!='missed' or call.connected_at is not None:return 'source_ineligible'
        else:
            snapshot=call.config_snapshot if isinstance(call.config_snapshot,dict) else {}
            config=snapshot.get('resolved_config');config=config if isinstance(config,dict) else {}
            followup=config.get('followup');followup=followup if isinstance(followup,dict) else {}
            minimum=followup.get('summary_min_effective_seconds',DEFAULT_MINIMUM_SECONDS)
            if type(minimum) is not int or minimum<1:minimum=DEFAULT_MINIMUM_SECONDS
            if call.status!='ended' or call.connected_at is None or call.duration_seconds<minimum or call.summary_status!='ready':
                return 'source_ineligible'
            texts=await db.scalars(select(VoiceCallTurn.user_text_final).where(
                VoiceCallTurn.call_id==call.call_id,VoiceCallTurn.turn_status.in_(['finalized','interrupted']),
                VoiceCallTurn.effective_text_evidence!='none',VoiceCallTurn.assistant_text_effective.is_not(None),
                VoiceCallTurn.assistant_text_effective!='',VoiceCallTurn.effective_text_cleared_at.is_(None),
                VoiceCallTurn.effective_text_expires_at>now,VoiceCallTurn.user_content_safety_status=='passed',
                VoiceCallTurn.assistant_content_safety_status=='passed',VoiceCallTurn.user_crisis_status=='passed',
                VoiceCallTurn.assistant_crisis_status=='passed'))
            if not any(meaningful_user_text(text) for text in texts):return 'source_ineligible'
        if call.ended_at is None:return 'source_ineligible'
        chat_query=select(ConversationLog.id).where(ConversationLog.user_id==job.user_id,
            ConversationLog.role=='user',ConversationLog.created_at>=call.ended_at).limit(1)
        # Acquire timeline order before locking chat ranges: enqueue_send locks
        # that sequence before inserting text. Reversing the order deadlocks.
        chatted=await db.scalar(chat_query.with_for_update() if lock_chat else chat_query)
        if chatted is not None:return 'user_chatted'
        # Outside the frozen window, defer before requiring a model result.
        # Recheck the topic on the next eligible attempt, when it is current.
        topic_inputs=(await self._topic_inputs(db,call,job,now,locked=True)
            if self._next_window(job,now) is None else None)
        if topic_inputs is not None:
            if topic_result is None or topic_result[0]!=self._topic_digest(topic_inputs):
                raise RuntimeError('topic_inputs_changed')
            if topic_result[1]:return 'topic_continued'
        sent=await db.scalar(select(VoiceFollowupJob.id).where(VoiceFollowupJob.call_id==job.call_id,
            VoiceFollowupJob.id!=job.id,VoiceFollowupJob.agent_message_id.is_not(None)).limit(1).with_for_update())
        if sent is not None:return 'already_sent'
        return None

    @staticmethod
    def _topic_digest(inputs):
        return hashlib.sha256(json.dumps(inputs,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

    async def _topic_inputs(self,db,call,job,now,*,locked=False):
        query=(select(VoiceCallTurn.user_text_final)
            .join(VoiceCall,VoiceCall.call_id==VoiceCallTurn.call_id).where(
                VoiceCall.user_id==job.user_id,VoiceCall.call_id!=call.call_id,
                VoiceCall.connected_at>=call.ended_at,VoiceCall.deleted_at.is_(None),VoiceCall.deletion_fence_at.is_(None),
                or_(VoiceCall.transcript_expires_at.is_(None),VoiceCall.transcript_expires_at>now),
                VoiceCallTurn.user_text_final.is_not(None),VoiceCallTurn.user_text_final!='',
                VoiceCallTurn.effective_text_cleared_at.is_(None),VoiceCallTurn.effective_text_expires_at>now,
                VoiceCallTurn.user_content_safety_status=='passed',VoiceCallTurn.user_crisis_status=='passed')
            .order_by(VoiceCall.connected_at,VoiceCallTurn.turn_index))
        later_texts=list((await db.scalars(query.with_for_update(read=True) if locked else query)).all())
        if not later_texts:return None
        return dict(user_id=job.user_id,source_call_id=call.call_id,content_type=job.content_type,
            followup_content=job.content,unfinished_topics=call.unfinished_topics or [],
            later_user_texts=later_texts,config_snapshot=call.config_snapshot)

    async def _prepare_topic(self,job_id,owner):
        # Plain snapshot reads finish before awaiting the external model.
        async with self.factory() as db:
            job=await db.get(VoiceFollowupJob,job_id)
            if job is None or job.status!='processing' or job.lease_owner!=owner:return None
            call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==job.call_id))
            now=self.clock()
            if (call is None or call.ended_at is None or call.deleted_at or call.deletion_fence_at
                    or (call.transcript_expires_at and call.transcript_expires_at<=now)
                    or now>job.latest_due_at or self._next_window(job,now) is not None):return None
            inputs=await self._topic_inputs(db,call,job,now)
            lease_until=job.lease_expires_at
        if inputs is None:return None
        if self.topic_continued is None:raise RuntimeError('topic_check_unavailable')
        continued=await asyncio.wait_for(self.topic_continued(**inputs),
            timeout=max(0,(lease_until-self.clock()).total_seconds()))
        if type(continued) is not bool:raise RuntimeError('topic_check_unavailable')
        return self._topic_digest(inputs),continued

    @staticmethod
    def _next_window(job,now):
        if job.timezone_snapshot!='Asia/Shanghai' or not isinstance(job.allowed_window_snapshot,list) or not job.allowed_window_snapshot:
            raise ValueError('invalid_window_snapshot')
        local=now+timedelta(hours=8);future=[]
        for window in job.allowed_window_snapshot:
            if not isinstance(window,dict):raise ValueError('invalid_window_snapshot')
            bounds=[]
            for key in ('start','end'):
                text=window.get(key)
                if not isinstance(text,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',text):
                    raise ValueError('invalid_window_snapshot')
                hour,minute=map(int,text.split(':'));bounds.append(local.replace(hour=hour,minute=minute,second=0,microsecond=0))
            start,end=bounds
            if start>=end:raise ValueError('invalid_window_snapshot')
            if start<=local<end:return None
            future.append((start if local<start else start+timedelta(days=1))-timedelta(hours=8))
        return min(future)

    async def _stage_message(self,db,call,job,now,*,topic_result=None):
        sequence=(await allocate_sort_seq(job.user_id,1,db))[0]
        now=self.clock()
        reason=await self._ineligible(db,call,job,now,lock_chat=True,topic_result=topic_result)
        if reason:return reason
        now=self.clock()
        if now>job.latest_due_at:return 'deadline_exceeded'
        if call.transcript_expires_at and call.transcript_expires_at<=now:return 'source_expired'
        if job.lease_expires_at<=now:raise RuntimeError('lease_expired')
        if self._next_window(job,now) is not None:raise RuntimeError('window_changed')
        message=AgentMessage(user_id=job.user_id,trigger_type='VOICE_FOLLOWUP',content=job.content,
            action_score=0,sort_seq=sequence,created_at=now)
        db.add(message);await db.flush()
        job.agent_message_id=message.id;job.status='sent';job.cancel_reason=None
        job.fail_reason='count_pending';job.next_retry_at=None

    async def _cancel(self,db,job,reason):
        job.status='cancelled';job.cancel_reason=reason;job.fail_reason=None;job.next_retry_at=None
        self._release(job);await db.commit();await self._observe('cancel',{'reason':reason});return 'cancelled'

    async def _failure(self,job_id,owner,reason,*,retryable):
        async with self.factory() as db:
            _,job=await self._locked(db,job_id)
            if job is None or job.status!='processing' or job.lease_owner!=owner:return 'stale'
            job.status='pending' if retryable else 'failed';job.fail_reason=reason
            job.next_retry_at=self.clock()+timedelta(seconds=self.retry_seconds) if retryable else None
            self._release(job);await db.commit()
            await self._observe('retry' if retryable else 'failure',{'reason':reason})
            return job.status

    async def _account(self,job_id,owner):
        async with self.factory() as db:
            call,job=await self._locked(db,job_id)
            if job is None or job.status!='sent' or job.lease_owner!=owner:return 'stale'
            message=await db.get(AgentMessage,job.agent_message_id)
            if message is None or message.user_id!=job.user_id:
                job.fail_reason='message_missing';self._release(job);await db.commit()
                await self._observe('failure',{'reason':'message_missing'});return 'sent'
            snapshot=call.config_snapshot if call is not None and isinstance(call.config_snapshot,dict) else {}
            config=snapshot.get('resolved_config');config=config if isinstance(config,dict) else {}
            retention=config.get('retention');retention=retention if isinstance(retention,dict) else {}
            days=retention.get('job_log_days',DEFAULT_JOB_RETENTION_DAYS)
            if type(days) is not int or days<1:days=DEFAULT_JOB_RETENTION_DAYS
            args=dict(user_id=job.user_id,message_id=message.id,occurred_at=message.created_at,
                dedupe_ttl_seconds=days*86400,
                idempotency_key=f'voice-followup:{job.id}:{message.id}')
        try:
            await self.count_sent(**args)
            success=True
        except Exception:
            success=False
        async with self.factory() as db:
            _,job=await self._locked(db,job_id)
            if job is None or job.status!='sent' or job.lease_owner!=owner:return 'stale'
            job.fail_reason=None if success else 'count_pending'
            job.next_retry_at=None if success else self.clock()+timedelta(seconds=self.retry_seconds)
            self._release(job);await db.commit()
            if not success:await self._observe('retry',{'reason':'count_pending'})
        return 'sent'
