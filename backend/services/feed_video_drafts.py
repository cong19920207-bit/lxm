"""Transactional edit and admission state. The singleton protects capacity and arrival order."""
import hashlib
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.feed_post import FeedPost
from backend.models.feed_video import FeedVideoAsset, FeedVideoEdit, FeedVideoSelection, FeedVideoTask
from backend.models.feed_video_upload import FeedDraftRequest, FeedVideoAdmission, FeedVideoUpload
from backend.services.feed_service import feed_now
from backend.services.feed_video_media import MAX_BYTES, runtime_root
from backend.services.memory_business_guard import guard_business_write
from backend.utils.admin_auth import log_operation

# 180s working files for a 720p master, preview and covers, in addition to the upload.
WORKING_BYTES = 96 * 1024**2
RECEIVE_TTL = timedelta(minutes=15)
RECEIVING_STATES = ("reserved", "receiving", "validating")
RECEIVE_FAILURES = ("rejected", "expired")
RESERVATION_EXPIRED = "上传预留已过期，请重新选择视频文件"
NO_SPACE = "临时空间不足，请稍后重试"


async def lock_admission(db):
    await guard_business_write(db)
    if db.get_bind().dialect.name == "sqlite":
        await db.execute(update(FeedVideoAdmission).where(FeedVideoAdmission.id == 1)
                         .values(last_sequence=FeedVideoAdmission.last_sequence))
    return (await db.scalars(select(FeedVideoAdmission).where(FeedVideoAdmission.id == 1)
                             .with_for_update().execution_options(populate_existing=True))).one()


async def edit_row(db, eid, *, write=False):
    stmt = select(FeedVideoEdit).where(FeedVideoEdit.id == eid)
    if write:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    edit = await db.scalar(stmt)
    if edit is None:
        raise HTTPException(404, "编辑不存在")
    if edit.state=="draft" and not edit.media_expired_at and edit.last_edited_at+timedelta(days=7)<=datetime.utcnow():
        from backend.services.feed_video_retention import expire_draft
        await lock_admission(db)
        await db.refresh(edit,with_for_update=True)
        if edit.state=="draft" and edit.last_edited_at+timedelta(days=7)<=datetime.utcnow():
            await expire_draft(db,edit,datetime.utcnow())
    if write and edit.state != "draft":
        raise HTTPException(409, "当前编辑已结束，请重新读取")
    return edit


def upload_view(upload):
    return dict(operation_id=upload.id, edit_id=upload.edit_id, task_id=upload.task_id,
                state=upload.state, filename=upload.filename, size_bytes=upload.expected_size,
                arrival_sequence=upload.arrival_sequence, failure_reason=upload.failure_reason)


async def upload_issue(db, eid, *, lock=False):
    """Return the outstanding transfer or failure, including receipts written by older versions."""
    upload = FeedVideoUpload
    unsequenced_failure = and_(upload.state.in_(RECEIVE_FAILURES), upload.arrival_sequence.is_(None))
    # Older receipts can have identical second-precision times. A partial transfer has no queue
    # sequence, so ask the operator to confirm when its order relative to a success is unknowable.
    stmt = (select(upload)
            .where(upload.edit_id == eid, upload.state.in_((*RECEIVING_STATES, *RECEIVE_FAILURES, "accepted")))
            .order_by(case((upload.state.in_(RECEIVING_STATES), 0), else_=1),
                      func.coalesce(upload.received_at, upload.deadline).desc(),
                      case((unsequenced_failure, 0), else_=1), upload.arrival_sequence.desc(), upload.id.desc())
            .limit(1))
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(stmt)
    if row is None or row.state == "accepted":
        return None
    attempt = upload_view(row)
    if row.state == "expired" or (row.state == "reserved" and (not row.deadline or row.deadline <= datetime.utcnow())):
        attempt.update(state="expired", failure_reason=RESERVATION_EXPIRED)
    elif row.state == "rejected" and not row.failure_reason:
        attempt["failure_reason"] = "上传失败，请重新选择视频文件"
    return attempt


async def resolve_receive_failures(db, eid, *, confirmed_id=None):
    # Resolving earlier failures explicitly also disambiguates operations in the same MySQL second.
    resolved = FeedVideoUpload.state.in_(RECEIVE_FAILURES)
    if confirmed_id:
        # An expired reservation may still be stored as reserved until another writer visits it.
        resolved = or_(resolved, FeedVideoUpload.id == confirmed_id)
    await db.execute(update(FeedVideoUpload).where(
        FeedVideoUpload.edit_id == eid, resolved
    ).values(state="superseded", reserved_bytes=0,
             unreferenced_at=func.coalesce(FeedVideoUpload.unreferenced_at, datetime.utcnow())))


