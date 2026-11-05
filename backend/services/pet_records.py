"""Fact-first business-day views and idempotent background aggregation, without AI."""
from collections import Counter
from datetime import date,datetime,time,timedelta
from sqlalchemy import select,or_,and_
import base64,json
from backend.models.pet import PetProfile,PetFactEvent,PetDisplayEntry,PetSnapshot,PetFormalText
from backend.models.user import User
from backend.services.pet_user_service import lock_owner,owner_pet,now_utc,BUSINESS_ZONE,current_config,PetInputError
from backend.services.pet_settlement import iso,aware
from backend.services.pet_persistence import _utc
from backend.services.pet_rule_jobs import enqueue_job,claim_job,execute_job,StaleClaim

INTERACTIONS={'touch','feed','play','joint_ball','joint_photo'}
TITLES={'adopted':'到家了','renamed':'换了一个名字','touch':'轻轻抚摸','feed':'吃了一顿饭','play':'追着小球玩','joint_ball':'一起玩球','joint_photo':'共同留影','joint_player_pass':'你递出了小球','joint_xiaomeng_receive':'小梦接应小球','natural_growth':'自然长大','birthday':'生日日期纪念'}

def fact_view(fact):
    return {'event_id':fact.id,'type':fact.event_type,'title':TITLES.get(fact.event_type,'生活记录'),'source':fact.source,'participants':fact.participants,
        'occurred_at':iso(fact.occurred_at),'recorded_at':iso(fact.recorded_at),'business_date':fact.business_date.isoformat(),
        'result':fact.result,'state_before':fact.state_before,'state_after':fact.state_after,'reaction':fact.reaction,'rule_snapshot_id':fact.rule_snapshot_id}

async def owned(db,user_id):
    await lock_owner(db,user_id);pet=await owner_pet(db,user_id)
    if not pet:raise LookupError('pet_not_found')
    return pet

async def daily_for_pet(db,pet,day,now):
    start=_utc(datetime.combine(day,time.min,tzinfo=BUSINESS_ZONE));end=start+timedelta(days=1)
    facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.business_date==day,PetFactEvent.occurred_at<=_utc(now),PetFactEvent.recorded_at<=_utc(now)).order_by(PetFactEvent.occurred_at,PetFactEvent.id)))
    display=set(await db.scalars(select(PetDisplayEntry.source_event_id).where(PetDisplayEntry.pet_id==pet.id,PetDisplayEntry.surface=='daily')))
    visible=[f for f in facts if f.id in display]
    interactions=[f for f in facts if f.event_type in INTERACTIONS and f.source=='actual_execution' and f.result.get('completed') and not f.result.get('photo_cleared')]
    participants=Counter('joint' if set(f.participants)=={'player','xiaomeng'} else f.participants[0] if f.participants else 'none' for f in interactions)
    snapshots=list(await db.scalars(select(PetSnapshot).where(PetSnapshot.pet_id==pet.id,PetSnapshot.kind.in_(['adoption','photo','observation']),PetSnapshot.captured_at>=start,PetSnapshot.captured_at<end,PetSnapshot.captured_at<=_utc(now)).order_by(PetSnapshot.captured_at,PetSnapshot.id)))
    mood=[s.state.get('values',{}).get('mood') for s in snapshots];mood=[x for x in mood if x is not None]
    summaries=list(await db.scalars(select(PetFormalText).where(PetFormalText.pet_id==pet.id,PetFormalText.kind=='daily',PetFormalText.coverage_start>=start,PetFormalText.coverage_start<end,PetFormalText.recorded_at<=_utc(now)).order_by(PetFormalText.version.desc())))
    latest={}
    from backend.models.pet_text_visibility import PetTextVisibility
    for text in summaries:latest.setdefault(text.business_key,text)
    latest={k:t for k,t in latest.items() if not ((flag:=await db.get(PetTextVisibility,t.id)) and flag.hidden)}
    points=[f.occurred_at for f in visible]+[s.captured_at for s in snapshots]
    settlements=[f for f in facts if f.source=='rule_settlement' and f.event_type=='system_settlement']
    return {'date':day.isoformat(),'today':now.astimezone(BUSINESS_ZONE).date().isoformat(),
        'interaction_counts':dict(Counter(f.event_type for f in interactions)),'participants':dict(participants),
        'timeline':[fact_view(f) for f in visible],
        'state_changes':[{'event_id':f.id,'before':f.state_before,'after':f.state_after} for f in visible if f.state_before!=f.state_after],
        'snapshots':[{'id':s.id,'kind':s.kind,'captured_at':iso(s.captured_at),'state':s.state,'source_event_id':s.source_event_id} for s in snapshots],
        'mood_observation':{'first':mood[0],'last':mood[-1],'minimum':min(mood),'maximum':max(mood),'stable_observed':len(mood)>=2 and min(mood)==max(mood)} if mood else None,
        'coverage_until':iso(max(points)) if points else None,'rule_settlement_until':iso(settlements[-1].occurred_at) if settlements else None,
        'summaries':[{'id':t.id,'version':t.version,'body':t.body,'source_photo_cleared':bool(t.config_snapshot.get('source_photo_cleared')),'coverage_start':iso(t.coverage_start),'coverage_end':iso(t.coverage_end)} for t in latest.values()]}

