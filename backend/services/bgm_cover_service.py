"""Independent optional cover operations; never changes audio execution or enablement."""
import asyncio
from datetime import timedelta
import hashlib,json,time
from fastapi import HTTPException
from sqlalchemy import select
from backend.constants.bgm import COVER_SOURCE_MAX_BYTES,HIDDEN_DELETE_WAIT_SECONDS
from backend.models.bgm import BgmAsset,BgmCatalog,BgmOperation,BgmTrack,new_id,utcnow
from backend.services.bgm_asset_service import object_location
from backend.services.bgm_cover_media import validate_cover_type
from backend.services.bgm_directory_service import matching
from backend.services.bgm_errors import BgmError
from backend.services.bgm_media import MediaError
from backend.services.bgm_process import OwnedWork
from backend.services.bgm_service import operation_detail
from backend.services.bgm_upload_service import (TOTAL_SECONDS,RECEIVE_SECONDS,PROCESS_SECONDS,CLEANUP_SECONDS,
    authorize,locked_slot,release,claim,release_replay,fail,audit)


def digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


async def lock_catalog(db):
    row=await db.scalar(select(BgmCatalog).where(BgmCatalog.id==1).with_for_update())
    if row is None:raise BgmError(20207,503)
    return row


async def checked_track(db,track_id,snapshot,catalog):
    track=await db.scalar(select(BgmTrack).where(BgmTrack.id==track_id).with_for_update())
    if track is None or track.audio_state=='deleted':raise BgmError(20200,404)
    if track.audio_state in {'deleting','delete_failed'}:raise BgmError(20201)
    if track.record_version!=snapshot['expected_revision'] or catalog.catalog_version!=snapshot['expected_catalog_version']:
        raise BgmError(20202)
    return track


async def prepare(sessions,actor,body):
    snapshot=body.model_dump(mode='json',exclude={'operation_id'});request_digest=digest(snapshot)
    async with sessions() as db:
        catalog=await lock_catalog(db);slot=await locked_slot(db);admin=await authorize(db,actor)
        original=await db.get(BgmOperation,str(body.operation_id))
        if original:
            matching(original,actor,request_digest);return await operation_detail(db,original.id)
        if slot.state!='free':raise BgmError(20205,429)
        track=await checked_track(db,str(body.track_id),snapshot,catalog)
        now=utcnow()
        op=BgmOperation(id=str(body.operation_id),admin_id=admin.id,track_id=track.id,action='upload_cover',
            attempt=track.record_version,request_digest=request_digest,request_snapshot={**snapshot,'admin_token_version':actor['token_version'],
                'cover_action':'replace_cover' if track.cover_asset_id else 'add_cover'},
            source_sha256=body.source_sha256,source_size=body.source_size,state='accepted',
            created_at=now,deadline_at=now+timedelta(seconds=TOTAL_SECONDS),receive_deadline_at=now+timedelta(seconds=RECEIVE_SECONDS))
        db.add(op);slot.state='reserved';slot.operation_id=op.id;slot.owner_id=None;slot.attempt=op.attempt
        slot.deadline_at=op.deadline_at;slot.lease_until=op.receive_deadline_at
        await audit(db,admin,op,'accepted');await db.commit()
        return await operation_detail(db,op.id)


async def mark_processing(sessions,operation,work,location):
    async with sessions() as db:
        slot=await locked_slot(db);op=await db.get(BgmOperation,operation.id)
        if not op or op.state!='receiving' or op.owner_id!=work.owner or slot.owner_id!=work.owner or slot.operation_id!=op.id or op.deadline_at<=utcnow():
            raise MediaError('stale_attempt')
        op.state=slot.state='processing'
        asset=BgmAsset(id=new_id(),track_id=op.track_id,operation_id=op.id,attempt=op.attempt,kind='cover',
            version=location['object_key'].rsplit('/',1)[1].removesuffix('.webp'),**location)
        db.add(asset);await db.commit();return asset.id


async def retire_current(db,track):
    if not track.cover_asset_id:return False
    old=await db.get(BgmAsset,track.cover_asset_id)
    if not old or old.track_id!=track.id or old.kind!='cover':raise BgmError(20207,503)
    old.retired_at=utcnow();old.not_before=old.retired_at+timedelta(seconds=HIDDEN_DELETE_WAIT_SECONDS)
    old.cleanup_state='pending'
    return True


async def result_snapshot(db,track,catalog,url):
    pending=await db.scalar(select(BgmAsset.id).where(BgmAsset.track_id==track.id,BgmAsset.kind=='cover',
                                  BgmAsset.cleanup_state.in_(['pending','failed'])).limit(1))
    return dict(track_id=track.id,record_version=track.record_version,cover_version=track.cover_version,
        cover_url=url,catalog_version=catalog.catalog_version,association_removed=track.cover_asset_id is None,
        cleanup_state='pending' if pending else 'not_requested')


