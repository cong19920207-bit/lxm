"""Every crisis read requires super_admin and a committed read audit."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, func

from backend.database import get_db
from backend.models.realtime_voice import VoiceCrisisRecord
from backend.utils.admin_auth import require_role, log_operation

router = APIRouter()
_CRISIS_READ_ROLES = ('super_admin',)


def project(row, *, detail=False):
    expired = row.cleared_at is not None or row.expires_at <= datetime.utcnow()
    result = dict(id=row.id, call_id=row.call_id, turn_index=row.turn_index,
        direction=row.direction, match_status=row.match_status,
        is_persona_incident=row.is_persona_incident, expired=expired,
        created_at=row.created_at.isoformat(), expires_at=row.expires_at.isoformat())
    if detail:
        result.update(content_plaintext=None if expired else row.content_plaintext,
                      matched_keyword=None if expired else row.matched_keyword)
    return result


async def audited_response(db, admin, request, action, rows, data):
    # Each bounded target fits the existing VARCHAR(500), without truncating
    # the identities of any records read from a full page.
    targets = [{'call_ids': [r.call_id], 'record_ids': [r.id]} for r in rows] or [
        {'call_ids': [], 'record_ids': []}]
    result = 'failure'
    try:
        for target in targets:
            await log_operation(db, admin, module='voice_crisis', action=action,
                target_description=json.dumps(target, ensure_ascii=False), request=request)
        # Do not release any payload if the audit cannot durably commit.
        await db.commit()
        result = 'success'
    finally:
        metrics = getattr(request.app.state, 'voice_metrics', None) if request is not None else None
        if metrics is not None:
            await metrics.emit_many([('voice.crisis.audit',
                {'action':'list' if action == 'read_list' else 'detail','result':result},1)])
    return JSONResponse({'code': 0, 'data': data}, headers={'Cache-Control': 'no-store'})


@router.get('/crisis-records')
async def list_records(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       admin=require_role(*_CRISIS_READ_ROLES), db=Depends(get_db)):
    rows = (await db.scalars(select(VoiceCrisisRecord).order_by(
        VoiceCrisisRecord.is_persona_incident.desc(), VoiceCrisisRecord.created_at.desc(),
        VoiceCrisisRecord.id.desc()).offset((page-1)*page_size).limit(page_size))).all()
    total = await db.scalar(select(func.count()).select_from(VoiceCrisisRecord))
    return await audited_response(db, admin, request, 'read_list', rows,
        {'items': [project(r) for r in rows], 'total': total, 'page': page, 'page_size': page_size})


@router.get('/crisis-records/{record_id}')
async def record_detail(record_id: int, request: Request,
                        admin=require_role(*_CRISIS_READ_ROLES), db=Depends(get_db)):
    row = await db.get(VoiceCrisisRecord, record_id)
    if row is None:
        raise HTTPException(404, '记录不存在')
    return await audited_response(db, admin, request, 'read_detail', [row], project(row, detail=True))
