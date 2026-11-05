"""Prepared scene captures are archived explicitly; no image generation or reward."""
import base64, binascii, io, asyncio
from hashlib import sha256
from datetime import timedelta
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from backend.models.pet import PetSnapshot
from backend.models.pet_photo import PetPhotoAsset,PetPhotoDeleteJob
from backend.services.pet_photo_storage import storage,PhotoStorageError
from backend.models.pet_config import PetConfigVersion
from backend.models.pet_interaction import PetInteraction
from backend.services.pet_interactions import context,get_attempt,response
from backend.services.pet_joint_service import require_scene,clear_expired,valid_running,end
from backend.services.pet_user_service import now_utc,stable_key,current_config,runtime_flags,PetInputError,PetConflict,PetDisabled
from backend.services.pet_persistence import FactCommand,append_fact,_utc
from backend.services.pet_settlement import settle_pet,iso

def validate_image(data_url):
    if not isinstance(data_url,str) or len(data_url)>3_000_000:raise PetInputError('invalid_photo')
    try:
        prefix,encoded=data_url.split(',',1)
        if prefix not in {'data:image/jpeg;base64','data:image/png;base64'}:raise ValueError()
        data=base64.b64decode(encoded,validate=True)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'JPEG','PNG'} or not (32<=image.width<=2048 and 32<=image.height<=4096):raise ValueError()
            image.load()
            if all(lo==hi for lo,hi in image.convert('RGB').getextrema()):raise ValueError()
            size=[image.width,image.height]
    except (ValueError,UnidentifiedImageError,OSError,binascii.Error,Image.DecompressionBombError):raise PetInputError('invalid_or_empty_photo')
    return {'sha256':sha256(data).hexdigest(),'size':size}

async def owned_photo(db,user_id,attempt_id):
    pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    if attempt.kind!='photo':raise PetInputError('not_photo')
    return pet,state,attempt

async def start(db,user_id,*,request_key,resources_ready,now=None):
    now=now or now_utc();stable_key(request_key);pet,state=await context(db,user_id)
    old=await db.scalar(select(PetInteraction).where(PetInteraction.pet_id==pet.id,PetInteraction.request_key==request_key))
    if old:
        if old.kind!='photo':raise PetConflict('request_content_changed')
        return await photo_response(db,old,pet,state)
    if not (await runtime_flags(db,now))['interactions_enabled']:raise PetDisabled('interactions_disabled')
    await clear_expired(db,state,now);await settle_pet(db,pet.id,user_id,until=now);await require_scene(db,state,resources_ready)
    rules=await current_config(db,'rules',now)
    attempt=PetInteraction(pet_id=pet.id,request_key=request_key,kind='photo',state='pending',config_id=rules.id,pet_data_version=pet.data_version,
        started_at=_utc(now),expires_at=_utc(now)+timedelta(seconds=120),payload={'prepared':False,'captured':False,'storage':'oss-v1'})
    db.add(attempt);await db.flush();state.active_activity={'id':attempt.id,'kind':'photo'};await db.flush();return await photo_response(db,attempt,pet,state)

async def prepare(db,user_id,attempt_id,*,now=None):
    now=now or now_utc();pet,state,a=await owned_photo(db,user_id,attempt_id)
    if await valid_running(db,pet,state,a,now):
        a.payload={**a.payload,'prepared':True,'prepared_at':iso(now),'preparation':'quiet_gaze' if state.values['energy']<20 else 'stand_ready'}
    await db.flush();return await photo_response(db,a,pet,state)

async def photo_response(db,a,pet,state):
    value=await response(db,a,pet,state)
    asset=await db.get(PetPhotoAsset,a.id)
    if asset and a.state not in {'pending','done'} and asset.state not in {'archived','delete_pending','deleted'}:await queue_delete(db,asset,'attempt_'+a.state)
    value['photo']={'id':asset.id,'state':asset.state,'url':None} if asset else None
    if asset and asset.state in {'ready','archived'}:
        try:value['photo']['url']=storage().url(asset.object_key)
        except PhotoStorageError:value['photo']['reason']='storage_unavailable'
    return value

async def queue_delete(db,asset,reason):
    if asset.state=='archived' and reason!='account_deleted':return
    asset.state='delete_pending';asset.generation+=1
    job=await db.get(PetPhotoDeleteJob,asset.id)
    if not job:
        job=PetPhotoDeleteJob(id=asset.id,bucket=asset.bucket,namespace=asset.namespace,object_key=asset.object_key,reason=reason)
        db.add(job)
    else:job.state='pending';job.reason=reason;job.next_check_at=now_utc().replace(tzinfo=None)

