"""One rule-origin anniversary per pet/year, independent of AI and participation."""
import calendar
from datetime import date,datetime,time
from sqlalchemy import select
from backend.models.pet import PetProfile,PetState,PetFactEvent,PetSnapshot,PetRuleSnapshot
from backend.models.user import User
from backend.services.pet_user_service import now_utc,current_config,BUSINESS_ZONE
from backend.services.pet_interactions import context
from backend.services.pet_records import owned
from backend.services.pet_settlement import settle_pet,aware,iso
from backend.services.pet_persistence import FactCommand,append_fact,_utc
from backend.services.pet_rule_jobs import enqueue_job,claim_job,execute_job,StaleClaim

def birthday_date(birth,year,leap_day):
    if (birth.month,birth.day)==(2,29) and not calendar.isleap(year):
        month,day=map(int,leap_day.split('-'));return date(year,month,day)
    return date(year,birth.month,birth.day)

async def birthday_once(db,job,*,now):
    pet=await db.get(PetProfile,job.pet_id);pet,state=await context(db,pet.user_id)
    today=now.astimezone(BUSINESS_ZONE).date()
    if aware(job.covered_until).astimezone(BUSINESS_ZONE).date()!=today:return {'created':False,'reason':'birthday_window_expired'}
    rules=await current_config(db,'rules',now);config=rules.content['birthday']
    if not config['enabled'] or birthday_date(pet.birth_date,today.year,config['leap_day'])!=today or pet.birth_date>today:return {'created':False,'reason':'not_business_birthday'}
    key='birthday:'+str(today.year)
    existing=await db.scalar(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.business_key==key))
    if existing:return {'created':False,'event_id':existing.id,'reason':'already_recorded'}
    await settle_pet(db,pet.id,pet.user_id,until=now)
    ai=await current_config(db,'ai',now)
    body=config['template'].format(pet_name=pet.name,business_date=today.isoformat())
    if ai and 'birthday' in ai.content.get('templates',{}):
        from backend.services.pet_templates import render
        body=render(ai.content,'birthday',pet_name=pet.name,date=today.isoformat(),facts='',participants='',stage=state.stage)
    fact=await append_fact(db,FactCommand(pet_id=pet.id,user_id=pet.user_id,request_key=key,business_key=key,expected_version=state.record_version,
        event_type='birthday',source='rule_settlement',participants=(),occurred_at=now,
        result={'name':pet.name,'birthday_date':today.isoformat(),'estimated_birth_date':pet.birth_date.isoformat(),'template_body':body,'active_eligible':False,'completed':False,'basis':'estimated_birth_date'},
        state_after=state.values,closeness_delta=0,rule_snapshot_id=rules.snapshot_id,display_surfaces=('daily','album')))
    appearance=await db.get(PetRuleSnapshot,state.appearance_rule_id) if state.appearance_rule_id else None
    db.add(PetSnapshot(pet_id=pet.id,business_key=key,kind='birthday',source_event_id=fact.id,captured_at=_utc(now),profile={'name':pet.name,'stage':state.stage,'birthday_date':today.isoformat()},
        state={'values':dict(state.values),'basis':'rule_settlement'},resources={'appearance_rule_id':state.appearance_rule_id,'appearance':appearance.content if appearance else None},rule_snapshot_id=rules.snapshot_id))
    await db.flush();return {'created':True,'event_id':fact.id,'business_date':today.isoformat()}

async def current_birthday(db,user_id,*,now=None):
    now=now or now_utc();pet=await owned(db,user_id);today=now.astimezone(BUSINESS_ZONE).date()
    fact=await db.scalar(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.event_type=='birthday',PetFactEvent.business_date==today))
    if fact is None:return None
    return {'event_id':fact.id,'date':today.isoformat(),'name':fact.result['name'],'body':fact.result['template_body'],
        'basis':'estimated_birth_date','participants':[],'note':'这是按估算出生日期记录的游戏内生日纪念。日期到来不代表已经举行庆祝。'}

async def scan_birthdays(sessions,*,now,owner,limit=100,after=None,clock=None):
    today=now.astimezone(BUSINESS_ZONE).date();cutoff=datetime.combine(today,time.min,tzinfo=BUSINESS_ZONE)
    async with sessions() as db:
        rules=await current_config(db,'rules',now)
        if not rules or not rules.content['birthday']['enabled']:return {'completed':0,'errors':0,'next_cursor':None}
        query=select(PetProfile).join(User,User.id==PetProfile.user_id).where(User.is_banned.is_(False)).order_by(PetProfile.id).limit(limit)
        if after:query=query.where(PetProfile.id>after)
        pets=list(await db.scalars(query));ids=[p.id for p in pets if p.birth_date<=today and birthday_date(p.birth_date,today.year,rules.content['birthday']['leap_day'])==today]
    completed=errors=0
    for pet_id in ids:
        try:
            async with sessions.begin() as db:job_id=(await enqueue_job(db,pet_id,'birthday','birthday:'+str(today.year)+':'+today.isoformat(),cutoff)).id
            claim=await claim_job(sessions,job_id,owner=owner,now=aware(clock()) if clock else now)
            if claim is None:continue
            async def work(db,job):return await birthday_once(db,job,now=aware(clock()) if clock else now)
            await execute_job(sessions,claim,work,clock=clock or (lambda:now));completed+=1
        except (StaleClaim,ValueError,LookupError,PermissionError):errors+=1
    return {'completed':completed,'errors':errors,'next_cursor':pets[-1].id if len(pets)==limit else None}
