import os
import pytest
import pytest_asyncio
from backend.database import Base
from backend.models.conversation_log import ConversationLog
from backend.models.agent_message import AgentMessage
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from backend.services.realtime_voice_card_service import stage_call_card
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from backend.services.timeline_read_service import get_timeline
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env as record_env
from tests.test_realtime_voice_step021_metrics import test_card_insert_metric_commit_and_replay,test_cursor_observations_use_actual_anchor_and_page
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest_asyncio.fixture
async def card_env(record_env):
    factory,call_id=record_env
    tables=[ConversationLog.__table__,AgentMessage.__table__]
    async with factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    try:yield factory,call_id
    finally:
        async with factory.kw["bind"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)


@pytest.mark.asyncio
async def test_timeline_real_counter_and_shared_zero_pollution(card_env,runtime):
    factory,call_id=card_env;cache=runtime[2];metrics=VoiceMetrics(cache,deadline_seconds=1)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ended'
        await stage_call_card(db,call);await db.commit();await flush_voice_metrics(db,metrics)
        await get_timeline(1,db,include_calls=True,pending_reload=True,metrics=metrics)
    keys=[key async for key in cache.scan_iter(match='voice.timeline.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.timeline.insert','voice.timeline.pending_reload'}
    for key in keys:
        assert set((await cache.hgetall(key)).values())=={'1'}
        assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared
