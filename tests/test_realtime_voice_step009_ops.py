from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from backend.routers.admin.voice_ops import router,get_voice_ops
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.utils.admin_auth import get_current_admin
from backend.database import get_db

ROLES=('super_admin','tech_ops','observer','ops_admin','ai_trainer')
ACTIONS=('/ops/active-calls','/ops/soft-stop','/ops/hard-stop','/calls/'+str(uuid4())+'/force-end')

class Ops:
    def __init__(self):self.writes=[]
    confirm=staticmethod(VoiceOpsService.confirm)
    async def active_calls(self,db):return {'calls':[],'database_count':0,'lease_count':0}
    async def soft_stop(self,db,**kw):self.confirm(kw['confirm_text']);self.writes.append('soft');return {}
    async def hard_stop(self,db,**kw):self.confirm(kw['confirm_text']);self.writes.append('hard');return {'failed':[]}
    async def end_call(self,**kw):self.writes.append('end');return {}

@pytest.mark.asyncio
@pytest.mark.parametrize('role',ROLES)
@pytest.mark.parametrize('action',ACTIONS)
async def test_five_roles_each_endpoint(role,action):
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice');ops=Ops()
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role=role,id=1,username=role)
    app.dependency_overrides[get_voice_ops]=lambda:ops
    app.dependency_overrides[get_db]=lambda:None
    read=action==ACTIONS[0]
    allowed=role in (('super_admin','tech_ops','observer') if read else ('super_admin','tech_ops'))
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.get('/api/admin/voice'+action) if read else await client.post('/api/admin/voice'+action,json={'confirm_text':'CONFIRM'})
    assert response.status_code==(200 if allowed else 403)
    if not allowed or read:assert ops.writes==[]
    else:assert len(ops.writes)==1

@pytest.mark.asyncio
@pytest.mark.parametrize('action',ACTIONS[1:])
@pytest.mark.parametrize('value',['confirm',' CONFIRM','CONFIRM ',''])
async def test_exact_confirm_required_before_any_mutation(action,value):
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice');ops=Ops()
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='super_admin',id=1,username='root')
    app.dependency_overrides[get_voice_ops]=lambda:ops
    app.dependency_overrides[get_db]=lambda:None
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result=await client.post('/api/admin/voice'+action,json={'confirm_text':value})
    assert result.status_code==400 and ops.writes==[]

import json
from datetime import datetime, timezone
import pytest_asyncio
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
import backend.models
from backend.database import Base
from backend.models.user import User
from backend.models.admin_user import AdminUser
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_config import AdminConfig
from backend.models.realtime_voice import VoiceCall,VoiceCallTurn,VoiceUsageLedger,VoiceQuotaAccount,VoiceFollowupJob,VoiceCrisisRecord
from backend.models.user_timeline_seq import UserTimelineSeq
from backend.services.realtime_voice_quota_service import VoiceQuotaService,ConnectedMeter

class StateCache:
    def __init__(self):self.data={};self.events=[]
    async def get(self,key):return self.data.get(key)
    async def setex(self,key,ttl,value):self.data[key]=value
    async def eval(self,*args):
        if len(args) > 4 and args[2].startswith('voice:session_context:') and args[4] == 'delete':
            self.data.pop(args[2], None)
            return ['ok']
        return 0
    async def publish(self,key,value):self.events.append((key,value))
    async def zcard(self,key):return 0


@pytest.mark.asyncio
@pytest.mark.parametrize('connected,owner,expected',[(True,True,'hard_limit'),(False,False,'system_error'),(False,True,None)])
async def test_reconcile_hard_limit_only_after_connection(storage,monkeypatch,connected,owner,expected):
    from datetime import timedelta
    from backend.services.realtime_voice_lease_service import VoiceLeaseService
    cache=StateCache();call_id=await add_call(storage,'connected' if connected else 'ringing',cache)
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));row.created_at=datetime.utcnow()-timedelta(hours=2)
        if connected:row.connected_at=datetime.utcnow()-timedelta(hours=2)
        await db.commit()
    async def matches(self,**kw):return owner
    monkeypatch.setattr(VoiceLeaseService,'owner_matches',matches)
    service=VoiceOpsService(cache=cache,session_factory=storage)
    reasons=[]
    async def end(**kw):reasons.append(kw['reason'])
    monkeypatch.setattr(service,'end_call',end)
    await service.reconcile()
    assert reasons==([expected] if expected else [])

@pytest_asyncio.fixture
async def storage():
    from backend.models.relationship import Relationship
    from backend.models.relationship_growth_log import RelationshipGrowthLog
    from backend.models.relationship_level_history import RelationshipLevelHistory
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[m.__table__ for m in (User,AdminUser,AdminOperationLog,AdminConfig,VoiceCrisisRecord,VoiceCall,VoiceCallTurn,VoiceQuotaAccount,VoiceUsageLedger,UserTimelineSeq,Relationship,RelationshipGrowthLog,RelationshipLevelHistory,VoiceFollowupJob)])
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async with factory() as db:
        db.add(User(id=1,username='ops',password_hash='unused'))
        db.add(AdminUser(id=1,username='ops',password_hash='unused',role='tech_ops'))
        await db.commit()
    yield factory
    await engine.dispose()

