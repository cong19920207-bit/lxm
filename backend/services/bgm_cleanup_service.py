"""Manual, bounded cleanup of registered BGM assets. No expiry-triggered deletes."""
from datetime import timedelta
import time
from fastapi import HTTPException
from sqlalchemy import func, select, or_

from backend.constants.bgm import HIDDEN_DELETE_WAIT_SECONDS
from backend.models.admin_user import AdminUser
from backend.models.bgm import BgmAsset, BgmCatalog, BgmOperation, BgmTrack, utcnow
from backend.schemas.bgm import utc_iso
from backend.services.bgm_cover_service import lock_catalog, digest
from backend.services.bgm_directory_service import matching
from backend.services.bgm_errors import BgmError
from backend.services.bgm_media import MediaError
from backend.services.bgm_process import OwnedWork
from backend.services.bgm_service import operation_detail
from backend.services.bgm_upload_service import authorize, locked_slot, release, audit, CLEANUP_SECONDS

CLEANUP_TOTAL_SECONDS = 180
OBJECT_SECONDS = 25
MAX_OBJECTS = 100
ACTIVE = ('accepted','receiving','processing')


def eligible(track, now):
    if track.enabled or track.active_operation_id or track.audio_state not in {'ready','failed'}:
        return False
    return not track.ever_published or bool(track.hidden_at and
        now >= track.hidden_at + timedelta(seconds=HIDDEN_DELETE_WAIT_SECONDS))


def candidates(track, mode, now):
    clauses = [BgmAsset.track_id==track.id, BgmAsset.cleanup_state!='deleted']
    if mode=='cleanup_assets':
        clauses += [BgmAsset.cleanup_state.in_(['pending','failed']),
                    or_(BgmAsset.not_before.is_(None),BgmAsset.not_before<=now)]
        for current in [track.audio_asset_id,track.cover_asset_id]:
            if current:clauses.append(BgmAsset.id!=current)
    return clauses


def asset_projection(asset):
    return dict(id=asset.id,kind=asset.kind,cleanup_state=asset.cleanup_state,failure_category=asset.failure_category)


async def status(db, track_id, page=1, page_size=20):
    track=await db.get(BgmTrack,track_id)
    if not track:return None
    now=utcnow();catalog=await db.get(BgmCatalog,1)
    active=await db.scalar(select(BgmOperation.id).where(BgmOperation.track_id==track.id,BgmOperation.state.in_(ACTIVE)).limit(1))
    total=await db.scalar(select(func.count()).select_from(BgmAsset).where(BgmAsset.track_id==track.id))
    assets=(await db.scalars(select(BgmAsset).where(BgmAsset.track_id==track.id).order_by(BgmAsset.id)
                            .offset((page-1)*page_size).limit(page_size))).all()
    mode='delete_track' if track.audio_state in {'deleting','delete_failed'} else 'cleanup_assets'
    remaining=await db.scalar(select(func.count()).select_from(BgmAsset).where(*candidates(track,mode,now)))
    return dict(track_id=track.id,name=track.name,record_version=track.record_version,
        catalog_version=catalog.catalog_version if catalog else 0,audio_state=track.audio_state,
        server_time=utc_iso(now),hidden_at=utc_iso(track.hidden_at),
        deletable_at=utc_iso(track.hidden_at+timedelta(seconds=HIDDEN_DELETE_WAIT_SECONDS)) if track.ever_published and track.hidden_at else None,
        can_delete=eligible(track,now) and not active,
        can_cleanup=track.audio_state!='deleted' and not active and (bool(remaining) or mode=='delete_track'),
        list=[{**asset_projection(a), 'version':a.version,'not_before':utc_iso(a.not_before)} for a in assets],
        total=total,page=page,page_size=page_size)


