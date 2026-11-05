"""One durable mutex serializes the lightweight domain's multi-layer allocation."""
from datetime import timedelta
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from backend.models.pet_budget import PetBudgetMutex,PetRequestAttempt,PetBudgetEntry
from backend.models.pet_activity import PetAbsence
from backend.services.pet_user_service import current_config,BUSINESS_ZONE,stable_key,now_utc,PetConflict
from backend.services.pet_activity import owned,offline_eligibility
from backend.services.pet_persistence import _utc

class BudgetDenied(ValueError):pass

async def mutex(db):
 row=await db.get(PetBudgetMutex,1)
 if row is None:
  try:
   async with db.begin_nested():db.add(PetBudgetMutex(id=1));await db.flush()
  except IntegrityError:pass
 await db.scalar(select(PetBudgetMutex).where(PetBudgetMutex.id==1).with_for_update().execution_options(populate_existing=True))

async def layers(db,a,cost,now):
 day=now.astimezone(BUSINESS_ZONE).date().isoformat();items=[('global',day,cost['global_daily'])]
 if a.origin=='debug':return items+[('debug',str(a.debug_owner)+':'+day,cost['debug_daily'])]
 items.append(('user',str(a.user_id)+':'+day,cost['user_daily']))
 if a.kind in {'daily','period','return'}:items.append(('narrative',str(a.user_id)+':'+day,cost['narrative_daily']))
 if a.origin in {'offline','return'}:
  absence=await db.get(PetAbsence,a.absence_id)
  if absence is None or absence.pet_id!=a.pet_id:raise BudgetDenied('absence_invalid')
  if a.origin=='offline':
   allowed,reason=offline_eligibility(absence,now,cost)
   if not allowed:raise BudgetDenied(reason)
   items.append(('offline',absence.id,cost['offline_total']))
  else:
   if not absence.ended_at or not a.return_id:raise BudgetDenied('return_not_confirmed')
   items.append(('return',a.return_id,min(1,cost['return_total'])))
 return items

async def allocate(db,a,now,*,exclude_self=False,dry_run=False):
 rules=await current_config(db,'rules',now,lock=True)
 if rules is None:raise BudgetDenied('global_configuration_missing')
 cost=rules.content['costs'];wanted=await layers(db,a,cost,now)
 # Check all layers before mutating any entry. Reservations and consumption are disjoint.
 for layer,bucket,limit in wanted:
  q=select(PetBudgetEntry.id).where(PetBudgetEntry.layer==layer,PetBudgetEntry.bucket==bucket,PetBudgetEntry.state.in_(['reserved','consumed']))
  if exclude_self:q=q.where(PetBudgetEntry.attempt_id!=a.id)
  if len(list(await db.scalars(q.with_for_update())))>=limit:raise BudgetDenied(layer+'_exhausted')
 active=select(PetRequestAttempt.id).where(PetRequestAttempt.concurrent_active.is_(True),PetRequestAttempt.concurrent_until>_utc(now))
 if a.id:active=active.where(PetRequestAttempt.id!=a.id)
 if len(list(await db.scalars(active.with_for_update())))>=cost['global_concurrency']:raise BudgetDenied('global_concurrency')
 if a.origin=='debug' and len(list(await db.scalars(active.where(PetRequestAttempt.origin=='debug').with_for_update())))>=cost.get('debug_concurrency',0):raise BudgetDenied('debug_concurrency')
 if dry_run:return
 a.config_id=rules.id
 if not a.id:db.add(a);await db.flush()
 old=list(await db.scalars(select(PetBudgetEntry).where(PetBudgetEntry.attempt_id==a.id)))
 for row in old:
  if row.state=='reserved':row.state='released'
 for layer,bucket,limit in wanted:
  row=next((x for x in old if x.layer==layer and x.bucket==bucket),None)
  if row:row.state='reserved';row.limit_at_reserve=limit
  else:db.add(PetBudgetEntry(attempt_id=a.id,layer=layer,bucket=bucket,state='reserved',limit_at_reserve=limit))
 await db.flush()

async def reserve(db,user_id,*,request_key,origin,kind,absence_id=None,return_id=None,debug_owner=None,content_date=None,now=None,lease_seconds=120):
 now=now or now_utc();stable_key(request_key)
 if origin not in {'offline','interactive','return','debug'} or kind not in {'immediate','daily','period','return'}:raise BudgetDenied('invalid_budget_source')
 if origin=='return' and kind!='return':raise BudgetDenied('invalid_return_kind')
 if origin=='debug':
  if user_id is not None or debug_owner is None:raise BudgetDenied('debug_identity_required')
  pet=None
 else:pet=await owned(db,user_id)
 await mutex(db);key=('debug:'+str(debug_owner) if origin=='debug' else 'user:'+str(user_id))+':'+request_key
 old=await db.scalar(select(PetRequestAttempt).where(PetRequestAttempt.request_key==key).with_for_update())
 if old:
  if (old.origin,old.kind,old.absence_id,old.return_id)!=(origin,kind,absence_id,return_id):raise PetConflict('attempt_request_changed')
  return old
 a=PetRequestAttempt(request_key=key,pet_id=pet.id if pet else None,user_id=user_id,debug_owner=debug_owner,origin=origin,kind=kind,
  absence_id=absence_id,return_id=return_id,content_date=content_date,reserved_at=_utc(now),concurrent_until=_utc(now)+timedelta(seconds=lease_seconds),concurrent_active=True,state='reserved',result={})
 await allocate(db,a,now);return a

async def lock_attempt(db,attempt_id):
 a=await db.get(PetRequestAttempt,attempt_id)
 if a is None:raise LookupError('attempt_not_found')
 if a.user_id is not None:
  from backend.models.user import User
  from backend.models.pet import PetProfile
  await db.scalar(select(User).where(User.id==a.user_id).with_for_update())
  await db.scalar(select(PetProfile).where(PetProfile.id==a.pet_id).with_for_update())
 await mutex(db)
 return await db.scalar(select(PetRequestAttempt).where(PetRequestAttempt.id==attempt_id).with_for_update().execution_options(populate_existing=True))

async def release(db,attempt_id,reason='confirmed_not_sent'):
 a=await lock_attempt(db,attempt_id)
 if a.state!='reserved':return False
 rows=list(await db.scalars(select(PetBudgetEntry).where(PetBudgetEntry.attempt_id==a.id,PetBudgetEntry.state=='reserved')))
 for row in rows:row.state='released'
 a.state='released';a.reason=reason;a.concurrent_active=False;await db.flush();return True

async def authorize_send(db,attempt_id,*,now=None):
 now=now or now_utc();a=await lock_attempt(db,attempt_id)
 if a.state!='reserved':return False
 if a.concurrent_until<=_utc(now):await release(db,a.id,'reservation_expired');return False
 try:await allocate(db,a,now,exclude_self=True)
 except BudgetDenied as error:await release(db,a.id,str(error));return False
 a.state='sent';a.sent_at=_utc(now);a.submission_date=now.astimezone(BUSINESS_ZONE).date()
 for row in await db.scalars(select(PetBudgetEntry).where(PetBudgetEntry.attempt_id==a.id,PetBudgetEntry.state=='reserved')):row.state='consumed'
 if a.origin=='offline' and a.kind in {'daily','period'}:
  absence=await db.get(PetAbsence,a.absence_id);absence.last_narrative_at=_utc(now)
 await db.flush();return True

async def finish(db,attempt_id,state,*,now=None,result=None,reason=None):
 a=await lock_attempt(db,attempt_id)
 if a.state not in {'sent','unknown'}:return False
 if state not in {'success','failure','unknown'}:raise ValueError('invalid_attempt_result')
 a.state=state;a.reason=reason;a.finished_at=_utc(now or now_utc());a.result=dict(result or {});a.concurrent_active=False;await db.flush();return True

async def report(db,user_id,*,now=None):
 now=now or now_utc();await owned(db,user_id);rules=await current_config(db,'rules',now);cost=rules.content['costs'];result={}
 attempts=list(await db.scalars(select(PetRequestAttempt).where(PetRequestAttempt.user_id==user_id)))
 # Account overview includes its own entries and shared global entries without other identities.
 rows=list(await db.scalars(select(PetBudgetEntry).join(PetRequestAttempt,PetRequestAttempt.id==PetBudgetEntry.attempt_id).where((PetRequestAttempt.user_id==user_id)|(PetBudgetEntry.layer=='global'))))
 limits={'global':cost['global_daily'],'user':cost['user_daily'],'narrative':cost['narrative_daily'],'offline':cost['offline_total'],'return':min(1,cost['return_total'])}
 for row in rows:
  key=row.layer+':'+row.bucket;item=result.setdefault(key,{'reserved':0,'consumed':0,'released':0,'limit':limits.get(row.layer,cost['debug_daily'])});item[row.state]+=1
 for item in result.values():
  used=item['reserved']+item['consumed'];item.update(remaining=max(0,item['limit']-used),over_limit=used>item['limit'])
 return {'layers':result,'actual_attempts':sum(a.sent_at is not None for a in attempts),'reserved_attempts':sum(a.state=='reserved' for a in attempts),'concurrent':sum(a.concurrent_active and a.concurrent_until>_utc(now) for a in attempts)}
