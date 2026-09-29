"""Voice record routes: explicit body roles and durable, content-free read audits."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, or_, and_, cast, String, literal

from backend.database import get_db
from backend.models.realtime_voice import VoiceCall, VoiceCallTurn, VoiceMemoryJob, VoicePostprocessJob, VoiceFollowupJob
from backend.services.realtime_voice_record_service import effective_turn, export_turn, overview, iso, record_statistics, transcript_statistics
from backend.utils.admin_auth import require_role, deny_observer_export, log_operation
from backend.schemas.realtime_voice_records import ExportRequest, EffectiveExportResponse
from backend.services.realtime_voice_retention_service import build_voice_retention_service

from backend.services.realtime_voice_record_metric_service import VoiceRecordMetricRoute, record_role

router = APIRouter(route_class=VoiceRecordMetricRoute)
_RECORD_READ_ROLES = ('super_admin', 'ops_admin', 'observer')
_RECORD_EXPORT_ROLES = ('super_admin', 'ops_admin')
_JOB_READ_ROLES = ('super_admin', 'ops_admin', 'observer', 'tech_ops')


@router.delete('/calls/{call_id}')
async def delete_record(call_id: str, request: Request,
                        admin=record_role('super_admin'),service=Depends(build_voice_retention_service)):
    from backend.services.realtime_voice_config_service import VoiceConfigError
    try:
        result=await service.delete_call(call_id=call_id,admin=admin,request=request)
    except VoiceConfigError as exc:
        raise HTTPException(exc.status_code,exc.message) from None
    except Exception:
        raise HTTPException(503,'通话删除未完成，请重试') from None
    return JSONResponse({'code':0,'data':result},headers={'Cache-Control':'no-store'})


async def audited(db, admin, request, action, data, *, call_ids):
    from backend.services.realtime_voice_record_metric_service import write_record_audit
    request.state.voice_record_audit='failure'
    await write_record_audit(db, admin, request, action, call_ids=call_ids, writer=log_operation)
    await db.commit()
    request.state.voice_record_audit='success'
    request.state.voice_record_outcome_saved=True
    return JSONResponse({'code': 0, 'data': data}, headers={'Cache-Control': 'no-store'})


@router.get('/calls')
async def list_records(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       user_id: int | None = Query(None, ge=1), status: str | None = None,
                       end_reason: str | None = None, provider: str | None = None,
                       model: str | None = None, config_version: int | None = Query(None, ge=1),
                       summary_status: str | None = None, memory_status: str | None = None,
                       postprocess_status: str | None = None, interrupted: bool | None = None,
                       expired: bool | None = None, cleared: bool | None = None,
                       audit_view: bool = False, deleted: bool | None = None,
                       started_from: datetime | None = None, started_before: datetime | None = None,
                       admin=record_role(*_RECORD_READ_ROLES), db=Depends(get_db)):
    from datetime import timezone
    def utc(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value
    started_from, started_before = utc(started_from), utc(started_before)
    if started_from and started_before and started_from >= started_before:
        raise HTTPException(422, '开始时间必须早于结束时间')
    if deleted is not None and not audit_view:
        raise HTTPException(422, '已删除筛选仅限审计视图')
    filters = []
    for field, value in ((VoiceCall.user_id,user_id),(VoiceCall.status,status),(VoiceCall.end_reason,end_reason),
                         (VoiceCall.provider,provider),(VoiceCall.summary_status,summary_status)):
        if value is not None: filters.append(field == value)
    if not audit_view: filters.append(VoiceCall.deleted_at.is_(None))
    if deleted is not None: filters.append(VoiceCall.deleted_at.is_not(None) if deleted else VoiceCall.deleted_at.is_(None))
    if started_from: filters.append(VoiceCall.created_at >= started_from)
    if started_before: filters.append(VoiceCall.created_at < started_before)
    if model is not None: filters.append(VoiceCall.config_snapshot['resolved_config']['s2s']['model_version'].as_string() == model)
    if config_version is not None: filters.append(VoiceCall.config_snapshot['config_version'].as_integer() == config_version)
    now = datetime.utcnow()
    if expired is not None:
        filters.append(VoiceCall.transcript_expires_at <= now if expired else
            or_(VoiceCall.transcript_expires_at.is_(None), VoiceCall.transcript_expires_at > now))
    for kind, model_cls, value in (('memory',VoiceMemoryJob,memory_status),('postprocess',VoicePostprocessJob,postprocess_status)):
        if value is not None:
            filters.append(select(model_cls.id).where(model_cls.call_id==VoiceCall.call_id, model_cls.status==value).exists())
    if interrupted is not None:
        has = select(VoiceCallTurn.id).where(VoiceCallTurn.call_id==VoiceCall.call_id, VoiceCallTurn.assistant_interrupted.is_(True)).exists()
        filters.append(has if interrupted else ~has)
    if cleared is not None:
        has = select(VoiceCallTurn.id).where(VoiceCallTurn.call_id==VoiceCall.call_id, VoiceCallTurn.effective_text_cleared_at.is_not(None)).exists()
        filters.append(has if cleared else ~has)
    total = await db.scalar(select(func.count()).select_from(VoiceCall).where(*filters))
    rows = (await db.scalars(select(VoiceCall).where(*filters).order_by(VoiceCall.created_at.desc(), VoiceCall.id.desc())
        .offset((page-1)*page_size).limit(page_size))).all()
    items = [overview(row, now=now) for row in rows]
    stats = await record_statistics(db, [row.call_id for row in rows])
    for item in items: item.update(stats[item['call_id']])
    return await audited(db, admin, request, 'read_list', dict(items=items,total=total,page=page,page_size=page_size),
                         call_ids=[row.call_id for row in rows])


@router.post('/calls/export', dependencies=[Depends(deny_observer_export)], response_model=EffectiveExportResponse)
async def export_records(payload: ExportRequest, request: Request,
                         admin=record_role(*_RECORD_EXPORT_ROLES), db=Depends(get_db)):
    # Lock selected parent rows until the snapshot and its audit are committed.
    calls = (await db.scalars(select(VoiceCall).where(VoiceCall.call_id.in_(set(payload.call_ids)))
        .order_by(VoiceCall.call_id).with_for_update().execution_options(populate_existing=True))).all()
    if len(calls) != len(set(payload.call_ids)):
        raise HTTPException(404, '通话不存在')
    now = datetime.utcnow()
    items = []
    expected_items = []
    for call in calls:
        turns = (await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id == call.call_id)
            .order_by(VoiceCallTurn.turn_index).with_for_update().execution_options(populate_existing=True))).all()
        for turn in turns:
            item = effective_turn(call, turn, now=now)
            if item['content_available']:
                items.append(export_turn(item))
                expected_items.append(dict(call_id=turn.call_id,turn_index=turn.turn_index,
                    user_text_final=turn.user_text_final,assistant_text_effective=turn.assistant_text_effective,
                    effective_text_expires_at=iso(turn.effective_text_expires_at)))
    from collections import Counter
    import json
    from pydantic import ValidationError
    try:
        data = EffectiveExportResponse(code=0, data={'items':items,'snapshot_at':now}).model_dump(mode='json')['data']
        actual=Counter(json.dumps(item,sort_keys=True) for item in data['items'])
        expected=Counter(json.dumps(item,sort_keys=True) for item in expected_items)
        if actual!=expected:raise ValueError('voice_export_projection_mismatch')
    except (ValidationError,ValueError):
        request.state.voice_record_snapshot='projection_mismatch'
        raise HTTPException(500,'导出投影校验失败') from None
    request.state.voice_record_snapshot='valid'
    return await audited(db, admin, request, 'export', data,
                         call_ids=[call.call_id for call in calls])


@router.get('/calls/{call_id}/turns')
async def record_turns(call_id: str, request: Request, after: int = Query(0, ge=0),
                      limit: int = Query(50, ge=1, le=200),
                      admin=record_role(*_RECORD_READ_ROLES), db=Depends(get_db)):
    call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
    if call is None:
        raise HTTPException(404, '通话不存在')
    rows = (await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id == call_id,
        VoiceCallTurn.turn_index > after).order_by(VoiceCallTurn.turn_index).limit(limit+1))).all()
    now = datetime.utcnow()
    items = [effective_turn(call, turn, now=now) for turn in rows[:limit]]
    return await audited(db, admin, request, 'read_turns', {
        'items': items, 'next_after': rows[limit-1].turn_index if len(rows)>limit else None}, call_ids=[call_id])


@router.get('/calls/{call_id}')
async def record_detail(call_id: str, request: Request,
                        admin=record_role(*_RECORD_READ_ROLES), db=Depends(get_db)):
    call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
    if call is None:
        raise HTTPException(404, '通话不存在')
    now = datetime.utcnow()
    data = overview(call, now=now)
    data.update((await transcript_statistics(db, [call_id], now=now))[call_id])
    return await audited(db, admin, request, 'read_detail', data, call_ids=[call_id])


@router.get('/calls/{call_id}/debug')
async def record_debug(call_id: str, request: Request, after: int = Query(0, ge=0),
                       limit: int = Query(50, ge=1, le=200),
                       admin=record_role('super_admin'), db=Depends(get_db)):
    call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id)
        .with_for_update().execution_options(populate_existing=True))
    if call is None:
        raise HTTPException(404, '通话不存在')
    now = datetime.utcnow()
    live = call.deleted_at is None and call.deletion_fence_at is None
    rows = (await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id == call_id,
        VoiceCallTurn.turn_index > after).order_by(VoiceCallTurn.turn_index).limit(limit+1))).all()
    items = []
    for turn in rows[:limit]:
        readable = (live and turn.generated_text_cleared_at is None
            and turn.generated_text_expires_at is not None and turn.generated_text_expires_at > now
            and turn.user_crisis_status == 'passed' and turn.assistant_crisis_status == 'passed')
        items.append(dict(turn_index=turn.turn_index,
            assistant_text_generated=turn.assistant_text_generated if readable else None,
            generated_text_expires_at=iso(turn.generated_text_expires_at),
            generated_text_cleared_at=iso(turn.generated_text_cleared_at)))
    reasoning_live = live and call.reasoning_expires_at is not None and call.reasoning_expires_at > now
    return await audited(db, admin, request, 'read_debug', dict(call_id=call_id,
        reasoning=call.summary_reasoning if reasoning_live else None,
        reasoning_expires_at=iso(call.reasoning_expires_at), items=items,
        next_after=rows[limit-1].turn_index if len(rows)>limit else None), call_ids=[call_id])


@router.get('/calls/{call_id}/jobs')
async def record_jobs(call_id: str, request: Request, kind: Literal['memory','postprocess','followup']='memory',
                      after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                      admin=record_role(*_JOB_READ_ROLES), db=Depends(get_db)):
    exists = await db.scalar(select(VoiceCall.id).where(VoiceCall.call_id == call_id))
    if exists is None:
        raise HTTPException(404, '通话不存在')
    model = {'memory':VoiceMemoryJob, 'postprocess':VoicePostprocessJob, 'followup':VoiceFollowupJob}[kind]
    rows = (await db.scalars(select(model).where(model.call_id == call_id, model.id > after)
        .order_by(model.id).limit(limit+1))).all()
    safe_reasons = {'extract_unavailable','write_unavailable','lease_expired','invalid_or_rejected_output',
        'model_unavailable','result_commit_failed','source_expired','admin_deleted'}
    items = [dict(id=row.id, call_id=call_id, kind=kind, status=row.status,
        job_type=row.job_type if kind=='postprocess' else row.content_type if kind=='followup' else 'memory',
        retry_path=(f'/jobs/{row.id}/retry' if kind=='memory' else
            f'/summary-jobs/{row.id}/retry' if kind=='postprocess' and row.job_type=='call_summary' else None)
            if row.status=='failed' and row.fail_reason in {'extract_unavailable','write_unavailable','lease_expired',
                'invalid_or_rejected_output','model_unavailable','result_commit_failed'} else None,
        attempt_count=row.attempt_count, next_retry_at=iso(row.next_retry_at),
        fail_reason=row.fail_reason if row.fail_reason in safe_reasons else 'other' if row.fail_reason else None,
        created_at=iso(row.created_at), updated_at=iso(row.updated_at)) for row in rows[:limit]]
    return await audited(db, admin, request, 'read_jobs', dict(items=items,
        next_after=rows[limit-1].id if len(rows)>limit else None), call_ids=[call_id])


@router.post('/summary-jobs/{job_id}/retry')
async def retry_summary(job_id: int, request: Request,
                        admin=record_role('super_admin','tech_ops'), db=Depends(get_db)):
    from backend.services.realtime_voice_summary_job_service import retry_summary_job
    from backend.services.realtime_voice_config_service import VoiceConfigError
    try:
        result = await retry_summary_job(db, job_id=job_id, admin=admin, request=request)
    except VoiceConfigError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return JSONResponse({'code':0, 'data':result}, headers={'Cache-Control':'no-store'})


@router.get('/calls/{call_id}/usage')
async def record_usage(call_id: str, request: Request,
                        admin=record_role(*_RECORD_READ_ROLES), db=Depends(get_db)):
    from backend.models.realtime_voice import VoiceUsageLedger
    from backend.models.relationship_growth_log import RelationshipGrowthLog
    call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
    if call is None:
        raise HTTPException(404, '通话不存在')
    ledger = (await db.scalars(select(VoiceUsageLedger).where(VoiceUsageLedger.call_id == call_id)
        .order_by(VoiceUsageLedger.segment_seq))).all()
    growth = (await db.scalars(select(RelationshipGrowthLog).where(
        RelationshipGrowthLog.source_type == 'voice_call', RelationshipGrowthLog.source_id == call_id)
        .order_by(RelationshipGrowthLog.id))).all()
    data = dict(call_id=call_id, ledger=[dict(id=row.id,segment_seq=row.segment_seq,
        usage_type=row.usage_type,duration_seconds=row.duration_seconds,
        free_seconds_used=row.free_seconds_used,extra_seconds_used=row.extra_seconds_used,
        quota_date=iso(row.quota_date)) for row in ledger],
        growth=[dict(id=row.id,points=row.points,eligible_seconds=row.eligible_seconds,
            business_date=iso(row.business_date),created_at=iso(row.created_at)) for row in growth])
    return await audited(db, admin, request, 'read_usage', data, call_ids=[call_id])


@router.get('/calls/{call_id}/config')
async def record_config(call_id: str, request: Request,
                         admin=record_role(*_RECORD_READ_ROLES), db=Depends(get_db)):
    from backend.services.realtime_voice_config_service import project_voice_snapshot_for_role
    call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
    if call is None:
        raise HTTPException(404, '通话不存在')
    keys = ('config_version','config_content_sha256','config_schema_version','config_published_at',
        'script_version','script_content_sha256','script_schema_version','script_published_at',
        'resolved_config','resolved_script')
    stored_snapshot = call.config_snapshot or {}
    snapshot = {key: stored_snapshot[key] for key in keys if key in stored_snapshot}
    return await audited(db,admin,request,'read_config',dict(call_id=call_id,
        config_snapshot=project_voice_snapshot_for_role(snapshot, admin.role),
        capability_snapshot=project_voice_snapshot_for_role(call.capability_snapshot, admin.role)),call_ids=[call_id])


@router.get('/calls/{call_id}/audit')
async def record_audit(call_id: str, request: Request, before: int | None = Query(None, ge=1),
                       limit: int = Query(50, ge=1, le=200),
                       admin=record_role(*_RECORD_READ_ROLES), db=Depends(get_db)):
    import json
    from backend.models.admin_operation_log import AdminOperationLog
    if await db.scalar(select(VoiceCall.id).where(VoiceCall.call_id == call_id)) is None:
        raise HTTPException(404, '通话不存在')
    direct = and_(AdminOperationLog.module.in_(['voice_calls','voice_call','voice_ops','voice_job']),
        AdminOperationLog.target_description.in_([json.dumps({'call_id':call_id},ensure_ascii=False),
            call_id, f'语音通话 {call_id}']))
    memory_target = literal('memory:') + cast(VoiceMemoryJob.id, String)
    summary_target = literal('call_summary:') + cast(VoicePostprocessJob.id, String)
    if db.bind.dialect.name == 'mysql':
        # Existing operation logs use utf8mb4_unicode_ci, while MySQL 8 casts
        # use the connection's utf8mb4_0900_ai_ci collation.
        memory_target = memory_target.collate('utf8mb4_unicode_ci')
        summary_target = summary_target.collate('utf8mb4_unicode_ci')
    legacy_memory = select(VoiceMemoryJob.id).where(VoiceMemoryJob.call_id==call_id,
        AdminOperationLog.target_description == memory_target).exists()
    legacy_summary = select(VoicePostprocessJob.id).where(VoicePostprocessJob.call_id==call_id,
        VoicePostprocessJob.job_type=='call_summary',
        AdminOperationLog.target_description == summary_target).exists()
    filters = [or_(direct, and_(AdminOperationLog.module=='voice_job',or_(legacy_memory,legacy_summary)))]
    if before is not None: filters.append(AdminOperationLog.id < before)
    rows = (await db.scalars(select(AdminOperationLog).where(*filters).order_by(AdminOperationLog.id.desc())
        .limit(limit+1))).all()
    items = [dict(id=row.id,admin_username=row.admin_username,module=row.module,action=row.action,
        created_at=iso(row.created_at),call_id=call_id) for row in rows[:limit]]
    return await audited(db,admin,request,'read_audit',dict(items=items,
        next_before=rows[limit-1].id if len(rows)>limit else None),call_ids=[call_id])
