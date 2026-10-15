"""S15 business-entry barrier; old processes additionally require external fencing."""
import os
from sqlalchemy import select
from backend.models.memory_control import MemoryRuntimeFence
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence


def require_uncleared_call(call):
    if call is not None and getattr(call,'cleared_run_id',None):
        raise MemoryControlError(20126,'call_cleared')
    return call


async def guard_business_write(db,expected=None):
    if db.info.get('s15_maintenance') and db.info.get('s15_drain_call'):return None
    expected = expected or business_epoch.get()
    environment=os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip()
    if not environment:
        # Legacy deployment is not activated by this code. S15 requires its
        # credentials/processes sealed and 022 installs the explicit environment.
        return None
    fence=await db.scalar(select(MemoryRuntimeFence).where(MemoryRuntimeFence.environment_id==environment))
    if not fence:raise MemoryControlError(20126,'runtime_not_active')
    if expected is not None and (expected.get('environment_id')!=environment or expected.get('target_epoch')!=fence.target_epoch
            or expected.get('target_fingerprint')!=fence.target_fingerprint.hex()):
        raise MemoryControlError(20127,'runtime_target_changed')
    await require_active_fence(db,environment,fence.target_epoch,fence.target_fingerprint,allow_isolated=environment.startswith('isolated:'))
    context = {'environment_id':environment,'target_epoch':fence.target_epoch,'target_fingerprint':fence.target_fingerprint.hex()}
    db.info['memory_business_epoch'] = context
    return context


async def guard_voice_call(db,call):
    require_uncleared_call(call)
    if call is not None:
        from backend.models.realtime_voice import VoiceCall
        marker = await db.scalar(select(VoiceCall.cleared_run_id).where(VoiceCall.call_id==call.call_id))
        if marker: raise MemoryControlError(20126,"call_cleared")
    if call is not None and db.info.get('s15_drain_call') and db.info['s15_drain_call']!=call.call_id:
        raise MemoryControlError(20127,'drain_call_changed')
    expected=(call.config_snapshot or {}).get('_memory_runtime') if call is not None else None
    await guard_business_write(db,expected)
    return call


async def guard_writer_transaction(db,writer):
    """Use the original writer snapshot, in the very transaction committing SQL."""
    if writer is None:raise MemoryControlError(20126,'writer_context_missing')
    mutations=writer.mutations
    await require_active_fence(db,mutations.environment_id,writer.config.target_epoch,
        bytes.fromhex(writer.config.target_fingerprint),mutations.allow_isolated)


def uncleared_call_condition(model):
    from backend.models.realtime_voice import VoiceCall
    return select(VoiceCall.call_id).where(VoiceCall.call_id==model.call_id,VoiceCall.cleared_run_id.is_(None)).exists()

# Requests and spawned tasks inherit the same epoch, so a late coroutine cannot
# re-resolve a new epoch and revive its pre-reset payload.
from contextvars import ContextVar
from sqlalchemy import event
from sqlalchemy.orm import Session
business_epoch=ContextVar('memory_business_epoch',default=None)


def _transaction_guard(session):
    environment=os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip()
    if not environment or session.info.get('s15_maintenance'):return
    expected=business_epoch.get() or session.info.get('memory_business_epoch')
    if expected is None:raise MemoryControlError(20126,'business_epoch_not_frozen')
    connection=session.connection()
    fence=connection.execute(select(MemoryRuntimeFence.__table__).where(
        MemoryRuntimeFence.environment_id==environment).with_for_update()).mappings().first()
    if fence is None or fence['mode']!='active':raise MemoryControlError(20126,'runtime_not_active')
    if (expected.get('environment_id')!=environment or expected['target_epoch']!=fence['target_epoch']
            or expected['target_fingerprint']!=fence['target_fingerprint'].hex()):
        raise MemoryControlError(20127,'runtime_target_changed')


@event.listens_for(Session,'before_flush')
def _guard_flush(session,flush_context,instances):
    changed=session.new|session.dirty|session.deleted
    if changed:_transaction_guard(session)
    # This immutable per-call tombstone also applies before activation and to
    # direct service calls outside HTTP. Read from SQL, not a stale ORM object.
    from backend.models.realtime_voice import VoiceCall
    ids={getattr(row,'call_id',None) for row in changed if getattr(row,'__tablename__','').startswith('voice_')
         and getattr(row,'__tablename__','') not in {'voice_metric_daily','voice_usage_ledger'}}-{None}
    if ids and not session.info.get('s15_maintenance'):
        connection=session.connection()
        if connection.execute(select(VoiceCall.call_id).where(VoiceCall.call_id.in_(ids),VoiceCall.cleared_run_id.is_not(None))).first():
            raise MemoryControlError(20126,'call_cleared')


@event.listens_for(Session,'do_orm_execute')
def _guard_dml(state):
    if state.is_update or state.is_delete or state.is_insert:_transaction_guard(state.session)


async def enter_business_epoch(sessions):
    async with sessions() as db:return await guard_business_write(db,business_epoch.get())


class BusinessMaintenanceMiddleware:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type'] not in {'http','websocket'} or not os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip():
            return await self.app(scope,receive,send)
        from backend.database import async_session_maker
        try:context=await enter_business_epoch(async_session_maker)
        except MemoryControlError:
            if scope['type']=='websocket':return await send({'type':'websocket.close','code':1013})
            from starlette.responses import JSONResponse
            return await JSONResponse({'code':20126,'message':'系统维护中','data':None},status_code=503)(scope,receive,send)
        token=business_epoch.set(context)
        try:return await self.app(scope,receive,send)
        finally:business_epoch.reset(token)


def fenced_scheduler(function):
    from functools import wraps
    @wraps(function)
    async def guarded(*args,**kwargs):
        from backend.database import async_session_maker
        try:context=await enter_business_epoch(async_session_maker)
        except MemoryControlError:return None
        token=business_epoch.set(context)
        try:return await function(*args,**kwargs)
        finally:business_epoch.reset(token)
    return guarded
