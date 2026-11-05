from copy import deepcopy
from sqlalchemy import select
from fastapi import HTTPException
from backend.models.pet import PetFormalText,PetTextSource,PetFactEvent,PetProfile,utcnow
from backend.models.pet_text_visibility import PetTextVisibility
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_budget import PetRequestAttempt
from backend.models.user import User
from backend.services.pet_admin_security import check_permission,prepare_operation,execute_operation,PetAdminDenied
from backend.services.pet_admin_read import serialize
from backend.services.pet_config_service import fingerprint,ConfigConflict,ConfigInvalid
from backend.services.pet_expression import validate_output,fact_view,workflow_config
from backend.services.pet_settlement import aware

async def latest(db,text,*,lock=False):
 query=select(PetFormalText).where(PetFormalText.pet_id==text.pet_id,PetFormalText.business_key==text.business_key).order_by(PetFormalText.version.desc()).limit(1)
 if lock:query=query.with_for_update().execution_options(populate_existing=True)
 return await db.scalar(query)
async def visible(db,text):
 if text is None:return None
 current=await latest(db,text);flag=await db.get(PetTextVisibility,current.id)
 return None if flag and flag.hidden else current
async def basis(db,text):
 ids=list(await db.scalars(select(PetTextSource.event_id).where(PetTextSource.text_id==text.id).order_by(PetTextSource.event_id)))
 facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==text.pet_id,PetFactEvent.id.in_(ids)).order_by(PetFactEvent.id)))
 flag=await db.get(PetTextVisibility,text.id);pet=await db.get(PetProfile,text.pet_id)
 digest=fingerprint({'text':serialize(text,'super_admin'),'visibility':serialize(flag,'super_admin') if flag else None,'facts':[serialize(f,'super_admin') for f in facts],'source_ids':ids,'data_version':pet.data_version})
 return digest,ids,facts,flag
async def view(db,actor,text_id,domain='copy'):
 await check_permission(db,actor,'audit.read',domain);text=await db.get(PetFormalText,text_id)
 if not text:raise HTTPException(404,detail='text_not_found')
 digest,ids,facts,flag=await basis(db,text);current=await latest(db,text)
 return {'text':serialize(text,actor['role']),'source_ids':ids,'facts':[serialize(f,actor['role']) for f in facts],'hidden':bool(flag and flag.hidden),'basis_digest':digest,'current_version':current.version,'current_id':current.id,'domain':domain}

async def regeneration_reason(db,t):
 marker=(t.result or {}).get('regenerate')
 if not marker:return None
 text=await db.get(PetFormalText,marker['text_id'])
 if not text or (await latest(db,text)).id!=text.id:return 'text_version_changed'
 if (await basis(db,text))[0]!=marker['basis_digest']:return 'text_basis_changed'
 return None

async def change(sessions,actor,*,text_id,operation_id,reason,basis_digest,action,domain='copy',output=None,now=None):
 if action not in {'hide','correct','regenerate'}:raise ConfigInvalid('text_action_invalid')
 if domain not in {'copy','fault'} or (domain=='fault' and action=='correct'):raise PetAdminDenied()
 permission='task.retry' if action=='regenerate' else 'text.hide';now=aware(now or utcnow())
 await prepare_operation(sessions,actor,operation_id=operation_id,action=permission,domain=domain,target=text_id,reason=reason,payload={'text_action':action,'basis_digest':basis_digest,'output':output})
 async def work(db,op):
  text=await db.get(PetFormalText,text_id)
  if not text:raise LookupError('text_missing')
  pet=await db.get(PetProfile,text.pet_id)
  from backend.services.pet_user_service import lock_owner
  await lock_owner(db,pet.user_id);await db.scalar(select(PetProfile).where(PetProfile.id==pet.id).with_for_update().execution_options(populate_existing=True))
  current=await latest(db,text,lock=True)
  await db.scalar(select(PetTextVisibility).where(PetTextVisibility.text_id==text.id).with_for_update().execution_options(populate_existing=True))
  digest,ids,facts,flag=await basis(db,text)
  if digest!=basis_digest or current.id!=text.id:raise ConfigConflict('text_version_or_basis_changed')
  if len(facts)!=len(ids):raise ConfigInvalid('source_facts_missing')
  if action=='hide':
   if flag is None:flag=PetTextVisibility(text_id=text.id,pet_id=text.pet_id,hidden=True,revision=1,operation_id=operation_id);db.add(flag)
   else:flag.hidden=True;flag.revision+=1;flag.operation_id=operation_id
   return {'text_id':text.id,'version':text.version,'hidden':True,'original_body':text.body,'source_ids':ids}
  if action=='correct':
   c=workflow_config(text.config_snapshot.get('ai',{}),text.kind);value=validate_output(output,[fact_view(f) for f in facts],maximum=c['maximum'],allowed_invitations=[],title_max=c['title_max'])
   corrected=PetFormalText(pet_id=text.pet_id,business_key=text.business_key,kind=text.kind,version=text.version+1,body=value['body'],coverage_start=text.coverage_start,coverage_end=text.coverage_end,config_snapshot={**deepcopy(text.config_snapshot),'correction':{'operation_id':operation_id,'previous_id':text.id,'source_ids':ids}})
   db.add(corrected);await db.flush()
   for event_id in ids:db.add(PetTextSource(text_id=corrected.id,event_id=event_id,pet_id=text.pet_id))
   return {'text_id':corrected.id,'version':corrected.version,'before':text.body,'after':corrected.body,'source_ids':ids}
  task_id=text.config_snapshot.get('generation_task_id');t=await db.get(PetGenerationTask,task_id) if task_id else None
  if not t or t.pet_id!=text.pet_id or set(t.source_ids)!=set(ids):raise ConfigInvalid('original_task_or_scope_missing')
  if t.state not in {'succeeded','retryable_failed','final_failed'}:raise ConfigInvalid('task_not_regenerable')
  from backend.services.pet_generation import reason as eligible
  why=await eligible(db,t,pet,await db.get(User,pet.user_id),now)
  attempt=await db.get(PetRequestAttempt,t.attempt_id) if t.attempt_id else None
  if t.origin=='return' and attempt and (attempt.sent_at or attempt.state=='unknown'):why='return_attempt_spent'
  if why:raise ConfigInvalid(why)
  from backend.services import pet_budget as budget
  await budget.mutex(db);probe=PetRequestAttempt(pet_id=t.pet_id,user_id=t.user_id,origin=t.origin,kind=t.kind,absence_id=t.absence_id,return_id=t.return_id)
  await budget.allocate(db,probe,now,dry_run=True)
  t.result={**t.result,'regenerate':{'text_id':text.id,'basis_digest':basis_digest,'operation_id':operation_id},'admin_operation_id':operation_id};t.state='queued';t.generation+=1;t.reason=None
  return {'text_id':text.id,'task_id':t.id,'state':'queued','source_ids':ids,'budget_origin':t.origin}
 return await execute_operation(sessions,actor,operation_id,work)
