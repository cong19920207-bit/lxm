"""Future identity, current-read arbitration and original-success effect boundaries."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import uuid
from sqlalchemy import select, text, update
from backend.database import async_session_maker
from backend.models.future_consumption import FutureConsumption
from backend.models.relationship import Relationship
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.chat_lifecycle import ChatLifecycleEffect
from backend.services.chat_lifecycle import lock_user, db_now, LostOwnership, REASONS
from backend.services.chat_timing import TIMING

log = logging.getLogger(__name__)
ACTIVE_SNAPSHOTS = set()

@dataclass(frozen=True)
class Slot:
    user_id: int
    version: int
    timestamp: int | None
    action: str | None

    @classmethod
    def from_row(cls, row):
        return cls(row.user_id, row.future_slot_version, row.future_timestamp, row.future_action)

@dataclass(frozen=True)
class Execution:
    slot: Slot
    consume_id: str
    owner: str
    epoch: int
    deadline_at: datetime
    reconcile_until: datetime
    @property
    def user_id(self): return self.slot.user_id

@dataclass(frozen=True)
class Result:
    consume_id: str | None
    terminal: str
    success_kind: str | None = None
    agent_message_id: int | None = None
    commit_evidence: str | None = None
    effects: dict = field(default_factory=dict)
    def __bool__(self): raise TypeError('consume terminal explicitly; unknown is not failure')

async def locked(db, user_id, consume_id):
    return (await db.execute(select(FutureConsumption).where(FutureConsumption.user_id==user_id,
        FutureConsumption.consume_id==consume_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()

async def lock_relationship(db, user_id):
    return (await db.execute(select(Relationship).where(Relationship.user_id==user_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()

def matches(rel, slot):
    return rel is not None and Slot.from_row(rel)==slot

def owns(row, handle, now):
    return (row is not None and row.state=='pending' and row.lease_owner==handle.owner
        and row.lease_epoch==handle.epoch and row.deadline_at==handle.deadline_at
        and row.lease_until is not None and row.lease_until>now and row.deadline_at>now)

async def capture(user_id, *, sessions=None):
    async with (sessions or async_session_maker)() as db:
        row=await db.scalar(select(Relationship).where(Relationship.user_id==user_id))
        return Slot.from_row(row) if row else None

async def clear_slot(slot, *, sessions=None):
    if slot is None:return False
    async with (sessions or async_session_maker)() as db:
        await lock_user(db,slot.user_id)
        consumption=await db.scalar(select(FutureConsumption).where(FutureConsumption.user_id==slot.user_id,
            FutureConsumption.slot_version==slot.version).with_for_update().execution_options(populate_existing=True))
        if consumption is not None and consumption.state=='pending':return False
        result=await db.execute(update(Relationship).where(Relationship.user_id==slot.user_id,
            Relationship.future_slot_version==slot.version,
            Relationship.future_timestamp==slot.timestamp,Relationship.future_action==slot.action).values(
                future_timestamp=None,future_action=None,future_slot_version=Relationship.future_slot_version+1))
        await db.commit()
        return result.rowcount==1

async def accept(slot, *, sessions=None):
    """Trusted DB-clock acceptance. Repeated slot identity never grants a new worker."""
    async with (sessions or async_session_maker)() as db:
        us=await lock_user(db,slot.user_id)
        prior=await db.scalar(select(FutureConsumption).where(FutureConsumption.user_id==slot.user_id,
            FutureConsumption.slot_version==slot.version).with_for_update().execution_options(populate_existing=True))
        if prior:return await result_for(db,prior)
        rel=await lock_relationship(db,slot.user_id)
        if not matches(rel,slot):return Result(None,'superseded')
        now=await db_now(db)
        if slot.timestamp is None or not (int(now.replace(tzinfo=timezone.utc).timestamp())-1800<slot.timestamp<=int(now.replace(tzinfo=timezone.utc).timestamp())):
            return Result(None,'failed')
        us.state_revision+=1
        row=FutureConsumption(consume_id=str(uuid.uuid4()),user_id=slot.user_id,slot_version=slot.version,
            slot_timestamp=slot.timestamp,slot_action=slot.action or '',accepted_at=now,
            deadline_at=now+timedelta(seconds=180),reconcile_until=now+timedelta(seconds=180,milliseconds=TIMING.reconcile_margin_ms),
            timing_config_version=TIMING.version,state='pending',phase='running',state_revision=us.state_revision,
            lease_owner=str(uuid.uuid4()),lease_epoch=1,lease_until=now+timedelta(milliseconds=TIMING.lease_ms))
        db.add(row);await db.commit()
        return Execution(slot,row.consume_id,row.lease_owner,row.lease_epoch,row.deadline_at,row.reconcile_until)

async def is_cleared(db, consume_id):
    from backend.models.memory_backfill import MemoryResetItem
    items=(await db.scalars(select(MemoryResetItem).where(MemoryResetItem.kind=='resource',
        MemoryResetItem.resource_key=='sql:future_consumption'))).all()
    for item in items:
        ids=(item.fixed_scope or {}).get('ids',[])
        end=len(ids) if item.state=='confirmed' else (item.cursor or {}).get('index',0)
        if {'consume_id':consume_id} in ids[:end]:return True
    return False

async def result_for(db,row):
    if await is_cleared(db,row.consume_id):return Result(row.consume_id,'cleared')
    effects=dict((await db.execute(select(ChatLifecycleEffect.effect_kind,ChatLifecycleEffect.state).where(
        ChatLifecycleEffect.user_id==row.user_id,ChatLifecycleEffect.owner_kind=='future',
        ChatLifecycleEffect.owner_id==row.consume_id))).all())
    terminal='unverified' if row.state=='pending' and (row.phase in ('commit_prepared','commit_unknown','reconcile_exhausted') or row.deadline_at<=datetime.utcnow()) else row.state
    return Result(row.consume_id,terminal,row.success_kind,row.agent_message_id,row.commit_evidence_kind,effects)

async def renew(handle, *, remote=False, sessions=None):
    async with (sessions or async_session_maker)() as db:
        await lock_user(db,handle.user_id);row=await locked(db,handle.user_id,handle.consume_id)
        now=await db_now(db)
        if not owns(row,handle,now):return False
        row.lease_until=min(row.deadline_at,now+timedelta(milliseconds=TIMING.lease_ms))
        if remote and row.remote_started_at is None:row.remote_started_at=now
        await db.commit();return True

async def terminal(db,us,row,reason,now):
    us.state_revision+=1;row.state_revision=us.state_revision
    row.state='failed';row.phase='terminal';row.reason=reason;row.terminal_at=now

async def fail(handle,reason, *, sessions=None):
    if reason not in REASONS:raise ValueError('invalid_future_reason')
    async with (sessions or async_session_maker)() as db:
        us=await lock_user(db,handle.user_id);row=await locked(db,handle.user_id,handle.consume_id)
        if row is None:return Result(handle.consume_id,'unverified')
        if (row.state=='pending' and row.lease_owner==handle.owner and row.lease_epoch==handle.epoch
            and row.phase not in ('commit_prepared','commit_unknown','reconcile_exhausted')):
            now=await db_now(db)
            await terminal(db,us,row,'deadline_exceeded' if now>=row.deadline_at else reason,now)
            await db.commit()
        return await result_for(db,row)

async def prepare(handle,marker,*,sessions):
    async with sessions() as db:
        us=await lock_user(db,handle.user_id);row=await locked(db,handle.user_id,handle.consume_id)
        if not owns(row,handle,await db_now(db)) or row.phase!='running':raise LostOwnership()
        row.phase='commit_prepared';row.commit_marker=marker
        us.state_revision+=1;row.state_revision=us.state_revision
        await db.commit()

async def commit_success(handle, marker, *, content, score, success_kind, round_id,
                         on_success=None, sessions=None, before_cas=None, after_cas=None):
    from backend.services.timeline_seq_service import allocate_sort_seq
    sessions=sessions or async_session_maker
    if success_kind not in ('normal','fallback'):raise ValueError('invalid_future_success_kind')
    notified=False
    def confirmed():
        nonlocal notified
        if not notified:
            notified=True
            if on_success:on_success()
    await prepare(handle,marker,sessions=sessions)
    async with sessions() as db:
        try:
            us=await lock_user(db,handle.user_id);row=await locked(db,handle.user_id,handle.consume_id)
            rel=await lock_relationship(db,handle.user_id)
            if not owns(row,handle,await db_now(db)) or row.commit_marker!=marker or not matches(rel,handle.slot):raise LostOwnership()
            seq=await allocate_sort_seq(handle.user_id,1,db)
            msg=AgentMessage(user_id=handle.user_id,trigger_type=TriggerType.FUTURE,content=content,action_score=score,sort_seq=seq[0])
            db.add(msg)
            kinds=('step6','normal_decay','handler_proactive','agent_count') if success_kind=='normal' else ('handler_proactive','agent_count')
            effects=[]
            for kind in kinds:
                effect=ChatLifecycleEffect(user_id=handle.user_id,owner_kind='future',owner_id=handle.consume_id,effect_kind=kind,state='pending',
                    lease_owner=handle.owner,lease_until=handle.reconcile_until)
                db.add(effect);effects.append(effect)
            await db.flush()
            if await db_now(db)>=row.deadline_at:raise LostOwnership()
            if before_cas:await before_cas(db)
            revision=us.state_revision+1
            changed=await db.execute(text("""UPDATE future_consumption SET state='success',phase='terminal',
                state_revision=:revision,success_kind=:kind,agent_message_id=:mid,round_id=:rid,
                decision_at=UTC_TIMESTAMP(6),terminal_at=UTC_TIMESTAMP(6),commit_evidence_kind='atomic_decision',updated_at=UTC_TIMESTAMP(6)
                WHERE user_id=:uid AND consume_id=:cid AND state='pending' AND lease_owner=:owner
                AND lease_epoch=:epoch AND commit_marker=:marker AND deadline_at>UTC_TIMESTAMP(6)
                AND lease_until>UTC_TIMESTAMP(6)"""),dict(revision=revision,kind=success_kind,mid=msg.id,rid=round_id,
                    uid=handle.user_id,cid=handle.consume_id,owner=handle.owner,epoch=handle.epoch,marker=marker))
            if changed.rowcount!=1:raise LostOwnership()
            await db.refresh(row);us.state_revision=revision
            for effect in effects:effect.effect_date=row.decision_at.date()
            await db.flush()
            answer=Result(row.consume_id,'success',success_kind,msg.id,'atomic_decision',{k:'pending' for k in kinds})
            if after_cas:await after_cas(db)
        except BaseException:
            await db.rollback()
            await reconcile(handle.user_id,handle.consume_id,marker=marker,handle=handle,sessions=sessions)
            raise
        try:await db.commit()
        except BaseException:
            await db.close()
            return await reconcile(handle.user_id,handle.consume_id,marker=marker,handle=handle,sessions=sessions,on_success=confirmed)
        confirmed()  # no await before registering independent effects, including __aexit__
    return answer

async def reconcile(user_id,consume_id,*,marker=None,handle=None,sessions=None,on_success=None):
    try:
        async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
            async with (sessions or async_session_maker)() as db:
                us=await lock_user(db,user_id);row=await locked(db,user_id,consume_id)
                if row is None:return Result(consume_id,'unverified')
                now=await db_now(db)
                if await is_cleared(db,row.consume_id):return Result(row.consume_id,'cleared')
                if row.state=='success':
                    msg=await db.scalar(select(AgentMessage.id).where(AgentMessage.user_id==user_id,AgentMessage.id==row.agent_message_id).with_for_update())
                    if (not msg or not row.commit_marker or not row.decision_at or row.decision_at>=row.deadline_at
                        or (marker is not None and marker!=row.commit_marker)
                        or (handle is not None and (row.lease_epoch!=handle.epoch or row.lease_owner!=handle.owner))):
                        return Result(consume_id,'unverified')
                    # Authority is established: register before any cancellable projection/exit.
                    if on_success:on_success()
                    return await result_for(db,row)
                if row.state=='pending':
                    # Lock acquisition joined the original result transaction. Never replay it.
                    if now>=row.deadline_at:await terminal(db,us,row,'deadline_exceeded',now)
                    elif row.phase in ('commit_prepared','commit_unknown') and (marker is not None or (row.lease_until and row.lease_until<=now)):await terminal(db,us,row,'llm_failed',now)
                    elif row.lease_until and row.lease_until<=now:await terminal(db,us,row,'execution_lost',now)
                    await db.commit()
                return await result_for(db,row)
    except Exception:
        log.warning('future_commit_unverified consume=%s',consume_id)
        return Result(consume_id,'unverified')

async def effect_row(db, user_id, consume_id, kind):
    return await db.scalar(select(ChatLifecycleEffect).where(ChatLifecycleEffect.user_id==user_id,
        ChatLifecycleEffect.owner_kind=='future',ChatLifecycleEffect.owner_id==consume_id,
        ChatLifecycleEffect.effect_kind==kind).with_for_update().execution_options(populate_existing=True))

async def sql_effect(user_id,consume_id,kind,action,*,sessions=None):
    """Effect mark and its SQL business mutation are in one committed transaction."""
    async with (sessions or async_session_maker)() as db:
        await lock_user(db,user_id);row=await locked(db,user_id,consume_id)
        if row is None or row.state!='success' or await is_cleared(db,consume_id):return False
        rel=await lock_relationship(db,user_id)
        effect=await effect_row(db,user_id,consume_id,kind)
        if effect is None or effect.state!='pending':return False
        await action(db,rel,row)
        effect.state='done';effect.attempts+=1;effect.completed_at=await db_now(db)
        await db.commit();return True

COUNT_LUA="""
if redis.call('EXISTS',KEYS[1]) == 1 then return 0 end
redis.call('SET',KEYS[1],'1','EX',ARGV[1])
redis.call('INCR',KEYS[2])
redis.call('EXPIRE',KEYS[2],ARGV[2])
return 1
"""

async def handler_effects(user_id,consume_id,*,sessions=None,redis=None,key_prefix=''):
    sessions=sessions or async_session_maker
    async def increment(db,rel,row):
        if rel is not None:rel.proactive_times=min(3,rel.proactive_times+1)
    # Original normal_decay occurs before the separate Handler increment.
    async with sessions() as db:
        await lock_user(db,user_id);row=await locked(db,user_id,consume_id)
        if row is None or row.state!='success' or await is_cleared(db,consume_id):return
        decay=await effect_row(db,user_id,consume_id,'normal_decay')
        if decay is not None and decay.state in ('pending','running'):return
    await sql_effect(user_id,consume_id,'handler_proactive',increment,sessions=sessions)
    async with sessions() as db:
        await lock_user(db,user_id);row=await locked(db,user_id,consume_id)
        effect=await effect_row(db,user_id,consume_id,'agent_count')
        if row is None or row.state!='success' or effect is None:return
        counted=effect.state=='done'
        effect_date=effect.effect_date
        day=effect_date.strftime('%Y-%m-%d');slot=Slot(row.user_id,row.slot_version,row.slot_timestamp,row.slot_action)
    if not counted:
        if redis is None:
            from backend.redis_client import get_redis
            redis=await get_redis()
        day_end=datetime.combine(effect_date,datetime.max.time())
        count_ttl=max(60,int((day_end-datetime.utcnow()).total_seconds()))
        await redis.eval(COUNT_LUA,2,f'{key_prefix}agent:future:effect:{consume_id}',f'{key_prefix}agent:count:{user_id}:{day}',
            TIMING.tombstone_seconds,count_ttl)
        async def noop(*args):pass
        await sql_effect(user_id,consume_id,'agent_count',noop,sessions=sessions)
    await clear_slot(slot,sessions=sessions)

async def step6_effect(handle,run,*,sessions=None):
    sessions=sessions or async_session_maker
    async with sessions() as db:
        await lock_user(db,handle.user_id);row=await locked(db,handle.user_id,handle.consume_id)
        effect=await effect_row(db,handle.user_id,handle.consume_id,'step6')
        if row is None or row.state!='success' or effect is None or effect.state!='pending' or await is_cleared(db,handle.consume_id):return
        effect.state='running';effect.attempts+=1;effect.lease_owner=handle.owner
        await db.commit()
    try:await run();state='done'
    except Exception:
        log.exception('future_step6_failed consume=%s',handle.consume_id);state='failed'
    async with sessions() as db:
        await lock_user(db,handle.user_id)
        effect=await effect_row(db,handle.user_id,handle.consume_id,'step6')
        effect.state=state;effect.completed_at=await db_now(db) if state=='done' else None
        await db.commit()

async def recover_effects(user_id,consume_id,*,sessions=None):
    """Recover identity/date-only effects, without inventing a lost model snapshot."""
    sessions=sessions or async_session_maker
    if consume_id in ACTIVE_SNAPSHOTS:return
    async with sessions() as db:
        await lock_user(db,user_id);row=await locked(db,user_id,consume_id)
        if row is None or row.state!='success' or await is_cleared(db,consume_id):return
        now=await db_now(db)
        for kind in ('normal_decay','step6'):
            effect=await effect_row(db,user_id,consume_id,kind)
            if effect is not None and effect.state=='pending' and (effect.lease_until is None or effect.lease_until<=now):
                effect.state='unverified';effect.last_reason='execution_lost'
        await db.commit()
    await handler_effects(user_id,consume_id,sessions=sessions)

async def effect_failed(user_id,consume_id,kind,*,sessions=None):
    async with (sessions or async_session_maker)() as db:
        await lock_user(db,user_id);row=await locked(db,user_id,consume_id)
        if row is None or row.state!='success':return
        effect=await effect_row(db,user_id,consume_id,kind)
        if effect is not None and effect.state=='pending':
            effect.state='failed';effect.last_reason='execution_lost';await db.commit()
