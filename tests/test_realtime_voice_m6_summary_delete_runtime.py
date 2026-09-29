"""Cross-step summary/card/record/export/deletion acceptance on isolated stores."""
import json
import os
from datetime import datetime
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from backend.database import Base, get_db
from backend.models.conversation_log import ConversationLog
from backend.models.agent_message import AgentMessage
from backend.models.realtime_voice import VoiceCall, VoiceFollowupJob
from backend.models.relationship import Relationship
from backend.routers.admin.voice_records import router
from backend.utils.admin_auth import get_current_admin
from backend.services.realtime_voice_retention_service import VoiceRetentionService, build_voice_retention_service
from backend.services.realtime_voice_summary_followup_service import stage_summary_followup
from backend.services.timeline_read_service import get_timeline
from tests.test_realtime_voice_step033_runtime import containers, runtime, card_env
from tests.test_realtime_voice_step031_jobs import summary_env as base_summary_env, service
from tests.test_realtime_voice_step031_summary import output
from tests.test_realtime_voice_step034_delete import ADMIN

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME') != '1', reason='isolated runtime opt-in')


@pytest_asyncio.fixture
async def summary_env(base_summary_env):
    factory, call_id = base_summary_env
    tables = [m.__table__ for m in (Relationship, ConversationLog, AgentMessage)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    try:
        yield factory, call_id
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=tables)


@pytest.mark.asyncio
async def test_summary_card_records_export_and_delete(summary_env, runtime):
    factory, call_id = summary_env
    _, _, cache = runtime
    async with factory() as db:
        db.add(Relationship(user_id=1, level=1, growth_value=20))
        call = await db.scalar(select(VoiceCall))
        call.ended_at = datetime.utcnow()
        sequence = call.sort_seq
        await db.commit()
    async def model(prompt):
        return json.dumps(output())
    worker = service(factory, model=model, stage_followup=stage_summary_followup)
    await worker.enqueue(call_id=call_id)
    assert await worker.process(call_id=call_id) == 'ready'
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        assert call.sort_seq == sequence
        followup = await db.scalar(select(VoiceFollowupJob))
        assert followup.status == 'pending'
        timeline = await get_timeline(1, db, include_calls=True)
        assert any(row['call_id'] == call_id for row in timeline['items'])
        assert 'reasoning' not in json.dumps(timeline, default=str)
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: ADMIN
    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[build_voice_retention_service] = lambda: VoiceRetentionService(session_factory=factory, cache=cache)
    await cache.set(f'voice:session_context:{call_id}', 'synthetic-context')
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        path = '/api/admin/voice/calls/' + call_id
        detail = await client.get(path)
        assert detail.status_code == 200 and detail.json()['data']['call_summary'] == output()['call_summary']
        debug = await client.get(path + '/debug')
        assert debug.json()['data']['reasoning'] == output()['reasoning']
        exported = await client.post('/api/admin/voice/calls/export', json={'call_ids':[call_id]})
        assert exported.status_code == 200 and len(exported.json()['data']['items']) == 1
        assert 'reasoning' not in exported.text and 'assistant_text_generated' not in exported.text
        assert (await client.delete(path)).status_code == 200
        for suffix in ('', '/turns', '/debug'):
            response = await client.get(path + suffix)
            assert response.status_code == 200
            assert output()['call_summary'] not in response.text and output()['reasoning'] not in response.text
        exported = await client.post('/api/admin/voice/calls/export', json={'call_ids':[call_id]})
        assert exported.json()['data']['items'] == []
    async with factory() as db:
        assert (await db.scalar(select(VoiceFollowupJob))).status == 'cancelled'
        assert (await get_timeline(1, db, include_calls=True))['items'] == []
    assert await cache.get(f'voice:session_context:{call_id}') is None
