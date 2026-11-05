"""Bounded care producer. Recovery checks the present; it never replays missed meals."""
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from backend.models.pet import PetProfile,PetState,PetFactEvent
from backend.models.user import User
from backend.services.pet_rule_jobs import enqueue_job,claim_job,execute_job,StaleClaim
from backend.services.pet_user_service import current_config,runtime_flags,BUSINESS_ZONE,PetInputError
from backend.services.pet_interactions import feed,context
from backend.services.pet_joint_service import clear_expired
from backend.services.pet_settlement import settle_pet,aware,iso
from backend.services.pet_persistence import _utc
from backend.services.pet_rewards import complete_participation

async def care_once(db,job,*,now):
    pet=await db.get(PetProfile,job.pet_id);pet,state=await context(db,pet.user_id)
    rules=await current_config(db,'rules',now);config=rules.content['care']
    if (_utc(now)-job.covered_until).total_seconds()>config['check_hours']*3600:return {'executed':False,'reason':'check_window_expired'}
    await settle_pet(db,pet.id,pet.user_id,until=now)
    if not (await runtime_flags(db,now,lock=True))['care_enabled']:return {'executed':False,'reason':'care_disabled'}
    try:await clear_expired(db,state,now)
    except PetInputError:return {'executed':False,'reason':'pet_busy'}
    history=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.source=='actual_execution').order_by(PetFactEvent.occurred_at.desc())))
    care=[f for f in history if f.participants==['xiaomeng'] and f.event_type in {'feed','touch'} and f.result.get('completed')]
    today=now.astimezone(BUSINESS_ZONE).date()
    from backend.services.pet_rule_decisions import care_reason
    why=care_reason(rules.content,state.values,used=sum(f.business_date==today for f in care),elapsed_hours=(_utc(now)-care[0].occurred_at).total_seconds()/3600 if care else float('inf'))
    if why in {'daily_cap','care_interval'}:return {'executed':False,'reason':why}
    if why is None:
        result=await feed(db,pet.user_id,request_key='care:'+job.id,actor='xiaomeng',now=now,target=config['feed_target'])
        return {'executed':result['state']=='done','event_id':result['event_id'],'action':'feed','state':result['state']}
    # A home event uses the already implemented gentle-touch response. No new toy,
    # invented action, offline activity timestamp or AI request is introduced here.
    from backend.services.pet_activity import activity_for,tier
    activity=await activity_for(db,pet)
    if tier(activity.last_active_at,now,rules.content['costs']) in {'long','extended'}:return {'executed':False,'reason':'nonessential_home_event_suppressed'}
    home=[f for f in care if f.result.get('home_event')]
    if home and (_utc(now)-home[0].occurred_at).total_seconds()<config['home_event_interval_hours']*3600:return {'executed':False,'reason':'home_interval'}
    if state.values['mood']>=rules.content['state']['initial']['mood']:return {'executed':False,'reason':'no_action_needed'}
    fact=await complete_participation(db,pet,state,rules,action='touch',request_key='care:'+job.id,business_key='care:'+job.id,
        now=now,state_after=dict(state.values),participants=('xiaomeng',),result={'home_event':True,'name':pet.name,'template':'小梦轻轻摸了摸它。'},
        reaction={'type':'lean_towards_hand','scene':state.stage,'outcome':'responded'})
    return {'executed':True,'action':'gentle_touch','event_id':fact.id}

async def scan_care(sessions,*,now,owner,limit=100,after=None,clock=None):
    async with sessions() as db:
        rules=await current_config(db,'rules',now)
        if not rules:return {'completed':0,'errors':0,'next_cursor':None}
        interval=rules.content['care']['check_hours']*3600
        seconds=int((now.timestamp()+8*3600)//interval)*interval-8*3600
        cutoff=datetime.fromtimestamp(seconds,timezone.utc)
        query=select(PetProfile.id).join(User,User.id==PetProfile.user_id).where(User.is_banned.is_(False)).order_by(PetProfile.id).limit(limit)
        if after:query=query.where(PetProfile.id>after)
        ids=list(await db.scalars(query))
    completed=errors=0
    for pet_id in ids:
        try:
            async with sessions.begin() as db:job_id=(await enqueue_job(db,pet_id,'care','care:'+iso(cutoff),cutoff)).id
            current=aware(clock()) if clock else now
            claim=await claim_job(sessions,job_id,owner=owner,now=current)
            if claim is None:continue
            async def work(db,job):return await care_once(db,job,now=aware(clock()) if clock else now)
            await execute_job(sessions,claim,work,clock=clock or (lambda:now));completed+=1
        except (StaleClaim,ValueError,LookupError,PermissionError):errors+=1
    return {'completed':completed,'errors':errors,'next_cursor':ids[-1] if len(ids)==limit else None}
