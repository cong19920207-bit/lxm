"""Catalog row serializes atomic default, order and track mutations; no external I/O."""
import hashlib
import json
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select
from backend.constants.bgm import AUDIO_OUTPUT_MAX_BYTES, AUDIO_MAX_SECONDS
from backend.models.bgm import BgmCatalog, BgmTrack, BgmOperation, BgmAsset, utcnow
from backend.services.bgm_errors import BgmError
from backend.services.bgm_service import operation_detail
from backend.services.bgm_upload_service import authorize
from backend.utils.admin_auth import log_operation


async def read_order(db):
    # One statement: header and complete active order cannot come from different
    # commits, including on READ COMMITTED deployments and an empty catalog.
    rows=(await db.execute(select(BgmCatalog.catalog_version,BgmCatalog.default_track_id,BgmTrack)
        .outerjoin(BgmTrack,BgmTrack.enabled.is_(True)).where(BgmCatalog.id==1)
        .order_by(BgmTrack.sort_position,BgmTrack.id))).all()
    if not rows:
        return dict(catalog_version=0,default_track_id=None,tracks=[])
    return dict(catalog_version=rows[0][0],default_track_id=rows[0][1],
                tracks=[dict(id=t.id,name=t.name,record_version=t.record_version) for _,_,t in rows if t])


async def verified_audio(db, track):
    if track.audio_state!='ready' or track.active_operation_id or not track.audio_asset_id:
        return False
    asset=await db.get(BgmAsset,track.audio_asset_id)
    return bool(asset and asset.kind=='audio' and asset.track_id==track.id and asset.state=='ready'
        and asset.version==track.media_version and asset.retired_at is None
        and asset.cleanup_state=='not_requested' and asset.mime_type=='audio/mp4'
        and asset.sha256 and len(asset.sha256)==64
        and isinstance(track.size_bytes,int) and asset.size_bytes==track.size_bytes and 0<track.size_bytes<=AUDIO_OUTPUT_MAX_BYTES
        and track.duration_seconds and 0<track.duration_seconds<=AUDIO_MAX_SECONDS
        and urlsplit(asset.public_url or '').scheme=='https' and urlsplit(asset.public_url or '').hostname)


def matching(operation, actor, digest):
    if operation.admin_id!=actor['id'] or operation.request_digest!=digest:
        raise BgmError(20203)


async def mutate(sessions,actor,body,*,track_id=None):
    action=body.action if track_id else 'reorder'
    snapshot={**body.model_dump(mode='json',exclude={'operation_id'}),'action':action,'track_id':track_id}
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    operation_id=str(body.operation_id)
    try:
        return await _mutate(sessions,actor,operation_id,snapshot,digest)
    except (BgmError,HTTPException):
        raise
    except Exception:
        # A commit response can be lost after the database durably succeeded.
        # Recheck that exact actor + immutable snapshot; never issue a new action.
        async with sessions() as db:
            await authorize(db,actor)
            original=await db.get(BgmOperation,operation_id)
            if original:
                matching(original,actor,digest)
                if original.state=='succeeded':return await operation_detail(db,operation_id)
        raise


async def _mutate(sessions,actor,operation_id,snapshot,digest):
    async with sessions() as db:
        catalog=await db.scalar(select(BgmCatalog).where(BgmCatalog.id==1).with_for_update())
        if catalog is None:raise BgmError(20207,503)
        admin=await authorize(db,actor)
        original=await db.get(BgmOperation,operation_id)
        if original:
            matching(original,actor,digest)
            return await operation_detail(db,operation_id)
        if catalog.catalog_version!=snapshot['expected_catalog_version']:raise BgmError(20202)
        # Every catalog writer takes catalog first, then track rows in ID order.
        tracks=(await db.scalars(select(BgmTrack).where(BgmTrack.audio_state!='deleted')
                                  .order_by(BgmTrack.id).with_for_update())).all()
        by_id={t.id:t for t in tracks}; track=by_id.get(snapshot['track_id'])
        ordered=sorted((t for t in tracks if t.enabled),key=lambda t:(t.sort_position if t.sort_position is not None else 2**31,t.id))
        active_ids=[t.id for t in ordered]
        if ((active_ids and catalog.default_track_id not in active_ids) or
                (not active_ids and catalog.default_track_id is not None)):
            raise BgmError(20207,503)  # Don't silently repair inconsistent persisted data.
        action=snapshot['action']
        if action=='reorder':
            ids=snapshot['track_ids']
            if len(ids)!=len(active_ids) or len(set(ids))!=len(ids) or set(ids)!=set(active_ids):raise BgmError(20201)
            ordered=[by_id[i] for i in ids]
        else:
            if track is None:raise BgmError(20200,404)
            if track.record_version!=snapshot['expected_revision']:raise BgmError(20202)
            if track.audio_state in {'deleting','delete_failed'}:raise BgmError(20201)
            if action=='rename':track.name=snapshot['name']
            elif action=='enable':
                if track.enabled or not await verified_audio(db,track):raise BgmError(20201)
                if not ordered:catalog.default_track_id=track.id
                ordered.append(track);track.enabled=True;track.ever_published=True;track.hidden_at=None
            elif action=='hide':
                if not track.enabled:raise BgmError(20201)
                ordered=[t for t in ordered if t.id!=track.id]
                replacement=snapshot.get('replacement_default_id')
                if catalog.default_track_id==track.id:
                    if ordered:
                        if replacement not in {t.id for t in ordered}:raise BgmError(20201)
                        catalog.default_track_id=replacement
                    else:
                        if replacement is not None:raise BgmError(20201)
                        catalog.default_track_id=None
                elif replacement is not None:raise BgmError(20201)
                track.enabled=False;track.sort_position=None;track.hidden_at=utcnow()
            elif action=='set_default':
                if not track.enabled or not await verified_audio(db,track):raise BgmError(20201)
                catalog.default_track_id=track.id
            track.record_version+=1
        for index,row in enumerate(ordered):row.sort_position=index
        catalog.catalog_version+=1
        result=dict(catalog_version=catalog.catalog_version,default_track_id=catalog.default_track_id,
                    ordered_track_ids=[t.id for t in ordered],track_id=track.id if track else None,
                    record_version=track.record_version if track else None)
        operation=BgmOperation(id=operation_id,admin_id=admin.id,action=action,track_id=track.id if track else None,
            request_digest=digest,request_snapshot=snapshot,state='succeeded',finished_at=utcnow(),result=result)
        db.add(operation)
        await log_operation(db,admin,'bgm',action,'音乐 '+(track.id if track else '歌单'),
                            after_value=json.dumps(dict(operation_id=operation_id,role=admin.role,result='succeeded',**result),ensure_ascii=False))
        await db.commit()
        from backend.services.bgm_catalog_service import invalidate
        await invalidate(catalog.catalog_version)
        return await operation_detail(db,operation_id)
