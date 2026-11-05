from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.models.pet import utcnow
from backend.models.pet_health import PetJobHealth
PRODUCERS={'care':['pet_care_scan_task'],'growth_snapshot':['pet_rule_scan_task'],'birthday':['pet_birthday_scan_task'],'daily_overview':['pet_daily_scan_task'],'generation':['pet_generation_candidates_task','pet_generation_queue_task'],'cleanup':['pet_generation_cleanup_task']}
async def record(sessions,producer,*,error=None,summary=None,now=None):
 now=now or utcnow()
 async with sessions.begin() as db:
  row=await db.scalar(select(PetJobHealth).where(PetJobHealth.producer==producer).with_for_update())
  if row is None:
   try:
    async with db.begin_nested():
     row=PetJobHealth(producer=producer,last_run_at=now,summary={});db.add(row);await db.flush()
   except IntegrityError:row=await db.scalar(select(PetJobHealth).where(PetJobHealth.producer==producer).with_for_update())
  row.last_run_at=now
  if error or (summary or {}).get('errors',0):row.last_error_at=now;row.last_error=type(error).__name__ if error else 'job_errors'
  else:row.last_success_at=now;row.last_error=None
  row.summary={k:v for k,v in (summary or {}).items() if isinstance(v,(int,bool))}