async def add_call(factory,status,cache):
    call_id=str(uuid4());now=datetime.now(timezone.utc)
    async with factory() as db:
        db.add(VoiceCall(call_id=call_id,user_id=1,initiated_by='user',status=status,summary_status='pending',
                        connected_at=now.replace(tzinfo=None) if status=='connected' else None,
                        config_snapshot={'resolved_config':{'quota':{'hard_limit_seconds':3600}}},capability_snapshot={},
                        transcript_retention_days=180,generated_retention_days=30))
        await db.commit()
        if status=='connected':
            from dataclasses import asdict
            from datetime import timedelta
            meter=ConnectedMeter(call_id,1,300,30);quota=VoiceQuotaService()
            await quota.observe(db,meter,connected=True,monotonic=0,now=now)
            await quota.observe(db,meter,connected=True,monotonic=9,now=now+timedelta(seconds=9))
            cache.data['voice:quota:'+call_id]=json.dumps(asdict(meter))
    return call_id

@pytest.mark.asyncio
async def test_hard_stop_fixed_active_set_control_rows_unchanged_and_replay(storage):
    cache=StateCache();service=VoiceOpsService(cache=cache,session_factory=storage)
    active=[await add_call(storage,state,cache) for state in ('connected','ringing')]
    control=await add_call(storage,'missed',cache)
    async with storage() as db:
        admin=await db.get(AdminUser,1)
        result=await service.hard_stop(db,confirm_text='CONFIRM',admin_user=admin)
        assert set(result['targets'])==set(active) and not result['failed']
        again=await service.hard_stop(db,confirm_text='CONFIRM',admin_user=admin)
        assert again['targets']==[]
    async with storage() as db:
        rows=(await db.scalars(select(VoiceCall))).all()
        # C83: a successful hard stop does not imply the call ever connected.
        assert all(r.status==('ended' if r.connected_at else 'failed') and r.end_reason=='system_error'
                   for r in rows if r.call_id in active)
        assert next(r for r in rows if r.call_id==control).status=='missed'
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger))==1
        assert await db.scalar(select(func.count()).select_from(AdminOperationLog))==4

@pytest.mark.asyncio
async def test_soft_stop_only_changes_published_gate_preserves_draft_and_active_calls(storage,monkeypatch):
    import backend.services.realtime_voice_ops_service as module
    async def compensated(db,key,operation,**kw):
        result=await operation();await db.commit();return result
    monkeypatch.setattr(module,'_execute_publish_with_compensation',compensated)
    from tests.test_realtime_voice_step031_metrics import CounterCache
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    sink=CounterCache()
    cache=StateCache();service=VoiceOpsService(cache=cache,session_factory=storage,metrics=VoiceMetrics(sink))
    call_id=await add_call(storage,'ringing',cache)
    original={'global':{'soft_stop':False},'unrelated':{'preserve':'exact'}}
    draft=json.dumps({'unrelated':'user draft'})
    async with storage() as db:
        db.add_all([AdminConfig(config_key='voice_call_config',config_value=json.dumps(original),version=4,is_active=True,is_draft=False),
                    AdminConfig(config_key='voice_call_config',config_value=draft,version=4,draft_revision=7,is_active=False,is_draft=True)])
        await db.commit();admin=await db.get(AdminUser,1)
        await service.soft_stop(db,confirm_text='CONFIRM',admin_user=admin)
        await service.soft_stop(db,confirm_text='CONFIRM',admin_user=admin)
        configs=(await db.scalars(select(AdminConfig).order_by(AdminConfig.id))).all()
        assert len(configs)==3 and json.loads(configs[0].config_value)==original
        assert configs[1].config_value==draft and configs[1].draft_revision==7
        expected={**original,'global':{'soft_stop':True}}
        assert json.loads(configs[2].config_value)==expected
        assert (await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))).status=='ringing'
        assert not cache.events

    assert [e for batch in sink.batches for e in batch]==[
        ("voice.ops_stop.result",{"operation":"soft","result":"success"},1),
        ("voice.ops_stop.result",{"operation":"soft","result":"repeated"},1)]

@pytest.mark.asyncio
async def test_local_owner_ends_and_settles_even_when_redis_is_down(storage):
    from backend.services.realtime_voice_local_runtime import LocalVoiceCall,local_voice_calls
    from backend.services.realtime_voice_lease_service import VoiceLeaseService
    cache=StateCache();call_id=await add_call(storage,'connected',cache)
    meter=ConnectedMeter(**json.loads(cache.data['voice:quota:'+call_id]));stopped=[]
    async def stop():stopped.append(call_id)
    local_voice_calls[call_id]=LocalVoiceCall(meter=meter,stop=stop)
    async def broken(*args):raise ConnectionError('cache unavailable')
    cache.get=cache.eval=cache.publish=broken
    service=VoiceOpsService(cache=cache,session_factory=storage)
    leases=VoiceLeaseService(cache,end_call=service.end_call)
    try:
        assert not await leases.renew(user_id=1,call_id=call_id,ttl_ms=15000)
        async with storage() as db:
            row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
            assert row.status=='ended' and row.end_reason=='system_error' and row.free_seconds_used==9
        assert stopped==[call_id]
    finally:local_voice_calls.pop(call_id,None)

@pytest.mark.asyncio
async def test_reconcile_retries_cleanup_for_already_committed_end(storage):
    cache=StateCache();call_id=await add_call(storage,'connected',cache)
    service=VoiceOpsService(cache=cache,session_factory=storage)
    normal_eval,normal_publish=cache.eval,cache.publish
    async def broken(*args):raise ConnectionError('cache unavailable')
    cache.eval=cache.publish=broken
    async with storage() as db:
        admin=await db.get(AdminUser,1)
        result=await service.hard_stop(db,confirm_text='CONFIRM',admin_user=admin)
        assert result['failed']==[call_id]
    cache.eval,cache.publish=normal_eval,normal_publish
    await service.reconcile()
    assert ('voice:control:end',call_id) in cache.events
    async with storage() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger))==1