async def finish(sessions,actor,operation,work,asset_id,metadata):
    async with sessions() as db:
        catalog=await lock_catalog(db);slot=await locked_slot(db);admin=await authorize(db,actor)
        op=await db.get(BgmOperation,operation.id)
        if not op or op.state!='processing' or op.owner_id!=work.owner or slot.owner_id!=work.owner or slot.operation_id!=op.id or op.deadline_at<=utcnow():raise MediaError('stale_attempt')
        if op.request_snapshot['admin_token_version']!=actor['token_version']:raise HTTPException(401,'提交会话已失效')
        track=await checked_track(db,op.track_id,op.request_snapshot,catalog)
        asset=await db.get(BgmAsset,asset_id)
        if not asset or asset.operation_id!=op.id or asset.track_id!=track.id or asset.kind!='cover':raise MediaError('invalid_asset')
        await retire_current(db,track)
        asset.state='ready';asset.sha256=metadata['sha256'];asset.size_bytes=metadata['size_bytes'];asset.mime_type=metadata['mime_type']
        track.cover_asset_id=asset.id;track.cover_version=asset.version;track.record_version+=1
        if track.enabled:catalog.catalog_version+=1
        op.state='succeeded';op.finished_at=utcnow();op.result=await result_snapshot(db,track,catalog,asset.public_url)
        release(slot);await audit(db,admin,op,'succeeded');await db.commit()
        if track.enabled:
            from backend.services.bgm_catalog_service import invalidate
            await invalidate(catalog.catalog_version)


async def receive(sessions,actor,operation_id,request):
    work=OwnedWork();operation=None;outcome_saved=False;replay=False
    try:
        operation,replay=await claim(sessions,actor,operation_id,work)
        snapshot=operation.request_snapshot
        validate_cover_type(snapshot['extension'],request.headers.get('content-type','').split(';')[0].lower())
        remaining=RECEIVE_SECONDS if replay else min((operation.receive_deadline_at-utcnow()).total_seconds(),(operation.deadline_at-utcnow()).total_seconds()-CLEANUP_SECONDS)
        received=hashlib.sha256();size=0
        async with asyncio.timeout(max(0,remaining)):
            with (work.directory/'source').open('wb') as stream:
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>COVER_SOURCE_MAX_BYTES or size>operation.source_size:raise MediaError('cover_size_limit')
                    stream.write(chunk);received.update(chunk)
        if size!=operation.source_size or received.hexdigest()!=operation.source_sha256:raise MediaError('source_mismatch')
        if replay:
            await work.stop();await release_replay(sessions,operation.id,work.owner,stopped=True)
        else:
            location=object_location(operation.track_id,new_id(),'cover')
            asset_id=await mark_processing(sessions,operation,work,location)
            remaining=min(PROCESS_SECONDS,(operation.deadline_at-utcnow()).total_seconds())-CLEANUP_SECONDS
            if remaining<=0:raise MediaError('processing_timeout')
            metadata=await work.run(dict(kind='cover',extension=snapshot['extension'],mime_type=snapshot['mime_type'],location=location,deadline_monotonic=time.monotonic()+remaining))
            await finish(sessions,actor,operation,work,asset_id,metadata)
        outcome_saved=True
    except BaseException as exc:
        try:await work.stop()
        finally:
            if operation:
                category=(str(exc) if isinstance(exc,MediaError) else 'version_conflict' if isinstance(exc,BgmError) and exc.code==20202 else
                    'authorization_changed' if isinstance(exc,HTTPException) else 'receive_timeout' if isinstance(exc,TimeoutError) else 'interrupted')
                if replay:await release_replay(sessions,operation.id,work.owner,stopped=work.quiescent)
                else:await fail(sessions,operation.id,work.owner,category,stopped=work.quiescent)
                outcome_saved=True
        if replay and isinstance(exc,MediaError):raise BgmError(20203) from None
        if isinstance(exc,HTTPException) or not isinstance(exc,Exception) or operation is None:raise
    finally:
        if not work.quiescent:await work.stop()
        if work.quiescent:work.close(preserve_receipt=operation is not None and not outcome_saved)
    async with sessions() as db:return await operation_detail(db,operation_id)


async def remove(sessions,actor,track_id,body):
    snapshot={**body.model_dump(mode='json',exclude={'operation_id'}),'action':'remove_cover','track_id':track_id}
    request_digest=digest(snapshot);operation_id=str(body.operation_id)
    try:
        async with sessions() as db:
            catalog=await lock_catalog(db);admin=await authorize(db,actor)
            original=await db.get(BgmOperation,operation_id)
            if original:
                matching(original,actor,request_digest);return await operation_detail(db,original.id)
            track=await checked_track(db,track_id,snapshot,catalog)
            await retire_current(db,track)
            track.cover_asset_id=None;track.cover_version=new_id();track.record_version+=1
            if track.enabled:catalog.catalog_version+=1
            op=BgmOperation(id=operation_id,admin_id=admin.id,track_id=track_id,action='remove_cover',
                request_digest=request_digest,request_snapshot=snapshot,state='succeeded',finished_at=utcnow(),
                result=await result_snapshot(db,track,catalog,None))
            db.add(op);await audit(db,admin,op,'succeeded');await db.commit()
            if track.enabled:
                from backend.services.bgm_catalog_service import invalidate
                await invalidate(catalog.catalog_version)
            return await operation_detail(db,op.id)
    except (BgmError,HTTPException):raise
    except Exception:
        async with sessions() as db:
            await authorize(db,actor);op=await db.get(BgmOperation,operation_id)
            if op:
                matching(op,actor,request_digest)
                if op.state=='succeeded':return await operation_detail(db,op.id)
        raise