async def daily(db,user_id,*,day=None,now=None):
    now=now or now_utc();pet=await owned(db,user_id);day=day or now.astimezone(BUSINESS_ZONE).date()
    return await daily_for_pet(db,pet,day,now)

async def detail(db,user_id,event_id,*,origin='daily',origin_date=None):
    pet=await owned(db,user_id)
    fact=await db.scalar(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.id==event_id))
    if not fact:raise LookupError('event_not_found')
    if origin not in {'daily','album'}:raise PetInputError('invalid_record_origin')
    if origin_date:
        try:date.fromisoformat(origin_date)
        except ValueError:raise PetInputError('invalid_record_date')
    return {**fact_view(fact),'historical':await historical_snapshot(db,fact),'return_context':{'surface':origin,'date':origin_date or fact.business_date.isoformat()}}

async def historical_snapshot(db,fact):
    from backend.models.pet import PetRuleSnapshot
    from backend.models.pet_config import PetResource
    from backend.services.pet_scene_resources import verify_resource
    snapshots=list(await db.scalars(select(PetSnapshot).where(PetSnapshot.pet_id==fact.pet_id,PetSnapshot.source_event_id==fact.id,PetSnapshot.kind.in_(['photo','adoption','observation','growth','birthday']))))
    if not snapshots:return {'available':False,'reason':'no_historical_snapshot','image_url':None}
    snapshot=next((s for s in snapshots if s.kind=='photo'),snapshots[0]);resources=snapshot.resources
    value={'snapshot_id':snapshot.id,'name':snapshot.profile.get('name'),'stage':snapshot.profile.get('stage'),'captured_at':iso(snapshot.captured_at),
        'appearance_rule_id':resources.get('appearance_rule_id'),'available':False,'image_url':None}
    if snapshot.kind=='photo':
        from backend.models.pet_photo import PetPhotoAsset
        from backend.services.pet_photo_storage import storage,PhotoStorageError
        asset=await db.get(PetPhotoAsset,resources.get('photo_asset_id')) if resources.get('photo_asset_id') else None
        if not asset or asset.pet_id!=fact.pet_id or asset.state!='archived':return {**value,'reason':'photo_unavailable','kind':'photo'}
        try:url=storage().url(asset.object_key)
        except PhotoStorageError:return {**value,'reason':'storage_unavailable','kind':'photo'}
        return {**value,'available':True,'image_url':url,'resource_version':resources.get('resource_version'),'kind':'photo'}
    appearance=resources.get('appearance')
    if not appearance and resources.get('appearance_rule_id'):
        basis=await db.get(PetRuleSnapshot,resources['appearance_rule_id']);appearance=basis.content if basis else None
    resource_id=appearance.get('stages',{}).get(value['stage']) if appearance else None
    resource=await db.get(PetResource,resource_id) if resource_id else None
    if not resource or not resource.available:return {**value,'reason':'historical_resource_unavailable'}
    try:verify_resource(resource)
    except ValueError:return {**value,'reason':'historical_resource_unavailable'}
    return {**value,'available':True,'image_url':resource.uri,'resource_version':resource.version,'kind':snapshot.kind}

async def album(db,user_id,*,cursor=None,limit=20):
    pet=await owned(db,user_id)
    if not 1<=limit<=50:raise PetInputError('invalid_page_size')
    query=select(PetFactEvent).join(PetDisplayEntry,PetDisplayEntry.source_event_id==PetFactEvent.id).where(PetFactEvent.pet_id==pet.id,PetDisplayEntry.pet_id==pet.id,PetDisplayEntry.surface=='album')
    if cursor:
        try:
            if len(cursor)>512:raise ValueError()
            stamp,identifier=json.loads(base64.urlsafe_b64decode(cursor).decode());stamp=_utc(datetime.fromisoformat(stamp))
            if not isinstance(identifier,str) or len(identifier)>36:raise ValueError()
        except (ValueError,TypeError,UnicodeError):raise PetInputError('invalid_album_cursor')
        query=query.where(or_(PetFactEvent.occurred_at<stamp,and_(PetFactEvent.occurred_at==stamp,PetFactEvent.id<identifier)))
    rows=list(await db.scalars(query.order_by(PetFactEvent.occurred_at.desc(),PetFactEvent.id.desc()).limit(limit+1)))
    page=rows[:limit];next_cursor=None
    if len(rows)>limit:next_cursor=base64.urlsafe_b64encode(json.dumps([iso(page[-1].occurred_at),page[-1].id]).encode()).decode()
    return {'items':[{**fact_view(f),'historical':await historical_snapshot(db,f)} for f in page],'next_cursor':next_cursor}

async def aggregate_day(db,job,*,now):
    pet=await db.get(PetProfile,job.pet_id);day=date.fromisoformat(job.business_key.split(':')[1])
    record=await daily_for_pet(db,pet,day,aware(job.covered_until))
    if not record['timeline'] and not record['snapshots']:return {'organized':False,'reason':'no_evidence','date':day.isoformat()}
    key=job.business_key
    old=await db.scalar(select(PetSnapshot).where(PetSnapshot.pet_id==pet.id,PetSnapshot.business_key==key))
    if old:return {'organized':True,'snapshot_id':old.id,'date':day.isoformat()}
    rules=await current_config(db,'rules',now)
    snapshot=PetSnapshot(pet_id=pet.id,business_key=key,kind='daily_overview',captured_at=_utc(now),profile={'business_date':day.isoformat()},
        state=record,resources={},rule_snapshot_id=rules.snapshot_id)
    db.add(snapshot);await db.flush();return {'organized':True,'snapshot_id':snapshot.id,'date':day.isoformat()}

async def scan_daily(sessions,*,now,owner,limit=100,after=None,clock=None):
    cutoff=_utc(now).replace(minute=(_utc(now).minute//10)*10,second=0,microsecond=0)
    today=now.astimezone(BUSINESS_ZONE).date()
    async with sessions() as db:
        query=select(PetProfile.id).join(User,User.id==PetProfile.user_id).where(User.is_banned.is_(False)).order_by(PetProfile.id).limit(limit)
        if after:query=query.where(PetProfile.id>after)
        ids=list(await db.scalars(query))
    completed=errors=0
    for pet_id in ids:
        for day in [today-timedelta(days=1),today]:
            try:
                async with sessions.begin() as db:job_id=(await enqueue_job(db,pet_id,'daily_overview','daily:'+day.isoformat()+':'+iso(cutoff),aware(cutoff))).id
                claim=await claim_job(sessions,job_id,owner=owner,now=aware(clock()) if clock else now)
                if claim is None:continue
                async def work(db,job):return await aggregate_day(db,job,now=aware(clock()) if clock else now)
                await execute_job(sessions,claim,work,clock=clock or (lambda:now));completed+=1
            except (StaleClaim,ValueError,LookupError,PermissionError):errors+=1
    return {'completed':completed,'errors':errors,'next_cursor':ids[-1] if len(ids)==limit else None}
