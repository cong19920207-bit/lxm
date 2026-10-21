"""Bounded BGM crash recovery. Reads never invoke this lifecycle task."""
import asyncio
import logging
import os
import shutil

from sqlalchemy import select

from backend.models.bgm import BgmOperation, BgmProcessingSlot, utcnow
from backend.services.bgm_process import acquire_inactive_owner, temporary_root
from backend.services.bgm_upload_service import fail, release_replay

logger = logging.getLogger(__name__)
_task = None


async def recover_once(sessions):
    # Exactly one global slot: neither a table-wide media scan nor a task queue.
    async with sessions() as db:
        slot = await db.get(BgmProcessingSlot, 1)
        operation = await db.get(BgmOperation, slot.operation_id) if slot and slot.operation_id else None
    if operation and slot.state in {'replay', 'replay_quarantined'}:
        proof = acquire_inactive_owner(slot.owner_id)
        if proof or slot.deadline_at <= utcnow():
            try:
                await release_replay(sessions, operation.id, slot.owner_id, stopped=proof is not None)
                if proof: shutil.rmtree(proof[1])
            finally:
                if proof: os.close(proof[0])
    elif operation:
        expired = (operation.receive_deadline_at if operation.owner_id is None else operation.deadline_at) <= utcnow()
        proof = acquire_inactive_owner(operation.owner_id) if operation.owner_id else None
        stopped = proof is not None or operation.owner_id is None
        if proof or (expired and operation.state != 'failed'):
            try:
                handler=fail
                if operation.action in {'delete_track','cleanup_retry'}:
                    from backend.services.bgm_cleanup_service import fail as cleanup_fail
                    handler=cleanup_fail
                await handler(sessions, operation.id, operation.owner_id,
                           'deadline_expired' if expired else 'worker_interrupted', stopped=stopped)
                if proof:
                    shutil.rmtree(proof[1])
            finally:
                if proof: os.close(proof[0])
    # Recover a local proof receipt left by DB loss after a completed worker.
    # Only our UUID directories, held flock, and no current slot/active operation.
    checked = 0
    for directory in temporary_root().iterdir():
        if checked >= 32: break
        checked += 1
        proof = acquire_inactive_owner(directory.name)
        if not proof: continue
        try:
            async with sessions() as db:
                active = await db.scalar(select(BgmOperation.id).where(
                    BgmOperation.owner_id == directory.name,
                    BgmOperation.state.in_(['accepted', 'receiving', 'processing'])).limit(1))
                slot_owner = await db.scalar(select(BgmProcessingSlot.id).where(
                    BgmProcessingSlot.owner_id == directory.name).limit(1))
            if not active and not slot_owner:
                shutil.rmtree(directory)
        finally:
            os.close(proof[0])


async def _loop(sessions):
    from backend.services.memory_business_guard import enter_business_epoch, business_epoch
    while True:
        try:
            context = await enter_business_epoch(sessions)
            token = business_epoch.set(context)
            try:
                await recover_once(sessions)
            finally:
                business_epoch.reset(token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning('BGM recovery unavailable; owned resources remain fenced')
        await asyncio.sleep(5)


def start():
    global _task
    from backend.database import async_session_maker
    if _task is None:
        _task = asyncio.create_task(_loop(async_session_maker))


async def stop():
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
