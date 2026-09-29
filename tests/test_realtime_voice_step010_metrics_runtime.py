import os
from uuid import uuid4
from datetime import datetime,timezone
import pytest
from backend.database import Base
from backend.models.user import User
from backend.models.realtime_voice import VoiceCallCreateIdempotency
from backend.services.realtime_voice_create_service import VoiceCreateService,VoicePreflightError
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec
from tests.test_realtime_voice_step010_create import Loader
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_preflight_actual_commit_replay_and_shared_zero_writes(runtime):
    factory,_,cache=runtime
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoiceCallCreateIdempotency.__table__])
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for name,value in shared.items():await cache.set(name,value)
    async def health(config):return True
    async def end(**kwargs):pass
    loader=Loader();loader.bundle.value['global']['rollout']['user_ids']=[2]
    service=VoiceCreateService(loader=loader,cache=cache,leases=VoiceLeaseService(cache,end_call=end),
        ticket_codec=VoiceTicketCodec(b'x'*32),provider_preflight=health)
    key=str(uuid4());payload=dict(source='home',device_id=str(uuid4()),browser_supported=True,microphone_granted=True)
    async with factory() as db:
        db.add(User(id=2,username='metric-user',password_hash='unused'));await db.commit()
        kwargs=dict(user_id=2,idempotency_key=key,payload=payload,now=datetime.now(timezone.utc))
        first=await service.create(db,**kwargs);assert await service.create(db,**kwargs)==first
        with pytest.raises(VoicePreflightError):await service.create(db,**{**kwargs,'payload':{**payload,'device_id':str(uuid4())}})
    keys=[name async for name in cache.scan_iter(match='voice.preflight.*')]
    assert {name.split(':')[0] for name in keys}=={'voice.preflight.result','voice.preflight.idempotency','voice.preflight.block_reason'}
    for name in keys:
        assert 172790<=await cache.ttl(name)<=172800
        values=await cache.hgetall(name)
        assert set(values.values())=={'1'} and first['call_id'] not in str(values)
    assert {name:await cache.get(name) for name in shared}==shared
