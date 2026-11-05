"""Durable dispatch fencing. Network work is always outside a business transaction."""
from datetime import timedelta
from sqlalchemy import select
from backend.models.pet import PetProfile,PetFactEvent
from backend.models.user import User
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_budget import PetRequestAttempt
from backend.models.pet_activity import PetAbsence
from backend.services import pet_budget as budget
from backend.services.pet_activity import owned,offline_eligibility
from backend.services.pet_user_service import runtime_flags,current_config,now_utc,PetConflict
from backend.services.pet_persistence import _utc
from backend.services.pet_settlement import aware,iso

class StaleExecution(ValueError):pass
TERMINAL={'succeeded','final_failed','policy_skipped','superseded'}

async def enqueue(db,user_id,*,business_key,kind,origin,source_ids,coverage_start,coverage_end,expires_at,now=None,absence_id=None,return_id=None):
 pet=await owned(db,user_id)
 old=await db.scalar(select(PetGenerationTask).where(PetGenerationTask.pet_id==pet.id,PetGenerationTask.business_key==business_key).with_for_update())
 if old:return old
 facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.id.in_(source_ids))))
 if len(facts)!=len(set(source_ids)) or not source_ids:raise ValueError('source_facts_required')
 if coverage_start>coverage_end or expires_at<=coverage_end:raise ValueError('invalid_task_window')
 task=PetGenerationTask(pet_id=pet.id,user_id=user_id,business_key=business_key,kind=kind,origin=origin,source_ids=list(dict.fromkeys(source_ids)),absence_id=absence_id,return_id=return_id,
  coverage_start=_utc(coverage_start),coverage_end=_utc(coverage_end),expires_at=_utc(expires_at),pet_data_version=pet.data_version,state='queued',generation=0,configuration={},result={})
 db.add(task);await db.flush();return task

async def locked(db,task_id):
 task=await db.get(PetGenerationTask,task_id)
 if task is None:raise LookupError('generation_not_found')
 user=await db.scalar(select(User).where(User.id==task.user_id).with_for_update().execution_options(populate_existing=True))
 pet=await db.scalar(select(PetProfile).where(PetProfile.id==task.pet_id).with_for_update().execution_options(populate_existing=True))
 task=await db.scalar(select(PetGenerationTask).where(PetGenerationTask.id==task_id).with_for_update().execution_options(populate_existing=True))
 return task,pet,user

async def reason(db,t,pet,user,now):
 from backend.services.pet_admin_security import task_actor_reason
 denied=await task_actor_reason(db,t,commit=True)
 if denied:return denied
 if not user or user.is_banned:return 'user_inactive'
 from backend.services.pet_lifecycle import account_available
 if not await account_available(db,t.user_id):return 'account_deletion'
 if not pet or pet.data_version!=t.pet_data_version:return 'pet_version_changed'
 if t.state=='superseded':return 'superseded'
 from backend.services.pet_admin_text import regeneration_reason
 changed=await regeneration_reason(db,t)
 if changed:return changed
 if _utc(now)>=t.expires_at:return 'task_expired'
 if not (await runtime_flags(db,now,lock=True))['ai_enabled']:return 'ai_disabled'
 rules=await current_config(db,'rules',now,lock=True)
 if rules is None:return 'rules_missing'
 if t.origin=='offline':
  a=await db.scalar(select(PetAbsence).where(PetAbsence.id==t.absence_id).with_for_update().execution_options(populate_existing=True))
  if not a:return 'absence_missing'
  allowed,why=offline_eligibility(a,now,rules.content['costs'])
  if not allowed:return why
  if t.kind=='daily' and why!='daily':return 'daily_tier_changed'
  if t.kind=='period' and why!='short':return 'period_tier_changed'
 if t.origin=='return':
  from backend.models.pet_return import PetReturn
  ret=await db.get(PetReturn,t.return_id)
  if ret is None or ret.pet_id!=pet.id or ret.confirmed_at is None:return 'return_not_confirmed'
  cost=rules.content['costs']
  if (ret.coverage_end-ret.coverage_start).total_seconds()<cost['return_min_hours']*3600:return 'absence_too_short'
  recent=select(PetRequestAttempt).where(PetRequestAttempt.user_id==t.user_id,PetRequestAttempt.origin=='return',PetRequestAttempt.sent_at.is_not(None))
  if t.attempt_id:recent=recent.where(PetRequestAttempt.id!=t.attempt_id)
  previous=await db.scalar(recent.order_by(PetRequestAttempt.sent_at.desc()).limit(1).with_for_update())
  if previous and (_utc(now)-previous.sent_at).total_seconds()<cost['return_cooldown_hours']*3600:return 'return_cooldown'
 facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==t.pet_id,PetFactEvent.id.in_(t.source_ids))))
 if len(facts)!=len(t.source_ids):return 'facts_changed'
 return None

