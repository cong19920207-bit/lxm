"""Internal account integration only. No public abandonment or deletion route."""
from sqlalchemy import select,delete,update
from backend.models.user import User
from backend.models.pet import PetProfile,PetState
from backend.models.pet_lifecycle import PetAccountLifecycle
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_rule_job import PetRuleJob
from backend.models.pet_interaction import PetInteraction
from backend.models.pet_budget import PetRequestAttempt,PetBudgetEntry
from backend.services.pet_user_service import now_utc,stable_key

async def account_available(db,user_id):
 return await db.get(PetAccountLifecycle,user_id) is None

async def invalidate_account(db,user_id,*,reason,now=None):
 now=now or now_utc()
 await db.scalar(select(User).where(User.id==user_id).with_for_update())
 pet=await db.scalar(select(PetProfile).where(PetProfile.user_id==user_id).with_for_update().execution_options(populate_existing=True))
 if pet is None:return None
 pet.data_version+=1
 from backend.services.pet_generation import stop_attempt
 for task in await db.scalars(select(PetGenerationTask).where(PetGenerationTask.pet_id==pet.id,PetGenerationTask.state.in_(['queued','claimed','requesting','retryable_failed'])).with_for_update()):
  await stop_attempt(db,task,now);task.state='superseded';task.reason=reason;task.generation+=1
 for job in await db.scalars(select(PetRuleJob).where(PetRuleJob.pet_id==pet.id,PetRuleJob.state.in_(['pending','running','error'])).with_for_update()):
  job.state='obsolete';job.last_error=reason;job.generation+=1
 for action in await db.scalars(select(PetInteraction).where(PetInteraction.pet_id==pet.id,PetInteraction.state.in_(['pending','invited']))):
  action.state='cancelled';action.result={'reason':reason,'completed':False}
 state=await db.get(PetState,pet.id)
 if state:state.active_activity=None
 await db.flush();return pet.id

async def prepare_deletion(db,user_id,*,operation_id):
 stable_key(operation_id)
 user=await db.scalar(select(User).where(User.id==user_id).with_for_update())
 if user is None:raise LookupError('user_not_found')
 old=await db.get(PetAccountLifecycle,user_id)
 if old:
  if old.operation_id!=operation_id:raise ValueError('deletion_operation_changed')
  return old.state
 await invalidate_account(db,user_id,reason='account_deletion')
 db.add(PetAccountLifecycle(user_id=user_id,operation_id=operation_id,state='deleting'));await db.flush()
 return 'deleting'

async def purge_deleted_account_pet(db,user_id,*,operation_id):
 """Caller must have authorized account deletion; call in its deletion transaction."""
 await db.scalar(select(User).where(User.id==user_id).with_for_update())
 gate=await db.get(PetAccountLifecycle,user_id)
 if gate is None or gate.operation_id!=operation_id:raise PermissionError('deletion_not_prepared')
 if gate.state=='purged':return
 pet=await db.scalar(select(PetProfile).where(PetProfile.user_id==user_id).with_for_update().execution_options(populate_existing=True))
 if pet:
  # Preserve global consumed/reserved cost history, without private payload/identity.
  from backend.services.pet_budget import mutex
  await mutex(db)
  attempts=list(await db.scalars(select(PetRequestAttempt).where(PetRequestAttempt.pet_id==pet.id)))
  for a in attempts:
   await db.execute(delete(PetBudgetEntry).where(PetBudgetEntry.attempt_id==a.id,PetBudgetEntry.layer!='global'))
   a.user_id=None;a.pet_id=None;a.absence_id=None;a.return_id=None;a.result={};a.request_key='deleted:'+a.id
  await db.flush()
  from backend.models.pet_photo import PetPhotoAsset
  from backend.services.pet_photos import queue_delete
  for asset in await db.scalars(select(PetPhotoAsset).where(PetPhotoAsset.pet_id==pet.id).with_for_update()):
   await queue_delete(db,asset,'account_deleted')
  await db.flush()
  from backend.database import Base
  for table in reversed(Base.metadata.sorted_tables):
   if table.name.startswith('pet_') and 'pet_id' in table.c and table.name!='pet_request_attempt':
    await db.execute(delete(table).where(table.c.pet_id==pet.id))
  await db.execute(delete(PetProfile).where(PetProfile.id==pet.id))
 gate.state='purged';await db.flush()
