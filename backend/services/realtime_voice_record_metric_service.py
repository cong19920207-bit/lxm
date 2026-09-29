"""Bounded read/export audits and metrics, preserving FastAPI RBAC/errors."""
import hashlib
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import Depends, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.exceptions import HTTPException
from backend.database import get_db
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

_ACTIONS={
    'list_records':'view','record_turns':'view','record_detail':'view','record_jobs':'view',
    'record_usage':'view','record_config':'view','record_audit':'view','export_records':'export',
    'record_debug':'debug','retry_summary':'retry','retry_job':'retry','delete_record':'delete',
}

# Delete/retry already own their transaction audits. They remain metrics-only.
_AUDIT_ACTIONS = {
    'list_records': 'read_list', 'record_turns': 'read_turns',
    'record_detail': 'read_detail', 'record_jobs': 'read_jobs',
    'record_usage': 'read_usage', 'record_config': 'read_config',
    'record_audit': 'read_audit', 'record_debug': 'read_debug',
    'export_records': 'export',
}
_LIST_FILTERS = frozenset({'page', 'page_size', 'user_id', 'status', 'end_reason',
    'provider', 'model', 'config_version', 'summary_status', 'memory_status',
    'postprocess_status', 'interrupted', 'expired', 'cleared', 'audit_view',
    'deleted', 'started_from', 'started_before'})