async def begin(sessions,actor,track_id,body,action,work):
    snapshot={**body.model_dump(mode='json',exclude={'operation_id'}),'action':action,'track_id':track_id}
    request_digest=digest(snapshot)
    async with sessions() as db:
        catalog=await lock_catalog(db);slot=await locked_slot(db);admin=await authorize(db,actor)
        original=await db.get(BgmOperation,str(body.operation_id))
        if original:
            matching(original,actor,request_digest)
            return original,False
        if slot.state!='free':raise BgmError(20205,429)
        track=await db.scalar(select(BgmTrack).where(BgmTrack.id==track_id).with_for_update())
        if not track or track.audio_state=='deleted':raise BgmError(20200,404)
        if track.record_version!=body.expected_revision or catalog.catalog_version!=body.expected_catalog_version:raise BgmError(20202)
        active=await db.scalar(select(BgmOperation.id).where(BgmOperation.track_id==track.id,BgmOperation.state.in_(ACTIVE)).limit(1))
        if active or track.active_operation_id:raise BgmError(20201)
        now=utcnow()
        mode='delete_track' if action=='delete_track' or track.audio_state in {'deleting','delete_failed'} else 'cleanup_assets'
        if action=='delete_track' and not eligible(track,now):raise BgmError(20201)
        if mode=='delete_track' and track.enabled:raise BgmError(20201)
        if mode=='cleanup_assets' and track.audio_state not in {'ready','failed'}:raise BgmError(20201)
        assets=(await db.scalars(select(BgmAsset).where(*candidates(track,mode,now)).order_by(BgmAsset.id).limit(MAX_OBJECTS).with_for_update())).all()
        if mode=='cleanup_assets' and not assets:raise BgmError(20201)
        if mode=='delete_track':
            track.audio_state='deleting';track.sort_position=None;track.attempt+=1;track.record_version+=1
        for asset in assets:asset.cleanup_state='deleting';asset.failure_category=None
        op=BgmOperation(id=str(body.operation_id),admin_id=admin.id,action=action,track_id=track.id,
            request_digest=request_digest,request_snapshot={**snapshot,'mode':mode,'asset_ids':[a.id for a in assets]},
            attempt=track.record_version,owner_id=work.owner,state='processing',
            deadline_at=now+timedelta(seconds=CLEANUP_TOTAL_SECONDS),receive_deadline_at=now)
        db.add(op)
        slot.state='processing';slot.operation_id=op.id;slot.owner_id=work.owner;slot.attempt=op.attempt
        slot.deadline_at=slot.lease_until=op.deadline_at
        op.result=await snapshot_result(db,op,track)
        await audit(db,admin,op,'accepted');await db.commit()
        return op,True


async def snapshot_result(db,op,track):
    await db.flush()
    ids=op.request_snapshot['asset_ids']
    assets=(await db.scalars(select(BgmAsset).where(BgmAsset.id.in_(ids)).order_by(BgmAsset.id))).all() if ids else []
    # Nonselected assets remain durably located; a bounded batch never claims
    # full completion while more eligible objects remain.
    remaining=await db.scalar(select(func.count()).select_from(BgmAsset).where(*candidates(track,op.request_snapshot['mode'],utcnow())))
    if op.request_snapshot['mode']=='cleanup_assets':
        remaining += sum(a.cleanup_state=='deleting' for a in assets)
    return dict(track_id=track.id,record_version=track.record_version,mode=op.request_snapshot['mode'],
                track_deleted=track.audio_state=='deleted',remaining_count=remaining,assets=[asset_projection(a) for a in assets])


def qualified(slot,op,owner):
    if not op or op.state!='processing' or op.owner_id!=owner or slot.owner_id!=owner or slot.operation_id!=op.id:
        raise MediaError('stale_attempt')


async def next_asset(sessions,actor,operation_id,owner,asset_id):
    async with sessions() as db:
        await lock_catalog(db);slot=await locked_slot(db);await authorize(db,actor)
        op=await db.get(BgmOperation,operation_id);qualified(slot,op,owner)
        if op.deadline_at<=utcnow()+timedelta(seconds=CLEANUP_SECONDS):raise MediaError('processing_timeout')
        track=await db.get(BgmTrack,op.track_id);asset=await db.get(BgmAsset,asset_id)
        if not track or not asset or asset.track_id!=track.id or asset_id not in op.request_snapshot['asset_ids']:raise MediaError('asset_ownership')
        if op.request_snapshot['mode']=='cleanup_assets' and asset_id in {track.audio_asset_id,track.cover_asset_id}:raise MediaError('asset_ownership')
        if op.request_snapshot['mode']=='delete_track' and (track.enabled or track.audio_state!='deleting'):raise MediaError('stale_attempt')
        return {key:getattr(asset,key) for key in ['id','track_id','kind','version','bucket','object_key']}


