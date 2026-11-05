"""Bounded current-window producers. No catch-up diary queue is ever created."""
from datetime import datetime,timedelta,time
from sqlalchemy import select
from backend.models.pet import PetProfile,PetFactEvent,PetDisplayEntry,PetFormalText,PetTextSource
from backend.models.pet_generation import PetGenerationTask
from backend.models.user import User
from backend.services.pet_activity import owned,ensure_absence,activity_for,tier,offline_eligibility
from backend.services.pet_user_service import current_config,runtime_flags,BUSINESS_ZONE
from backend.services.pet_settlement import aware,iso
from backend.services.pet_persistence import _utc
from backend.services.pet_generation import enqueue
from backend.services.pet_rule_jobs import enqueue_job,claim_job,execute_job,StaleClaim

async def build_candidate(db,pet,now):
 await owned(db,pet.user_id);rules=await current_config(db,'rules',now)
 if not rules:return {'created':0,'reason':'rules_missing'}
 if not (await runtime_flags(db,now))['ai_enabled']:return {'created':0,'reason':'ai_disabled'}
 costs=rules.content['costs'];config=rules.content.get('narrative',{'day_start_minute':10,'day_end_minute':360,'selected_facts':8})
 activity=await activity_for(db,pet);band=tier(activity.last_active_at,now,costs)
 if band in {'long','extended'}:return {'created':0,'reason':'offline_tier_forbidden'}
 absence=await ensure_absence(db,pet,now)
 if absence is None:return {'created':0,'reason':'active_session'}
 allowed,why=offline_eligibility(absence,now,costs)
 if not allowed:return {'created':0,'reason':why}
 if band=='daily':
  local=now.astimezone(BUSINESS_ZONE);minute=local.hour*60+local.minute
  if not config['day_start_minute']<=minute<config['day_end_minute']:return {'created':0,'reason':'outside_daily_window'}
  end=datetime.combine(local.date(),time(),BUSINESS_ZONE);start=end-timedelta(days=1)
  expiry=end+timedelta(minutes=config['day_end_minute']);key='daily:'+start.date().isoformat();kind='daily'
 else:
  pending=await db.scalar(select(PetGenerationTask).where(PetGenerationTask.pet_id==pet.id,PetGenerationTask.absence_id==absence.id,PetGenerationTask.kind=='period',PetGenerationTask.state.in_(['queued','claimed','requesting'])).with_for_update())
  if pending:return {'created':0,'reason':'pending_period','task_id':pending.id}
  end=now.replace(minute=now.minute//10*10,second=0,microsecond=0);start=aware(absence.started_at)
  previous=list(await db.scalars(select(PetFormalText).where(PetFormalText.pet_id==pet.id,PetFormalText.kind=='period',PetFormalText.coverage_start>=absence.started_at).order_by(PetFormalText.coverage_end.desc())))
  if previous:start=aware(previous[0].coverage_end)
  expiry=min(now+timedelta(hours=6),aware(absence.started_at)+timedelta(days=costs['short_days']))
  if expiry<=end:return {'created':0,'reason':'period_window_ended'}
  key='period:'+absence.id+':'+iso(end);kind='period'
 old=await db.scalar(select(PetGenerationTask).where(PetGenerationTask.pet_id==pet.id,PetGenerationTask.business_key==key).with_for_update())
 if old:return {'created':0,'reason':'same_range','task_id':old.id}
 q=select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.occurred_at>=_utc(start),PetFactEvent.event_type!='system_settlement')
 q=q.where(PetFactEvent.occurred_at<_utc(end)) if kind=='daily' else q.where(PetFactEvent.occurred_at<=_utc(end))
 facts=list(await db.scalars(q.order_by(PetFactEvent.occurred_at,PetFactEvent.id)))
 covered=set(await db.scalars(select(PetTextSource.event_id).where(PetTextSource.pet_id==pet.id)))
 facts=[f for f in facts if f.id not in covered]
 album=set(await db.scalars(select(PetDisplayEntry.source_event_id).where(PetDisplayEntry.pet_id==pet.id,PetDisplayEntry.surface=='album')))
 important=[f for f in facts if f.result.get('active_eligible') or f.event_type in {'natural_growth','birthday'} or f.result.get('home_event') or (f.participants==['xiaomeng'] and f.id in album)]
 if not important:return {'created':0,'reason':'no_important_new_facts'}
 t=await enqueue(db,pet.user_id,business_key=key,kind=kind,origin='offline',source_ids=[f.id for f in facts],coverage_start=start,coverage_end=end,expires_at=expiry,now=now,absence_id=absence.id)
 return {'created':1,'task_id':t.id,'kind':kind,'source_ids':t.source_ids}

async def scan_candidates(sessions,*,now,owner,limit=100,after=None,clock=None):
 cutoff=now.replace(minute=now.minute//10*10,second=0,microsecond=0)
 async with sessions() as db:
  q=select(PetProfile.id).join(User,User.id==PetProfile.user_id).where(User.is_banned.is_(False)).order_by(PetProfile.id).limit(limit)
  if after:q=q.where(PetProfile.id>after)
  ids=list(await db.scalars(q))
 created=errors=0
 for pet_id in ids:
  try:
   async with sessions.begin() as db:j=await enqueue_job(db,pet_id,'generation_candidates','generation_candidates:'+iso(cutoff),cutoff);jid=j.id
   c=await claim_job(sessions,jid,owner=owner,now=now)
   if c is None:continue
   async def work(db,job):return await build_candidate(db,await db.get(PetProfile,job.pet_id),aware(clock()) if clock else now)
   result=await execute_job(sessions,c,work,clock=clock or (lambda:now));created+=result['created']
  except (StaleClaim,ValueError,PermissionError,LookupError):errors+=1
 return {'created':created,'errors':errors,'next_cursor':ids[-1] if len(ids)==limit else None}