_FILTERS = {
    'list_records': _LIST_FILTERS,
    'record_turns': frozenset({'after', 'limit'}),
    'record_debug': frozenset({'after', 'limit'}),
    'record_jobs': frozenset({'after', 'limit', 'kind'}),
    'record_audit': frozenset({'before', 'limit'}),
}
_ENUMS = {
    'status': {'ringing', 'connecting', 'connected', 'reconnecting', 'ending', 'ended', 'missed', 'failed', 'cancelled'},
    'summary_status': {'pending', 'ready', 'failed', 'not_applicable'},
    'memory_status': {'pending', 'processing', 'success', 'failed', 'skipped', 'cancelled'},
    'postprocess_status': {'pending', 'processing', 'success', 'failed', 'skipped', 'cancelled'},
    'kind': {'memory', 'postprocess', 'followup'},
}
_IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_BEARER = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def _safe_filter(key, value):
    """Never copy arbitrary filter text or validation input into the audit."""
    text = str(value)
    if len(text) > 128:
        raise ValueError('oversized')
    if key in {'page', 'page_size', 'user_id', 'config_version', 'after', 'before', 'limit'}:
        number = int(text)
        minimum = 0 if key == 'after' else 1
        maximum = 100 if key == 'page_size' else 200 if key == 'limit' else 2**63-1
        if not minimum <= number <= maximum:
            raise ValueError('range')
        return number
    if key in {'interrupted', 'expired', 'cleared', 'audit_view', 'deleted'}:
        if text.lower() not in {'1', 'true', 'yes', 'on', '0', 'false', 'no', 'off'}:
            raise ValueError('boolean')
        return text.lower() in {'1', 'true', 'yes', 'on'}
    if key in {'started_from', 'started_before'}:
        moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if moment.tzinfo is not None:
            moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
        return moment.isoformat()
    if key in _ENUMS:
        if text not in _ENUMS[key]:
            raise ValueError('enum')
        return text
    # Provider/model/end_reason are unrestricted query strings in the existing
    # API. Hash their bounded values instead of leaking text supplied as filters.
    return {'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}


def _audit_inputs(request):
    endpoint = request.state.voice_record_endpoint
    defaults = {'page': 1, 'page_size': 20, 'audit_view': False} if endpoint == 'list_records' else (
        {'after': 0, 'limit': 50} if endpoint in {'record_turns', 'record_debug', 'record_jobs'} else
        {'limit': 50} if endpoint == 'record_audit' else {})
    if endpoint == 'record_jobs':
        defaults['kind'] = 'memory'
    filters, omitted = dict(defaults), []
    for key in sorted(_FILTERS.get(endpoint, ())):
        if key not in request.query_params:
            continue
        try:
            filters[key] = _safe_filter(key, request.query_params[key])
        except (ValueError, TypeError, OverflowError):
            filters.pop(key, None)
            omitted.append(key)
    call_ids = []
    if endpoint == 'export_records':
        # FastAPI has already parsed valid JSON; never re-read arbitrary bodies.
        body = getattr(request, '_json', None)
        selected = body.get('call_ids') if isinstance(body, dict) else None
        if isinstance(selected, list) and 1 <= len(selected) <= 100 and all(
                isinstance(item, str) and _IDENTIFIER.fullmatch(item) for item in selected):
            call_ids = sorted(set(selected))
            filters['call_ids'] = call_ids
        else:
            omitted.append('call_ids')
    target = request.path_params.get('call_id')
    if isinstance(target, str) and _IDENTIFIER.fullmatch(target):
        call_ids = [target]
    return filters, omitted, call_ids


async def write_record_audit(db, admin, request, action, *, call_ids, status=200,
                             failure_category=None, writer=log_operation):
    filters, omitted, _ = _audit_inputs(request)
    request_id = request.state.voice_record_request_id
    # Semantic audit labels only; the existing role tuples still authorize.
    permission = {'export': 'voice_transcript.export', 'read_debug': 'voice_debug_generated.read',
                  'read_turns': 'voice_transcript.read', 'read_jobs': 'voice_jobs.read'}.get(action, 'voice_calls.read')
    payload = dict(schema_version=1, kind='request', request_id=request_id,
                   permission=permission, filters=filters, omitted_filter_fields=omitted,
                   result='success' if status < 400 else 'rejected' if status < 500 else 'failure',
                   http_status=status, failure_category=failure_category)
    await writer(db, admin, 'voice_calls', action, json.dumps({'request_id': request_id}),
                 after_value=json.dumps(payload, ensure_ascii=False), request=request)
    # Preserve exact legacy targets for /calls/{call_id}/audit and keep each
    # VARCHAR(500) target bounded regardless of the number of selected calls.
    for call_id in sorted(set(call_ids)):
        if not isinstance(call_id, str) or not _IDENTIFIER.fullmatch(call_id):
            continue
        await writer(db, admin, 'voice_calls', action,
                     json.dumps({'call_id': call_id}, ensure_ascii=False),
                     after_value=json.dumps(dict(schema_version=1, kind='call_reference',
                                                 request_id=request_id)), request=request)


async def _audit_failure(request, status, exc):
    if getattr(request.state, 'voice_record_outcome_saved', False) or status == 401:
        return
    try:
        db = getattr(request.state, 'voice_record_db', None)
        if db is None:
            # Malformed JSON can abort before dependencies run. Authenticate via
            # the existing validator, never by decoding an unverified token.
            credentials = await _BEARER(request)
            if credentials is None:
                return
            provider = request.app.dependency_overrides.get(get_db, get_db)
            async with asynccontextmanager(provider)() as auth_db:
                try:
                    await get_current_admin(request, credentials=credentials, db=auth_db)
                except HTTPException:
                    pass
                db = getattr(request.state, 'voice_record_db', None)
        actor = getattr(request.state, 'voice_record_admin', None)
        if db is None or actor is None:
            return
        bind = db.bind
        await db.rollback()
        category = ('audit_unavailable' if getattr(request.state, 'voice_record_audit', None) == 'failure' else
                    'projection_mismatch' if getattr(request.state, 'voice_record_snapshot', None) == 'projection_mismatch' else
                    'database_error' if isinstance(exc, SQLAlchemyError) else
                    {403: 'forbidden', 404: 'not_found', 422: 'invalid_request'}.get(status, 'internal_error'))
        request.state.voice_record_audit = 'failure'
        _, _, call_ids = _audit_inputs(request)
        async with async_sessionmaker(bind, expire_on_commit=False)() as audit_db:
            await write_record_audit(audit_db, SimpleNamespace(**actor), request,
                                     _AUDIT_ACTIONS[request.state.voice_record_endpoint],
                                     call_ids=call_ids, status=status, failure_category=category)
            await audit_db.commit()
        request.state.voice_record_outcome_saved = True
        if category != 'audit_unavailable':
            request.state.voice_record_audit = 'success'
    except Exception:
        request.state.voice_record_audit = 'failure'
        # Do not log the original exception, SQL, parameters or request body.
        logger.warning('Voice record failure audit unavailable')


def record_role(*roles):
    async def authorized(request:Request,admin=require_role(*roles),db=Depends(get_db)):
        request.state.voice_record_authorized=True
        if getattr(request.state, 'voice_record_audit_enabled', False):
            request.state.voice_record_admin = dict(id=admin.id, username=admin.username, role=admin.role)
            request.state.voice_record_db = db
        return admin
    return Depends(authorized)


class VoiceRecordMetricRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        action=_ACTIONS.get(self.endpoint.__name__)
        if action is None:return handler
        async def observed(request):
            scoped = self.endpoint.__name__ in _AUDIT_ACTIONS
            if scoped:
                request.state.voice_record_audit_enabled = True
                request.state.voice_record_endpoint = self.endpoint.__name__
                request.state.voice_record_request_id = uuid4().hex
            status=500
            try:
                response=await handler(request)
                status=response.status_code
                return response
            except HTTPException as exc:
                status=exc.status_code
                if scoped:await _audit_failure(request, status, exc)
                raise
            except RequestValidationError as exc:
                status=422
                if scoped:await _audit_failure(request, status, exc)
                raise
            except Exception as exc:
                if scoped:await _audit_failure(request, status, exc)
                raise
            finally:
                metrics=getattr(request.app.state,'voice_metrics',None)
                if metrics is not None:
                    events=[('voice.admin_record.result',{'action':action,
                        'result':'success' if status<400 else 'rejected' if status<500 else 'failure'},1)]
                    if status in (401,403):
                        events.append(('voice.admin_record.authorization',{'action':action,'result':'denied'},1))
                    elif getattr(request.state,'voice_record_authorized',False):
                        events.append(('voice.admin_record.authorization',{'action':action,'result':'authorized'},1))
                    audit=getattr(request.state,'voice_record_audit',None)
                    if audit:events.append(('voice.admin_record.audit',{'action':action,'result':audit},1))
                    snapshot=getattr(request.state,'voice_record_snapshot',None)
                    if snapshot:events.append(('voice.admin_record.fixed_snapshot',{'result':snapshot},1))
                    await metrics.emit_many(events)
        return observed
