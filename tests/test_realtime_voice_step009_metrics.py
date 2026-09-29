from uuid import uuid4
import pytest
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step009_ops import storage,StateCache,add_call,AdminUser


@pytest.mark.asyncio
@pytest.mark.parametrize('outage',[False,True])
async def test_renew_failure_ends_before_observation(outage):
    sink=CounterCache();ended=[]
    class Cache:
        async def eval(self,*args):
            if outage:raise ConnectionError('private-redis-error')
            return 0
    async def end(**kwargs):
        assert sink.batches==[];ended.append(kwargs)
    lease=VoiceLeaseService(Cache(),end_call=end,metrics=VoiceMetrics(sink));call_id=str(uuid4())
    assert not await lease.renew(user_id=1,call_id=call_id,ttl_ms=15000)
    assert ended==[dict(call_id=call_id,user_id=1,reason='system_error')]
    events=[e for b in sink.batches for e in b]
    assert ('voice.lease.renew',{'result':'failure' if outage else 'owner_mismatch'},1) in events
    assert any(e[0]=='voice.lease.owner_mismatch' for e in events)==(not outage)


@pytest.mark.asyncio
async def test_stop_and_reconcile_actual_paths(storage,monkeypatch):
    from backend.services.realtime_voice_config_service import VoiceConfigError
    sink=CounterCache();cache=StateCache();service=VoiceOpsService(cache=cache,session_factory=storage,metrics=VoiceMetrics(sink))
    call_id=await add_call(storage,'ringing',cache)
    async with storage() as db:
        admin=await db.get(AdminUser,1)
        with pytest.raises(VoiceConfigError):await service.soft_stop(db,confirm_text='invalid',admin_user=admin)
        result=await service.hard_stop(db,confirm_text='CONFIRM',admin_user=admin)
        assert result['failed']==[]
    await service.reconcile()
    events=[e for b in sink.batches for e in b]
    assert ('voice.ops_stop.result',{'operation':'soft','result':'rejected'},1) in events
    assert ('voice.ops_stop.result',{'operation':'hard','result':'success'},1) in events
    assert ('voice.lease.reconcile',{'result':'success'},1) in events


@pytest.mark.asyncio
@pytest.mark.parametrize('terminal',[True,False])
async def test_reconcile_cleanup_pending_never_reports_success(storage,monkeypatch,terminal):
    sink=CounterCache();cache=StateCache();service=VoiceOpsService(cache=cache,session_factory=storage,metrics=VoiceMetrics(sink))
    await add_call(storage,'missed' if terminal else 'ringing',cache)
    async def incomplete(*args,**kwargs):return False
    async def end(**kwargs):return {'cleanup_pending':True}
    monkeypatch.setattr(service,'_cleanup_ended',incomplete)
    monkeypatch.setattr(service,'end_call',end)
    if terminal:
        from sqlalchemy import update
        from datetime import datetime
        from backend.models.realtime_voice import VoiceCall
        async with storage() as db:
            await db.execute(update(VoiceCall).values(ended_at=datetime.utcnow()));await db.commit()
    await service.reconcile()
    events=[e for b in sink.batches for e in b]
    assert ('voice.lease.reconcile',{'result':'failure'},1) in events
    assert ('voice.lease.reconcile',{'result':'success'},1) not in events
