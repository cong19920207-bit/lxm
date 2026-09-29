import os
import pytest
from sqlalchemy import update
from backend.models.realtime_voice import VoiceCall
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step035_priced_daily import test_source_to_ten_materialized_rows_and_isolated_price_history as verify_pipeline
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_priced_source_to_ten_rows(runtime):
    factory=runtime[0]
    async with factory() as db:
        await db.execute(update(VoiceCall).values(status='ended'))
        await db.commit()
    await verify_pipeline(factory)
