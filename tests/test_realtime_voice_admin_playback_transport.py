import asyncio,json
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from backend.services.realtime_voice_admin_playback_transport import RedisPlaybackTarget,PlaybackTargetError,acknowledge_playback


@pytest.mark.asyncio
async def test_target_registers_expected_identity_before_asking_browser_to_ack():
    cache=AsyncMock();cache.set.return_value=True
    target=await RedisPlaybackTarget.open(cache,admin_id=7)
    expected=dict(call_id=str(uuid4()),session_id=str(uuid4()),reply_id=str(uuid4()),audio_bytes=16)
    cache.blpop.return_value=('key',json.dumps(expected))
    assert await target.wait_played(**expected)==expected
    event=await target.events.get()
    assert event==dict(type='playback_end',test_id=target.test_id,**expected)
    state=json.loads(cache.setex.call_args.args[2])
    assert state==dict(admin_id=7,expected=expected)
    await target.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('case',['owner','session','missing','stale'])
async def test_ack_rejects_wrong_owner_identity_expired_and_close_race(case):
    cache=AsyncMock();tid=str(uuid4())
    expected=dict(call_id=str(uuid4()),session_id=str(uuid4()),reply_id=str(uuid4()),audio_bytes=16)
    cache.get.return_value=None if case=='missing' else json.dumps(dict(admin_id=7,expected=expected))
    supplied={**expected,'session_id':'wrong'} if case=='session' else expected
    cache.eval.return_value=0
    with pytest.raises(PlaybackTargetError):
        await acknowledge_playback(cache,test_id=tid,admin_id=8 if case=='owner' else 7,ack=supplied)
    assert cache.eval.await_count==(1 if case=='stale' else 0)


@pytest.mark.asyncio
async def test_duplicate_admin_playback_is_rejected_before_provider():
    cache=AsyncMock();cache.set.return_value=False
    with pytest.raises(PlaybackTargetError):await RedisPlaybackTarget.open(cache,admin_id=7)
