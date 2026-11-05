"""Read projections only: never call user entry, settlement, activity or producer paths."""
from datetime import datetime,timedelta
from sqlalchemy import select,func,and_
from fastapi import HTTPException
from backend.models.pet import PetProfile,PetState,PetFactEvent,PetSnapshot,PetDisplayEntry,PetFormalText,PetTextSource,utcnow
from backend.models.user import User
from backend.models.pet_activity import PetActivity,PetAbsence
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_budget import PetRequestAttempt,PetBudgetEntry
from backend.models.pet_return import PetReturn
from backend.models.pet_rule_job import PetRuleJob
from backend.models.pet_config import PetConfigVersion
from backend.services.pet_admin_security import check_permission
from backend.services.pet_config_service import defaults
from backend.services.pet_user_service import current_config
from backend.services.pet_activity import tier
from backend.services.pet_settlement import aware,age_days
from backend.utils.credential_redaction import redact_credentials

PRIVATE_ROLES={'super_admin','ops_admin'}
PANELS={'facts':PetFactEvent,'snapshots':PetSnapshot,'events':PetDisplayEntry,'texts':PetFormalText,'returns':PetReturn,'tasks':PetGenerationTask,'attempts':PetRequestAttempt,'rule-jobs':PetRuleJob,'absences':PetAbsence}

def serialize(row,role):
 data={c.name:getattr(row,c.name) for c in row.__table__.columns}
 for key in ('request_digest','password_hash','configuration'):data.pop(key,None)
 def safe(v):
  if isinstance(v,dict):return {k:('宠物' if k=='name' and role not in PRIVATE_ROLES else safe(x)) for k,x in v.items() if k not in {'photo_data_url'} and not (k=='user_id' and role not in PRIVATE_ROLES)}
  if isinstance(v,list):return [safe(x) for x in v]
  if hasattr(v,'isoformat'):return v.isoformat()
  return v
 return redact_credentials(safe(data))

async def rules_at(db,at):
 config=await current_config(db,'rules',aware(at))
 return config.content if config else defaults('rules')

async def list_pets(db,actor,*,at=None,page=1,page_size=20,pet_id=None,user_id=None,name=None,stage=None,band=None,account=None,start=None,end=None):
 await check_permission(db,actor,'pet.read','facts');at=at or utcnow();rules=await rules_at(db,at)
 where=[PetProfile.adopted_at<=at]
 if pet_id:where.append(PetProfile.id==pet_id)
 if user_id is not None:
  if actor['role'] not in PRIVATE_ROLES:raise HTTPException(403,detail='account_filter_out_of_scope')
  where.append(PetProfile.user_id==user_id)
 if name:where.append(PetProfile.name.contains(name,autoescape=True))
 if stage:where.append(PetState.stage==stage)
 if start:where.append(PetProfile.adopted_at>=start)
 if end:where.append(PetProfile.adopted_at<=end)
 if account:where.append(User.is_banned==(account=='disabled'))
 anchor=func.coalesce(PetActivity.last_active_at,PetProfile.adopted_at)
 costs=rules['costs'];bounds=[at-timedelta(hours=costs['daily_hours']),at-timedelta(days=costs['short_days']),at-timedelta(days=costs['long_days'])]
 if band:
  filters={'daily':anchor>=bounds[0],'short':and_(anchor<bounds[0],anchor>=bounds[1]),'long':and_(anchor<bounds[1],anchor>=bounds[2]),'extended':anchor<bounds[2]}
  if band not in filters:raise HTTPException(422,detail='invalid_tier')
  where.append(filters[band])
 q=select(PetProfile,PetState,PetActivity,User.is_banned).join(User,User.id==PetProfile.user_id).outerjoin(PetState,PetState.pet_id==PetProfile.id).outerjoin(PetActivity,PetActivity.pet_id==PetProfile.id).where(*where)
 total=await db.scalar(select(func.count()).select_from(q.subquery()))
 rows=(await db.execute(q.order_by(PetProfile.adopted_at.desc(),PetProfile.id).offset((page-1)*page_size).limit(page_size))).all()
 result=[]
 for pet,state,activity,banned in rows:
  item=serialize(pet,actor['role']);item.update(stage=state.stage if state else None,settled_at=state.settled_at.isoformat() if state else None,last_active_at=activity.last_active_at.isoformat() if activity else None,tier=tier(activity.last_active_at if activity else pet.adopted_at,aware(at),costs),account='disabled' if banned else 'active',active_activity=state.active_activity if state else None,anomaly='state_missing' if state is None else None);result.append(item)
 return {'list':result,'total':total,'page':page,'page_size':page_size,'at':at.isoformat(),'timezone':'Asia/Shanghai','basis':'saved_projection; no settlement; adopted_at fallback for missing activity'}

