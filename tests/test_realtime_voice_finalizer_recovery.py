"""Production session settings, atomic settlement, and actionable admin failures."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.database import get_db
from backend.models.realtime_voice import VoiceCall, VoiceUsageLedger
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.models.user_timeline_seq import UserTimelineSeq
from backend.routers.admin.voice_ops import get_voice_ops, router
from backend.services.realtime_voice_ops_service import VoiceOpsService
from backend.services.relationship_service import RelationshipService
from backend.utils.admin_auth import get_current_admin
from tests.test_realtime_voice_step009_ops import StateCache, add_call, storage


def admin_app(factory, service):
    app = FastAPI()
    app.include_router(router, prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(
        id=1, username='ops', role='tech_ops')
    app.dependency_overrides[get_voice_ops] = lambda: service

    async def session():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize('has_timeline', [False, True])
@pytest.mark.parametrize('entrypoint', ['single', 'batch', 'reconcile'])
async def test_all_finalizers_preserve_terminal_card_and_single_settlement(storage, has_timeline, entrypoint):
    factory = async_sessionmaker(storage.kw['bind'], expire_on_commit=False, autoflush=False)
    cache = StateCache()
    call_id = await add_call(factory, 'connected', cache)
    if has_timeline:
        async with factory() as db:
            db.add(UserTimelineSeq(user_id=1, next_seq=10))
            await db.commit()
    service = VoiceOpsService(cache=cache, session_factory=factory)
    if entrypoint == 'reconcile':
        # No owner in Redis; reconcile must use the same durable finalizer.
        assert await service.reconcile() == 1
    else:
        path = f'/calls/{call_id}/force-end' if entrypoint == 'single' else '/ops/hard-stop'
        async with AsyncClient(transport=ASGITransport(app=admin_app(factory, service)), base_url='http://test') as client:
            result = await client.post('/api/admin/voice' + path, json={'confirm_text': 'CONFIRM'})
        assert result.status_code == 200, result.text
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert row.status == 'ended' and row.ended_at is not None
        assert row.sort_seq == (10 if has_timeline else 1)
        assert row.duration_seconds == row.free_seconds_used == 9
        original = (row.sort_seq, row.ended_at, row.end_reason)
    assert (await service.end_call(call_id=call_id))['changed'] is False
    await service.reconcile()
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id))
        assert (row.sort_seq, row.ended_at, row.end_reason) == original
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1
        assert await db.scalar(select(func.count()).select_from(RelationshipGrowthLog)) == 1


@pytest.mark.asyncio
async def test_flush_does_not_commit_a_partial_finalization(storage, monkeypatch):
    factory = async_sessionmaker(storage.kw['bind'], expire_on_commit=False, autoflush=False)
    cache = StateCache()
    call_id = await add_call(factory, 'connected', cache)
    service = VoiceOpsService(cache=cache, session_factory=factory)
    original = RelationshipService.add_voice_growth

    async def fail_after_staged_terminal(self, *args):
        row = await self.db.scalar(select(VoiceCall).execution_options(populate_existing=True))
        assert row.status == 'ended' and row.sort_seq is not None
        raise RuntimeError('injected growth failure')
    monkeypatch.setattr(RelationshipService, 'add_voice_growth', fail_after_staged_terminal)
    with pytest.raises(RuntimeError, match='injected growth failure'):
        await service.end_call(call_id=call_id)
    async with factory() as db:
        row = await db.scalar(select(VoiceCall))
        assert row.status == 'connected' and row.ended_at is None and row.sort_seq is None
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0
    monkeypatch.setattr(RelationshipService, 'add_voice_growth', original)
    assert (await service.end_call(call_id=call_id))['cleanup_pending'] is False


@pytest.mark.asyncio
async def test_admin_partial_failure_keeps_fixed_targets_and_safe_reason(storage):
    factory = async_sessionmaker(storage.kw['bind'], expire_on_commit=False, autoflush=False)
    cache = StateCache()
    good = await add_call(factory, 'connected', cache)
    missing = await add_call(factory, 'connected', cache)
    del cache.data['voice:quota:' + missing]
    service = VoiceOpsService(cache=cache, session_factory=factory)
    async with AsyncClient(transport=ASGITransport(app=admin_app(factory, service)), base_url='http://test') as client:
        response = await client.post('/api/admin/voice/ops/hard-stop', json={'confirm_text': 'CONFIRM'})
        assert response.status_code == 503
        data = response.json()['data']
        assert set(data['targets']) == {good, missing} and data['failed'] == [missing]
        assert [r['call_id'] for r in data['results']] == [good]
        detail = data['failure_details'][0]
        assert detail['call_id'] == missing
        assert detail['error_code'] == 'VOICE_END_SETTLEMENT_REVIEW_REQUIRED'
        assert detail['retryable'] is False
        single = await client.post(f'/api/admin/voice/calls/{missing}/force-end', json={'confirm_text': 'CONFIRM'})
        assert single.status_code == 409
        assert single.json()['data'] == detail
    async with factory() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == missing))
        assert row.status == 'connected' and row.ended_at is None
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['single', 'batch'])
async def test_cleanup_pending_can_retry_terminal_target_without_double_billing(storage, entrypoint):
    factory = async_sessionmaker(storage.kw['bind'], expire_on_commit=False, autoflush=False)
    cache = StateCache()
    call_id = await add_call(factory, 'connected', cache)
    normal_publish = cache.publish

    async def unavailable(*args):
        raise ConnectionError('private dependency details')
    cache.publish = unavailable
    service = VoiceOpsService(cache=cache, session_factory=factory)
    async with AsyncClient(transport=ASGITransport(app=admin_app(factory, service)), base_url='http://test') as client:
        path = f'/api/admin/voice/calls/{call_id}/force-end'
        first_path = path if entrypoint == 'single' else '/api/admin/voice/ops/hard-stop'
        first = await client.post(first_path, json={'confirm_text': 'CONFIRM'})
        if entrypoint == 'single':
            assert first.status_code == 200 and first.json()['data']['cleanup_pending'] is True
        else:
            assert first.status_code == 503
            assert first.json()['data']['failed'] == [call_id]
            assert first.json()['data']['failure_details'][0]['error_code'] == 'VOICE_END_CLEANUP_PENDING'
            assert first.json()['data']['results'][0]['cleanup_pending'] is True
        cache.publish = normal_publish
        replay = await client.post(path, json={'confirm_text': 'CONFIRM'})
        assert replay.json()['data'] == {'call_id': call_id, 'changed': False, 'cleanup_pending': False}
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 1
        assert await db.scalar(select(func.count()).select_from(RelationshipGrowthLog)) == 1


@pytest.mark.asyncio
async def test_unexpected_admin_failure_does_not_expose_exception_details(storage, monkeypatch):
    service = VoiceOpsService(cache=StateCache(), session_factory=storage)

    async def fail(**kwargs):
        raise RuntimeError('private credential or SQL content')
    monkeypatch.setattr(service, 'end_call', fail)
    async with AsyncClient(transport=ASGITransport(app=admin_app(storage, service)), base_url='http://test') as client:
        result = await client.post('/api/admin/voice/calls/fixed-id/force-end', json={'confirm_text': 'CONFIRM'})
    assert result.status_code == 503
    assert result.json()['data']['call_id'] == 'fixed-id'
    assert result.json()['data']['retryable'] is True
    assert 'private' not in result.text


@pytest.mark.asyncio
async def test_reconcile_owner_lookup_failure_does_not_end_active_call(storage, monkeypatch, caplog):
    from backend.services.realtime_voice_lease_service import VoiceLeaseService
    cache = StateCache()
    call_id = await add_call(storage, 'connected', cache)
    service = VoiceOpsService(cache=cache, session_factory=storage)

    async def unavailable(self, **kwargs):
        raise ConnectionError('private cache details')
    monkeypatch.setattr(VoiceLeaseService, 'owner_matches', unavailable)
    assert await service.reconcile() == 0
    async with storage() as db:
        row = await db.scalar(select(VoiceCall))
        assert row.status == 'connected' and row.ended_at is None
        assert await db.scalar(select(func.count()).select_from(VoiceUsageLedger)) == 0
    assert call_id in caplog.text and 'VOICE_END_DEPENDENCY_UNAVAILABLE' in caplog.text
    assert 'private cache details' not in caplog.text
