# -*- coding: utf-8 -*-
"""STEP-006 / AC77 在真实 Redis 上的 Lua 契约验证。"""

from __future__ import annotations

import json
import os
import uuid

import pytest
import redis.asyncio as aioredis

from backend.config import get_redis_url
import backend.services.realtime_voice_config_service as config_service_module
import backend.services.realtime_voice_runtime_config_service as runtime_service_module


pytestmark = pytest.mark.asyncio


def _envelope(version: int, marker: str) -> str:
    return json.dumps(
        {
            "envelope_schema_version": 1,
            "config_key": "voice_call_config",
            "config_version": version,
            "marker": marker,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


async def test_ac77_lua_contracts_against_real_redis() -> None:
    if os.getenv("RUN_REAL_REDIS_INTEGRATION") != "1":
        pytest.skip("set RUN_REAL_REDIS_INTEGRATION=1 to exercise the project Redis")

    redis = aioredis.from_url(get_redis_url(), decode_responses=True)
    nonce = uuid.uuid4().hex
    anchor_key = f"codex:m1:ac77:anchor:{nonce}"
    metric_key = f"codex:m1:ac77:metric:{nonce}"
    version_one = _envelope(1, "one")
    version_two = _envelope(2, "two")
    conflicting_two = _envelope(2, "conflict")
    metric_dimensions = json.dumps(
        {
            "config_key": "voice_call_config",
            "mysql_status": "missing",
            "outcome": "continued",
            "redis_status": "missing",
        },
        separators=(",", ":"),
        sort_keys=True,
    )

    try:
        await redis.delete(anchor_key, metric_key)

        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT,
            1,
            anchor_key,
            1,
            version_one,
        ) == 1
        assert await redis.ttl(anchor_key) == -1
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT,
            1,
            anchor_key,
            2,
            version_two,
        ) == 1
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT,
            1,
            anchor_key,
            1,
            version_one,
        ) == 0
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT,
            1,
            anchor_key,
            2,
            version_two,
        ) == 2
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_SET_IF_NEWER_SCRIPT,
            1,
            anchor_key,
            2,
            conflicting_two,
        ) == -3

        newer_take = await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_TAKE_SCRIPT,
            1,
            anchor_key,
            1,
        )
        assert newer_take == [-1, version_two]
        assert await redis.get(anchor_key) == version_two

        accepted_take = await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_TAKE_SCRIPT,
            1,
            anchor_key,
            2,
        )
        assert accepted_take == [1, version_two]
        assert await redis.get(anchor_key) is None
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_RESTORE_IF_ABSENT_SCRIPT,
            1,
            anchor_key,
            version_two,
        ) == 1
        assert await redis.ttl(anchor_key) == -1
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_DELETE_IF_MATCH_SCRIPT,
            1,
            anchor_key,
            conflicting_two,
        ) == 0
        assert await redis.eval(
            config_service_module._PUBLISHED_ANCHOR_DELETE_IF_MATCH_SCRIPT,
            1,
            anchor_key,
            version_two,
        ) == 1

        assert await redis.eval(
            runtime_service_module._FALLBACK_METRIC_INCREMENT_SCRIPT,
            1,
            metric_key,
            metric_dimensions,
            1,
            runtime_service_module._FALLBACK_METRIC_TTL_SECONDS,
        ) == 1
        assert await redis.eval(
            runtime_service_module._FALLBACK_METRIC_INCREMENT_SCRIPT,
            1,
            metric_key,
            metric_dimensions,
            1,
            runtime_service_module._FALLBACK_METRIC_TTL_SECONDS,
        ) == 2
        metric_payload = json.loads(await redis.get(metric_key))
        assert metric_payload == {metric_dimensions: 2}
        metric_ttl = await redis.ttl(metric_key)
        assert 0 < metric_ttl <= runtime_service_module._FALLBACK_METRIC_TTL_SECONDS
    finally:
        await redis.delete(anchor_key, metric_key)
        await redis.aclose()
