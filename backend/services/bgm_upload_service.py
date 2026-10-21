"""Short DB transactions surround bounded receive and isolated media work."""
import asyncio
from datetime import timedelta
import hashlib
import json
import time

from fastapi import HTTPException
from sqlalchemy import select

from backend.constants.bgm import BGM_WRITE_ROLES, AUDIO_SOURCE_MAX_BYTES
from backend.models.admin_user import AdminUser
from backend.models.bgm import BgmAsset, BgmCatalog, BgmOperation, BgmProcessingSlot, BgmTrack, new_id, utcnow
from backend.services.bgm_asset_service import object_location
from backend.services.bgm_errors import BgmError
from backend.services.bgm_media import MediaError, validate_source_type
from backend.services.bgm_process import OwnedWork
from backend.services.bgm_service import operation_detail
from backend.utils.admin_auth import log_operation

TOTAL_SECONDS = 300
RECEIVE_SECONDS = 120
PROCESS_SECONDS = 180
CLEANUP_SECONDS = 10


async def locked_slot(db):
    row = await db.scalar(select(BgmProcessingSlot).where(BgmProcessingSlot.id == 1).with_for_update())
    if row is None:
        raise BgmError(20207, 503)
    return row


async def authorize(db, actor):
    row = await db.scalar(select(AdminUser).where(AdminUser.id == actor['id']).with_for_update())
    if row is None or not row.is_active or row.is_locked or row.token_version != actor['token_version']:
        raise HTTPException(401, '账号或会话已失效')
    if row.role not in BGM_WRITE_ROLES:
        raise HTTPException(403, '权限不足')
    return row


async def audit(db, admin, operation, result, category=None):
    # Persist only explicit metadata, never the request snapshot, media bytes or
    # storage addresses. Flush keeps this same-transaction audit valid even for
    # session factories with autoflush disabled.
    await db.flush()
    track=await db.get(BgmTrack,operation.track_id) if operation.track_id else None
    catalog=await db.get(BgmCatalog,1)
    action=operation.action
    if action=='upload_cover':
        subtype=(operation.request_snapshot or {}).get('cover_action')
        if subtype in {'add_cover','replace_cover'}:action=subtype
    payload=dict(operation_id=operation.id,track_id=operation.track_id,attempt=operation.attempt,
        role=admin.role,result=result,failure_category=category,
        record_version=track.record_version if track else None,
        media_version=track.media_version if track else None,
        cover_version=track.cover_version if track else None,
        catalog_version=catalog.catalog_version if catalog else None)
    details=operation.result or {}
    for key in ['association_removed','cleanup_state','mode','track_deleted','remaining_count']:
        if key in details:payload[key]=details[key]
    if operation.action in {'delete_track','cleanup_retry'}:
        payload['assets']=[{key:a.get(key) for key in ['id','kind','cleanup_state','failure_category']}
                           for a in details.get('assets',[])[:100]]
    await log_operation(db,admin,'bgm',action,'音乐 '+(operation.track_id or '—'),
                        after_value=json.dumps(payload,ensure_ascii=False))


def release(slot):
    slot.operation_id = slot.owner_id = slot.lease_until = slot.deadline_at = None
    slot.state = 'free'


async def prepare(sessions, actor, body):
    snapshot = body.model_dump(mode='json', exclude={'operation_id'})
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    async with sessions() as db:
        slot = await locked_slot(db)
        admin = await authorize(db, actor)
        operation = await db.get(BgmOperation, str(body.operation_id))
        if operation:
            if operation.admin_id != admin.id or operation.request_digest != digest:
                raise BgmError(20203)
            return await operation_detail(db, operation.id)
        if slot.state != 'free':
            raise BgmError(20205, 429)
        if body.action == 'retry_audio':
            track = await db.get(BgmTrack, str(body.track_id))
            if track is None or track.audio_state == 'deleted':
                raise BgmError(20200, 404)
            if track.record_version != body.expected_revision:
                raise BgmError(20202)
            if track.audio_state != 'failed' or track.enabled or track.active_operation_id:
                raise BgmError(20201)
            track.record_version += 1
        else:
            track = BgmTrack(id=new_id(), name=body.name, attempt=0, record_version=1)
            db.add(track)
        now = utcnow()
        track.name = body.name; track.attempt += 1
        track.audio_state = 'receiving'; track.failure_category = None
        track.active_operation_id = str(body.operation_id)
        operation = BgmOperation(id=str(body.operation_id), admin_id=admin.id,
            action=body.action, track_id=track.id, request_digest=digest,
            request_snapshot={**snapshot, 'admin_token_version': actor['token_version']},
            source_sha256=body.source_sha256, source_size=body.source_size,
            attempt=track.attempt, state='accepted', created_at=now,
            deadline_at=now + timedelta(seconds=TOTAL_SECONDS),
            receive_deadline_at=now + timedelta(seconds=RECEIVE_SECONDS))
        db.add(operation)
        slot.state = 'reserved'; slot.operation_id = operation.id; slot.owner_id = None
        slot.attempt = track.attempt; slot.deadline_at = operation.deadline_at
        slot.lease_until = operation.receive_deadline_at
        await audit(db, admin, operation, 'accepted')
        await db.commit()
        return await operation_detail(db, operation.id)


