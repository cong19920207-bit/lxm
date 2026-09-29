"""AC74: soft stop leaves connected call settlement available and is audited."""
import json
import pytest
from sqlalchemy import select
from backend.models.admin_config import AdminConfig
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.services.realtime_voice_ops_service import VoiceOpsService
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache


@pytest.mark.asyncio
async def test_soft_stop_preserves_connected_call_then_normal_end_and_audit(storage, monkeypatch):
    import backend.services.realtime_voice_ops_service as module
    async def compensated(db, key, operation, **kwargs):
        result = await operation()
        await db.commit()
        return result
    monkeypatch.setattr(module, '_execute_publish_with_compensation', compensated)
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    service = VoiceOpsService(cache=cache, session_factory=storage)
    async with storage() as db:
        db.add(AdminConfig(config_key='voice_call_config', version=1, is_active=True,
            is_draft=False, config_value=json.dumps({'global':{'soft_stop':False}})))
        await db.commit()
        call = await db.scalar(select(VoiceCall))
        before = {col.name:getattr(call,col.name) for col in call.__table__.columns}
        await service.soft_stop(db, confirm_text='CONFIRM', admin_user=await db.get(AdminUser,1))
        await db.refresh(call)
        assert {col.name:getattr(call,col.name) for col in call.__table__.columns} == before
        assert not cache.events
        assert json.loads(cache.data['active_config:voice_call_config'])['global']['soft_stop'] is True
        logs = (await db.scalars(select(AdminOperationLog))).all()
        assert len(logs) == 1 and logs[0].action == 'soft_stop' and logs[0].admin_user_id == 1
        assert json.loads(logs[0].after_value)['soft_stop'] is True
    await service.end_call(call_id=call_id, user_id=1, reason='user_hangup')
    async with storage() as db:
        call = await db.scalar(select(VoiceCall))
        assert call.status == 'ended' and call.end_reason == 'user_hangup'
        assert call.free_seconds_used == 9
        ledger = (await db.scalars(select(VoiceUsageLedger))).all()
        assert len(ledger) == 1 and ledger[0].call_id == call_id