def valid(t,c,now):
 return t.generation==c['generation'] and t.owner==c['owner'] and t.attempt_id==c['attempt_id'] and t.lease_until and t.lease_until>_utc(now)

async def stop_attempt(db,t,now):
 if not t.attempt_id:return
 a=await db.get(PetRequestAttempt,t.attempt_id)
 if a.state=='reserved':await budget.release(db,a.id,'claim_expired_or_revoked')
 elif a.state=='sent':await budget.finish(db,a.id,'unknown',now=now,reason='claim_expired_or_revoked')

async def claim(sessions,task_id,*,owner,now=None,lease_seconds=120):
 now=now or now_utc()
 async with sessions.begin() as db:
  t,pet,user=await locked(db,task_id)
  if t.state in TERMINAL or t.state=='retryable_failed':return None
  if t.state in {'claimed','requesting'} and t.lease_until and t.lease_until>_utc(now):return None
  why=await reason(db,t,pet,user,now)
  if why:
   await stop_attempt(db,t,now);t.state='policy_skipped';t.reason=why;return None
  if t.attempt_id:
   await stop_attempt(db,t,now)
   a=await db.get(PetRequestAttempt,t.attempt_id)
   if t.origin=='return' and a.sent_at:t.state='final_failed';t.reason='return_attempt_spent';return None
  t.generation+=1
  try:
   a=await budget.reserve(db,t.user_id,request_key=t.id+':'+str(t.generation),origin=t.origin,kind=t.kind,absence_id=t.absence_id,return_id=t.return_id,content_date=aware(t.coverage_end).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Shanghai')).date(),now=now,lease_seconds=lease_seconds)
  except budget.BudgetDenied as error:t.state='policy_skipped';t.reason=str(error);return None
  ai=await current_config(db,'ai',now);rules=await current_config(db,'rules',now)
  t.configuration={'ai_id':ai.id if ai else None,'ai':ai.content if ai else {},'rules_id':rules.id,'rules':rules.content}
  t.owner=owner;t.lease_until=_utc(now)+timedelta(seconds=lease_seconds);t.attempt_id=a.id;t.state='claimed';t.reason=None
  return {'task_id':t.id,'owner':owner,'generation':t.generation,'attempt_id':a.id,'lease_until':iso(t.lease_until)}

async def permit(sessions,c,*,now=None,configuration_error=None,model_snapshot=None):
 if not c:return False
 now=now or now_utc()
 async with sessions.begin() as db:
  t,pet,user=await locked(db,c['task_id'])
  if not valid(t,c,now) or t.state!='claimed':return False
  why=await reason(db,t,pet,user,now)
  if why or configuration_error:
   await stop_attempt(db,t,now);t.state='retryable_failed' if configuration_error else 'policy_skipped';t.reason=configuration_error or why;return False
  if not await budget.authorize_send(db,c['attempt_id'],now=now):
   t.state='policy_skipped';t.reason=(await db.get(PetRequestAttempt,c['attempt_id'])).reason;return False
  if model_snapshot:
   t.configuration={**t.configuration,'model':model_snapshot}
   t.lease_until=_utc(now)+timedelta(seconds=model_snapshot['timeout_seconds']+30)
   (await db.get(PetRequestAttempt,c['attempt_id'])).concurrent_until=t.lease_until
   c['lease_until']=iso(t.lease_until)
  t.state='requesting';return True

async def commit_result(sessions,c,result,*,now=None,error=None,writer=None):
 now=now or now_utc()
 attempt_state='unknown' if error in {'send_unknown','execution_error','execution_cancelled'} else 'failure' if error else 'success'
 async with sessions.begin() as db:
  t,pet,user=await locked(db,c['task_id'])
  if not valid(t,c,now) or t.state!='requesting':
   old=await db.get(PetRequestAttempt,c['attempt_id'])
   if old and old.state in {'sent','unknown'}:
    await budget.finish(db,old.id,attempt_state,now=now,result=result,reason=error)
   return False
  # Usage belongs to the actual attempt even if the content has become stale.
  await budget.finish(db,c['attempt_id'],attempt_state,now=now,result=result,reason=error)
  why=await reason(db,t,pet,user,now)
  # Our own offline attempt advanced the spacing marker; do not invalidate its reply.
  if why=='short_interval':why=None
  if why:t.state='policy_skipped';t.reason=why;return False
  if error:t.state='final_failed' if t.origin=='return' else 'retryable_failed';t.reason=error
  else:
   if writer:result=await writer(db,t,result,now)
   t.result=result;t.state='succeeded';t.reason=None
  return True

async def retry(sessions,task_id,*,now=None):
 now=now or now_utc()
 async with sessions.begin() as db:
  t,pet,user=await locked(db,task_id)
  if t.state!='retryable_failed':return False
  why=await reason(db,t,pet,user,now)
  a=await db.get(PetRequestAttempt,t.attempt_id) if t.attempt_id else None
  if t.origin=='return' and a and a.sent_at:why='return_attempt_spent'
  if not why:
   await budget.mutex(db)
   probe=PetRequestAttempt(pet_id=t.pet_id,user_id=t.user_id,origin=t.origin,kind=t.kind,absence_id=t.absence_id,return_id=t.return_id)
   try:await budget.allocate(db,probe,now,dry_run=True)
   except budget.BudgetDenied as error:why=str(error)
  if why:t.state='policy_skipped';t.reason=why;return False
  t.state='queued';t.reason=None;return True

async def scan_cleanup(sessions,*,now,owner,limit=100,after=None):
 async with sessions() as db:
  query=select(PetGenerationTask.id).order_by(PetGenerationTask.id).limit(limit)
  if after:query=query.where(PetGenerationTask.id>after)
  ids=list(await db.scalars(query))
 cleaned=0
 for task_id in ids:
  async with sessions.begin() as db:
   t,pet,user=await locked(db,task_id)
   why=await reason(db,t,pet,user,now)
   expired=t.state in {'claimed','requesting'} and t.lease_until and t.lease_until<=_utc(now)
   if t.state!='succeeded' and (why or expired or t.state=='superseded'):
    await stop_attempt(db,t,now)
    if t.state!='superseded':t.state='policy_skipped' if why else 'final_failed' if t.origin=='return' else 'retryable_failed'
    t.reason=why or 'claim_expired';t.generation+=1;cleaned+=1
   from backend.services.pet_rule_jobs import enqueue_job
   j=await enqueue_job(db,t.pet_id,'generation_cleanup','generation_cleanup:'+iso(_utc(now).replace(minute=0,second=0,microsecond=0)),aware(_utc(now).replace(minute=0,second=0,microsecond=0)))
   j.state='done';j.owner=owner;j.last_success_at=_utc(now);j.result={'last_task_id':t.id,'reason':t.reason};j.last_error=None
 return {'cleaned':cleaned,'next_cursor':ids[-1] if len(ids)==limit else None}


async def transport_authorized(sessions,c,*,now):
 async with sessions.begin() as db:
  from backend.services.memory_business_guard import guard_business_write
  # All pet writers acquire the owner before the runtime fence at flush.
  # Reversing this order here deadlocks concurrent sends against those writers.
  t,pet,user=await locked(db,c['task_id'])
  await guard_business_write(db)
  if not valid(t,c,now) or t.state!='requesting':return False
  why=await reason(db,t,pet,user,now)
  if why and why!='short_interval':
   await stop_attempt(db,t,now);t.state='policy_skipped';t.reason=why;return False
  return True
