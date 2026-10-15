"""Bounded SQL outbox dispatch and owner leases; no dependency on a full queue."""
import asyncio
from contextlib import suppress
from datetime import datetime
import logging
from sqlalchemy import select, or_
from backend.database import async_session_maker
from backend.models.chat_lifecycle import ChatGeneration
from backend.services import chat_lifecycle as life
from backend.services.chat_timing import TIMING

log=logging.getLogger(__name__)
_tasks=set()
_scan_task=None
_failure_since=None
_failure_alerted=False
_exhausted=set()


def admission_confirmed():
    """A newly committed admission is fresh dependency-health evidence.

    This renews only the process's ability to discover new outbox records. The
    per-generation exhausted set and all persisted original deadlines survive.
    GETs and duplicate identities must never call it.
    """
    global _failure_since,_failure_alerted
    _failure_since=None
    _failure_alerted=False


def dispatch(user_id,generation_id,run_bundle,delay=0):
    async def run():
        if delay:await asyncio.sleep(delay)
        await run_bundle(user_id,generation_id)
    task=asyncio.create_task(run());_tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task

async def scan_once(run_bundle,*,sessions=None):
    """Only current unresolved lifecycle records; no remote execution replay."""
    global _failure_since,_failure_alerted
    sessions=sessions or async_session_maker
    if _failure_alerted:return
    try:
        async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
            async with sessions() as db:
                now=await life.db_now(db)
                rows=list((await db.execute(select(ChatGeneration).where(ChatGeneration.state=='pending',ChatGeneration.phase!='reconcile_exhausted',
                    ChatGeneration.generation_id.not_in(_exhausted),
                    or_(ChatGeneration.deadline_at<=now,
                        (ChatGeneration.dispatch_state=='pending')&(ChatGeneration.next_dispatch_at<=now),
                        ChatGeneration.lease_until<=now))
                    .order_by(ChatGeneration.next_dispatch_at,ChatGeneration.generation_id).limit(TIMING.scan_batch_size))).scalars())
        _failure_since=None;_failure_alerted=False
    except Exception:
        _failure_since=_failure_since or datetime.utcnow()
        if not _failure_alerted and (datetime.utcnow()-_failure_since).total_seconds()>=TIMING.reconcile_margin_ms/1000:
            log.error('chat_lifecycle_reconcile_exhausted: storage_unavailable');_failure_alerted=True
        return
    for row in rows:
        if now>=row.reconcile_until and row.phase=='reconcile_exhausted':continue
        status=await life.reconcile(row.user_id,row.generation_id,sessions=sessions)
        if status=='pending' and row.deadline_at>now:
            dispatch(row.user_id,row.generation_id,run_bundle)
        elif status=='unverified' and now>=row.reconcile_until:
            _exhausted.add(row.generation_id)
            log.error('chat_lifecycle_reconcile_exhausted generation=%s',row.generation_id)
            # Persistent status when storage permits; unavailable DB cannot be
            # falsely claimed to have stored a terminal or an alert receipt.
            try:
                async with asyncio.timeout(TIMING.probe_timeout_ms/1000):
                    async with sessions() as db:
                        us=await life.lock_user(db,row.user_id)
                        current=await life.locked_generation(db,row.user_id,row.generation_id)
                        if current.state=='pending' and current.phase!='reconcile_exhausted':
                            current.phase='reconcile_exhausted';current.reason='commit_unknown'
                            us.state_revision+=1;current.state_revision=us.state_revision
                            await db.commit()
            except Exception:pass

async def _loop(run_bundle):
    while True:
        await scan_once(run_bundle)
        try:await life.expire_submissions()
        except Exception:pass
        await asyncio.sleep(TIMING.scan_interval_ms/1000)

def start(run_bundle):
    global _scan_task
    if _scan_task is None or _scan_task.done():_scan_task=asyncio.create_task(_loop(run_bundle))

async def stop():
    global _scan_task
    if _scan_task:
        _scan_task.cancel()
        with suppress(asyncio.CancelledError):await _scan_task
        _scan_task=None

async def heartbeat(handle,worker):
    while True:
        await asyncio.sleep(TIMING.renew_ms/1000)
        try:valid=await life.renew(handle)
        except Exception:valid=False
        if not valid:
            payload=await life.generation_payload(handle.user_id,handle.generation_id)
            # A successful transaction may finish while this renewal waits on
            # its lock; allow the original success owner to dispatch effects.
            if payload is not None and payload.get('error') is False:return
            worker.cancel();return
