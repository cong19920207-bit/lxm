"""Voice dashboard read access is explicit for all five admin roles."""
from types import SimpleNamespace
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from backend.database import Base, get_db
from backend.models.realtime_voice import VoiceMemoryJob, VoicePostprocessJob, VoiceMetricDaily
from backend.utils.admin_auth import get_current_admin
from tests.test_realtime_voice_step009_ops import storage


async def build_api(storage):
    from backend.routers.admin.voice_metrics import router, observation_cache
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[VoiceMemoryJob.__table__, VoicePostprocessJob.__table__, VoiceMetricDaily.__table__])
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[observation_cache] = lambda: None
    async def session():
        async with storage() as db:
            yield db
    app.dependency_overrides[get_db] = session
    return app


@pytest_asyncio.fixture
async def api(storage):
    return await build_api(storage)


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['super_admin', 'ai_trainer', 'tech_ops', 'ops_admin', 'observer'])
@pytest.mark.parametrize('path', ['dictionary', 'daily?day=2026-09-19', 'observations?day=2026-09-19', 'history?start=2026-09-18&end=2026-09-19', 'billing-preview?start=2026-09-19&end=2026-09-19&bill_start=2026-09-19&bill_end=2026-09-19&unit_price=0.06&unit=minute&currency=CNY&bill_currency=CNY&billed_cost=0'])
async def test_five_roles_read_no_writes(api, storage, role, path):
    api.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(role=role)
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(storage.kw['bind'].sync_engine, 'before_cursor_execute', capture)
    try:
        async with AsyncClient(transport=ASGITransport(app=api), base_url='http://test') as client:
            response=await client.get('/api/admin/voice/metrics/'+path)
    finally:
        event.remove(storage.kw['bind'].sync_engine, 'before_cursor_execute', capture)
    assert response.status_code==200
    assert response.headers['cache-control']=='no-store'
    assert not set(statements)&{'INSERT','UPDATE','DELETE','REPLACE'}
    data=response.json()['data']
    if path.startswith('daily'):
        assert data['timezone']=='Asia/Shanghai'
        assert len(data['metrics'])==10
        cost=next(m for m in data['metrics'] if m['name']=='estimated_cost')
        assert cost==dict(name='estimated_cost',value=None,status='not_measurable',reason='price_unconfigured')
        assert 'current_durable_state'==data['history_basis']
    elif path.startswith('billing-preview'):
        assert data['data_source']=='simulated_pricing_and_bill'
        assert data['estimated_cost']=='0.000000' and data['difference_rate']=='0'
    elif path.startswith('history'):
        assert len(data['days'])==2
        assert all(item['value'] is None for item in data['days'][0]['metrics'])
    elif path.startswith('observations'):
        assert data['bucket_basis']=='observation_sent_utc'
        assert len(data['capability_metrics'])==4
        assert all(row['value'] is None for row in data['capability_metrics'])
    else:
        assert data['events'] and data['events'][0]['ttl_seconds']==172800
    def keys(value):
        if isinstance(value, dict):
            return set(value).union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value))
        return set()
    assert not keys(data)&{'user_id','call_id','api_key','reasoning','transcript'}


@pytest.mark.asyncio
async def test_auth_validation_and_no_mutation_routes(api):
    async with AsyncClient(transport=ASGITransport(app=api), base_url='http://test') as client:
        for path in ('dictionary','daily?day=2026-09-19','observations?day=2026-09-19','history?start=2026-09-18&end=2026-09-19', 'billing-preview?start=2026-09-19&end=2026-09-19&bill_start=2026-09-19&bill_end=2026-09-19&unit_price=0.06&unit=minute&currency=CNY&bill_currency=CNY&billed_cost=0'):
            assert (await client.get('/api/admin/voice/metrics/'+path)).status_code==401
        api.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='user')
        for path in ('dictionary','daily?day=2026-09-19','observations?day=2026-09-19','history?start=2026-09-18&end=2026-09-19', 'billing-preview?start=2026-09-19&end=2026-09-19&bill_start=2026-09-19&bill_end=2026-09-19&unit_price=0.06&unit=minute&currency=CNY&bill_currency=CNY&billed_cost=0'):
            assert (await client.get('/api/admin/voice/metrics/'+path)).status_code==403
        api.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
        for day in ('bad','9999-12-31','0001-01-01'):
            assert (await client.get('/api/admin/voice/metrics/daily',params={'day':day})).status_code==422
        for method in ('post','put','patch','delete'):
            for path in ('daily','dictionary','observations','history','billing-preview'):
                assert (await getattr(client,method)('/api/admin/voice/metrics/'+path)).status_code==405
        assert (await client.get('/api/admin/voice/metrics/export')).status_code==404
    assert all(set(methods)=={'get'} for path,methods in api.openapi()['paths'].items()
               if path.startswith('/api/admin/voice'))


