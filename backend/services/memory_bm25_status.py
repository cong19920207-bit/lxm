"""Read-only BM25 monitoring, scoped to the deployed environment, target and epoch.

Initialization is durable activation evidence, not a remote health probe. A missing
backfill is distinct from an unfinished one; neither encoder loading nor an old
completed run proves the current catalog is indexed.
"""
import asyncio
import hashlib
import os

from sqlalchemy import func, select
from sqlalchemy.orm import load_only

from backend.models.memory_backfill import MemoryBackfillRun, MemoryResetRun
from backend.models.memory_control import MemoryIdentity, MemoryRuntimeFence
from backend.services.memory_bm25 import ENCODER_VERSION
from backend.services.memory_effective_config import bm25_capability, server_time


async def read_bm25_status(db, provider):
    result = bm25_capability()
    result.update(initialization={'state': 'unknown'}, index={'state': 'unknown'},
                  backfill={'state': 'unknown'}, checked_at=server_time())
    encoder_error = result['reason'] if not result['encoder_ready'] else None
    environment = os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID', '').strip()
    if not environment:
        result.update(initialization={'state': 'not_configured'}, ready=False,
                      reason=encoder_error or 'runtime_environment_not_configured')
        return result
    if provider is None:
        result.update(ready=False if encoder_error else None,
                      reason=encoder_error or 'provider_config_unavailable')
        return result
    fingerprint = hashlib.sha256(
        f'{provider.endpoint}/v1/collections/{provider.collection_name}'.encode()).digest()
    try:
        async with asyncio.timeout(3):
            initialization, fence = await _initialization(db, environment, fingerprint)
            result['initialization'] = initialization
            if initialization['state'] != 'ready':
                result.update(ready=None if initialization['state'] == 'unknown' and not encoder_error else False,
                              reason=encoder_error or 'index_' + initialization['state'])
                return result
            result['index'] = await _index(db, fence)
            result['backfill'] = await _backfill(db, environment, fence)
    except Exception:
        # No raw SQL/provider errors and no fallback to unrelated cached status.
        result.update(ready=False if encoder_error else None,
                      reason=encoder_error or 'index_status_unavailable')
        return result
    index_ready = result['index']['state'] in {'ready', 'empty'}
    backfill_ready = result['backfill']['state'] in {'completed', 'not_started'}
    result['ready'] = result['encoder_ready'] and index_ready and backfill_ready
    result['reason'] = encoder_error or (None if result['ready'] else 'index_or_backfill_pending')
    return result


async def _initialization(db, environment, fingerprint):
    fence = await db.get(MemoryRuntimeFence, environment, populate_existing=True)
    if fence is None:
        return {'state': 'not_initialized'}, None
    if fence.target_fingerprint != fingerprint:
        return {'state': 'target_mismatch'}, fence
    reset = await db.get(MemoryResetRun, fence.reset_run_id, populate_existing=True) if fence.reset_run_id else None
    if fence.mode == 'maintenance':
        state = 'maintenance'
        if reset and reset.environment_id == environment and reset.target_fingerprint == fingerprint:
            state = {'planned': 'initializing', 'maintenance': 'initializing', 'running': 'initializing',
                     'unknown': 'unknown', 'failed': 'failed'}.get(reset.state, 'maintenance')
        return {'state': state}, fence
    if (fence.mode != 'active' or reset is None or reset.environment_id != environment
            or reset.target_epoch != fence.target_epoch or reset.target_fingerprint != fingerprint
            or reset.state not in {'completed', 'opened'} or reset.completed_at is None):
        return {'state': 'unverified'}, fence
    return {'state': 'ready'}, fence


async def _index(db, fence):
    identity = MemoryIdentity
    rows = (await db.execute(select(identity.source_state, identity.index_state,
        identity.encoder_version, func.count()).where(
            identity.target_fingerprint == fence.target_fingerprint,
            identity.target_epoch == fence.target_epoch, identity.source_state != 'deleted'
        ).group_by(identity.source_state, identity.index_state, identity.encoder_version))).all()
    counts = dict(total=0, ready=0, pending=0, manual=0, unverified=0)
    for source, index, encoder, count in rows:
        counts['total'] += count
        if source != 'live':
            counts['unverified'] += count
        elif index == 'manual':
            counts['manual'] += count
        elif index == 'ready' and encoder == ENCODER_VERSION:
            counts['ready'] += count
        else:
            counts['pending'] += count
    state = ('empty' if not counts['total'] else 'attention' if counts['manual'] or counts['unverified']
             else 'pending' if counts['pending'] else 'ready')
    return dict(state=state, **counts)


async def _backfill(db, environment, fence):
    run = MemoryBackfillRun
    query = select(run).options(load_only(run.run_id, run.execution_state, run.stage,
        run.scanned_records, run.unique_source_ids, run.total_known, run.total_source_ids,
        run.unresolved_count, run.report_complete, run.source_scope, run.created_at,
        run.updated_at, run.ended_at)).where(
        run.source_scope['environment_id'].as_string() == environment,
        run.source_scope['target_fingerprint'].as_string() == fence.target_fingerprint.hex(),
        run.source_scope['target_epoch'].as_integer() == fence.target_epoch,
        run.frozen_versions['target_epoch'].as_integer() == fence.target_epoch,
        run.frozen_versions['encoder_version'].as_string() == ENCODER_VERSION,
    ).order_by(run.created_at.desc(), run.run_id.desc()).execution_options(populate_existing=True, yield_per=100)
    latest = row = None
    completed = []
    rows = await db.stream_scalars(query)
    try:
        async for current in rows:
            if latest is None:
                latest = current
            partitions = current.source_scope.get('partitions')
            scope = (frozenset(partitions) if isinstance(partitions, list) and partitions
                     and all(isinstance(p, str) and p for p in partitions) else None)
            if current.execution_state == 'completed' and current.report_complete and not current.unresolved_count:
                if scope and current.ended_at:
                    completed.append((scope, current.ended_at))
                continue
            # A completed rerun can replace a historical paused report only
            # when it covers that scope after its last change. Active/queued
            # work and runs resumed after completion remain visible.
            if (current.execution_state in {'interrupted', 'manual_required'} and scope
                    and any(scope <= coverage and ended >= current.updated_at for coverage, ended in completed)):
                continue
            row = current
            break
    finally:
        await rows.close()
    row = row or latest
    if row is None:
        return {'state': 'not_started'}
    state = row.execution_state
    if state == 'completed' and (not row.report_complete or row.unresolved_count):
        state = 'unverified'
    return dict(state=state, run_id=row.run_id, stage=row.stage, scanned_records=row.scanned_records,
                unique_source_ids=row.unique_source_ids, total_known=row.total_known,
                total_source_ids=row.total_source_ids if row.total_known else None,
                unresolved_count=row.unresolved_count, report_complete=row.report_complete)