def last_media_edit(edit, selected_upload):
    # Older drafts stored the reservation start. Their receipt still records the completed transfer.
    if (selected_upload and selected_upload.edit_id == edit.id and selected_upload.state == "accepted"
            and selected_upload.received_at):
        return max(edit.last_edited_at, selected_upload.received_at)
    return edit.last_edited_at


async def edit_view(db, edit):
    selection = await db.get(FeedVideoSelection, edit.id)
    upload = await db.get(FeedVideoUpload, selection.media_version) if selection else None
    task = await db.get(FeedVideoTask, upload.task_id) if upload and upload.task_id else None
    attempt = await upload_issue(db, edit.id) if edit.state == "draft" else None
    failed = attempt if attempt and attempt["state"] in RECEIVE_FAILURES else None
    from backend.services.feed_video_publish import selected_assets
    assets = await selected_assets(db,selection)
    from backend.models.feed_video import FeedPublication
    publication = await db.get(FeedPublication,edit.post_id)
    media = {kind:dict(url=a.public_url,width=a.width,height=a.height,size_bytes=a.size_bytes,
                       duration_ms=a.duration_ms,format=a.mime_type,sha256=a.sha256) for kind,a in assets.items()}
    last_edited = last_media_edit(edit, upload)
    return dict(last_receive_error=failed["failure_reason"] if failed else None, failed_upload=failed,
                media_expired=bool(edit.media_expired_at), is_replacement=bool(publication and publication.edit_id!=edit.id),
                assets=media,source_info=upload.source_info if upload else None,
                master_sha256=task.master_sha256 if task else None,
                cover_variant=selection.cover_variant if selection else None, pending_upload=attempt if not failed else None,
                id=edit.id, post_id=edit.post_id, version=edit.edit_version, state=edit.state,
                content_text=edit.content_text, hashtags=edit.hashtags or [], emotion=edit.emotion,
                scheduled_publish_time=edit.scheduled_publish_time,
                frame_mode=edit.frame_mode, frame_position=edit.frame_position,
                last_edited_at=last_edited, expires_at=last_edited + timedelta(days=7),
                upload=upload_view(upload) if upload else None, task_state=task.state if task else None,
                master_verified=bool(task and task.master_verified_at),
                failure_reason=task.failure_reason if task else None)


async def create_edit(db, actor, body):
    key = str(body.request_id)
    payload = body.model_dump(mode="json", exclude={"request_id"})
    # Preserve request receipts created before these optional fields existed.
    if not payload["hashtags"]:
        del payload["hashtags"]
    if payload["emotion"] == "平静":
        del payload["emotion"]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    await lock_admission(db)
    receipt = await db.scalar(select(FeedDraftRequest).where(FeedDraftRequest.request_id == key).with_for_update())
    if receipt:
        if receipt.actor_id != actor.id or receipt.request_digest != digest:
            raise HTTPException(409, "建稿请求已用于其他内容")
        return await edit_view(db, await edit_row(db, receipt.edit_id))
    now = datetime.utcnow()
    post = FeedPost(media_kind="video", scheduled_publish_time=body.scheduled_publish_time or feed_now(),
                    content_text="", generation_status="generating", emotion="平静", city="", season="",
                    base_likes=0, like_multiplier=1, dedup_hash=key)
    db.add(post)
    await db.flush()
    edit = FeedVideoEdit(post_id=post.id, admin_id=actor.id, base_post_version=post.post_version,
                         content_text=body.content_text, hashtags=body.hashtags, emotion=body.emotion,
                         scheduled_publish_time=body.scheduled_publish_time,
                         created_at=now, last_edited_at=now)
    db.add(edit)
    await db.flush()
    db.add(FeedDraftRequest(request_id=key, edit_id=edit.id, actor_id=actor.id, request_digest=digest))
    await log_operation(db, actor, "feed", "video_draft", f"创建视频编辑 {edit.id}")
    await db.flush()
    await db.refresh(edit)
    return await edit_view(db, edit)


async def save_edit(db, actor, eid, body):
    await lock_admission(db)
    edit = await edit_row(db, eid, write=True)
    if edit.edit_version != body.version:
        raise HTTPException(409, "编辑已更新，请刷新")
    changed = False
    for key, value in body.model_dump(exclude_unset=True, exclude={"version"}).items():
        if getattr(edit, key) != value:
            setattr(edit, key, value)
            changed = True
    if changed:
        edit.edit_version += 1
        edit.last_edited_at = datetime.utcnow()
        await log_operation(db, actor, "feed", "video_edit", f"保存视频编辑 {eid}")
    await db.flush()
    await db.refresh(edit)
    return await edit_view(db, edit)


