"""Bounded crisis-keyword reads with a published-DB fallback.

Never substitute an empty list or defaults for an unavailable safety policy.
Admin inspection is read-only so opening the page cannot hide a broken cache.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from sqlalchemy import select

from backend.models.admin_config import AdminConfig
from backend.services.realtime_voice_config_service import VoiceConfigError, normalize_crisis_keywords

CACHE_KEY = 'active_config:crisis_keywords'
CACHE_TTL = 3600
_REFILL = """
local current = redis.call('GET', KEYS[1])
if (ARGV[1] == '1' and not current) or (ARGV[1] == '0' and current == ARGV[2]) then
    redis.call('SET', KEYS[1], ARGV[3], 'EX', ARGV[4])
    return 1
end
return 0
"""


@dataclass(frozen=True, slots=True)
class CrisisKeywordLoadResult:
    keywords: tuple[str, ...]
    suspected_hit: bool
    failure_reason: str | None = None


def parse_keywords(raw):
    if raw is None:
        return (), 'missing'
    try:
        value = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except (UnicodeDecodeError, TypeError, ValueError):
        return (), 'invalid_json'
    try:
        return tuple(normalize_crisis_keywords(value)), None
    except (VoiceConfigError, TypeError, ValueError):
        return (), 'invalid_or_empty'


class CrisisConfigReader:
    # Each operation has a deadline; no detached DB/cache task outlives the caller.
    io_timeout = 1.0

    def __init__(self, *, session_factory, redis_provider):
        self.session_factory, self.redis_provider = session_factory, redis_provider

    async def _read_cache(self):
        cache = await self.redis_provider()
        return cache, await cache.get(CACHE_KEY)

    async def _read_published(self, db=None):
        if db is None:
            async with self.session_factory() as session:
                return await self._read_published(session)
        rows = (await db.execute(select(AdminConfig.config_value, AdminConfig.version).where(
            AdminConfig.config_key == 'crisis_keywords',
            AdminConfig.is_active.is_(True), AdminConfig.is_draft.is_(False)).limit(2))).all()
        if not rows:
            return (), None, 'unpublished'
        if len(rows) != 1:
            return (), None, 'invalid'
        words, error = parse_keywords(rows[0].config_value)
        return words, rows[0].version, 'invalid' if error else 'published'

    async def load(self, *, db=None):
        cache = None
        raw = None
        try:
            cache, raw = await asyncio.wait_for(self._read_cache(), self.io_timeout)
            words, reason = parse_keywords(raw)
            if reason is None:
                return CrisisKeywordLoadResult(words, False)
        except Exception:
            reason = 'redis_unavailable'

        try:
            words, _, status = await asyncio.wait_for(self._read_published(db), self.io_timeout)
        except Exception:
            # Keep failure dimensions bounded; never log keywords or DB errors.
            return CrisisKeywordLoadResult((), True, reason)
        if status != 'published':
            return CrisisKeywordLoadResult((), True, reason)

        if cache is not None and (raw is None or isinstance(raw, (str, bytes))):
            try:
                # Compare with the exact value observed before the DB read.
                # A concurrent publication/rollback always wins over this refill.
                await asyncio.wait_for(cache.eval(_REFILL, 1, CACHE_KEY,
                    '1' if raw is None else '0', raw if raw is not None else '',
                    json.dumps(words, ensure_ascii=False), CACHE_TTL), self.io_timeout)
            except Exception:
                pass  # The published DB policy remains usable without Redis.
        return CrisisKeywordLoadResult(words, False)

    async def inspect(self, *, db):
        """Return durable publication and cache health without warming the cache."""
        try:
            words, version, publication = await asyncio.wait_for(self._read_published(db), self.io_timeout)
        except Exception:
            words, version, publication = (), None, 'unavailable'
        try:
            _, raw = await asyncio.wait_for(self._read_cache(), self.io_timeout)
            cached, error = parse_keywords(raw)
            cache_status = ('missing' if error == 'missing' else 'invalid' if error else
                            'healthy' if publication == 'published' and cached == words else 'out_of_sync')
        except Exception:
            cache_status = 'unavailable'
        return list(words), dict(publication_status=publication, active_version=version,
            keyword_count=len(words), cache_status=cache_status, fallback_ready=publication == 'published')
