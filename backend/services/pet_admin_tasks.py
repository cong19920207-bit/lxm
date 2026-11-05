"""Saved task diagnostics and bounded recovery; never perform a model send here."""
from sqlalchemy import select,func
from fastapi import HTTPException
from backend.models.pet import PetProfile,PetState,PetFactEvent,PetFormalText,utcnow
from backend.models.user import User
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_budget import PetRequestAttempt,PetBudgetEntry
from backend.models.pet_interaction import PetInteraction
from backend.models.pet_rule_job import PetRuleJob
from backend.services.pet_admin_read import serialize,PRIVATE_ROLES
from backend.services.pet_admin_security import check_permission,prepare_operation,execute_operation
from backend.services.pet_config_service import ConfigInvalid
from backend.services.pet_settlement import aware
from backend.services.pet_persistence import _utc
from backend.services import pet_generation as generation,pet_budget as budget

async def attempts(db,t):
 return list(await db.scalars(select(PetRequestAttempt).where(PetRequestAttempt.request_key.startswith('user:'+str(t.user_id)+':'+t.id+':')).order_by(PetRequestAttempt.reserved_at,PetRequestAttempt.id)))

async def eligibility(db,t,now):
 pet=await db.get(PetProfile,t.pet_id);user=await db.get(User,t.user_id)
 why=await generation.reason(db,t,pet,user,now)
 rows=await attempts(db,t)
 own=next((a for a in rows if a.id==t.attempt_id and a.state=='reserved' and a.concurrent_until>_utc(now)),None)
 if t.origin=='return' and any(a.sent_at or a.state=='unknown' for a in rows):why='return_attempt_spent'
 layers=[];concurrency={}
 rules=await __import__('backend.services.pet_user_service',fromlist=['current_config']).current_config(db,'rules',now)
 if rules:
  probe=PetRequestAttempt(pet_id=t.pet_id,user_id=t.user_id,origin=t.origin,kind=t.kind,absence_id=t.absence_id,return_id=t.return_id)
  try:
   for layer,bucket,limit in await budget.layers(db,probe,rules.content['costs'],now):
    counts=dict((await db.execute(select(PetBudgetEntry.state,func.count()).where(PetBudgetEntry.layer==layer,PetBudgetEntry.bucket==bucket).group_by(PetBudgetEntry.state))).all())
    used=counts.get('reserved',0)+counts.get('consumed',0)
    own_count=await db.scalar(select(func.count()).select_from(PetBudgetEntry).where(PetBudgetEntry.attempt_id==own.id,PetBudgetEntry.layer==layer,PetBudgetEntry.bucket==bucket,PetBudgetEntry.state=='reserved')) if own else 0
    layers.append({'layer':layer,'limit':limit,'reserved':counts.get('reserved',0),'consumed':counts.get('consumed',0),'remaining':max(0,limit-used),'over_limit':used>limit,'own_reservation':own_count,'available_to_this_task':max(0,limit-used+own_count)})
    if used-own_count>=limit and not why:why=layer+'_exhausted'
   active=await db.scalar(select(func.count()).select_from(PetRequestAttempt).where(PetRequestAttempt.concurrent_active.is_(True),PetRequestAttempt.concurrent_until>_utc(now)))
   concurrency={'active':active,'limit':rules.content['costs']['global_concurrency']}
   if active-(1 if own and own.concurrent_active else 0)>=concurrency['limit'] and not why:why='global_concurrency'
  except budget.BudgetDenied as e:why=why or str(e)
 else:why=why or 'global_configuration_missing'
 can_retry=t.state=='retryable_failed' and not why
 return {'eligible':not bool(why),'retryable':can_retry,'reason':why or (None if can_retry else 'task_not_retryable'), 'checked_at':now.isoformat(),'budget_layers':layers,'concurrency':concurrency,'attempt_count':len(rows),'unknown_count':sum(a.state=='unknown' for a in rows),'account_active':bool(user and not user.is_banned),'pet_data_version':pet.data_version if pet else None,'required_data_version':t.pet_data_version,'expires_at':t.expires_at.isoformat(),'configuration_ids':{k:v for k,v in t.configuration.items() if k.endswith('_id')}}

