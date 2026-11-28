"""One decoder owner on the shared POSIX volume, with durable order in MySQL."""
import asyncio
from datetime import datetime
import logging

from sqlalchemy import case, select

from backend.models.feed_video import FeedVideoAsset, FeedVideoEdit, FeedVideoSelection, FeedVideoTask
from backend.models.feed_video_upload import FeedVideoUpload
from backend.services.feed_video_drafts import lock_admission
from backend.services.feed_video_receive import recover_receives
from backend.services.feed_video_media import InvalidMedia, UnusableSource, decoder_lock_fd, runtime_root, try_lock
from backend.services.memory_business_guard import business_epoch, enter_business_epoch
from backend.services.memory_runtime_service import MemoryControlError

logger = logging.getLogger(__name__)


async def claim(sessions):
    async with sessions.begin() as db:
        await lock_admission(db)
        front = (await db.execute(
            select(FeedVideoUpload, FeedVideoTask, FeedVideoEdit)
            .outerjoin(FeedVideoTask, FeedVideoTask.id == FeedVideoUpload.task_id)
            .join(FeedVideoEdit, FeedVideoEdit.id == FeedVideoUpload.edit_id)
            .where((FeedVideoUpload.state == "validating") |
                   FeedVideoTask.state.in_(("processing", "queued")))
            .order_by(case((FeedVideoTask.state == "processing", 0), else_=1),
                      FeedVideoUpload.arrival_sequence).limit(1).with_for_update()
        )).first()
        if not front:
            return None
        upload, task, edit = front
        if task is None:
            return None
        selection = await db.get(FeedVideoSelection, edit.id)
        if edit.state != "draft" or not selection or selection.media_version != task.media_version:
            task.state = "cancelled"
            upload.reserved_bytes = 0
            return None
        task.state = "processing"
        task.attempt += 1
        await db.flush()
        return task.id


async def finish(sessions, task_id, state, reason=None):
    async with sessions.begin() as db:
        await lock_admission(db)
        task = await db.get(FeedVideoTask, task_id)
        edit = await db.get(FeedVideoEdit, task.edit_id)
        selection = await db.get(FeedVideoSelection, edit.id)
        upload = await db.get(FeedVideoUpload, task.media_version)
        if edit.state != "draft" or not selection or selection.media_version != task.media_version:
            state = "cancelled"
        if state == "ready":
            ready = (await db.scalars(select(FeedVideoAsset.kind).where(
                FeedVideoAsset.media_version == task.media_version,
                FeedVideoAsset.verified_at.is_not(None), FeedVideoAsset.public_url.is_not(None),
                ((FeedVideoAsset.kind.in_(("video","preview"))) |
                 (FeedVideoAsset.variant == selection.cover_variant))))).all()
            if set(ready) != {"video","preview","cover_small","cover_large"}:
                state = "queued"
        if state == "failed" and not task.master_verified_at and task.source_path and not task.first_failed_at:
            task.first_failed_at = datetime.utcnow()
        task.state, task.failure_reason = state, reason
        if state in ("ready", "cancelled", "failed"):
            upload.reserved_bytes = 0


async def run_one(sessions, process):
    with try_lock(runtime_root() / ".processing.lock") as fd:
        if fd is None:
            return False
        await recover_receives(sessions)
        task_id = await claim(sessions)
        if task_id is None:
            return False
        token = decoder_lock_fd.set(fd)
        try:
            state = await process(sessions, task_id)
        except UnusableSource as exc:
            async with sessions.begin() as db:
                task = await db.get(FeedVideoTask, task_id, with_for_update=True)
                (runtime_root() / task.media_version / "source").unlink(missing_ok=True)
                task.source_path = None
            await finish(sessions, task_id, "failed", str(exc))
        except InvalidMedia as exc:
            await finish(sessions, task_id, "failed", str(exc))
        except (OSError, TimeoutError):
            logger.exception("Feed media task %s stopped during local media work", task_id)
            await finish(sessions, task_id, "failed", "媒体处理暂时失败，请重试")
        else:
            await finish(sessions, task_id, state)
        finally:
            decoder_lock_fd.reset(token)
        return True


async def run_loop(sessions, process):
    from time import monotonic
    from backend.services.feed_video_retention import collect
    next_collection = 0
    while True:
        try:
            # All transactions for one media job must see the same runtime epoch.
            token = business_epoch.set(await enter_business_epoch(sessions))
            try:
                if monotonic() >= next_collection:
                    next_collection = monotonic()+60
                    await collect(sessions)
                worked = await run_one(sessions, process)
            finally:
                business_epoch.reset(token)
        except MemoryControlError:
            worked = False
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Feed media worker will resume its durable task")
            worked = False
        await asyncio.sleep(0 if worked else 2)
