"""Receive media without holding an authentication or edit transaction open."""
import asyncio
import os
from contextlib import ExitStack
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import ClientDisconnect

from backend.models.feed_video import FeedVideoSelection, FeedVideoTask
from backend.models.feed_video_upload import FeedVideoUpload
from backend.services.feed_video_drafts import WORKING_BYTES, edit_row, lock_admission, resolve_receive_failures, upload_view
from backend.services.feed_video_media import InvalidMedia, MAX_BYTES, runtime_root, validate_source, try_lock


async def locked_upload(db, key):
    row = await db.scalar(select(FeedVideoUpload).where(FeedVideoUpload.id == key).with_for_update())
    if row is None:
        raise HTTPException(404, "接收操作不存在")
    return row


async def fail_receive(sessions, key, reason):
    async with sessions.begin() as db:
        await lock_admission(db)
        row = await locked_upload(db, key)
        if row.state in ("receiving", "validating", "cancelling"):
            row.state = "cancelled" if row.state == "cancelling" else "rejected"
            row.failure_reason = reason
            row.received_at = row.received_at or datetime.utcnow()
            row.deadline = None
            row.reserved_bytes = 0


async def accept(sessions, key, metadata, source, root):
    async with sessions.begin() as db:
        await lock_admission(db)
        row = await locked_upload(db, key)
        if row.state != "validating":
            raise HTTPException(409, "编辑已放弃")
        edit = await edit_row(db, row.edit_id, write=True)
        accepted_at = datetime.utcnow()
        edit.media_expired_at = None
        edit.last_edited_at = max(edit.last_edited_at, accepted_at)
        task = FeedVideoTask(post_id=edit.post_id, edit_id=edit.id, state="queued", media_version=key,
                             source_path=str(source.relative_to(root)), received_at=row.received_at)
        db.add(task)
        await db.flush()
        selection = await db.get(FeedVideoSelection, edit.id)
        prior = selection.media_version if selection else None
        if selection:
            previous = await db.get(FeedVideoUpload, selection.media_version)
            if previous:
                previous.unreferenced_at = accepted_at
            selection.media_version, selection.cover_variant = key, "default"
        else:
            db.add(FeedVideoSelection(post_id=edit.post_id, edit_id=edit.id, media_version=key))
        row.task_id, row.source_info = task.id, metadata
        row.state, row.reserved_bytes, row.deadline = "accepted", WORKING_BYTES, None
        await resolve_receive_failures(db, edit.id)
        if prior:
            from backend.services.feed_video_retention import refresh_references
            await refresh_references(db,prior,accepted_at)
        return upload_view(row)


async def receive(sessions, actor_id, key, request):
    with ExitStack() as locks:
        return await _receive(sessions, actor_id, key, request, locks)


async def _receive(sessions, actor_id, key, request, locks):
    root = runtime_root()
    source = root / key / "source"
    async with sessions.begin() as db:
        await lock_admission(db)
        row = await locked_upload(db, key)
        if row.actor_id != actor_id:
            raise HTTPException(403, "仅本次接收的操作人可传文件")
        if row.state == "accepted":
            return upload_view(row)
        if row.state != "reserved" or row.deadline <= datetime.utcnow():
            raise HTTPException(409, "接收操作已变化，请读取最新状态")
        await edit_row(db, row.edit_id, write=True)
        source.parent.mkdir(exist_ok=True, mode=0o700)
        if locks.enter_context(try_lock(source.parent / ".receive.lock")) is None:
            raise HTTPException(409, "文件正在传输")
        row.state = "receiving"
        expected = row.expected_size

    try:
        received = 0
        async with asyncio.timeout(900):
            with source.open("xb") as output:
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > MAX_BYTES:
                        raise InvalidMedia("视频大小超过 200 MiB")
                    if received > expected:
                        raise InvalidMedia("实收大小与预留不一致")
                    output.write(chunk)
                if not received or received != expected:
                    raise InvalidMedia("文件为空或接收不完整")
                output.flush()
                os.fsync(output.fileno())
            # Persist the arrival order before validation; decoding time cannot reorder uploads.
            async with sessions.begin() as db:
                head = await lock_admission(db)
                row = await locked_upload(db, key)
                if row.state != "receiving":
                    raise HTTPException(409, "编辑已放弃")
                head.last_sequence += 1
                row.arrival_sequence = head.last_sequence
                row.state = "validating"
                row.received_at = datetime.utcnow()
            metadata = await validate_source(source)
            return await accept(sessions, key, metadata, source, root)
    except (InvalidMedia, ClientDisconnect, TimeoutError, OSError, HTTPException, asyncio.CancelledError) as exc:
        reason = ("上传中断，请重新选择文件" if isinstance(exc, (ClientDisconnect, asyncio.CancelledError))
                  else "接收或校验超时" if isinstance(exc, TimeoutError)
                  else "临时文件写入失败" if isinstance(exc, OSError)
                  else str(exc.detail) if isinstance(exc, HTTPException) else str(exc))
        source.unlink(missing_ok=True)
        await asyncio.shield(fail_receive(sessions, key, reason))
        if isinstance(exc, (HTTPException, asyncio.CancelledError)):
            raise
        raise HTTPException(422, reason) from None

async def recover_receives(sessions):
    """After process death, an unlocked receipt can be finalized or released."""
    async with sessions() as db:
        keys = (await db.scalars(select(FeedVideoUpload.id).where(FeedVideoUpload.state.in_(
            ("receiving", "validating", "cancelling"))))).all()
    root = runtime_root()
    for key in keys:
        directory = root / key
        directory.mkdir(exist_ok=True, mode=0o700)
        source = directory / "source"
        with try_lock(directory / ".receive.lock") as fd:
            if fd is None:
                continue
            async with sessions.begin() as db:
                head = await lock_admission(db)
                row = await locked_upload(db, key)
                if row.state not in ("receiving", "validating", "cancelling"):
                    continue
                if row.state != "cancelling" and source.is_file() and source.stat().st_size == row.expected_size:
                    if row.arrival_sequence is None:
                        head.last_sequence += 1
                        row.arrival_sequence = head.last_sequence
                        row.received_at = datetime.utcnow()
                    row.state = "validating"
                    complete = True
                else:
                    complete = False
            if complete:
                try:
                    metadata = await validate_source(source)
                    await accept(sessions, key, metadata, source, root)
                    continue
                except (InvalidMedia, HTTPException, TimeoutError, OSError):
                    pass
            source.unlink(missing_ok=True)
            await fail_receive(sessions, key, "上传中断或文件失效，请重新选择文件")
