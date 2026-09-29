"""Metadata-only administrative requeue; execution stays in the memory worker."""
import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from backend.models.realtime_voice import VoiceMemoryJob, VoiceCallTurn
from backend.services.realtime_voice_state_service import lock_call
from backend.services.realtime_voice_config_service import VoiceConfigError
from backend.services.realtime_voice_memory_service import PIPELINE_VERSION, parse_memory_items
from backend.utils.admin_auth import log_operation


def rejected(code='VOICE_JOB_NOT_RETRYABLE', status=409):
    return VoiceConfigError(code, '该任务当前不能补跑', status_code=status)


async def retry_memory_job(db, *, job_id, admin, request=None):
    if admin.role not in {'super_admin', 'tech_ops'}:
        raise rejected('VOICE_JOB_FORBIDDEN', 403)
    call_id = await db.scalar(select(VoiceMemoryJob.call_id).where(VoiceMemoryJob.id == job_id))
    if call_id is None:
        raise rejected('VOICE_JOB_NOT_FOUND', 404)
    call = await lock_call(db, call_id)
    # A concurrent worker cannot claim while this short call lock is held.
    # Refuse active processing, instead of waiting on vector I/O holding locks.
    try:
        # Locking read sees current MySQL state, not the earlier lookup snapshot.
        busy = await db.scalar(select(VoiceMemoryJob.id).where(
            VoiceMemoryJob.call_id == call_id, VoiceMemoryJob.status == 'processing')
            .limit(1).with_for_update(nowait=True))
    except OperationalError as exc:
        if getattr(exc.orig, 'args', (None,))[0] == 3572:
            raise rejected('VOICE_JOB_BUSY') from None
        raise
    if busy is not None:
        raise rejected('VOICE_JOB_BUSY')
    job = await db.scalar(select(VoiceMemoryJob).where(VoiceMemoryJob.id == job_id)
        .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if job is None:
        raise rejected('VOICE_JOB_BUSY')
    turn = await db.get(VoiceCallTurn, job.turn_id)
    expiry = call.transcript_expires_at or turn.effective_text_expires_at
    if (call.deletion_fence_at or expiry is None or expiry <= datetime.utcnow() or
            job.pipeline_version != PIPELINE_VERSION or job.status != 'failed' or
            job.fail_reason not in {'extract_unavailable', 'write_unavailable', 'lease_expired'}):
        raise rejected()
    snapshot = job.extraction_snapshot
    if not isinstance(snapshot, dict) or snapshot.get('version') != 1:
        raise rejected('VOICE_JOB_SNAPSHOT_REQUIRED')
    if snapshot.get('phase') == 'ready':
        try:
            _, dropped = parse_memory_items(json.dumps({'memory_items': snapshot.get('items')}))
            if dropped or type(snapshot.get('dropped')) is not int or snapshot['dropped'] < 0:
                raise ValueError
        except ValueError:
            raise rejected('VOICE_JOB_SNAPSHOT_INVALID') from None
    elif snapshot != {'version': 1, 'phase': 'extracting'}:
        raise rejected('VOICE_JOB_SNAPSHOT_INVALID')
    before = dict(status=job.status, attempt_count=job.attempt_count, fail_reason=job.fail_reason)
    job.status = turn.memory_status = 'pending'
    job.next_retry_at = job.lease_owner = job.lease_expires_at = None
    result = dict(job_id=job.id, job_type='memory', status='pending', attempt_count=job.attempt_count)
    # Preserve cumulative attempts and the immutable atom set. This request is
    # one explicit extra attempt; it never replenishes an exhausted auto budget.
    if request is not None:request.state.voice_record_audit='failure'
    await log_operation(db, admin, 'voice_job', 'retry', call_id,
        before_value=json.dumps(before), after_value=json.dumps(result), request=request)
    from backend.services.realtime_voice_metric_service import stage_voice_metrics, flush_voice_metrics
    stage_voice_metrics(db,[('voice.memory_job.retry',{'source':'admin','reason':before['fail_reason']},1)])
    await db.commit()
    if request is not None:request.state.voice_record_audit='success'
    metrics = getattr(getattr(getattr(request,'app',None),'state',None),'voice_metrics',None)
    await flush_voice_metrics(db,metrics)
    return result