async def detail(db,actor,pet_id,*,at=None):
 await check_permission(db,actor,'pet.read','facts');at=at or utcnow();pet=await db.get(PetProfile,pet_id)
 if not pet:raise HTTPException(404,detail='pet_not_found_or_removed')
 state=await db.get(PetState,pet_id);activity=await db.get(PetActivity,pet_id)
 result={'profile':serialize(pet,actor['role']),'state':serialize(state,actor['role']) if state else None,'activity':serialize(activity,actor['role']) if activity else None,'at':at.isoformat(),'basis':'saved_projection','age_days':age_days(pet.birth_date,aware(at)),'life_days':max(1,(aware(at).date()-pet.adopted_at.date()).days+1)}
 ids=[pet.growth_rule_id,state.appearance_rule_id if state else None]
 refs=await db.scalars(select(PetConfigVersion).where((PetConfigVersion.snapshot_id.in_(ids))|(PetConfigVersion.growth_snapshot_id.in_(ids))))
 result['version_refs']=[{'id':x.id,'domain':x.domain,'version':x.version} for x in refs]
 return result

async def panel(db,actor,pet_id,panel,*,at=None,page=1,page_size=20,source_id=None,start=None,end=None):
 await check_permission(db,actor,'pet.read','facts')
 if not await db.get(PetProfile,pet_id):raise HTTPException(404,detail='pet_not_found_or_removed')
 model=PANELS.get(panel)
 if model is None:raise HTTPException(404,detail='panel_not_found')
 at=at or utcnow();where=[model.pet_id==pet_id]
 stamp=next((getattr(model,k) for k in ('recorded_at','reserved_at','coverage_end','captured_at','covered_until','started_at') if hasattr(model,k)),None)
 if stamp is not None:
  where.append(stamp<=at)
  if start:where.append(stamp>=start)
  if end:where.append(stamp<=end)
 if source_id:where.append(model.id==source_id)
 q=select(model).where(*where);total=await db.scalar(select(func.count()).select_from(q.subquery()))
 q=q.order_by(stamp.desc(),model.id) if stamp is not None else q.order_by(model.id)
 rows=list(await db.scalars(q.offset((page-1)*page_size).limit(page_size)));items=[]
 for row in rows:
  item=serialize(row,actor['role'])
  if panel=='texts':item['source_ids']=list(await db.scalars(select(PetTextSource.event_id).where(PetTextSource.text_id==row.id)))
  if panel=='attempts':item['budget_entries']=[serialize(x,actor['role']) for x in await db.scalars(select(PetBudgetEntry).where(PetBudgetEntry.attempt_id==row.id))]
  items.append(item)
 return {'list':items,'total':total,'page':page,'page_size':page_size,'at':at.isoformat(),'timezone':'Asia/Shanghai','completeness':'available','basis':'saved_records'}

async def daily_record(db,actor,pet_id,*,day,at=None):
 await check_permission(db,actor,'pet.read','facts')
 pet=await db.get(PetProfile,pet_id)
 if not pet:raise HTTPException(404,detail='pet_not_found_or_removed')
 from backend.services.pet_records import daily_for_pet
 value=await daily_for_pet(db,pet,day,aware(at or utcnow()))
 # Reuse only the read projection, never a user entry/activity producer.
 def private(v):
  if isinstance(v,dict):return {k:('宠物' if k=='name' and actor['role'] not in PRIVATE_ROLES else private(x)) for k,x in v.items()}
  if isinstance(v,list):return [private(x) for x in v]
  return v
 return {**private(value),'at':(at or utcnow()).isoformat(),'basis':'saved_projection; no settlement'}

async def photo_image(db,actor,snapshot_id):
 await check_permission(db,actor,'pet.read','facts')
 if actor['role'] not in PRIVATE_ROLES:raise HTTPException(403,detail='private_photo_out_of_scope')
 snap=await db.get(PetSnapshot,snapshot_id)
 if not snap or snap.kind!='photo' or not snap.source_event_id:raise HTTPException(404,detail='photo_unavailable')
 fact=await db.get(PetFactEvent,snap.source_event_id)
 from backend.services.pet_records import historical_snapshot
 return await historical_snapshot(db,fact)
