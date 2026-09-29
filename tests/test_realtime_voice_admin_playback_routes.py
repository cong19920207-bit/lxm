import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest,pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from backend.database import Base,get_db
from backend.redis_client import get_redis
from backend.models.admin_user import AdminUser
from backend.models.admin_operation_log import AdminOperationLog
from backend.utils.admin_auth import get_current_admin
from backend.routers.admin import voice_playback as module

@pytest_asyncio.fixture
async def setup(monkeypatch):
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all,tables=[AdminUser.__table__,AdminOperationLog.__table__])
    factory=async_sessionmaker(engine,expire_on_commit=False)
    cache=AsyncMock();cache.set.return_value=True;cache.get.return_value=None
    seen=[]
    class Runner:
        def __init__(self,**kwargs):self.target=kwargs['playback_target']
        async def run_playback(self,**kwargs):
            seen.append('runner')
            return {'status':'error','failure_category':'evidence_invalid'}
    async def snapshot(db):return SimpleNamespace(config={},revision=8,content_sha256='a'*64)
    monkeypatch.setattr(module,'_load_draft_snapshot',snapshot)
    monkeypatch.setattr(module,'_resolve_server_secret',lambda snapshot:('sentinel-secret',None))
    app=FastAPI();app.include_router(module.router,prefix='/api/admin/voice')
    app.dependency_overrides[get_db]=lambda:None
    app.dependency_overrides[get_redis]=lambda:cache
    app.dependency_overrides[module.playback_runner_factory]=lambda:Runner
    app.dependency_overrides[module.audit_session_factory]=lambda:factory
    yield app,cache,seen,factory
    await engine.dispose()

@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','tech_ops','observer','ops_admin','ai_trainer'])
@pytest.mark.parametrize('ack',[False,True])
async def test_playback_both_endpoints_enforce_five_roles(setup,role,ack):
    app,cache,seen,factory=setup
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='tester',role=role)
    base='/api/admin/voice/config/test-playback'
    path=base+'/'+str(uuid4())+'/ack' if ack else base
    body=dict(call_id='c',session_id='s',reply_id='r',audio_bytes=16) if ack else {}
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post(path,json=body)
    allowed=role in ('super_admin','tech_ops')
    assert response.status_code==((409 if ack else 200) if allowed else 403)
    assert len(seen)==(1 if allowed and not ack else 0)
    async with factory() as db:
        logs=(await db.scalars(select(AdminOperationLog))).all()
        assert len(logs)==len(seen)
        if logs:
            data=json.loads(logs[0].after_value)
            assert data['tested_draft_revision']==8 and data['test_id']
            assert logs[0].action=='test_playback'
            assert 'sentinel' not in logs[0].after_value and 'sentinel' not in response.text
    if not allowed:cache.set.assert_not_awaited();cache.eval.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('path,body',[
    ('/config/test-playback',{'secret':'must-reject'}),
    ('/config/test-playback/'+str(uuid4())+'/ack',dict(call_id='c',session_id='s',reply_id='r',audio_bytes=True)),
    ('/config/test-playback?token=fixture',{}),
])
async def test_playback_rejects_extra_input_bool_bytes_and_url_credentials(setup,path,body):
    app,cache,seen,_=setup
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='tester',role='super_admin')
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/admin/voice'+path,json=body)
    assert response.status_code in (400,422)
    assert not seen;cache.set.assert_not_awaited()

@pytest.mark.asyncio
async def test_stream_disconnect_waits_for_cleanup_and_audit(setup):
    import asyncio
    app,cache,seen,factory=setup
    started=asyncio.Event();cleaned=asyncio.Event()
    class SlowRunner:
        def __init__(self,**kwargs):self.target=kwargs['playback_target']
        async def run_playback(self,**kwargs):
            started.set()
            try:await asyncio.Event().wait()
            finally:
                await asyncio.sleep(.01)
                cleaned.set()
    response=await module.test_playback(module.EmptyPlaybackRequest(),
        __import__('starlette.requests',fromlist=['Request']).Request({'type':'http','method':'POST','path':'/','headers':[], 'query_string':b''}),
        admin=SimpleNamespace(id=1,username='tester'),db=None,cache=cache,
        runner_type=SlowRunner,audit_factory=factory)
    async def receive():
        await started.wait()
        return {'type':'http.disconnect'}
    async def send(message):pass
    await response({'type':'http','asgi':{'spec_version':'2.0'}},receive,send)
    assert cleaned.is_set()
    cache.eval.assert_awaited()
    async with factory() as db:
        logs=(await db.scalars(select(AdminOperationLog))).all()
        assert len(logs)==1
        assert json.loads(logs[0].after_value)['failure_category']=='client_disconnected'

@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','tech_ops','observer','ops_admin','ai_trainer'])
async def test_stop_ack_has_same_five_role_gate_and_exact_target(setup,role):
    app,cache,seen,_=setup
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='tester',role=role)
    body=dict(call_id='c',session_id='s',reply_id='r',audio_bytes=480,played_ms=10,stopped=True)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result=await client.post('/api/admin/voice/config/test-playback/'+str(uuid4())+'/stop-ack',json=body)
    assert result.status_code==(409 if role in ('super_admin','tech_ops') else 403)
    assert not seen

@pytest.mark.asyncio
@pytest.mark.parametrize('delta',[{'played_ms':True},{'played_ms':11},{'stopped':False},{'stopped':1},{'stopped':'true'}])
async def test_stop_ack_rejects_forged_types_or_duration(setup,delta):
    app,cache,seen,_=setup
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='tester',role='super_admin')
    body=dict(call_id='c',session_id='s',reply_id='r',audio_bytes=480,played_ms=10,stopped=True,**{})
    body.update(delta)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result=await client.post('/api/admin/voice/config/test-playback/'+str(uuid4())+'/stop-ack',json=body)
    assert result.status_code==422
    cache.get.assert_not_awaited()