async def record_asset(sessions,operation_id,owner,asset_id,category):
    async with sessions() as db:
        await lock_catalog(db);slot=await locked_slot(db)
        op=await db.get(BgmOperation,operation_id);qualified(slot,op,owner)
        asset=await db.get(BgmAsset,asset_id)
        if not asset or asset.track_id!=op.track_id or asset_id not in op.request_snapshot['asset_ids']:raise MediaError('asset_ownership')
        asset.cleanup_state='failed' if category else 'deleted';asset.failure_category=category
        if not category:asset.state='deleted'
        track=await db.get(BgmTrack,op.track_id);op.result=await snapshot_result(db,op,track)
        await db.commit()


async def finish(sessions,operation_id,owner):
    async with sessions() as db:
        await lock_catalog(db);slot=await locked_slot(db)
        op=await db.get(BgmOperation,operation_id);qualified(slot,op,owner)
        track=await db.get(BgmTrack,op.track_id)
        result=await snapshot_result(db,op,track);complete=result['remaining_count']==0
        if op.request_snapshot['mode']=='delete_track':
            track.audio_state='deleted' if complete else 'delete_failed';track.record_version+=1
            if complete:track.audio_asset_id=track.cover_asset_id=None
        op.state='succeeded' if complete else 'failed';op.finished_at=utcnow()
        op.failure_category=None if complete else 'cleanup_incomplete'
        op.result=await snapshot_result(db,op,track);release(slot)
        admin=await db.get(AdminUser,op.admin_id)
        if admin:await audit(db,admin,op,op.state,op.failure_category)
        await db.commit()


async def fail(sessions,operation_id,owner,category,*,stopped):
    async with sessions() as db:
        await lock_catalog(db);slot=await locked_slot(db);op=await db.get(BgmOperation,operation_id)
        if not op or op.owner_id!=owner or op.state=='succeeded':return
        was_failed=op.state=='failed';track=await db.get(BgmTrack,op.track_id)
        for aid in op.request_snapshot['asset_ids']:
            asset=await db.get(BgmAsset,aid)
            if asset and asset.track_id==op.track_id and asset.cleanup_state=='deleting':
                asset.cleanup_state='failed';asset.failure_category=category
        if track and op.request_snapshot['mode']=='delete_track' and track.audio_state=='deleting':
            track.audio_state='delete_failed';track.record_version+=1
        op.state='failed';op.finished_at=utcnow();op.failure_category=category
        op.result=await snapshot_result(db,op,track)
        if slot.operation_id==op.id and slot.owner_id==owner:
            if stopped:release(slot)
            else:slot.state='quarantined'
        admin=await db.get(AdminUser,op.admin_id)
        if admin and not was_failed:await audit(db,admin,op,'failed',category)
        await db.commit()


async def execute(sessions,actor,track_id,body,action):
    work=OwnedWork();settled=False;operation_id=str(body.operation_id)
    try:
        operation,created=await begin(sessions,actor,track_id,body,action,work)
        if created:
            deadline=time.monotonic()+max(0,(operation.deadline_at-utcnow()).total_seconds()-CLEANUP_SECONDS)
            for aid in operation.request_snapshot['asset_ids']:
                asset=await next_asset(sessions,actor,operation_id,work.owner,aid)
                category=None
                try:
                    result=await work.run(dict(kind='cleanup',asset=asset,deadline_monotonic=min(deadline,time.monotonic()+OBJECT_SECONDS)))
                    if result!={'deleted':True}:raise MediaError('cleanup_not_confirmed')
                except MediaError as exc:
                    if not work.quiescent:raise
                    category=str(exc)
                await record_asset(sessions,operation_id,work.owner,aid,category)
            await work.stop()
            await finish(sessions,operation_id,work.owner)
        settled=True
    except BaseException as exc:
        await work.stop()
        category=str(exc) if isinstance(exc,MediaError) else 'authorization_changed' if isinstance(exc,HTTPException) else 'interrupted'
        await fail(sessions,operation_id,work.owner,category,stopped=work.quiescent)
        settled=True
        if isinstance(exc,(BgmError,HTTPException)) or not isinstance(exc,Exception):raise
        async with sessions() as db:
            op=await db.get(BgmOperation,operation_id)
            if not op:raise
    finally:
        if not work.quiescent:await work.stop()
        work.close(preserve_receipt=not settled)
    async with sessions() as db:
        await authorize(db,actor)
        return await operation_detail(db,operation_id)
