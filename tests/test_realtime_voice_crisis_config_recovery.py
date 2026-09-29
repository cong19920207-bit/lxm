"""Crisis configuration recovery and read-only admin health (awaiting test gate)."""
import asyncio
import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.admin_config import AdminConfig
from backend.services.realtime_voice_runtime_config_service import RealtimeVoiceRuntimeConfigService
from backend.services.realtime_voice_crisis_config_service import CrisisConfigReader, CACHE_KEY


class Cache:
    def __init__(self, raw=None, *, unavailable=False, replacement=None):
        self.raw, self.unavailable, self.replacement = raw, unavailable, replacement
        self.writes = 0

    async def get(self, key):
        assert key == CACHE_KEY
        if self.unavailable:
            raise ConnectionError('cache unavailable')
        return self.raw

    async def eval(self, script, count, key, missing, observed, value, ttl):
        assert count == 1 and key == CACHE_KEY
        if self.replacement is not None:
            self.raw = self.replacement
        if (missing == '1' and self.raw is None) or (missing == '0' and self.raw == observed):
            self.raw = value
            self.writes += 1
            return 1
        return 0


@pytest_asyncio.fixture
async def config_db():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=[AdminConfig.__table__])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def publish(factory, value='["fixture-only-keyword"]', **flags):
    async with factory() as db:
        db.add(AdminConfig(config_key='crisis_keywords', config_value=value,
                           version=4, is_active=flags.get('active', True),
                           is_draft=flags.get('draft', False)))
        await db.commit()


def reader(factory, cache):
    async def provider():
        return cache
    return CrisisConfigReader(session_factory=factory, redis_provider=provider)


@pytest.mark.asyncio
@pytest.mark.parametrize('raw', [None, 'bad-json', '[]', '{}', b'\xff'])
async def test_missing_or_invalid_cache_uses_published_database(config_db, raw):
    await publish(config_db)
    cache = Cache(raw)
    result = await reader(config_db, cache).load()
    assert not result.suspected_hit and result.keywords == ('fixture-only-keyword',)
    assert json.loads(cache.raw) == ['fixture-only-keyword']
    assert cache.writes == 1


@pytest.mark.asyncio
async def test_valid_cache_does_not_access_database():
    def forbidden():
        raise AssertionError('database must not be needed')
    result = await reader(forbidden, Cache('[" valid ","valid"]')).load()
    assert result.keywords == ('valid',) and not result.suspected_hit


@pytest.mark.asyncio
@pytest.mark.parametrize('flags,value', [({'draft': True}, '["word"]'),
    ({'active': False}, '["word"]'), ({}, '[]'), ({}, '{}'), ({}, 'broken')])
async def test_no_trusted_publication_remains_closed(config_db, flags, value):
    await publish(config_db, value, **flags)
    cache = Cache()
    result = await reader(config_db, cache).load()
    assert result.suspected_hit and result.keywords == () and cache.writes == 0


@pytest.mark.asyncio
async def test_unpublished_and_duplicate_active_rows_remain_closed(config_db):
    assert (await reader(config_db, Cache()).load()).suspected_hit
    await publish(config_db)
    await publish(config_db, '["second"]')
    assert (await reader(config_db, Cache()).load()).suspected_hit


@pytest.mark.asyncio
async def test_redis_outage_and_writeback_failure_do_not_discard_valid_database(config_db):
    await publish(config_db)
    assert not (await reader(config_db, Cache(unavailable=True)).load()).suspected_hit
    cache = Cache()
    async def fail(*args):
        raise ConnectionError('write failed')
    cache.eval = fail
    assert not (await reader(config_db, cache).load()).suspected_hit


@pytest.mark.asyncio
@pytest.mark.parametrize('raw', [None, 'broken'])
async def test_recovery_does_not_overwrite_concurrent_publish_or_rollback(config_db, raw):
    await publish(config_db)
    cache = Cache(raw, replacement='["new-publication"]')
    assert not (await reader(config_db, cache).load()).suspected_hit
    assert cache.raw == '["new-publication"]' and cache.writes == 0


@pytest.mark.asyncio
async def test_bounded_cache_read_falls_back_and_database_timeout_stays_closed(config_db):
    await publish(config_db)
    cache = Cache()
    async def slow(*args):
        await asyncio.sleep(10)
    cache.get = slow
    service = reader(config_db, cache)
    service.io_timeout = 0.01
    assert not (await service.load()).suspected_hit
    service._read_published = slow
    result = await service.load()
    assert result.suspected_hit and result.keywords == ()


@pytest.mark.asyncio
async def test_existing_transaction_is_reused(config_db):
    await publish(config_db)
    def forbidden():
        raise AssertionError('do not open another DB connection inside the turn transaction')
    async def provider():
        return Cache()
    loader = RealtimeVoiceRuntimeConfigService(session_factory=forbidden, redis_provider=provider)
    async with config_db() as db:
        result = await loader.load_crisis_keywords(db=db)
    assert not result.suspected_hit


@pytest.mark.asyncio
async def test_admin_health_is_read_only_and_distinguishes_publication_and_cache(config_db):
    cache = Cache()
    service = reader(config_db, cache)
    async with config_db() as db:
        keywords, status = await service.inspect(db=db)
        assert keywords == [] and status['publication_status'] == 'unpublished'
    await publish(config_db)
    async with config_db() as db:
        keywords, status = await service.inspect(db=db)
    assert keywords == ['fixture-only-keyword']
    assert status['publication_status'] == 'published' and status['active_version'] == 4
    assert status['cache_status'] == 'missing' and status['fallback_ready'] is True
    assert cache.raw is None and cache.writes == 0
    cache.raw = '["older"]'
    async with config_db() as db:
        _, status = await service.inspect(db=db)
    assert status['cache_status'] == 'out_of_sync'
