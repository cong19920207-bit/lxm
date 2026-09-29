"""Server lease boundary tests; Redis Lua runtime verified separately in DB15."""
from uuid import uuid4
import pytest
from backend.services.realtime_voice_lease_service import VoiceLeaseService

class Cache:
    async def eval(self, *args): raise ConnectionError('not logged')

@pytest.mark.asyncio
async def test_renew_failure_actively_ends_exact_owner_call():
    ends=[]; metrics=[]
    async def end(**kwargs): ends.append(kwargs)
    call_id=str(uuid4())
    service=VoiceLeaseService(Cache(),end_call=end,metric=lambda key,v:metrics.append(key))
    assert not await service.renew(user_id=1,call_id=call_id,ttl_ms=15000)
    assert ends==[dict(user_id=1,call_id=call_id,reason='system_error')]
    assert metrics==['voice.lease.renew_failed']

@pytest.mark.asyncio
async def test_invalid_lease_bounds_do_not_call_redis_or_end_other_calls():
    async def end(**kwargs): pytest.fail('invalid request must not end call')
    service=VoiceLeaseService(Cache(),end_call=end)
    with pytest.raises(ValueError):
        await service.renew(user_id=1,call_id=str(uuid4()),ttl_ms=1)
