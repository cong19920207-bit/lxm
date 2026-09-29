"""Automatic startup cleanup must not become an unconditional hangup."""
from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

import backend.routers.realtime_voice as routes
from backend.database import get_db
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.models.user_timeline_seq import UserTimelineSeq
from backend.utils.auth_middleware import get_current_user
from tests.test_realtime_voice_step009_ops import storage, StateCache, add_call


def app_for(storage, cache, monkeypatch, user_id=1):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: user_id
    async def db():
        async with storage() as session:
            yield session
    async def redis():
        return cache
    app.dependency_overrides[get_db] = db
    monkeypatch.setattr(routes, 'get_redis', redis)
    monkeypatch.setattr(routes, 'async_session_maker', storage)
    return app


@pytest.mark.asyncio
async def test_connection_winning_cancel_race_is_not_ended(storage, monkeypatch):
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        row.status, row.connected_at = 'ringing', None
        await db.commit()
    original = routes.transition_call
    async def connect_before_lock(db, **kwargs):
        # The route has already read 'ringing'; connection wins the next lock.
        async with storage() as other:
            row = await other.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
            row.status, row.connected_at = 'connected', datetime.utcnow()
            await other.commit()
        return await original(db, **kwargs)
    monkeypatch.setattr(routes, 'transition_call', connect_before_lock)
    app = app_for(storage, cache, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(f'/api/voice/calls/{call_id}/end?only_if_unconnected=true')
    assert response.status_code == 409
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.status == 'connected' and row.ended_at is None
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['deciding', 'ringing'])
async def test_unconnected_cancel_and_terminal_cleanup_replay(storage, monkeypatch, status):
    cache = StateCache()
    call_id = await add_call(storage, status, cache)
    app = app_for(storage, cache, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        first = await client.post(f'/api/voice/calls/{call_id}/end?only_if_unconnected=true')
        replay = await client.post(f'/api/voice/calls/{call_id}/end?only_if_unconnected=true')
    assert first.status_code == replay.status_code == 200
    assert replay.json()['data']['changed'] is False
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.status == 'cancelled' and row.connected_at is None
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0


@pytest.mark.asyncio
async def test_conditional_cancel_does_not_change_manual_hangup(storage, monkeypatch):
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    app = app_for(storage, cache, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        refused = await client.post(f'/api/voice/calls/{call_id}/end?only_if_unconnected=true')
        ended = await client.post(f'/api/voice/calls/{call_id}/end')
    assert refused.status_code == 409 and ended.status_code == 200
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.status == 'ended' and row.end_reason == 'user_hangup'
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1


@pytest.mark.asyncio
async def test_conditional_cancel_still_requires_owner(storage, monkeypatch):
    cache = StateCache()
    call_id = await add_call(storage, 'ringing', cache)
    app = app_for(storage, cache, monkeypatch, user_id=999)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(f'/api/voice/calls/{call_id}/end?only_if_unconnected=true')
    assert response.status_code == 404
    async with storage() as db:
        assert (await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))).status == 'ringing'


@pytest.mark.asyncio
@pytest.mark.parametrize('has_timeline', [False, True])
async def test_connected_hangup_with_production_autoflush_setting(storage, monkeypatch, has_timeline):
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    if has_timeline:
        async with storage() as db:
            db.add(UserTimelineSeq(user_id=1, next_seq=10))
            await db.commit()
    factory = async_sessionmaker(storage.kw['bind'], expire_on_commit=False, autoflush=False)
    app = app_for(factory, cache, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test') as client:
        ended = await client.post(f'/api/voice/calls/{call_id}/end')
        replay = await client.post(f'/api/voice/calls/{call_id}/end')
    assert ended.status_code == replay.status_code == 200
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.status == 'ended' and row.ended_at is not None and row.sort_seq is not None
        assert row.end_reason == 'user_hangup'
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1