async def listing(db,actor,*,at=None,page=1,page_size=20,kind=None,pet_id=None,user_id=None,state=None,reason=None,start=None,end=None,unknown=None,validity=None,time_field='created_at'):
 await check_permission(db,actor,'overview.read','runtime');at=_utc(aware(at or utcnow()));where=[(PetGenerationTask.created_at<=at)|(PetGenerationTask.created_at.is_(None))]
 for value,column in ((kind,PetGenerationTask.kind),(pet_id,PetGenerationTask.pet_id),(state,PetGenerationTask.state),(reason,PetGenerationTask.reason)):
  if value:where.append(column==value)
 if user_id is not None:
  if actor['role'] not in PRIVATE_ROLES:raise HTTPException(403,detail='account_filter_out_of_scope')
  where.append(PetGenerationTask.user_id==user_id)
 if time_field not in {'created_at','updated_at'}:raise HTTPException(422,detail='invalid_time_field')
 stamp=getattr(PetGenerationTask,time_field)
 if start:where.append(stamp>=_utc(aware(start)))
 if end:where.append(stamp<=_utc(aware(end)))
 if validity and validity not in {'valid','expired'}:raise HTTPException(422,detail='invalid_validity')
 if validity:where.append(PetGenerationTask.expires_at>at if validity=='valid' else PetGenerationTask.expires_at<=at)
 if unknown is not None:
  sub=select(PetRequestAttempt.id).where(PetRequestAttempt.request_key.startswith(func.concat('user:',PetGenerationTask.user_id,':',PetGenerationTask.id,':')),PetRequestAttempt.state=='unknown').exists();where.append(sub if unknown else ~sub)
 q=select(PetGenerationTask).where(*where);total=await db.scalar(select(func.count()).select_from(q.subquery()));rows=list(await db.scalars(q.order_by(stamp.desc(),PetGenerationTask.id).offset((page-1)*page_size).limit(page_size)))
 items=[]
 for t in rows:items.append({**serialize(t,actor['role']),'qualification':await eligibility(db,t,aware(at))})
 return {'list':items,'total':total,'page':page,'page_size':page_size,'at':at.isoformat(),'basis':'saved tasks; eligibility checked at query cutoff; execution always rechecks'}

async def detail(db,actor,object_id,*,type='task',now=None):
 await check_permission(db,actor,'overview.read','runtime');now=aware(now or utcnow());role=actor['role']
 if type in {'attempt','attempt_id'}:
  a=await db.get(PetRequestAttempt,object_id)
  if not a:raise HTTPException(404,detail='attempt_missing')
  task=await db.scalar(select(PetGenerationTask).where(PetGenerationTask.id==a.request_key.split(':')[2])) if a.origin!='debug' and len(a.request_key.split(':'))>=4 else None
  return {'attempt':serialize(a,role),'task_id':task.id if task else None,'budget_entries':[serialize(x,role) for x in await db.scalars(select(PetBudgetEntry).where(PetBudgetEntry.attempt_id==a.id))],'unknown_explanation':'发送结果未知保留消耗；不会自动退款或重发' if a.state=='unknown' else None}
 if type in {'interaction','rule-job','rule'}:
  model=PetInteraction if type=='interaction' else PetRuleJob;x=await db.get(model,object_id)
  if not x:raise HTTPException(404,detail='object_missing')
  recoverable=bool(type=='interaction' and x.state in {'cancelled','expired','obsolete','blocked','incomplete','pending'} and (x.state!='pending' or x.expires_at<=_utc(now)))
  return {type:serialize(x,role),'qualification':{'interaction_releasable':recoverable,'checked_at':now.isoformat(),'reason':None if recoverable else 'interaction_still_valid_or_not_recoverable'}}
 t=await db.get(PetGenerationTask,object_id)
 if not t:raise HTTPException(404,detail='task_missing')
 rows=await attempts(db,t);texts=list(await db.scalars(select(PetFormalText).where(PetFormalText.pet_id==t.pet_id,PetFormalText.business_key==t.business_key).order_by(PetFormalText.version)))
 q=await eligibility(db,t,now)
 a=next((a for a in rows if a.id==t.attempt_id),None)
 q['release_allowed']=bool(a and a.state=='reserved' and not a.sent_at and ((await generation.reason(db,t,await db.get(PetProfile,t.pet_id),await db.get(User,t.user_id),now)) or (t.lease_until and t.lease_until<=_utc(now))))
 q['release_reason']=None if q['release_allowed'] else 'not_confirmed_unsent_expired_reservation'
 return {'task':serialize(t,role),'qualification':q,'attempts':[serialize(a,role) for a in rows],'facts':[serialize(f,role) for f in await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==t.pet_id,PetFactEvent.id.in_(t.source_ids)))],'texts':[serialize(x,role) for x in texts],'configuration_ids':{k:v for k,v in t.configuration.items() if k.endswith('_id')}}

