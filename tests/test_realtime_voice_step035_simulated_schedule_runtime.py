import os
from datetime import datetime
import pytest
from sqlalchemy import update
from backend.models.realtime_voice import VoiceCall
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step035_scheduler import test_explicit_simulation_batch_materializes_cost_and_keeps_default_isolated as verify_schedule
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_simulated_cost_schedule(runtime):
    factory=runtime[0]
    async with factory() as db:
        await db.execute(update(VoiceCall).values(status='ended',created_at=datetime(2026,9,17)))
        await db.commit()
    await verify_schedule(factory)
