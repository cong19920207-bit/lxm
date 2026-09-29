"""Direct HTTP owner boundaries and real local failed Provider handshakes."""
import json
import logging
from http import HTTPStatus
from uuid import uuid4

import httpx
import pytest
import websockets
from fastapi import FastAPI
from sqlalchemy import select

from backend.database import get_db
from backend.models.realtime_voice import VoiceCall
from backend.utils.auth_middleware import get_current_user
from backend.services.realtime_voice_provider_service import VoiceProviderAdapter, ProviderError, ENDPOINT
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache
from tests.test_realtime_voice_step007_provider import config


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['status','end','reconnect'])
async def test_other_user_cannot_read_end_or_reconnect_call(storage, monkeypatch, action):
    import backend.routers.realtime_voice as routes
    call_id = await add_call(storage,'connected',StateCache())
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: 2
    async def db_session():
        async with storage() as db:
            yield db
    app.dependency_overrides[get_db] = db_session
    async def forbidden_redis():
        pytest.fail('foreign call reached Redis/termination')
    monkeypatch.setattr(routes,'get_redis',forbidden_redis)
    def values(row):
        return {c.name:getattr(row,c.name) for c in row.__table__.columns}
    async with storage() as db:
        before = values(await db.scalar(select(VoiceCall)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://local') as client:
        async def invoke(target):
            base='/api/voice/calls/'+target
            return await client.get(base) if action=='status' else await client.post(base+'/'+action,
                json={'device_id':str(uuid4())} if action=='reconnect' else None)
        denied=await invoke(call_id)
        missing=await invoke(str(uuid4()))
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()
    assert call_id not in denied.text
    async with storage() as db:
        assert values(await db.scalar(select(VoiceCall))) == before


@pytest.mark.asyncio
async def test_real_handshake_rejection_does_not_expose_upstream_private_body(monkeypatch, caplog):
    sentinels=['isolated-secret-VOICE-037', 'synthetic-private-transcript-037', 'synthetic-personal-id-037']
    for name in ('DOUBAO_S2S_APP_ID','DOUBAO_S2S_APP_KEY','DOUBAO_S2S_ACCESS_KEY'):
        monkeypatch.setenv(name,sentinels[0])
    caplog.set_level(logging.INFO)
    requests=[]
    async def reject(connection, request):
        assert request.headers['X-Api-Access-Key'] == sentinels[0]
        requests.append(1)
        return connection.respond(HTTPStatus.UNAUTHORIZED, ' '.join(sentinels))
    async def unused(connection):
        pytest.fail('rejected handshake entered session')
    snapshot=config()
    before=json.dumps(snapshot,sort_keys=True)
    async with websockets.serve(unused,'127.0.0.1',0,process_request=reject) as server:
        endpoint='ws://127.0.0.1:'+str(server.sockets[0].getsockname()[1])
        async def transport(url,**kwargs):
            assert url==ENDPOINT
            return await websockets.connect(endpoint,**kwargs)
        adapter=VoiceProviderAdapter(call_id=str(uuid4()),config=snapshot,transport_factory=transport)
        with pytest.raises(ProviderError) as caught:
            await adapter.create_connection()
        assert caught.value.__cause__ is None
        await adapter.finish_session()
    assert requests==[1]
    assert adapter._wire is None and adapter._connection_secret is None
    assert json.dumps(snapshot,sort_keys=True)==before
    public=json.dumps({'error':str(caught.value),'snapshot':snapshot})+caplog.text
    assert all(value not in public for value in sentinels)
