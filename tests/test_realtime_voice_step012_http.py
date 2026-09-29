from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from httpx import ASGITransport,AsyncClient
from tests.test_realtime_voice_step010_create import state
from backend.routers.realtime_voice import router,get_create_service
from backend.utils.auth_middleware import get_current_user
from backend.database import get_db


@pytest.mark.asyncio
@pytest.mark.parametrize('case',['normal','missing_key','bad_bool','extra_field','provider_unavailable'])
async def test_http_create_contract_uses_existing_service_and_safe_block_response(state,case):
    s=state;app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_current_user]=lambda:1
    app.dependency_overrides[get_db]=lambda:s.db
    app.dependency_overrides[get_create_service]=lambda:s.service
    payload=dict(s.payload);headers={'Idempotency-Key':str(uuid4())}
    if case=='missing_key':headers={}
    if case=='bad_bool':payload['microphone_granted']='true'
    if case=='extra_field':payload['duration_seconds']=900
    if case=='provider_unavailable':
        async def unavailable(config):return False
        s.service.provider_preflight=unavailable
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/voice/calls',json=payload,headers=headers)
        if case=='normal':
            assert response.status_code==200
            call=response.json()['data'];assert call['status']=='deciding' and call['call_ticket']
            status=await client.get('/api/voice/calls/'+call['call_id'])
            assert status.status_code==200 and 'call_ticket' not in status.text
            app.dependency_overrides[get_current_user]=lambda:2
            assert (await client.get('/api/voice/calls/'+call['call_id'])).status_code==404
        elif case=='provider_unavailable':
            assert response.status_code==503 and response.json()['data']=={'block_reason':'provider_unavailable'}
        else:assert response.status_code==422
    if case!='normal':
        from sqlalchemy import select,func
        from backend.models.realtime_voice import VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger
        for model in (VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger):
            assert await s.db.scalar(select(func.count()).select_from(model))==0
