"""Reference-aware expiration, serialized against media selection and the processing owner."""
import asyncio
from datetime import datetime,timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_,or_,select

from backend.models.feed_video import FeedPublication,FeedVideoAsset,FeedVideoEdit,FeedVideoSelection,FeedVideoTask
from backend.models.feed_video_upload import FeedVideoUpload
from backend.services.feed_video_drafts import last_media_edit, lock_admission
from backend.services.feed_video_media import blocking_work,runtime_root,try_lock

DAY = timedelta(days=1)
WEEK = timedelta(days=7)


async def refresh_references(db, version, now, *, expire=False):
    """The caller holds the admission lock and has written the candidate/published pointer."""
    await db.flush()
    variants=set(await db.scalars(select(FeedVideoSelection.cover_variant)
        .join(FeedVideoEdit,FeedVideoEdit.id==FeedVideoSelection.edit_id)
        .outerjoin(FeedPublication,FeedPublication.edit_id==FeedVideoEdit.id)
        .where(FeedVideoSelection.media_version==version,
               or_(FeedVideoEdit.state=="draft",FeedPublication.post_id.is_not(None))).with_for_update()))
    mark = now-DAY if expire else now
    upload=await db.get(FeedVideoUpload,version,with_for_update=True)
    if upload:
        upload.unreferenced_at = None if variants else (mark if expire else upload.unreferenced_at or mark)
    assets=(await db.scalars(select(FeedVideoAsset).where(FeedVideoAsset.media_version==version).with_for_update())).all()
    for asset in assets:
        needed = bool(variants) if asset.kind in ("video","preview") else asset.variant in variants
        if needed:
            asset.unreferenced_at=None
        elif asset.unreferenced_at is None or expire and not variants:
            asset.unreferenced_at=mark
    return variants


def delete_asset(asset):
    from backend.services.bgm_asset_service import _bucket
    from backend.services.feed_video_delivery import asset_key,owned
    key=asset_key(asset.media_version,asset.kind,asset.variant)
    if key!=asset.object_key:
        raise ValueError("媒体对象键与所属版本不一致")
    bucket=_bucket()
    if not bucket.object_exists(key):
        return
    head=bucket.head_object(key)
    if not owned(head,dict(version=asset.media_version,sha256=asset.sha256,size_bytes=asset.size_bytes)):
        raise ValueError("远端文件所属版本不一致")
    bucket.delete_object(key)
    if bucket.object_exists(key):
        raise OSError("待确认远端对象是否已清理")


async def expire_draft(db,edit,now):
    sel=await db.get(FeedVideoSelection,edit.id,with_for_update=True)
    if not sel:return
    upload=await db.get(FeedVideoUpload,sel.media_version,with_for_update=True)
    edit.last_edited_at=last_media_edit(edit,upload)
    if edit.last_edited_at+WEEK>now:
        return
    task=await db.scalar(select(FeedVideoTask).where(FeedVideoTask.media_version==sel.media_version))
    pending=await db.scalar(select(FeedVideoUpload.id).where(FeedVideoUpload.edit_id==edit.id,
        or_(FeedVideoUpload.state.in_(("receiving","validating")),
            and_(FeedVideoUpload.state=="reserved",FeedVideoUpload.deadline>now))).limit(1))
    if pending or task and task.state in ("queued","processing"):
        return
    version=sel.media_version
    await db.delete(sel)
    edit.media_expired_at=now
    edit.edit_version+=1
    await refresh_references(db,version,now,expire=True)
    if upload and upload.edit_id==edit.id:upload.state="expired_media"


async def collect(sessions, now=None, remove=None):
    remove = remove or delete_asset
    now=now or datetime.utcnow()
    root=runtime_root()
    # A surviving encoder also owns this lock. Expiration cannot race a live decoder.
    with try_lock(root/".processing.lock") as fd:
        if fd is None:return
        async with sessions.begin() as db:
            await lock_admission(db)
            drafts=(await db.scalars(select(FeedVideoEdit).where(FeedVideoEdit.state=="draft",
                                   FeedVideoEdit.last_edited_at<=now-WEEK).with_for_update())).all()
            for edit in drafts:
                await expire_draft(db,edit,now)
            failed=(await db.scalars(select(FeedVideoTask).where(FeedVideoTask.state=="failed",
                     FeedVideoTask.first_failed_at<=now-DAY,FeedVideoTask.master_verified_at.is_(None),
                     FeedVideoTask.source_path.is_not(None)).with_for_update())).all()
            for task in failed:
                (root/str(UUID(task.media_version))/"source").unlink(missing_ok=True)
                task.source_path=None
                task.failure_reason="原片已清理，请重新选择视频文件"
        async with sessions() as db:
            versions=set(await db.scalars(select(FeedVideoUpload.id).where(
                FeedVideoUpload.unreferenced_at<=now-DAY)))
            versions.update(await db.scalars(select(FeedVideoAsset.media_version).where(
                FeedVideoAsset.unreferenced_at<=now-DAY)))
        for version in versions:
            async with sessions.begin() as db:
                await lock_admission(db)
                variants=await refresh_references(db,version,now)
                task=await db.scalar(select(FeedVideoTask).where(FeedVideoTask.media_version==version).with_for_update())
                if task and task.state in ("queued","processing"):continue
                assets=(await db.scalars(select(FeedVideoAsset).where(FeedVideoAsset.media_version==version,
                    FeedVideoAsset.unreferenced_at<=now-DAY).with_for_update())).all()
                for asset in assets:
                    try:
                        await blocking_work(remove,asset)
                    except Exception:
                        import logging
                        logging.getLogger(__name__).warning("Feed media cleanup pending for asset %s",asset.id)
                        continue
                    await db.delete(asset)
                    # Keep the locally recoverable default for a still-referenced movie.
                    if asset.kind.startswith("cover_") and (asset.variant!="default" or not variants):
                        variant=asset.variant if asset.variant=="default" else str(UUID(asset.variant))
                        (root/str(UUID(version))/variant/(asset.kind+".webp")).unlink(missing_ok=True)
                await db.flush()
                remaining=await db.scalar(select(FeedVideoAsset.id).where(FeedVideoAsset.media_version==version).limit(1))
                upload=await db.get(FeedVideoUpload,version)
                if upload and not remaining and not variants and upload.unreferenced_at and upload.unreferenced_at<=now-DAY:
                    folder=root/str(UUID(version))
                    if folder.exists():
                        import shutil
                        shutil.rmtree(folder)
                    upload.unreferenced_at=None
                    upload.reserved_bytes=0
                    if upload.state!="expired_media":upload.state="cleaned"
                    if task:
                        task.state,task.source_path,task.master_path="cleaned",None,None
                        task.master_verified_at=None
