"""Opt-in isolated MySQL/Redis recovery checks; never use application stores."""
import asyncio
import json
import os

import pytest

from backend.models.admin_config import AdminConfig
from backend.services.realtime_voice_crisis_config_service import CrisisConfigReader, CACHE_KEY
from tests.test_realtime_voice_m4_runtime import containers, runtime

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_CRISIS_CONFIG_RUNTIME') != '1',
                               reason='isolated MySQL/Redis test gate')


@pytest.mark.asyncio
@pytest.mark.parametrize('initial', ['expired', 'invalid', 'concurrent_publish', 'concurrent_rollback'])
async def test_real_redis_recovery_and_atomic_refill(runtime, initial):
    factory, _, cache = runtime
    async with factory() as db:
        db.add(AdminConfig(config_key='crisis_keywords', config_value='["fixture-policy"]',
                           is_active=True, is_draft=False, version=2))
        await db.commit()
    if initial == 'expired':
        await cache.set(CACHE_KEY, '["fixture-policy"]', px=1)
        await asyncio.sleep(0.02)
        assert await cache.get(CACHE_KEY) is None
    elif initial in {'invalid', 'concurrent_rollback'}:
        await cache.set(CACHE_KEY, 'corrupted')

    class ConcurrentCache:
        async def get(self, key):
            return await cache.get(key)
        async def eval(self, *args):
            replacement = 'published-new' if initial == 'concurrent_publish' else 'rollback-version'
            await cache.set(CACHE_KEY, json.dumps([replacement]), ex=3600)
            return await cache.eval(*args)

    async def provider():
        return ConcurrentCache() if initial.startswith('concurrent_') else cache
    result = await CrisisConfigReader(session_factory=factory, redis_provider=provider).load()
    assert not result.suspected_hit and result.keywords == ('fixture-policy',)
    expected = {'concurrent_publish':'published-new', 'concurrent_rollback':'rollback-version'}.get(initial,'fixture-policy')
    assert json.loads(await cache.get(CACHE_KEY)) == [expected]
    assert 3590 <= await cache.ttl(CACHE_KEY) <= 3600