async def recover(sessions,actor,*,object_id,operation_id,reason,action,domain='fault',now=None):
 if action not in {'retry','release','interaction'}:raise ConfigInvalid('recovery_action_invalid')
 if action!='retry' and domain!='fault':raise ConfigInvalid('fault_scope_required')
 now=aware(now or utcnow());await prepare_operation(sessions,actor,operation_id=operation_id,action='task.retry',domain=domain,target=object_id,reason=reason,payload={'action':action})
 async def work(db,op):
  if action=='interaction':
   i=await db.get(PetInteraction,object_id)
   if not i:raise ConfigInvalid('interaction_missing')
   p=await db.get(PetProfile,i.pet_id)
   from backend.services.pet_interactions import context
   pet,state=await context(db,p.user_id)
   i=await db.scalar(select(PetInteraction).where(PetInteraction.id==object_id).with_for_update().execution_options(populate_existing=True))
   if i.state=='pending' and i.expires_at>_utc(now):raise ConfigInvalid('interaction_still_valid')
   if i.state not in {'cancelled','expired','pending','obsolete','blocked','incomplete'}:raise ConfigInvalid('interaction_not_recoverable')
   if i.state=='pending':i.state='expired';i.result={'completed':False,'reason':'timeout','active_eligible':False}
   if state.active_activity and state.active_activity.get('id')==i.id:state.active_activity=None
   return {'interaction_id':i.id,'state':i.state,'released':True,'reward_granted':False}
  t,p,u=await generation.locked(db,object_id)
  if action=='retry':
   if t.state!='retryable_failed':raise ConfigInvalid('task_not_retryable')
   why=await generation.reason(db,t,p,u,now)
   rows=await attempts(db,t)
   if t.origin=='return' and any(a.sent_at or a.state=='unknown' for a in rows):why='return_attempt_spent'
   if why:raise ConfigInvalid(why)
   await budget.mutex(db);probe=PetRequestAttempt(pet_id=t.pet_id,user_id=t.user_id,origin=t.origin,kind=t.kind,absence_id=t.absence_id,return_id=t.return_id)
   await budget.allocate(db,probe,now,dry_run=True)
   t.state='queued';t.reason=None;t.generation+=1;t.result={**(t.result or {}),'admin_operation_id':operation_id}
   return {'task_id':t.id,'state':t.state,'new_attempt':'created only by fresh claim after eligibility and budget checks'}
  a=await db.get(PetRequestAttempt,t.attempt_id) if t.attempt_id else None
  if not a or a.state!='reserved' or a.sent_at:raise ConfigInvalid('not_confirmed_unsent_reservation')
  why=await generation.reason(db,t,p,u,now)
  expired=t.lease_until and t.lease_until<=_utc(now)
  if not why and not expired:raise ConfigInvalid('execution_still_valid')
  released=await budget.release(db,a.id,'admin_confirmed_unsent_expired')
  t.state='policy_skipped' if why else 'retryable_failed';t.reason=why or 'claim_expired';t.generation+=1
  return {'task_id':t.id,'attempt_id':a.id,'released':released,'state':t.state,'reason':t.reason}
 return await execute_operation(sessions,actor,operation_id,work)