async def claim(sessions, actor, operation_id, work):
    async with sessions() as db:
        slot = await locked_slot(db)
        await authorize(db, actor)
        operation = await db.get(BgmOperation, operation_id)
        if operation is None:
            raise BgmError(20200, 404)
        if operation.admin_id != actor['id']:
            raise HTTPException(403, '只能继续本人提交的上传')
        if operation.state in {'succeeded', 'failed'}:
            if slot.state != 'free':
                raise BgmError(20205, 429)
            slot.state = 'replay'; slot.operation_id = operation_id; slot.owner_id = work.owner
            slot.deadline_at = slot.lease_until = utcnow() + timedelta(seconds=RECEIVE_SECONDS)
            await db.commit()
            return operation, True
        if operation.state != 'accepted':
            raise BgmError(20205, 429)
        if slot.operation_id != operation_id or slot.owner_id is not None:
            raise BgmError(20205, 429)
        if operation.receive_deadline_at <= utcnow():
            raise BgmError(20206)
        operation.owner_id = work.owner; operation.state = 'receiving'
        slot.owner_id = work.owner; slot.state = 'receiving'
        await db.commit()
        return operation, False


async def release_replay(sessions, operation_id, owner, *, stopped):
    async with sessions() as db:
        slot = await locked_slot(db)
        if slot.operation_id == operation_id and slot.owner_id == owner and slot.state in {'replay', 'replay_quarantined'}:
            if stopped: release(slot)
            else: slot.state = 'replay_quarantined'
            await db.commit()


async def mark_processing(sessions, operation, work, location):
    async with sessions() as db:
        slot = await locked_slot(db)
        current = await db.get(BgmOperation, operation.id)
        track = await db.get(BgmTrack, operation.track_id)
        if not qualified(slot, current, track, work.owner):
            raise MediaError('stale_attempt')
        current.state = track.audio_state = slot.state = 'processing'
        version = location['object_key'].rsplit('/', 1)[1].removesuffix('.m4a')
        asset = BgmAsset(id=new_id(), track_id=track.id, operation_id=current.id,
                         attempt=current.attempt, kind='audio', version=version, **location)
        db.add(asset)
        await db.commit()
        return asset.id


def qualified(slot, operation, track, owner):
    return bool(operation and track and operation.state in {'receiving', 'processing'}
                and slot.operation_id == operation.id and slot.owner_id == owner
                and operation.owner_id == owner and track.active_operation_id == operation.id
                and track.attempt == operation.attempt and track.audio_state in {'receiving', 'processing'}
                and not track.enabled and operation.deadline_at > utcnow())


async def finish(sessions, actor, operation, work, asset_id, metadata):
    async with sessions() as db:
        slot = await locked_slot(db)
        admin = await authorize(db, actor)
        current = await db.get(BgmOperation, operation.id)
        track = await db.get(BgmTrack, operation.track_id)
        if not qualified(slot, current, track, work.owner):
            raise MediaError('stale_attempt')
        if current.request_snapshot['admin_token_version'] != actor['token_version']:
            raise HTTPException(401, '提交会话已失效')
        asset = await db.get(BgmAsset, asset_id)
        asset.state = 'ready'; asset.sha256 = metadata['sha256']
        asset.size_bytes = metadata['size_bytes']; asset.mime_type = metadata['mime_type']
        track.audio_asset_id = asset.id; track.media_version = asset.version
        track.audio_state = 'ready'; track.enabled = False; track.record_version += 1
        track.duration_seconds = metadata['duration_seconds']; track.size_bytes = metadata['size_bytes']
        track.active_operation_id = None
        current.state = 'succeeded'; current.finished_at = utcnow()
        current.result = {'track_id': track.id, 'record_version': track.record_version}
        release(slot)
        await audit(db, admin, current, 'succeeded')
        await db.commit()