async def capture(sessions,user_id,attempt_id,*,snapshot,resources_ready,now=None):
    now=now or now_utc();remote=storage()
    validation=validate_image(snapshot.get('data_url'))
    raw=base64.b64decode(snapshot['data_url'].split(',',1)[1],validate=True)
    mime='image/png' if snapshot['data_url'].startswith('data:image/png;') else 'image/jpeg'
    # Commit the exact-key intent before doing any external I/O.
    async with sessions.begin() as db:
        pet,state,a=await owned_photo(db,user_id,attempt_id)
        if not await valid_running(db,pet,state,a,now):return await photo_response(db,a,pet,state)
        if not a.payload.get('prepared'):raise PetInputError('preparation_required')
        appearance=await require_scene(db,state,resources_ready)
        if snapshot.get('stage')!=state.stage or snapshot.get('record_version')!=state.record_version:raise PetConflict('scene_snapshot_stale')
        from backend.models.pet_config import PetResource
        resource=await db.get(PetResource,appearance.content['stages'][state.stage])
        if snapshot.get('resource_version')!=resource.version:raise PetConflict('resource_version_changed')
        asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==a.id).with_for_update())
        if asset:
            if asset.sha256!=validation['sha256']:raise PetConflict('capture_already_saved')
            return await photo_response(db,a,pet,state)
        key=remote.object_key(pet.id,a.id,validation['sha256'],mime)
        asset=PetPhotoAsset(id=a.id,pet_id=pet.id,bucket=remote.bucket_name,namespace=remote.namespace,object_key=key,
            sha256=validation['sha256'],mime_type=mime,size_bytes=len(raw),width=validation['size'][0],height=validation['size'][1],
            state='uploading',generation=1,expires_at=_utc(now)+timedelta(hours=24),lease_until=_utc(now)+timedelta(minutes=2))
        db.add(asset)
        a.payload={**a.payload,'captured_at':iso(now),'profile':{'name':pet.name,'stage':state.stage,'birth_date':pet.birth_date.isoformat(),'adopted_at':iso(pet.adopted_at)},
            'state':{'values':dict(state.values),'record_version':state.record_version,'pose':'low-energy' if state.values['energy']<20 else 'standing'},
            'resources':{'appearance_rule_id':state.appearance_rule_id,'appearance':appearance.content,'resource_version':resource.version,'photo_asset_id':a.id},'image':validation}
        generation=asset.generation
    failure=None
    try:await asyncio.to_thread(remote.put_verified,key,raw,validation['sha256'],mime)
    except PhotoStorageError as error:failure=str(error)
    # Reacquire ownership/version fences; an old PUT cannot revive a cancelled photo.
    async with sessions.begin() as db:
        pet,state,a=await owned_photo(db,user_id,attempt_id)
        asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==attempt_id).with_for_update())
        if asset:
            asset.upload_finished_at=_utc(now_utc())
            if asset.generation!=generation or not await valid_running(db,pet,state,a,now):
                await queue_delete(db,asset,'upload_obsolete')
            elif failure and asset.state!='ready':asset.state='unknown'
            else:asset.state='ready';a.payload={**a.payload,'captured':True}
        await db.flush();return await photo_response(db,a,pet,state)

async def photo_status(sessions,user_id,attempt_id,*,now=None):
    now=now or now_utc()
    async with sessions() as db:
        pet,state,a=await owned_photo(db,user_id,attempt_id)
        asset=await db.get(PetPhotoAsset,attempt_id)
        probe=(asset.object_key,asset.sha256,asset.size_bytes,asset.generation) if asset and asset.state in {'unknown','uploading'} else None
    verified=False
    if probe:
        try:verified=await asyncio.to_thread(storage().head,*probe[:3])
        except PhotoStorageError:pass
    async with sessions.begin() as db:
        pet,state,a=await owned_photo(db,user_id,attempt_id)
        asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==attempt_id).with_for_update())
        if probe and verified and asset and asset.state in {'unknown','uploading'} and asset.generation==probe[3]:
            if await valid_running(db,pet,state,a,now):asset.state='ready';a.payload={**a.payload,'captured':True}
            else:await queue_delete(db,asset,'upload_obsolete')
        await db.flush();return await photo_response(db,a,pet,state)

