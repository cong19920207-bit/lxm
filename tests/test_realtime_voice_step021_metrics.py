from datetime import datetime
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from backend.models.agent_message import AgentMessage
from backend.services.realtime_voice_card_service import stage_call_card
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from backend.services.timeline_read_service import get_timeline
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('rollback',[True,False])
async def test_card_insert_metric_commit_and_replay(card_env,rollback):
    factory,call_id=card_env;sink=CounterCache();metrics=VoiceMetrics(sink)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ended';call.ended_at=datetime.utcnow()
        await stage_call_card(db,call);await stage_call_card(db,call)
        assert sink.batches==[]
        if rollback:await db.rollback()
        else:await db.commit()
        await flush_voice_metrics(db,metrics)
    assert [event for batch in sink.batches for event in batch]==([] if rollback else [('voice.timeline.insert',{'status':'ended'},1)])


@pytest.mark.asyncio
async def test_cursor_observations_use_actual_anchor_and_page(card_env):
    factory,call_id=card_env;sink=CounterCache();metrics=VoiceMetrics(sink)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ended';call.ended_at=datetime.utcnow();call.sort_seq=10
        db.add(AgentMessage(user_id=1,trigger_type='P0',content='private-content',action_score=1,sort_seq=10))
        await db.commit()
        first=await get_timeline(1,db,include_calls=True,pending_reload=True,metrics=metrics)
        assert len(first['items'])==2
        await get_timeline(1,db,cursor=10,include_calls=True,metrics=metrics)
        await get_timeline(1,db,cursor=9,include_calls=True,metrics=metrics)
        before=len(sink.batches)
        await get_timeline(1,db,cursor=9,metrics=metrics,pending_reload=True)
        assert len(sink.batches)==before  # Open's original path has no voice observation.
    assert [e for batch in sink.batches for e in batch]==[
        ('voice.timeline.pending_reload',{},1),('voice.timeline.cursor_duplicate',{'scope':'page'},1),
        ('voice.timeline.cursor_duplicate',{'scope':'anchor'},1),('voice.timeline.cursor_missing',{'scope':'anchor'},1)]


@pytest.mark.asyncio
async def test_h5_route_passes_pending_reload_to_real_reader(card_env,monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport,AsyncClient
    from backend.routers import chat
    factory,call_id=card_env;sink=CounterCache()
    app=FastAPI();app.state.voice_metrics=VoiceMetrics(sink);app.include_router(chat.router)
    async def db():
        async with factory() as session:yield session
    async def user():return 1
    async def recover(*args,**kwargs):pass
    monkeypatch.setattr(chat.chat_service,'trigger_recovery_if_queue_stuck',recover)
    app.dependency_overrides[chat.get_db]=db;app.dependency_overrides[chat.get_current_user]=user
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        reply=await client.get('/api/chat/timeline?pending_reload=true')
    assert reply.status_code==200 and reply.headers['cache-control']=='no-store'
    assert [e for batch in sink.batches for e in batch]==[('voice.timeline.pending_reload',{},1)]