async def fail(sessions, operation_id, owner, category, *, stopped):
    async with sessions() as db:
        slot = await locked_slot(db)
        operation = await db.get(BgmOperation, operation_id)
        if operation is None or operation.owner_id != owner:
            return
        # A lost commit response is not failure: check the durable original first.
        if operation.state == 'succeeded':
            return
        was_failed = operation.state == 'failed'
        track = await db.get(BgmTrack, operation.track_id)
        operation.state = 'failed'; operation.failure_category = category; operation.finished_at = utcnow()
        if track and track.active_operation_id == operation.id and track.attempt == operation.attempt:
            track.audio_state = 'failed'; track.active_operation_id = None
            track.failure_category = category; track.record_version += 1
        assets = (await db.scalars(select(BgmAsset).where(BgmAsset.operation_id == operation.id))).all()
        for asset in assets:
            if asset.state != 'ready':
                asset.state = 'unknown'; asset.cleanup_state = 'pending'; asset.failure_category = category
        if slot.operation_id == operation.id and slot.owner_id == owner:
            if stopped: release(slot)
            else: slot.state = 'quarantined'
        admin = await db.get(AdminUser, operation.admin_id)
        if admin and not was_failed:
            await audit(db, admin, operation, 'failed', category)
        await db.commit()


async def receive(sessions, actor, operation_id, request):
    work = OwnedWork(); operation = None; outcome_saved = False; replay = False
    try:
        operation, replay = await claim(sessions, actor, operation_id, work)
        snapshot = operation.request_snapshot
        actual_mime = request.headers.get('content-type', '').split(';')[0].lower()
        validate_source_type(snapshot['extension'], actual_mime)
        remaining = RECEIVE_SECONDS if replay else min((operation.receive_deadline_at - utcnow()).total_seconds(),
                                                       (operation.deadline_at - utcnow()).total_seconds() - CLEANUP_SECONDS)
        digest = hashlib.sha256(); size = 0
        async with asyncio.timeout(max(0, remaining)):
            with (work.directory/'source').open('wb') as source:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > AUDIO_SOURCE_MAX_BYTES or size > operation.source_size:
                        raise MediaError('size_limit')
                    source.write(chunk); digest.update(chunk)
        if size != operation.source_size or digest.hexdigest() != operation.source_sha256:
            raise MediaError('source_mismatch')
        if replay:
            # Browsers can transparently retry PUT after a lost response. Verify
            # actual bytes under the SAME global receive slot, then reuse the
            # durable result. This never restarts the original processing budget.
            await work.stop()
            await release_replay(sessions, operation.id, work.owner, stopped=True)
        else:
            location = object_location(operation.track_id, new_id())
            asset_id = await mark_processing(sessions, operation, work, location)
            remaining = min(PROCESS_SECONDS, (operation.deadline_at - utcnow()).total_seconds()) - CLEANUP_SECONDS
            if remaining <= 0:
                raise MediaError('processing_timeout')
            metadata = await work.run(dict(extension=snapshot['extension'], mime_type=snapshot['mime_type'],
                                          location=location, deadline_monotonic=time.monotonic()+remaining))
            await finish(sessions, actor, operation, work, asset_id, metadata)
        outcome_saved = True
    except BaseException as exc:
        try:
            await work.stop()
        finally:
            if operation:
                category = (str(exc) if isinstance(exc, MediaError) else
                            'receive_timeout' if isinstance(exc, TimeoutError) else
                            'authorization_changed' if isinstance(exc, HTTPException) else 'interrupted')
                if replay:
                    await release_replay(sessions, operation.id, work.owner, stopped=work.quiescent)
                else:
                    await fail(sessions, operation.id, work.owner, category, stopped=work.quiescent)
                outcome_saved = True
        if replay and isinstance(exc, MediaError):
            raise BgmError(20203) from None
        if isinstance(exc, (HTTPException, BgmError)) or not isinstance(exc, Exception) or operation is None:
            raise
    finally:
        if not work.quiescent:
            await work.stop()
        if work.quiescent:
            work.close(preserve_receipt=operation is not None and not outcome_saved)
    async with sessions() as db:
        return await operation_detail(db, operation_id)