async def archive(db,user_id,attempt_id,*,resources_ready,now=None):
    now=now or now_utc();pet,state,a=await owned_photo(db,user_id,attempt_id)
    if not await valid_running(db,pet,state,a,now):return await photo_response(db,a,pet,state)
    await require_scene(db,state,resources_ready)
    if not a.payload.get('captured'):raise PetInputError('capture_required')
    asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==a.id).with_for_update())
    if not asset or asset.state!='ready':raise PetInputError('photo_not_ready')
    # Validate the captured resource references too; current assets cannot substitute them.
    from backend.models.pet_config import PetResource
    from backend.services.pet_scene_resources import verify_resource
    for key in a.payload['resources']['appearance']['stages'].values():
        resource=await db.get(PetResource,key)
        if not resource or not resource.available:raise PetInputError('captured_resource_unavailable')
        verify_resource(resource)
    rules=await db.get(PetConfigVersion,a.config_id)
    from backend.services.pet_activity import activity_for
    await activity_for(db,pet)
    fact=await append_fact(db,FactCommand(pet_id=pet.id,user_id=user_id,request_key='photo:'+a.id,business_key='photo:'+a.id,expected_version=state.record_version,
        event_type='joint_photo',source='actual_execution',participants=('player','xiaomeng'),occurred_at=now,
        result={'completed':True,'active_eligible':True,'name':a.payload['profile']['name'],'captured_at':a.payload['captured_at'],'image_sha256':a.payload['image']['sha256'],
                'contributions':{'player':'prepared_and_captured','xiaomeng':'positioned_camera'}},state_after=state.values,closeness_delta=0,rule_snapshot_id=rules.snapshot_id,display_surfaces=('daily','album')))
    from datetime import datetime
    db.add(PetSnapshot(pet_id=pet.id,business_key='photo:'+a.id,kind='photo',source_event_id=fact.id,captured_at=_utc(datetime.fromisoformat(a.payload['captured_at'])),
        profile=a.payload['profile'],state=a.payload['state'],resources=a.payload['resources'],rule_snapshot_id=rules.snapshot_id))
    from backend.services.pet_activity import mark_active
    await mark_active(db,pet,now,source_event=fact)
    asset.state='archived';asset.archived_at=_utc(now)
    a.state='done';a.event_id=fact.id;a.result=fact.result;state.active_activity=None;await db.flush();return await photo_response(db,a,pet,state)

async def cancel(db,user_id,attempt_id):
    pet,state,a=await owned_photo(db,user_id,attempt_id)
    if a.state=='pending':
        end(a,state,'cancelled','user_cancelled')
        asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==a.id).with_for_update())
        if asset:await queue_delete(db,asset,'user_cancelled')
    await db.flush();return await photo_response(db,a,pet,state)

async def claim_growth_prompt(db,user_id,*,now=None):
    now=now or now_utc();pet,state=await context(db,user_id)
    await settle_pet(db,pet.id,user_id,until=now)
    if state.stage=='puppy':return {'show':False}
    key='growth-prompt:'+state.stage
    if await db.scalar(select(PetInteraction.id).where(PetInteraction.pet_id==pet.id,PetInteraction.request_key==key)):return {'show':False}
    rules=await current_config(db,'rules',now)
    db.add(PetInteraction(pet_id=pet.id,request_key=key,kind='growth_prompt',state='shown',config_id=rules.id,pet_data_version=pet.data_version,
        started_at=_utc(now),expires_at=_utc(now),payload={'stage':state.stage},result={'completed':False,'active_eligible':False}))
    await db.flush();return {'show':True,'stage':state.stage}


async def cleanup_objects(sessions,*,now=None,limit=50):
    now=_utc(now or now_utc());completed=failed=0
    async with sessions.begin() as db:
        expired=list(await db.scalars(select(PetPhotoAsset).where(PetPhotoAsset.expires_at<=now,PetPhotoAsset.state.in_(['uploading','unknown','ready'])).limit(limit).with_for_update()))
        for asset in expired:
            if asset.upload_finished_at or asset.lease_until<=now:await queue_delete(db,asset,'expired')
        await db.flush()
    async with sessions() as db:
        ids=list(await db.scalars(select(PetPhotoDeleteJob.id).where(PetPhotoDeleteJob.next_check_at<=now).limit(limit)))
    for identifier in ids:
        async with sessions.begin() as db:
            asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==identifier).with_for_update())
            job=await db.scalar(select(PetPhotoDeleteJob).where(PetPhotoDeleteJob.id==identifier).with_for_update())
            if not job or job.next_check_at>now:continue
            if asset and (asset.state=='archived' or (asset.upload_finished_at is None and asset.lease_until>now)):continue
            job.state='running';job.attempts+=1;job.next_check_at=now+timedelta(minutes=5)
            key=job.object_key;bucket=job.bucket;namespace=job.namespace
        error=None
        try:
            remote=storage()
            if bucket!=remote.bucket_name or namespace!=remote.namespace:raise PhotoStorageError('storage_configuration')
            await asyncio.to_thread(remote.delete,key)
        except PhotoStorageError as e:error=str(e)
        async with sessions.begin() as db:
            asset=await db.scalar(select(PetPhotoAsset).where(PetPhotoAsset.id==identifier).with_for_update())
            job=await db.scalar(select(PetPhotoDeleteJob).where(PetPhotoDeleteJob.id==identifier).with_for_update())
            if job.state!='running':continue
            job.state='pending' if error else 'deleted';job.next_check_at=now+timedelta(hours=1)
            if not error:
                job.confirmed_at=now
                if asset:asset.state='deleted'
                completed+=1
            else:failed+=1
    return {'completed':completed,'failed':failed}
