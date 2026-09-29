"""Direct AC2/AC37 edge checks without changing runtime policy."""
from datetime import date
import pytest
from sqlalchemy import select

from backend.database import Base
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.services.relationship_service import RelationshipService
from backend.services.realtime_voice_decision_service import RingGate, decide_call
from tests.test_realtime_voice_step022_growth import growth_env, memory_env, storage
from tests.test_realtime_voice_step010_create import state, create, NOW


@pytest.mark.asyncio
async def test_four_second_floor_and_target_ready_intersection():
    async def model(prompt):
        return '{"answer":true,"delay_seconds":0,"opening_text":"喂"}'
    decision = await decide_call(inputs={}, settings={'prompt_template':'接听'}, model=model)
    assert decision.delay_seconds == 4
    gate = RingGate(target_seconds=decision.delay_seconds)
    assert gate.result(elapsed=3.999, ready=True) == 'ringing'
    assert gate.result(elapsed=4, ready=False) == 'ringing'
    assert gate.result(elapsed=4, ready=True) == 'connected'
    later = RingGate(target_seconds=7)
    assert later.result(elapsed=4, ready=True) == 'ringing'
    assert later.result(elapsed=7, ready=False) == 'ringing'
    assert later.result(elapsed=7, ready=True) == 'connected'


@pytest.mark.asyncio
async def test_growth_already_capped_does_not_award_more(growth_env):
    factory, call_id = growth_env
    async with factory() as db:
        db.add(RelationshipGrowthLog(user_id=1, action_type='voice_call', points=100,
            source_type='voice_call', source_id='previous-call', eligible_seconds=600,
            business_date=date(2026,9,14)))
        await db.commit()
        before = (await db.scalar(select(Relationship))).growth_value
        result = await RelationshipService(db).add_voice_growth(1,65,call_id)
        await db.commit()
        assert result['points'] == 0
        assert (await db.scalar(select(Relationship))).growth_value == before
        assert sum((await db.scalars(select(RelationshipGrowthLog.points))).all()) == 100


@pytest.mark.asyncio
async def test_growth_cap_does_not_block_next_call(state):
    async with state.db.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[RelationshipGrowthLog.__table__])
    state.db.add(RelationshipGrowthLog(user_id=1, action_type='voice_call', points=100,
        source_type='voice_call', source_id='previous-call', eligible_seconds=600,
        business_date=NOW.date()))
    await state.db.commit()
    result = await create(state)
    assert result['call_id']
