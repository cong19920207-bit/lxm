"""Audit failed BGM writes outside the business transaction without weakening auth."""
import json
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID,uuid4

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.database import get_db
from backend.utils.admin_auth import log_operation
from backend.schemas.common import ApiResponse
from backend.services.bgm_errors import BgmError

logger = logging.getLogger(__name__)
WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


async def audit_rejection(request, status):
    """Only known categories and validated identity; never serialize body/exception."""
    if getattr(request.state, 'bgm_outcome_audited', False):
        return
    actor = getattr(request.state, 'bgm_audit_actor', None)
    actor = SimpleNamespace(**actor) if actor else SimpleNamespace(id=None, username='未认证', role=None)
    category = {401: 'unauthenticated', 403: 'forbidden', 409: 'conflict',
                422: 'invalid_request', 429: 'busy'}.get(status, 'internal_error')
    payload = dict(request_id=request.state.bgm_request_id, role=actor.role,
                   result='rejected' if status < 500 else 'failed', http_status=status,
                   failure_category=category, method=request.method)
    # Correlate only syntactically valid identifiers; never persist arbitrary URL
    # fragments or inspect an upload body just to produce a rejection log.
    for field in ['track_id','operation_id']:
        try:payload[field]=str(UUID(request.path_params[field]))
        except (KeyError,ValueError,TypeError,AttributeError):pass
    # Path values are untrusted and are not persisted; the matched route template is safe.
    route = request.scope.get('route')
    target = getattr(route, 'path', '/api/admin/bgm')
    try:
        source_db = getattr(request.state, 'bgm_auth_db', None)
        if source_db is not None:
            bind = source_db.bind
            await source_db.rollback()
        else:
            provider = request.app.dependency_overrides.get(get_db, get_db)
            async with asynccontextmanager(provider)() as auth_db:
                bind = auth_db.bind
        async with async_sessionmaker(bind, expire_on_commit=False)() as audit_db:
            await log_operation(audit_db, actor, 'bgm', 'denied' if status < 500 else 'failed',
                                target, after_value=json.dumps(payload, ensure_ascii=False), request=request)
            await audit_db.commit()
        request.state.bgm_outcome_audited = True
    except Exception:
        # Auth must remain denied even if audit storage itself is unavailable.
        logger.warning('BGM rejection audit unavailable; request_id=%s', request.state.bgm_request_id)


class BgmAuditRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def audited(request):
            if request.method not in WRITE_METHODS:
                return await handler(request)
            request.state.bgm_audit_enabled = True
            request.state.bgm_request_id = str(uuid4())
            try:
                return await handler(request)
            except BgmError as exc:
                await audit_rejection(request, exc.status)
                return JSONResponse(status_code=exc.status, content=ApiResponse.fail(exc.code).model_dump())
            except HTTPException as exc:
                await audit_rejection(request, exc.status_code)
                raise
            except RequestValidationError:
                await audit_rejection(request, 422)
                raise
            except Exception:
                await audit_rejection(request, 500)
                raise

        return audited
