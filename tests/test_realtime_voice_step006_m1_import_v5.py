"""Synthetic v7 storage fixture; never writes campaign or production facts."""
from copy import deepcopy
import pytest

from tests.test_realtime_voice_step006_evidence_import import (
    database, _import, _stable_state, _redis_state,
)
from tests.test_realtime_voice_step006_m1_protocol_v5 import native_bundle_v7


@pytest.mark.asyncio
async def test_v7_bundle_append_is_atomic_and_replay_preserves_active_and_redis():
    before = await _stable_state()
    redis_before = _redis_state()
    bundle = native_bundle_v7()
    await _import(bundle)
    imported = await _stable_state()
    assert len(imported['evidence']) == len(before['evidence']) + 6
    assert len(imported['audit']) == len(before['audit']) + 1
    assert [c for c in imported['configs'] if c[4]] == [c for c in before['configs'] if c[4]]
    assert _redis_state() == redis_before
    await _import(deepcopy(bundle))
    replayed = await _stable_state()
    assert replayed['evidence'] == imported['evidence']
    assert replayed['configs'] == imported['configs']
    assert _redis_state() == redis_before
