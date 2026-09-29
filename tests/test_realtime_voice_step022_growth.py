import ast
import hashlib
import json
from datetime import datetime, date
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.database import Base
from backend.models.realtime_voice import VoiceCall
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.models.relationship_level_history import RelationshipLevelHistory
from backend.services.relationship_service import RelationshipService
from tests.test_realtime_voice_step028_jobs import storage, memory_env, add_turn


@pytest_asyncio.fixture
async def growth_env(memory_env):
    factory, call_id = memory_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            RelationshipGrowthLog.__table__, RelationshipLevelHistory.__table__])
    await add_turn(factory, call_id)
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.status = 'ended'
        call.ended_at = datetime(2026, 9, 13, 16, 5)
        call.growth_eligible_seconds = 65
        db.add(Relationship(user_id=1, level=0, growth_value=195, proactive_times=3))
        await db.commit()
    return factory, call_id


@pytest.mark.asyncio
async def test_voice_growth_rounding_upgrade_and_replay(growth_env):
    factory, call_id = growth_env
    async with factory() as db:
        service = RelationshipService(db)
        first = await service.add_voice_growth(1, 65, call_id)
        await db.commit()
        assert first['points'] == 10 and first['leveled_up']
        assert (await service.add_voice_growth(1, 65, call_id))['points'] == 0
        row = await db.scalar(select(Relationship))
        assert (row.growth_value, row.level, row.proactive_times) == (205, 1, 0)
        assert row.last_interaction_at == datetime(2026, 9, 13, 16, 5)
        logs = (await db.scalars(select(RelationshipGrowthLog))).all()
        assert len(logs) == 1
        assert (logs[0].eligible_seconds, logs[0].business_date) == (65, date(2026, 9, 14))
        assert logs[0].source_type == 'voice_call' and logs[0].source_id == call_id


@pytest.mark.asyncio
async def test_voice_daily_cap_partial_and_old_log_unchanged(growth_env):
    factory, call_id = growth_env
    async with factory() as db:
        old = RelationshipGrowthLog(user_id=1, action_type='voice_call', points=95,
            source_type='voice_call', source_id='earlier-call', eligible_seconds=570,
            business_date=date(2026, 9, 14))
        db.add(old)
        await db.commit()
        await db.refresh(old)  # Freeze the stored projection, including MySQL datetime precision.
        before = {c.name: getattr(old, c.name) for c in old.__table__.columns}
        result = await RelationshipService(db).add_voice_growth(1, 65, call_id)
        await db.commit()
        assert result['points'] == 5
        await db.refresh(old)
        assert before == {c.name: getattr(old, c.name) for c in old.__table__.columns}


def test_original_text_growth_source_unchanged():
    source = Path('backend/services/relationship_service.py').read_text()
    expected = json.loads(Path('docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step022-protected-before.json').read_text())
    actual = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'add_growth':
            actual['add_growth'] = hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GROWTH_ACTIONS' for t in node.targets):
            actual['GROWTH_ACTIONS'] = hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
    assert actual == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['no_turn', 'ack_only', 'system_error', 'provider_error', 'reconnect_timeout', 'unconnected'])
async def test_ineligible_voice_is_zero(growth_env, change):
    from backend.models.realtime_voice import VoiceCallTurn
    from sqlalchemy import delete
    factory, call_id = growth_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        if change == 'no_turn':
            await db.execute(delete(VoiceCallTurn))
        elif change == 'ack_only':
            turn = await db.scalar(select(VoiceCallTurn))
            turn.user_text_final = '嗯嗯，好的。'
        elif change in {'system_error', 'provider_error', 'reconnect_timeout'}:
            call.end_reason = change
        else:
            call.connected_at = None
            call.status = 'missed'
        await db.commit()
        result = await RelationshipService(db).add_voice_growth(1, 65, call_id)
        assert result['points'] == 0


@pytest.mark.asyncio
async def test_frozen_growth_config_and_newer_interaction_preserved(growth_env):
    factory, call_id = growth_env
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.config_snapshot = {'resolved_config': {'growth': {
            'segment_seconds': 20, 'points_per_segment': 3,
            'daily_limit_points': 7, 'timezone': 'Asia/Shanghai'}}}
        rel = await db.scalar(select(Relationship))
        rel.last_interaction_at = datetime(2026, 9, 15)
        await db.commit()
        result = await RelationshipService(db).add_voice_growth(1, 65, call_id)
        assert result['points'] == 7
        assert rel.last_interaction_at == datetime(2026, 9, 15)


@pytest.mark.asyncio
async def test_end_transaction_settles_once(growth_env):
    from backend.services.realtime_voice_ops_service import VoiceOpsService
    from backend.services.realtime_voice_quota_service import ConnectedMeter
    from tests.test_realtime_voice_step009_ops import StateCache
    factory, call_id = growth_env
    cache = StateCache()
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.status = 'connected'
        call.ended_at = None
        await db.commit()
    # Existing durable quota checkpoint holds nine already observed seconds.
    from datetime import timezone
    from backend.services.realtime_voice_quota_service import VoiceQuotaService
    from dataclasses import asdict
    meter = ConnectedMeter(call_id, 1, 300, 30)
    async with factory() as db:
        now = datetime.now(timezone.utc)
        await VoiceQuotaService().observe(db, meter, connected=True, monotonic=0, now=now)
        from datetime import timedelta
        await VoiceQuotaService().observe(db, meter, connected=False, monotonic=65, now=now+timedelta(seconds=65))
    cache.data['voice:quota:' + call_id] = json.dumps(asdict(meter))
    ops = VoiceOpsService(cache=cache, session_factory=factory)
    await ops.end_call(call_id=call_id, reason='user_hangup')
    await ops.end_call(call_id=call_id, reason='system_error')
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        rel = await db.scalar(select(Relationship))
        assert call.growth_points == 10 and call.sort_seq is not None
        assert rel.growth_value == 205
        assert len((await db.scalars(select(RelationshipGrowthLog))).all()) == 1


@pytest.mark.asyncio
async def test_relationship_detail_includes_voice_points_on_shanghai_day(growth_env, monkeypatch):
    from datetime import timezone
    from zoneinfo import ZoneInfo
    from unittest.mock import AsyncMock
    from backend.models.conversation_log import ConversationLog
    factory, _ = growth_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[ConversationLog.__table__])
    cache = AsyncMock()
    cache.get.return_value = None
    monkeypatch.setattr('backend.services.relationship_service.get_redis', AsyncMock(return_value=cache))
    async with factory() as db:
        today = datetime.now(timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).date()
        db.add(RelationshipGrowthLog(user_id=1, action_type='voice_call', points=10,
            source_type='voice_call', source_id='today', eligible_seconds=65, business_date=today))
        await db.commit()
        detail = await RelationshipService(db).get_relationship_detail(1)
        assert detail['today_growth']['today_voice_points'] == 10
        assert detail['today_growth']['today_total_points'] == 10
