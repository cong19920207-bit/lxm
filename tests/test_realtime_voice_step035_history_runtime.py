import os
from types import SimpleNamespace
import pytest
from httpx import ASGITransport,AsyncClient
from backend.utils.admin_auth import get_current_admin
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step035_history import test_history_missing_invalid_and_version_isolation as seed_and_check
from tests.test_realtime_voice_step035_api import build_api
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_actual_mysql_history_http(runtime):
    factory=runtime[0]
    await seed_and_check(factory)
    app=await build_api(factory)
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(role='observer')
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.get('/api/admin/voice/metrics/history?start=2026-09-18&end=2026-09-19')
        assert response.status_code==200
        rows={row['name']:row for row in response.json()['data']['days'][1]['metrics']}
        assert rows['daily_call_count']['value']==0 and rows['connect_rate']['value']==.5
        assert rows['failure_rate']['value'] is None
        assert rows['billable_seconds']['value'] is None
        for start,end in [('2026-09-20','2026-09-19'),('2026-01-01','2026-09-19')]:
            assert (await client.get('/api/admin/voice/metrics/history',params=dict(start=start,end=end))).status_code==422
        assert 'DO_NOT_EXPOSE' not in response.text
