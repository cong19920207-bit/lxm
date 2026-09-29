from datetime import timedelta
from dataclasses import asdict

import pytest
from tests.test_realtime_voice_step008_quota import db, call, NOW
from backend.services.realtime_voice_quota_service import ConnectedMeter, VoiceQuotaService


@pytest.mark.asyncio
async def test_full_timeline_excludes_mute_reconnect_and_grace(db):
    row = await call(db)
    meter = ConnectedMeter(row.call_id, 1, 245, 30)
    service = VoiceQuotaService()
    # 10秒建立，30秒有效，180秒主动静音，20秒重连，35秒有效，30秒免费收尾。
    for second, connected, muted in [(0, False, False), (10, True, False),
        (40, True, True), (220, False, True), (240, True, False),
        (275, True, False), (305, False, False)]:
        await service.observe(db, meter, connected=connected, muted=muted,
            monotonic=second, now=NOW + timedelta(seconds=second))
    # Recovery must preserve the independent growth counter, including mute state.
    restored = ConnectedMeter(**asdict(meter))
    await service.settle(db, restored)
    assert row.growth_eligible_seconds == 65
    assert row.duration_seconds == 275
    assert row.free_seconds_used == 245 and row.grace_seconds == 30


@pytest.mark.asyncio
async def test_fractional_mute_boundaries_do_not_round_per_observation(db):
    row = await call(db)
    meter = ConnectedMeter(row.call_id, 1, 300, 30)
    service = VoiceQuotaService()
    for second, muted in [(0, False), (.6, True), (1.2, False), (1.8, True)]:
        await service.observe(db, meter, connected=True, muted=muted,
            monotonic=second, now=NOW + timedelta(seconds=second))
    await service.settle(db, meter)
    assert row.growth_eligible_seconds == 1


@pytest.mark.asyncio
async def test_growth_crosses_integer_without_new_billable_second(db):
    row = await call(db)
    meter = ConnectedMeter(row.call_id, 1, 300, 30)
    service = VoiceQuotaService()
    for second, muted in [(0, True), (.7, False), (1.3, False)]:
        await service.observe(db, meter, connected=True, muted=muted,
            monotonic=second, now=NOW + timedelta(seconds=second))
    await service.settle(db, meter)
    assert row.growth_eligible_seconds == 0 and row.free_seconds_used == 1
    await service.observe(db, meter, connected=True, muted=False,
        monotonic=1.8, now=NOW + timedelta(seconds=1.8))
    await service.settle(db, meter)
    assert row.growth_eligible_seconds == 1 and row.free_seconds_used == 1
