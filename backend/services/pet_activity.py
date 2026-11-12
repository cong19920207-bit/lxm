"""User/pet lock serializes anchors. Client timestamps are never accepted."""
from datetime import timedelta
from uuid import uuid5,NAMESPACE_URL
from sqlalchemy import select
from backend.models.pet import PetFactEvent
from backend.models.pet_activity import PetActivity,PetAbsence,PetViewSession
from backend.services.pet_user_service import lock_owner,owner_pet,current_config,now_utc,PetInputError
from backend.services.pet_persistence import _utc
from backend.services.pet_settlement import aware
SESSION_SECONDS=60
HEARTBEAT_MAX_GAP=10
VIEW_MAX_LIFETIME=3600

def tier(anchor,now,costs):
 elapsed=max(0,(_utc(now)-_utc(aware(anchor))).total_seconds())
 return 'daily' if elapsed<=costs['daily_hours']*3600 else 'short' if elapsed<=costs['short_days']*86400 else 'long' if elapsed<=costs['long_days']*86400 else 'extended'

def offline_eligibility(absence,now,costs):
 if absence is None or absence.ended_at is not None:return False,'absence_closed'
 band=tier(absence.started_at,now,costs)
 if band in {'long','extended'}:return False,'offline_tier_forbidden'
 if band=='short':
  earliest=absence.started_at+timedelta(hours=costs['short_interval_hours'])
  if absence.last_narrative_at:earliest=max(earliest,absence.last_narrative_at+timedelta(hours=costs['short_interval_hours']))
  if _utc(now)<earliest:return False,'short_interval'
 return True,band

async def activity_for(db,pet):
 # The owner lock can follow an older API authentication read view.
 a=await db.scalar(select(PetActivity).where(PetActivity.pet_id==pet.id).with_for_update().execution_options(populate_existing=True))
 if a is None:
  # Existing M1/M2 pets migrate lazily using their real completed participation.
  facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.source=='actual_execution').order_by(PetFactEvent.occurred_at.desc())))
  anchor=next((f.occurred_at for f in facts if 'player' in f.participants and f.result.get('active_eligible')),pet.adopted_at)
  a=PetActivity(pet_id=pet.id,last_active_at=anchor,session_until=anchor+timedelta(seconds=SESSION_SECONDS));db.add(a);await db.flush()
 return a

async def ensure_absence(db,pet,now):
 a=await activity_for(db,pet)
 if _utc(now)<=a.session_until:return None
 key=str(uuid5(NAMESPACE_URL,'pet:'+pet.id+':'+a.last_active_at.isoformat()))
 absence=await db.scalar(select(PetAbsence).where(PetAbsence.id==key,PetAbsence.pet_id==pet.id).with_for_update().execution_options(populate_existing=True))
 if absence is None:
  absence=PetAbsence(id=key,pet_id=pet.id,started_at=a.last_active_at);db.add(absence);await db.flush()
 return absence

async def mark_active(db,pet,now,*,source_event=None):
 a=await activity_for(db,pet);absence=await ensure_absence(db,pet,now)
 if absence:
  from backend.services.pet_return import confirm_before_activity
  await confirm_before_activity(db,pet,absence,now,source_event)
  # The old interval is retained before changing the active anchor.
  absence.ended_at=_utc(now);a.previous_absence_id=absence.id
 a.last_active_at=max(a.last_active_at,_utc(now));a.session_until=max(a.session_until,_utc(now)+timedelta(seconds=SESSION_SECONDS))
 await db.flush()
 return {'absence_id':absence.id if absence else a.previous_absence_id,'qualified':True}

async def owned(db,user_id):
 await lock_owner(db,user_id);pet=await owner_pet(db,user_id,lock=True)
 if pet is None:raise LookupError('pet_not_found')
 return pet

async def begin_view(db,user_id,*,now=None):
 now=now or now_utc();pet=await owned(db,user_id)
 await ensure_absence(db,pet,now)
 session=PetViewSession(pet_id=pet.id,started_at=_utc(now),heartbeat_at=_utc(now),seconds=0,sequence=0,foreground=True)
 db.add(session);await db.flush()
 return {'id':session.id,'heartbeat_seconds':5,'qualified':False}

async def heartbeat(db,user_id,session_id,*,sequence,foreground,surface,now=None):
 now=now or now_utc();pet=await owned(db,user_id);v=await db.get(PetViewSession,session_id)
 if v is None or v.pet_id!=pet.id:raise LookupError('view_not_found')
 if _utc(now)<v.heartbeat_at or (_utc(now)-v.started_at).total_seconds()>VIEW_MAX_LIFETIME:raise PetInputError('view_expired')
 if sequence<=v.sequence:return {'qualified':v.qualified_at is not None,'absence_id':v.absence_id}
 valid=foreground and surface in {'scene','records','album','event','profile','growth','photo','birthday','preference'}
 gap=(_utc(now)-v.heartbeat_at).total_seconds()
 v.seconds=v.seconds+gap if valid and v.foreground and 0<=gap<=HEARTBEAT_MAX_GAP else 0
 v.foreground=valid;v.heartbeat_at=_utc(now);v.sequence=sequence
 rules=await current_config(db,'rules',now)
 if valid and v.seconds>=rules.content['costs']['view_seconds']:
  result=await mark_active(db,pet,now)
  if v.qualified_at is None:v.qualified_at=_utc(now);v.absence_id=result['absence_id']
 await db.flush();return {'qualified':v.qualified_at is not None,'absence_id':v.absence_id}