async def reserve(db: AsyncSession, actor, eid, body):
    await lock_admission(db)
    edit = await edit_row(db, eid, write=True)
    key = str(body.operation_id)
    old = await db.scalar(select(FeedVideoUpload).where(FeedVideoUpload.id == key).with_for_update())
    if old:
        if (old.edit_id, old.actor_id, old.filename, old.expected_size) != (eid, actor.id, body.filename, body.size_bytes):
            raise HTTPException(409, "接收请求已用于其他文件")
        return upload_view(old)
    if body.version is not None and edit.edit_version != body.version:
        raise HTTPException(409, "编辑已更新，请刷新后重新选择")
    now = datetime.utcnow()
    await db.execute(update(FeedVideoUpload).where(FeedVideoUpload.state == "reserved",
                         FeedVideoUpload.deadline <= now).values(state="expired", reserved_bytes=0,
                                                                 failure_reason=RESERVATION_EXPIRED))
    unfinished = await db.scalar(select(FeedVideoUpload.id).where(FeedVideoUpload.edit_id == eid,
                                 FeedVideoUpload.state.in_(RECEIVING_STATES)).limit(1).with_for_update())
    if unfinished:
        raise HTTPException(409, "当前编辑已有接收任务，请重取原任务")
    needed = body.size_bytes + WORKING_BYTES
    reason = None
    if not 0 < body.size_bytes <= MAX_BYTES:
        reason = "文件不能为空，且不能超过 200 MiB"
    elif Path(body.filename).suffix.lower() not in {".mp4", ".mov"}:
        reason = "仅支持 MP4 或 MOV 视频"
    else:
        # A locking read sees reservations committed after authentication opened an InnoDB snapshot.
        reservations = await db.scalars(select(FeedVideoUpload.reserved_bytes)
                             .where(FeedVideoUpload.reserved_bytes > 0).with_for_update())
        if shutil.disk_usage(runtime_root()).free < needed + sum(reservations):
            reason = NO_SPACE
    await resolve_receive_failures(db, eid)
    upload = FeedVideoUpload(id=key, edit_id=eid, actor_id=actor.id, filename=body.filename,
                             expected_size=body.size_bytes, reserved_bytes=0 if reason else needed,
                             state="rejected" if reason else "reserved", failure_reason=reason,
                             received_at=now if reason else None, deadline=None if reason else now + RECEIVE_TTL)
    edit.edit_version += 1
    db.add(upload)
    await db.flush()
    return upload_view(upload)


async def keep_selected(db, actor, eid, failed_id, version, media_version):
    await lock_admission(db)
    edit = await edit_row(db, eid, write=True)
    selection = await db.get(FeedVideoSelection, eid, with_for_update=True)
    issue = await upload_issue(db, eid, lock=True)
    if (edit.edit_version != version or not selection or selection.media_version != media_version
            or not issue or issue["operation_id"] != failed_id or issue["state"] not in RECEIVE_FAILURES):
        raise HTTPException(409, "编辑已更新，请刷新后重新选择")
    task = await db.scalar(select(FeedVideoTask).where(FeedVideoTask.media_version == media_version).with_for_update())
    if not task or task.state != "ready":
        raise HTTPException(409, "原视频尚未就绪")
    await resolve_receive_failures(db, eid, confirmed_id=failed_id)
    edit.edit_version += 1
    await log_operation(db, actor, "feed", "video_keep_selected", f"编辑 {eid} 确认沿用视频 {media_version}")
    return await edit_view(db, edit)


async def abandon(db, actor, eid):
    await lock_admission(db)
    edit = await edit_row(db, eid, write=True)
    edit.state, edit.abandoned_at = "abandoned", datetime.utcnow()
    edit.edit_version += 1
    uploads = (await db.scalars(select(FeedVideoUpload).where(FeedVideoUpload.edit_id == eid)
                                .with_for_update())).all()
    for upload in uploads:
        upload.unreferenced_at = edit.abandoned_at
        if upload.state == "reserved":
            upload.state, upload.reserved_bytes = "cancelled", 0
        elif upload.state in ("receiving", "validating"):
            upload.state = "cancelling"
        elif upload.task_id:
            task = await db.get(FeedVideoTask, upload.task_id)
            if task.state == "queued":
                task.state = "cancelled"
                upload.reserved_bytes = 0
    selection = await db.get(FeedVideoSelection, eid)
    if selection:
        from backend.services.feed_video_retention import refresh_references
        version = selection.media_version
        await db.delete(selection)
        await refresh_references(db,version,edit.abandoned_at)
    await log_operation(db, actor, "feed", "video_abandon", f"放弃视频编辑 {eid}")
    return dict(id=eid, state=edit.state)


