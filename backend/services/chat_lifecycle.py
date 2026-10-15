"""SQL-authoritative chat admission and terminal protocol (STEP002 / STEP014).

All writers serialize at chat_user_state before reading a generation. Read APIs
never arbitrate or schedule. Redis and observer notifications are only hints.
"""
from __future__ import annotations
import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import uuid

from sqlalchemy import select, text, update, delete, or_
from sqlalchemy.dialects.mysql import insert
from backend.database import async_session_maker
from backend.models.chat_lifecycle import (ChatUserState, ChatGeneration, ChatSubmission,
    ChatSubmissionMessage, ChatMessageState, ChatGenerationMessage, ChatResendQuota, ChatLifecycleEffect)
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.services.chat_timing import TIMING

log=logging.getLogger(__name__)
REASONS={'llm_failed','content_blocked','prompt_budget_exceeded','prompt_budget_unverified',
    'deadline_exceeded','generation_superseded','execution_lost','commit_unknown',
    'deadline_unverified','storage_unavailable','legacy_record','legacy_pending','id_conflict','expired'}

class AdmissionError(Exception):
    def __init__(self, code, status=None): self.code,self.status=code,status

class LostOwnership(Exception): pass

@dataclass(frozen=True)
class Execution:
    user_id: int
    generation_id: str
    owner: str
    epoch: int
    deadline_at: datetime
    reconcile_until: datetime

@dataclass(frozen=True)
class Admission:
    generation_id: str
    request_id: str
    operation: str
    repeated: bool
    old_generation_id: str|None=None


def encode_request_id(value): return 'b64.'+base64.urlsafe_b64encode(value.encode('utf-8')).decode().rstrip('=')

def decode_request_id(operation, value):
    if operation not in ('send','resend') or not value.startswith('b64.'): raise ValueError('invalid_submission_identity')
    raw=value[4:]
    try:
        decoded=base64.b64decode(raw+'='*((-len(raw))%4),altchars=b'-_',validate=True).decode('utf-8')
        if encode_request_id(decoded)!=value or len(decoded)>(64 if operation=='send' else 128): raise ValueError()
        return decoded
    except (ValueError,UnicodeError): raise ValueError('invalid_submission_identity') from None

def fingerprint(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).digest()
def send_fingerprint(content): return fingerprint({'operation':'send','content':content.strip()})
def iso(value): return value.isoformat(timespec='microseconds')+'Z' if value else None
async def db_now(db): return (await db.execute(text('SELECT UTC_TIMESTAMP(6)'))).scalar_one()

