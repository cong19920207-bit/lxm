import json
import os
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall, VoiceCrisisRecord
from backend.services.realtime_voice_crisis_presentation_service import crisis_presentations
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from backend.services.timeline_read_service import get_timeline
from tests.test_realtime_voice_step033_runtime import containers, runtime, card_env
from tests.test_realtime_voice_m6_summary_delete_runtime import summary_env, base_summary_env
from tests.test_realtime_voice_step034_delete import ADMIN

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME') != '1', reason='isolated stores only')


@pytest.mark.asyncio
@pytest.mark.parametrize('clear', ['expiry', 'delete'])
async def test_public_resources_frozen_deduplicated_and_unrecoverable(summary_env, runtime, clear):
    factory, call_id = summary_env
    _, _, cache = runtime
    now = datetime.utcnow()
    sentinel = 'CRISIS-RAW-025-NEVER-PUBLIC'
    banner = '发布文案：请联系可信任的人，或拨打 12356。'
    resource = '发布资源：110/120；12356。'
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        call.config_snapshot = {**call.config_snapshot, 'resolved_script':{'crisis':{
            'in_call_banner':banner, 'post_call_resource_card':resource}}}
        for direction in ('user','assistant'):
            db.add(VoiceCrisisRecord(call_id=call_id, turn_index=1, direction=direction,
                content_plaintext=sentinel, matched_keyword=sentinel, match_status='matched',
                is_persona_incident=direction=='assistant', expires_at=now+timedelta(days=30)))
        await db.commit()
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        projection = await crisis_presentations(db, [call], now=now)
        assert projection[call_id]['banner'] == banner
        assert projection[call_id]['resource'] == resource
        assert len(projection) == 1 and sentinel not in json.dumps(projection)
        stored_expiry = await db.scalar(select(VoiceCrisisRecord.expires_at).limit(1))
        assert await crisis_presentations(db, [call], now=stored_expiry) == {}
        timeline = await get_timeline(1, db, include_calls=True)
        assert len(timeline['items']) == 1 and timeline['items'][0]['crisis_resource']['resource'] == resource
        assert sentinel not in json.dumps(timeline)
        assert all('crisis_resource' not in row for row in (await get_timeline(1, db))['items'])
    retention = VoiceRetentionService(session_factory=factory, cache=cache)
    if clear == 'delete':
        await retention.delete_call(call_id=call_id, admin=ADMIN)
    else:
        async with factory() as db:
            for row in (await db.scalars(select(VoiceCrisisRecord))).all(): row.expires_at = now.replace(microsecond=0)
            await db.commit()
        await retention.purge_contents(now=now)
    async with factory() as db:
        call = await db.scalar(select(VoiceCall))
        assert await crisis_presentations(db, [call]) == {}
        timeline = await get_timeline(1, db, include_calls=True)
        assert all(row['crisis_resource'] is None for row in timeline['items'])
        assert sentinel not in json.dumps(timeline)
        assert all(row.content_plaintext is None for row in (await db.scalars(select(VoiceCrisisRecord))).all())