async def retry_task(db, eid, operation_id):
    from backend.services.feed_video_master import HDR_ERROR, MISSING
    await lock_admission(db)
    await edit_row(db, eid, write=True)
    selection = await db.get(FeedVideoSelection, eid)
    if not selection or selection.media_version != operation_id:
        raise HTTPException(409, "媒体版本已变化，请刷新")
    upload = await db.get(FeedVideoUpload, operation_id)
    task = await db.get(FeedVideoTask, upload.task_id)
    if task.state != "failed":
        return upload_view(upload)
    base = runtime_root() / operation_id
    remote = await db.scalar(select(FeedVideoAsset.id).where(FeedVideoAsset.media_version==operation_id,
                             FeedVideoAsset.kind=="video",FeedVideoAsset.verified_at.is_not(None),
                             FeedVideoAsset.sha256==task.master_sha256))
    if not (task.master_verified_at and (remote or (base / "video.mp4").is_file())):
        if not (base / "source").is_file() or (
                task.first_failed_at and task.first_failed_at + timedelta(hours=24) <= datetime.utcnow()):
            raise HTTPException(409, MISSING)
        if task.failure_reason in (HDR_ERROR, "无法解码媒体，请检查文件是否损坏"):
            raise HTTPException(422, task.failure_reason)
    reservations = (await db.scalars(select(FeedVideoUpload.reserved_bytes)
                    .where(FeedVideoUpload.reserved_bytes > 0).with_for_update())).all()
    if shutil.disk_usage(base).free < WORKING_BYTES + sum(reservations):
        raise HTTPException(507, "临时空间不足，请稍后重试")
    upload.reserved_bytes = WORKING_BYTES
    task.state, task.failure_reason = "queued", None
    return upload_view(upload)


async def choose_cover(db, eid, version, edit_version, blob=None):
    import asyncio
    from uuid import uuid4
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from backend.services.feed_video_covers import decode_cover, make_pair, NO_COVER
    from backend.services.feed_video_media import InvalidMedia
    from backend.services.feed_video_pipeline import deliver

    async def current():
        edit = await edit_row(db,eid,write=True)
        selection = await db.scalar(select(FeedVideoSelection).where(FeedVideoSelection.edit_id==eid)
                                    .with_for_update().execution_options(populate_existing=True))
        if edit.edit_version!=edit_version or not selection or selection.media_version!=version:
            raise HTTPException(409,"编辑已更新，请刷新")
        task = await db.scalar(select(FeedVideoTask).where(FeedVideoTask.media_version==version).with_for_update())
        return edit,selection,task

    _,_,task = await current()
    already_ready = task.state == "ready"
    await db.commit()
    base = runtime_root() / version
    variant = str(uuid4()) if blob is not None else "default"
    folder = base / variant
    if blob is not None:
        try:
            image = await asyncio.to_thread(decode_cover,blob)
            await asyncio.to_thread(make_pair,image,folder)
        except InvalidMedia as exc:
            raise HTTPException(422,str(exc)) from None
    elif not all((folder/(kind+".webp")).is_file() for kind in ("cover_small","cover_large")):
        raise HTTPException(409,NO_COVER)
    if already_ready:
        sessions = async_sessionmaker(db.bind,expire_on_commit=False)
        try:
            for kind in ("cover_small","cover_large"):
                await deliver(sessions,version,kind,variant,folder/(kind+".webp"))
        except (InvalidMedia,OSError) as exc:
            raise HTTPException(422,str(exc)) from None
    await lock_admission(db)
    edit,selection,task = await current()
    if selection.cover_variant != variant:
        if task.state=="ready" and not already_ready:
            raise HTTPException(409,"视频已完成处理，请重新选择封面")
        selection.cover_variant = variant
        edit.last_edited_at,edit.edit_version = datetime.utcnow(),edit.edit_version+1
        if task.state=="failed" and task.master_verified_at:
            task.state,task.failure_reason = "queued",None
        await db.flush()
        await db.refresh(edit)
        from backend.services.feed_video_retention import refresh_references
        await refresh_references(db,version,datetime.utcnow())
    return await edit_view(db,edit)