async def lock_user(db,user_id):
    from backend.services.memory_business_guard import guard_business_write
    await guard_business_write(db)
    now=await db_now(db)
    await db.execute(insert(ChatUserState).values(user_id=user_id,state_revision=0,created_at=now,updated_at=now)
        .on_duplicate_key_update(user_id=user_id))
    return (await db.execute(select(ChatUserState).where(ChatUserState.user_id==user_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one()

async def locked_generation(db,user_id,generation_id):
    return (await db.execute(select(ChatGeneration).where(ChatGeneration.user_id==user_id,
        ChatGeneration.generation_id==generation_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()

async def find_submission(db,user_id,operation,request_id,*,current=False):
    query=select(ChatSubmission).where(ChatSubmission.user_id==user_id,
        ChatSubmission.operation==operation,ChatSubmission.request_id==request_id.encode('utf-8'))
    if current:query=query.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(query)).scalar_one_or_none()

async def effective_generation(db,sub,*,current=False):
    ids=select(ChatSubmissionMessage.conversation_id).where(ChatSubmissionMessage.user_id==sub.user_id,
        ChatSubmissionMessage.submission_id==sub.id)
    if current:
        # The runtime-fence pre-read may already have established an RR snapshot.
        # Both association levels must read after the authoritative user lock.
        ids=list((await db.execute(ids.with_for_update())).scalars())
    query=select(ChatMessageState.effective_generation_id).where(ChatMessageState.user_id==sub.user_id,
        ChatMessageState.conversation_id.in_(ids)).order_by(ChatMessageState.state_revision.desc()).limit(1)
    if current:query=query.with_for_update()
    effective=(await db.execute(query)).scalar_one_or_none()
    return effective or sub.accepted_generation_id

async def duplicate(db,user_id,operation,request_id,content=None,*,current=False):
    sub=await find_submission(db,user_id,operation,request_id,current=current)
    if sub is None:return None
    if sub.record_state!='active':raise AdmissionError(10110)
    if operation=='send' and sub.fingerprint!=send_fingerprint(content):raise AdmissionError(10109)
    return Admission(await effective_generation(db,sub,current=current),request_id,operation,True)

async def _message_terminal(db,gen,revision,now,state,reason):
    rows=list((await db.execute(select(ChatMessageState).where(ChatMessageState.user_id==gen.user_id,
        ChatMessageState.effective_generation_id==gen.generation_id).order_by(ChatMessageState.conversation_id).with_for_update().execution_options(populate_existing=True))).scalars())
    for ms in rows:
        ms.processing_state,ms.reason,ms.state_revision,ms.status_changed_at=state,reason,revision,now
        if state in ('success','failed'):
            row=await db.get(ConversationLog,ms.conversation_id,with_for_update=True,populate_existing=True)
            if state=='success':row.delivery_status='delivered';row.round_id=gen.round_id
            else:row.delivery_status='failed_blocked' if reason=='content_blocked' else ('failed_timeout' if reason=='deadline_exceeded' else 'failed_error')

async def _terminal(db,us,gen,state,reason,now):
    if gen.state!='pending':return False
    us.state_revision+=1
    gen.state,gen.reason,gen.phase=state,reason,'terminal'
    gen.state_revision,gen.terminal_at=us.state_revision,now
    gen.dispatch_state='done';gen.lease_owner=None;gen.lease_until=None
    await _message_terminal(db,gen,us.state_revision,now,state,reason)
    return True

async def admit(db,user_id,operation,request_id,*,content=None,persona_risk_flag=False,persona_risk_type=None,channel='h5'):
    """One transaction: idempotency, SQL quota, user row, handover and outbox."""
    from backend.services.chat_service import fetch_open_window_user_rows, _should_block_new_send, open_window_has_bang
    from backend.services.timeline_seq_service import allocate_sort_seq
    client_key_present=request_id is not None
    request_id=request_id if client_key_present else str(uuid.uuid4())
    try:
        us=await lock_user(db,user_id)
        repeated=await duplicate(db,user_id,operation,request_id,content,current=True)
        if repeated:
            await db.rollback()
            return repeated
        old=await locked_generation(db,user_id,us.current_generation_id) if us.current_generation_id else None
        # Unknown commit cannot grant new execution, even with another request ID.
        if old and old.state=='pending' and old.phase in ('commit_prepared','commit_unknown','reconcile_exhausted'):
            raise AdmissionError(10110)
        rel=(await db.execute(select(Relationship).where(Relationship.user_id==user_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        rows=await fetch_open_window_user_rows(db,user_id,current=True)
        now=await db_now(db)
        if operation=='send':
            if _should_block_new_send(rows):raise AdmissionError(10104)
            row=ConversationLog(user_id=user_id,role='user',content=content.strip(),memory_injected=None,
                persona_risk_flag=persona_risk_flag,persona_risk_type=persona_risk_type,
                delivery_status='pending_llm',skipped_in_prompt=False)
            rows.append(row)
        else:
            if not open_window_has_bang(rows):raise AdmissionError(10107)
            anchor=min(r.sort_seq for r in rows)
            quota=await db.get(ChatResendQuota,(user_id,anchor),with_for_update=True,populate_existing=True)
            if quota is None:
                quota=ChatResendQuota(user_id=user_id,batch_sort_seq=anchor,window_started_at=now,
                    expires_at=now+timedelta(seconds=60),accepted_count=0);db.add(quota)
            elif quota.expires_at<=now:quota.window_started_at=now;quota.expires_at=now+timedelta(seconds=60);quota.accepted_count=0
            if quota.accepted_count>=2:raise AdmissionError(10105)
            quota.accepted_count+=1
        # Timeline lock comes last, after all admission/message/quota locks.
        if operation=='send':
            row.sort_seq=(await allocate_sort_seq(user_id,1,db))[0];db.add(row);await db.flush()
        if rel is not None:rel.proactive_times=0
        if old and old.state=='pending':await _terminal(db,us,old,'superseded','generation_superseded',now)
        us.state_revision+=1
        generation_id=str(uuid.uuid4());deadline=now+timedelta(seconds=180)
        from backend.config import get_chat_debounce_ms
        gen=ChatGeneration(generation_id=generation_id,user_id=user_id,timing_config_version=TIMING.version,
            accepted_at=now,deadline_at=deadline,reconcile_until=deadline+timedelta(milliseconds=TIMING.reconcile_margin_ms),
            state='pending',phase='admitted',state_revision=us.state_revision,dispatch_state='pending',
            next_dispatch_at=now+timedelta(milliseconds=max(1,get_chat_debounce_ms()) if operation=='send' else 0))
        db.add(gen);await db.flush();us.current_generation_id=generation_id
        targets=[row] if operation=='send' else rows
        sub=ChatSubmission(user_id=user_id,operation=operation,request_id=request_id.encode(),
            client_key_present=client_key_present,channel=channel,
            fingerprint=send_fingerprint(content) if operation=='send' else fingerprint({'operation':'resend','targets':[r.id for r in targets]}),
            fingerprint_version=1,accepted_generation_id=generation_id,accepted_at=now,
            expires_at=now+timedelta(seconds=TIMING.retention_seconds),tombstone_until=now+timedelta(seconds=TIMING.tombstone_seconds),record_state='active')
        db.add(sub);await db.flush()
        for ordinal,r in enumerate(targets):db.add(ChatSubmissionMessage(user_id=user_id,submission_id=sub.id,conversation_id=r.id,ordinal=ordinal))
        for ordinal,r in enumerate(rows):
            in_prompt=ordinal>=len(rows)-10
            r.delivery_status='pending_llm';r.skipped_in_prompt=not in_prompt
            ms=await db.get(ChatMessageState,r.id,with_for_update=True,populate_existing=True)
            if ms is None:ms=ChatMessageState(conversation_id=r.id,user_id=user_id);db.add(ms)
            ms.effective_generation_id=generation_id;ms.processing_state='pending';ms.reason=None
            ms.state_revision=us.state_revision;ms.status_changed_at=now
            db.add(ChatGenerationMessage(user_id=user_id,generation_id=generation_id,conversation_id=r.id,ordinal=ordinal,in_prompt=in_prompt))
        await db.flush()
    except BaseException:
        await db.rollback();raise
    try:await db.commit()
    except BaseException:
        # The commit may have reached MySQL. Never re-run admission after this point.
        await db.close()
        try:
            async with async_session_maker() as probe:
                async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
                    await lock_user(probe,user_id)
                    found=await duplicate(probe,user_id,operation,request_id,content,current=True)
                    if found:return found
        except Exception:pass
        raise AdmissionError(10110,unknown_status(operation,request_id)) from None
    return Admission(generation_id,request_id,operation,False,old.generation_id if old else None)

async def claim(user_id,generation_id,*,sessions=None):
    sessions=sessions or async_session_maker
    async with sessions() as db:
        us=await lock_user(db,user_id);gen=await locked_generation(db,user_id,generation_id)
        now=await db_now(db)
        if gen is None or us.current_generation_id!=generation_id or gen.state!='pending':return None
        if gen.deadline_at<=now:
            await _terminal(db,us,gen,'failed','deadline_exceeded',now);await db.commit();return None
        if gen.phase!='admitted' or (gen.lease_until and gen.lease_until>now) or gen.next_dispatch_at>now:return None
        gen.lease_epoch+=1;gen.lease_owner=str(uuid.uuid4());gen.lease_until=min(gen.deadline_at,now+timedelta(milliseconds=TIMING.lease_ms))
        gen.phase='running';gen.dispatch_state='claimed'
        handle=Execution(user_id,generation_id,gen.lease_owner,gen.lease_epoch,gen.deadline_at,gen.reconcile_until)
        await db.commit();return handle

async def renew(handle,*,sessions=None,remote=False):
    sessions=sessions or async_session_maker
    async with sessions() as db:
        us=await lock_user(db,handle.user_id);gen=await locked_generation(db,handle.user_id,handle.generation_id);now=await db_now(db)
        if not owns(us,gen,handle,now):return False
        gen.lease_until=min(gen.deadline_at,now+timedelta(milliseconds=TIMING.lease_ms))
        if remote and gen.remote_started_at is None:gen.remote_started_at=now
        await db.commit();return True

def owns(us,gen,handle,now):
    return (gen is not None and us.current_generation_id==handle.generation_id and gen.state=='pending'
        and gen.lease_owner==handle.owner and gen.lease_epoch==handle.epoch and gen.lease_until is not None
        and gen.lease_until>now and gen.deadline_at>now)

async def fail(handle,reason,*,sessions=None):
    if reason not in REASONS:raise ValueError('invalid_chat_reason')
    sessions=sessions or async_session_maker
    async with sessions() as db:
        us=await lock_user(db,handle.user_id);gen=await locked_generation(db,handle.user_id,handle.generation_id);now=await db_now(db)
        if (gen is None or gen.state!='pending' or us.current_generation_id!=handle.generation_id
            or gen.lease_epoch!=handle.epoch or gen.lease_owner!=handle.owner):return False
        if gen.phase in ('commit_prepared','commit_unknown','reconcile_exhausted'):return False
        await _terminal(db,us,gen,'failed','deadline_exceeded' if now>=gen.deadline_at else reason,now)
        await db.commit();return True

async def prepare_commit(handle,marker,*,sessions=None):
    sessions=sessions or async_session_maker
    async with sessions() as db:
        us=await lock_user(db,handle.user_id);gen=await locked_generation(db,handle.user_id,handle.generation_id);now=await db_now(db)
        if not owns(us,gen,handle,now):raise LostOwnership()
        gen.phase='commit_prepared';gen.commit_marker=marker
        us.state_revision+=1;gen.state_revision=us.state_revision
        await _message_terminal(db,gen,us.state_revision,now,'pending',None)
        await db.commit()

async def commit_success(handle,marker,*,messages,emotion,round_id,sessions=None,before_cas=None,after_cas=None,on_success=None):
    """Atomic result/CAS; only an unknown ACK requires current-read verification.

    on_success is a synchronous, per-call once notification for the original
    worker to register effects before any cancellable observation or cleanup.

    Hooks are test-only injection points around the real SQL CAS; independent
    connections still exercise MySQL row locks and statement UTC_TIMESTAMP(6).
    """
    from backend.services.timeline_seq_service import allocate_sort_seq
    sessions=sessions or async_session_maker
    if not messages:raise ValueError('empty_chat_result')
    notified=False
    def confirmed():
        nonlocal notified
        if not notified:
            notified=True
            if on_success is not None:on_success()
    await prepare_commit(handle,marker,sessions=sessions)
    async with sessions() as db:
        try:
            us=await lock_user(db,handle.user_id);gen=await locked_generation(db,handle.user_id,handle.generation_id)
            if not owns(us,gen,handle,await db_now(db)) or gen.commit_marker!=marker:raise LostOwnership()
            gm=list((await db.execute(select(ChatGenerationMessage).where(ChatGenerationMessage.user_id==handle.user_id,
                ChatGenerationMessage.generation_id==handle.generation_id).order_by(ChatGenerationMessage.ordinal))).scalars())
            if not gm:raise LostOwnership()
            seqs=await allocate_sort_seq(handle.user_id,len(messages),db)
            for seq,msg in zip(seqs,messages):
                db.add(ConversationLog(user_id=handle.user_id,role='assistant',content=msg.content if hasattr(msg,'content') else msg['content'],
                    sort_seq=seq,round_id=round_id,delivery_status=None,skipped_in_prompt=False))
            db.add(EmotionLog(user_id=handle.user_id,conversation_id=gm[0].conversation_id,round_id=round_id,
                emotion_label=emotion.get('label','平静'),confidence=emotion.get('confidence',1.0)))
            # Effect anchors prevent duplicate post-success dispatch after a lost receipt.
            for effect in ('step6','post_success'):
                db.add(ChatLifecycleEffect(user_id=handle.user_id,owner_kind='chat',owner_id=handle.generation_id,
                    effect_kind=effect,state='pending'))
            await db.flush()
            if await db_now(db)>=gen.deadline_at:raise LostOwnership()
            if before_cas:await before_cas(db)
            revision=us.state_revision+1
            result=await db.execute(text("""UPDATE chat_generation SET state='success', phase='terminal',
                state_revision=:revision, round_id=:round_id, decision_at=UTC_TIMESTAMP(6), terminal_at=UTC_TIMESTAMP(6),
                commit_evidence_kind='atomic_decision', dispatch_state='done', updated_at=UTC_TIMESTAMP(6)
                WHERE user_id=:uid AND generation_id=:gid AND state='pending' AND lease_owner=:owner
                AND lease_epoch=:epoch AND commit_marker=:marker AND deadline_at>UTC_TIMESTAMP(6)
                AND lease_until>UTC_TIMESTAMP(6) AND generation_id=(SELECT current_generation_id FROM chat_user_state WHERE user_id=:uid)"""),
                dict(revision=revision,round_id=round_id,uid=handle.user_id,gid=handle.generation_id,owner=handle.owner,epoch=handle.epoch,marker=marker))
            if result.rowcount!=1:raise LostOwnership()
            await db.refresh(gen);us.state_revision=revision
            await _message_terminal(db,gen,revision,gen.decision_at,'success',None)
            await db.flush()
            if after_cas:await after_cas(db)
        except BaseException:
            await db.rollback()
            await reconcile(handle.user_id,handle.generation_id,sessions=sessions)
            raise
        try:await db.commit()
        except BaseException:
            # Closing joins/rolls back this connection; the next connection takes
            # the same row lock, avoiding repeatable-read snapshots and guesses.
            await db.close()
            return await reconcile(handle.user_id,handle.generation_id,marker=marker,sessions=sessions,on_success=confirmed)
        # No await between a confirmed ACK and the worker's effect registration:
        # even session cleanup may be cancelled at the original deadline.
        confirmed()
    return 'success'

async def reconcile(user_id,generation_id,*,marker=None,sessions=None,on_success=None):
    sessions=sessions or async_session_maker
    try:
        async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
            async with sessions() as db:
                us=await lock_user(db,user_id);gen=await locked_generation(db,user_id,generation_id);now=await db_now(db)
                if gen is None:return 'unverified'
                if gen.state=='success':
                    if marker is not None and gen.commit_marker!=marker:return 'unverified'
                    if not gen.commit_marker or not gen.decision_at or gen.decision_at>=gen.deadline_at:return 'unverified'
                    # Convey authoritative success before metadata/connection cleanup.
                    if on_success is not None:on_success()
                    if gen.commit_observed_at is None:
                        gen.commit_observed_at=now
                        try:await db.commit()
                        except Exception:
                            # Observation metadata cannot reverse the independently
                            # locked, already durable successful decision we read.
                            log.warning('chat_success_observation_write_unverified generation=%s',generation_id)
                    return 'success'
                if gen.state!='pending':return gen.state
                if now>=gen.deadline_at:
                    await _terminal(db,us,gen,'failed','deadline_exceeded',now)
                elif gen.phase in ('commit_prepared','commit_unknown'):
                    # Acquired the authority lock after the original result txn:
                    # no success means its CAS did not commit. No model replay.
                    await _terminal(db,us,gen,'failed','llm_failed',now)
                elif gen.lease_until and gen.lease_until<=now:
                    if gen.remote_started_at:
                        await _terminal(db,us,gen,'failed','execution_lost',now)
                    else:
                        gen.phase='admitted';gen.dispatch_state='pending';gen.lease_owner=None;gen.lease_until=None
                await db.commit();return gen.state
    except Exception:
        # No mutation can be asserted during a database outage. Pure readers
        # project unverified; process watchdog caps probes and logs once per run.
        return 'unverified'

async def claim_effect(handle,kind,*,sessions=None):
    sessions=sessions or async_session_maker
    async with sessions() as db:
        us=await lock_user(db,handle.user_id);gen=await locked_generation(db,handle.user_id,handle.generation_id)
        if gen is None or gen.state!='success':return False
        effect=(await db.execute(select(ChatLifecycleEffect).where(ChatLifecycleEffect.user_id==handle.user_id,
            ChatLifecycleEffect.owner_kind=='chat',ChatLifecycleEffect.owner_id==handle.generation_id,
            ChatLifecycleEffect.effect_kind==kind).with_for_update())).scalar_one_or_none()
        if effect is None or effect.state!='pending':return False
        effect.state='running';effect.attempts+=1;effect.lease_owner=handle.owner
        effect.lease_until=datetime.utcnow()+timedelta(seconds=180)
        await db.commit();return True

async def finish_effect(handle,kind,ok,*,sessions=None):
    sessions=sessions or async_session_maker
    async with sessions() as db:
        await db.execute(update(ChatLifecycleEffect).where(ChatLifecycleEffect.user_id==handle.user_id,
            ChatLifecycleEffect.owner_id==handle.generation_id,ChatLifecycleEffect.owner_kind=='chat',
            ChatLifecycleEffect.effect_kind==kind,ChatLifecycleEffect.lease_owner==handle.owner).values(
                state='done' if ok else 'failed',completed_at=datetime.utcnow() if ok else None,
                last_reason=None if ok else 'execution_lost',lease_until=None))
        await db.commit()

def unknown_status(operation,request_id):
    return dict(operation=operation,request_id=request_id,admission_state='unverified',processing_state='unverified',
        status_reason='storage_unavailable',state_origin='unavailable',state_revision=None,status_observed_at=iso(datetime.utcnow()),
        accepted_generation_id=None,effective_generation_id=None,accepted_at=None,original_deadline_at=None,
        effective_deadline_at=None,reconcile_until=None,dedupe_expires_at=None,source_messages=[],result=None,can_resend=False)

def projection(gen,now):
    state,reason=gen.state,gen.reason
    if state=='pending':
        if gen.phase in ('commit_prepared','commit_unknown','reconcile_exhausted'):state,reason='unverified','commit_unknown'
        elif now>=gen.deadline_at:state,reason='unverified','deadline_unverified'
        elif gen.lease_until and gen.lease_until<=now:state,reason='unverified','execution_lost'
    return dict(processing_state=state,status_reason=reason,state_origin='lifecycle',state_revision=str(gen.state_revision),status_observed_at=iso(now))

async def resend_window_eligibility(db,user_id,now):
    """Original read_status predicate, shared verbatim by the H5 compatibility projection."""
    from backend.services.chat_service import fetch_open_window_user_rows,open_window_has_bang
    window=await fetch_open_window_user_rows(db,user_id)
    current=await db.get(ChatUserState,user_id)
    active=await db.get(ChatGeneration,current.current_generation_id) if current and current.current_generation_id else None
    quota=await db.get(ChatResendQuota,(user_id,min(w.sort_seq for w in window))) if window else None
    quota_available=quota is None or quota.expires_at<=now or quota.accepted_count<2
    return window,bool(quota_available and open_window_has_bang(window) and (active is None or active.state!='pending'))


async def read_resend_eligibility(db,user_id):
    """Read only; absence/unavailability/unknown never grants a local resend button."""
    unavailable=dict(can_resend=False,message_ids=[],state_origin='unavailable')
    try:
        async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
            window,allowed=await resend_window_eligibility(db,user_id,await db_now(db))
            ids=[]
            if allowed:
                for row in window:
                    if row.delivery_status not in ('failed_timeout','failed_error'):continue
                    ms=await db.get(ChatMessageState,row.id)
                    gen=await db.get(ChatGeneration,ms.effective_generation_id) if ms else None
                    if ms is None or (gen and gen.user_id==user_id and gen.state=='failed' and gen.reason!='content_blocked'):
                        ids.append(row.id)
            return dict(can_resend=bool(ids),message_ids=ids,state_origin='lifecycle')
    except Exception:
        try:await db.rollback()
        except Exception:pass
        return unavailable


async def read_status(db,user_id,operation,request_id):
    """Read-only; failure is unverified, never legacy or a fabricated terminal."""
    result=unknown_status(operation,request_id)
    try:
        async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
            sub=await find_submission(db,user_id,operation,request_id)
            now=await db_now(db)
            if sub is None:
                result.update(admission_state='not_found',processing_state=None,status_reason=None,state_origin=None,status_observed_at=iso(now));return result
            if sub.record_state=='tombstone':
                result.update(admission_state='expired',processing_state=None,status_reason='expired',state_origin='lifecycle',dedupe_expires_at=iso(sub.expires_at));return result
            gid=await effective_generation(db,sub)
            gen=await db.get(ChatGeneration,gid)
            original=await db.get(ChatGeneration,sub.accepted_generation_id)
            if gen is None or original is None:return result
            result.update(projection(gen,now),admission_state='accepted',accepted_generation_id=sub.accepted_generation_id,
                effective_generation_id=gid,accepted_at=iso(sub.accepted_at),original_deadline_at=iso(original.deadline_at),
                effective_deadline_at=iso(gen.deadline_at),reconcile_until=iso(gen.reconcile_until),dedupe_expires_at=iso(sub.expires_at))
            rows=list((await db.execute(select(ConversationLog).join(ChatSubmissionMessage,
                ChatSubmissionMessage.conversation_id==ConversationLog.id).where(ChatSubmissionMessage.user_id==user_id,
                ChatSubmissionMessage.submission_id==sub.id,ConversationLog.user_id==user_id).order_by(ChatSubmissionMessage.ordinal))).scalars())
            result['source_messages']=[dict(source='user',id=r.id,sort_seq=str(r.sort_seq)) for r in rows]
            if gen.state=='success':result['result']=await read_result(db,user_id,gen.round_id)
            if gen.state=='failed' and gen.reason!='content_blocked':
                window,allowed=await resend_window_eligibility(db,user_id,now)
                result['can_resend']=bool(allowed and any(r.id in {w.id for w in window} for r in rows))
            return result
    except Exception:
        try:await db.rollback()
        except Exception:pass
        return unknown_status(operation,request_id)

async def read_result(db,user_id,round_id):
    rows=list((await db.execute(select(ConversationLog).where(ConversationLog.user_id==user_id,
        ConversationLog.round_id==round_id,ConversationLog.role=='assistant').order_by(ConversationLog.sort_seq))).scalars())
    emotion=(await db.execute(select(EmotionLog).where(EmotionLog.user_id==user_id,EmotionLog.round_id==round_id).limit(1))).scalar_one_or_none()
    if not rows or emotion is None:raise ValueError('chat_result_unavailable')
    return dict(round_id=round_id,messages=[dict(id=r.id,sort_seq=str(r.sort_seq),type='text',content=r.content) for r in rows],
        emotion=dict(label=emotion.emotion_label,confidence=emotion.confidence))

async def project_chat_message_states(user_id,message_keys,db):
    now=datetime.utcnow();keys=list(message_keys)
    unavailable=dict(processing_state='unverified',status_reason='storage_unavailable',state_origin='unavailable',state_revision=None,status_observed_at=iso(now))
    try:
        ids=[i for source,i in keys if source in ('conversation','user')]
        rows=list((await db.execute(select(ConversationLog,ChatMessageState,ChatGeneration)
            .outerjoin(ChatMessageState,(ChatMessageState.conversation_id==ConversationLog.id)&(ChatMessageState.user_id==user_id))
            .outerjoin(ChatGeneration,(ChatGeneration.generation_id==ChatMessageState.effective_generation_id)&(ChatGeneration.user_id==user_id))
            .where(ConversationLog.user_id==user_id,ConversationLog.id.in_(ids)))).all()) if ids else []
        by_id={r.id:(r,ms,g) for r,ms,g in rows};result={}
        for key in keys:
            source,i=key
            if source=='agent':continue  # STEP015 owns future projection; ordinary agent remains unchanged.
            if i not in by_id:result[key]=dict(unavailable);continue
            row,ms,gen=by_id[i]
            if row.role!='user':continue
            if ms is not None:
                result[key]=projection(gen,now) if gen else dict(unavailable)
            else:
                state='success' if row.delivery_status=='delivered' else ('failed' if (row.delivery_status or '').startswith('failed_') else 'unverified')
                result[key]=dict(processing_state=state,status_reason='legacy_pending' if state=='unverified' else 'legacy_record',
                    state_origin='legacy',state_revision=None,status_observed_at=iso(now))
        return result
    except Exception:
        try:await db.rollback()
        except Exception:pass
        return {key:dict(unavailable) for key in keys if key[0] in ('conversation','user')}

async def generation_payload(user_id,generation_id,*,sessions=None):
    sessions=sessions or async_session_maker
    try:
        async with sessions() as db:
            gen=(await db.execute(select(ChatGeneration).where(ChatGeneration.user_id==user_id,ChatGeneration.generation_id==generation_id))).scalar_one_or_none()
            if gen is None:return {'error':True,'code':10110}
            if gen.state=='success':
                result=await read_result(db,user_id,gen.round_id)
                return dict(error=False,step5={'messages':result['messages']},emotion=result['emotion'],round_id=gen.round_id,
                    generation_id=generation_id,state_revision=str(gen.state_revision),result=result)
            if gen.state=='failed':return dict(error=True,code=10101 if gen.reason=='content_blocked' else 10102,message=gen.reason,state_revision=str(gen.state_revision))
            if gen.state=='superseded':return {'obsolete':True}
            return None
    except Exception:return {'error':True,'code':10110}

_retention_after_id=0

async def expire_submissions(*,sessions=None):
    """Bounded retention work, only after confirmed terminal and no live handover."""
    global _retention_after_id
    sessions=sessions or async_session_maker
    async with sessions() as db:
        now=await db_now(db)
        candidates=list((await db.execute(select(ChatSubmission.user_id,ChatSubmission.id).where(
            ChatSubmission.id>_retention_after_id,
            or_((ChatSubmission.record_state=='active')&(ChatSubmission.expires_at<=now),
                (ChatSubmission.record_state=='tombstone')&(ChatSubmission.tombstone_until<=now)))
            .order_by(ChatSubmission.id).limit(TIMING.scan_batch_size))).all())
    # Bounded keyset progression lets protected unresolved heads yield to later
    # work. Wrap once the current pass ends; no persisted timing is changed.
    _retention_after_id=candidates[-1].id if len(candidates)==TIMING.scan_batch_size else 0
    for uid,sid in candidates:
        async with sessions() as db:
            await lock_user(db,uid)
            sub=await db.get(ChatSubmission,sid,with_for_update=True,populate_existing=True)
            if sub is None:continue
            if sub.record_state=='tombstone':
                if sub.tombstone_until<=now:await db.delete(sub);await db.commit()
                continue
            gid=await effective_generation(db,sub,current=True)
            gen=await locked_generation(db,uid,gid)
            if gen is None or gen.state=='pending':continue
            await db.execute(delete(ChatSubmissionMessage).where(ChatSubmissionMessage.user_id==uid,ChatSubmissionMessage.submission_id==sid))
            sub.record_state='tombstone';sub.fingerprint=None;sub.fingerprint_version=None;sub.accepted_generation_id=None
            await db.commit()