@pytest.mark.asyncio
async def test_database_failure_is_sanitized_and_cancellation_propagates(api, monkeypatch):
    import asyncio
    from sqlalchemy.exc import OperationalError
    from backend.routers.admin import voice_metrics
    api.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
    async def fail(db,day):
        raise OperationalError('PRIVATE_SQL',{},Exception('PRIVATE_PASSWORD'))
    monkeypatch.setattr(voice_metrics,'compute_daily_metrics',fail)
    async with AsyncClient(transport=ASGITransport(app=api),base_url='http://test') as client:
        result=await client.get('/api/admin/voice/metrics/daily?day=2026-09-19')
        assert result.status_code==503 and 'PRIVATE' not in result.text
        async def cancel(db,day):raise asyncio.CancelledError()
        monkeypatch.setattr(voice_metrics,'compute_daily_metrics',cancel)
        with pytest.raises(asyncio.CancelledError):
            await client.get('/api/admin/voice/metrics/daily?day=2026-09-19')


@pytest.mark.asyncio
async def test_user_token_cannot_authenticate_as_admin(api):
    from datetime import datetime, timedelta, timezone
    import jwt
    from backend.config import get_admin_jwt_secret, get_jwt_algorithm
    token=jwt.encode({'sub':'1','type':'user','role':'super_admin','token_version':0,
        'exp':datetime.now(timezone.utc)+timedelta(minutes=5)},get_admin_jwt_secret(),algorithm=get_jwt_algorithm())
    async with AsyncClient(transport=ASGITransport(app=api),base_url='http://test') as client:
        for path in ('dictionary','daily?day=2026-09-19','observations?day=2026-09-19','history?start=2026-09-18&end=2026-09-19', 'billing-preview?start=2026-09-19&end=2026-09-19&bill_start=2026-09-19&bill_end=2026-09-19&unit_price=0.06&unit=minute&currency=CNY&bill_currency=CNY&billed_cost=0'):
            result=await client.get('/api/admin/voice/metrics/'+path,headers={'Authorization':'Bearer '+token})
            assert result.status_code==401


@pytest.mark.asyncio
async def test_billing_preview_invalid_inputs_and_database_failure(api, monkeypatch):
    from backend.services import realtime_voice_cost_preview_service as service
    from sqlalchemy.exc import OperationalError
    api.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
    params=dict(start='2026-09-19',end='2026-09-19',bill_start='2026-09-19',bill_end='2026-09-19',
        unit_price='0.06',unit='minute',currency='CNY',bill_currency='CNY',billed_cost='1')
    async with AsyncClient(transport=ASGITransport(app=api),base_url='http://test') as client:
        for override in ({'unit_price':'-1'},{'bill_currency':'USD'},{'bill_start':'2026-09-18'},
                         {'unit_price':'1'*65},{'end':'9999-12-31'}):
            result=await client.get('/api/admin/voice/metrics/billing-preview',params={**params,**override})
            assert result.status_code==422
        async def fail(*args,**kwargs):
            raise OperationalError('PRIVATE_SQL',{},Exception('PRIVATE_PASSWORD'))
        monkeypatch.setattr(service,'preview_cost',fail)
        result=await client.get('/api/admin/voice/metrics/billing-preview',params=params)
        assert result.status_code==503 and 'PRIVATE' not in result.text
