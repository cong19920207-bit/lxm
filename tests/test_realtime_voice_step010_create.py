from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
import pytest_asyncio
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
import backend.models
from backend.database import Base
from backend.models.user import User
from backend.models.realtime_voice import VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger,VoiceCrisisRecord
from backend.constants.realtime_voice_config import get_default_voice_call_config
from backend.services.realtime_voice_create_service import VoiceCreateService,VoicePreflightError
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec

NOW=datetime(2026,9,9,6,tzinfo=timezone.utc)
REF={'config_key':'persona','version':1,'content_sha256':'sha256:'+'a'*64}
class Cache:
    def __init__(self):self.data={};self.reads=[]
    async def get(self,key):self.reads.append(key);return self.data.get(key)
class Leases:
    def __init__(self):self.cooldown=False;self.owners={};self.reason='acquired'
    async def check_new_dial(self,user):return self.cooldown
    async def acquire(self,**kw):
        if self.reason!='acquired':return False,self.reason
        self.owners[kw['user_id']]=kw['call_id'];return True,'acquired'
    async def release(self,**kw):
        if self.owners.get(kw['user_id'])==kw['call_id']:del self.owners[kw['user_id']]
class Bundle:
    def __init__(self):
        self.value=get_default_voice_call_config(REF);self.value['global'].update(enabled=True,rollout={'mode':'allowlist','user_ids':[1]})
        self.config=SimpleNamespace(technical_fallback=False)
        self.master_switch_enabled=True
        self.master_switch_version=1
    def build_snapshot(self,**kw):
        config=deepcopy(self.value)
        return SimpleNamespace(persistence_values=lambda:({'resolved_config':config},config['capabilities']))
    def should_block_new_call(self,user):
        g=self.value['global'];return not self.master_switch_enabled or g['soft_stop'] or g['maintenance_mode'] or user not in g['rollout']['user_ids']
class Loader:
    def __init__(self):self.bundle=Bundle();self.crisis_ready=True
    async def load_bundle(self,**kw):return self.bundle
    async def load_crisis_keywords(self,**kw):
        return SimpleNamespace(suspected_hit=not self.crisis_ready,
                               keywords=('fixture-only-keyword',) if self.crisis_ready else ())

@pytest_asyncio.fixture
async def state():
    engine=create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[m.__table__ for m in (User,VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger,VoiceCrisisRecord)])
    async with async_sessionmaker(engine,expire_on_commit=False)() as db:
        db.add(User(id=1,username='create',password_hash='unused'));await db.commit()
        cache=Cache();leases=Leases();loader=Loader()
        async def health(config):return True
        service=VoiceCreateService(loader=loader,cache=cache,leases=leases,ticket_codec=VoiceTicketCodec(b'x'*32),provider_preflight=health)
        payload=dict(source='home',device_id=str(uuid4()),browser_supported=True,microphone_granted=True)
        yield SimpleNamespace(db=db,cache=cache,leases=leases,loader=loader,service=service,payload=payload)
    await engine.dispose()

async def create(s,key=None,payload=None,now=NOW):
    return await s.service.create(s.db,user_id=1,idempotency_key=key or str(uuid4()),payload=payload or s.payload,now=now)


@pytest.mark.asyncio
async def test_missing_crisis_config_blocks_before_provider_quota_or_leases(state):
    s=state
    s.loader.crisis_ready=False
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    from tests.test_realtime_voice_step031_metrics import CounterCache
    sink=CounterCache();s.service.metrics=VoiceMetrics(sink)
    async def forbidden(config):
        pytest.fail('provider must not run without a crisis configuration')
    s.service.provider_preflight=forbidden
    with pytest.raises(VoicePreflightError,match='crisis_config_unavailable') as error:
        await create(s)
    assert error.value.status == 503
    for model in (VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger):
        assert await s.db.scalar(select(func.count()).select_from(model)) == 0
    assert not s.leases.owners
    assert [e for batch in sink.batches for e in batch] == [
        ('voice.preflight.result', {'result':'blocked'}, 1),
        ('voice.preflight.block_reason', {'reason':'crisis_config_unavailable'}, 1)]

@pytest.mark.asyncio
async def test_persistent_replay_precedes_cooldown_and_conflicting_payload_rejected(state):
    s=state;key=str(uuid4());first=await create(s,key)
    s.leases.cooldown=True
    s.loader.crisis_ready=False
    assert await create(s,key)==first
    with pytest.raises(VoicePreflightError,match='IDEMPOTENCY_KEY_REUSED'):
        await create(s,key,{**s.payload,'device_id':str(uuid4())})
    assert await s.db.scalar(select(func.count()).select_from(VoiceCall))==1
    assert await s.db.scalar(select(func.count()).select_from(VoiceCallCreateIdempotency))==1
    assert await s.db.scalar(select(func.count()).select_from(VoiceQuotaAccount))==0
    row=await s.db.scalar(select(VoiceCall));assert row.status=='deciding' and row.sort_seq is None

@pytest.mark.asyncio
@pytest.mark.parametrize('condition',['expired','consumed'])
async def test_ticket_expired_or_consumed_replays_only_original_status(state,condition):
    s=state;key=str(uuid4());first=await create(s,key)
    row=await s.db.scalar(select(VoiceCallCreateIdempotency))
    if condition=='consumed':row.ticket_consumed_at=NOW.replace(tzinfo=None);await s.db.commit()
    replay=await create(s,key,now=NOW+timedelta(seconds=40) if condition=='expired' else NOW)
    assert replay['call_id']==first['call_id'] and replay['call_ticket'] is None

@pytest.mark.asyncio
@pytest.mark.parametrize('condition',['db_ban','redis_ban','quota','allowlist','soft_stop','maintenance','disabled','cooldown','browser','microphone','capacity','provider'])
async def test_each_preflight_block_leaves_no_call_stub_account_ledger_or_lease(state,condition):
    s=state;c=s.loader.bundle.value
    if condition=='db_ban':(await s.db.get(User,1)).is_banned=True;await s.db.commit()
    if condition=='redis_ban':s.cache.data['user_banned:1']='1'
    if condition=='quota':c['quota']['daily_free_seconds']=0
    if condition=='allowlist':c['global']['rollout']['user_ids']=[]
    if condition=='soft_stop':c['global']['soft_stop']=True
    if condition=='maintenance':c['global']['maintenance_mode']=True
    if condition=='disabled':s.loader.bundle.master_switch_enabled=False
    if condition=='cooldown':s.leases.cooldown=True
    if condition=='browser':s.payload['browser_supported']=False
    if condition=='microphone':s.payload['microphone_granted']=False
    if condition=='capacity':s.leases.reason='capacity_full'
    if condition=='provider':
        async def unavailable(config):return False
        s.service.provider_preflight=unavailable
    with pytest.raises(VoicePreflightError):await create(s)
    for model in (VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger,VoiceCrisisRecord):
        assert await s.db.scalar(select(func.count()).select_from(model))==0
    assert not s.leases.owners and all(not k.startswith('ban:') for k in s.cache.reads)

@pytest.mark.asyncio
async def test_failure_after_lease_rolls_back_every_row_and_releases_only_owner(state,monkeypatch):
    s=state
    def broken(**kw):raise RuntimeError('ticket failure')
    monkeypatch.setattr(s.service.ticket_codec,'issue',broken)
    with pytest.raises(VoicePreflightError):await create(s)
    assert not s.leases.owners
    assert await s.db.scalar(select(func.count()).select_from(VoiceCall))==0
    assert await s.db.scalar(select(func.count()).select_from(VoiceCallCreateIdempotency))==0

@pytest.mark.asyncio
async def test_invalid_idempotency_is_client_error_and_live_db_call_blocks_new_key(state):
    s=state
    with pytest.raises(VoicePreflightError) as caught:
        await create(s,'not-a-uuid')
    assert caught.value.status==422
    await create(s)
    s.leases.owners.clear()  # Lease loss cannot authorize a second live DB call.
    with pytest.raises(VoicePreflightError,match='user_busy'):
        await create(s)
    assert await s.db.scalar(select(func.count()).select_from(VoiceCall))==1

@pytest.mark.asyncio
async def test_ticket_database_consume_once_and_bound_owner(state):
    from backend.services.realtime_voice_ticket_service import consume_voice_ticket,TicketError
    s=state;result=await create(s)
    async def matches(**kw):return s.leases.owners.get(kw['user_id'])==kw['call_id']
    s.leases.owner_matches=matches
    args=dict(codec=s.service.ticket_codec,cache=s.cache,leases=s.leases,ticket=result['call_ticket'],call_id=result['call_id'],device_id=s.payload['device_id'],now=NOW)
    row=await consume_voice_ticket(s.db,**args)
    assert row.call_id==result['call_id']
    with pytest.raises(TicketError,match='not_consumable'):await consume_voice_ticket(s.db,**args)

@pytest.mark.asyncio
async def test_cancel_after_acquire_rolls_back_and_releases_lease(state,monkeypatch):
    import asyncio
    s=state
    async def cancelled():raise asyncio.CancelledError()
    monkeypatch.setattr(s.db,'commit',cancelled)
    with pytest.raises(asyncio.CancelledError):await create(s)
    assert not s.leases.owners and not s.db.in_transaction()
    assert await s.db.scalar(select(func.count()).select_from(VoiceCall))==0

@pytest.mark.asyncio
async def test_stale_cached_quota_object_cannot_authorize_new_call(state):
    from sqlalchemy import update
    s=state
    row=VoiceQuotaAccount(user_id=1,free_quota_date=NOW.date(),free_remaining_seconds=10,extra_remaining_seconds=0,version=1)
    s.db.add(row);await s.db.commit()
    async with async_sessionmaker(s.db.bind,expire_on_commit=False)() as other:
        await other.execute(update(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id==1).values(free_remaining_seconds=0));await other.commit()
    with pytest.raises(VoicePreflightError,match='quota_empty'):await create(s)
    assert await s.db.scalar(select(func.count()).select_from(VoiceCall))==0


@pytest.mark.asyncio
async def test_cancelled_ticket_commit_rolls_back_and_preserves_owner(state,monkeypatch):
    import asyncio
    from backend.services.realtime_voice_ticket_service import consume_voice_ticket
    s=state;result=await create(s)
    async def matches(**kw):return s.leases.owners.get(kw['user_id'])==kw['call_id']
    s.leases.owner_matches=matches
    original=s.db.commit
    async def cancelled():raise asyncio.CancelledError()
    monkeypatch.setattr(s.db,'commit',cancelled)
    with pytest.raises(asyncio.CancelledError):
        await consume_voice_ticket(s.db,codec=s.service.ticket_codec,cache=s.cache,leases=s.leases,
            ticket=result['call_ticket'],call_id=result['call_id'],device_id=s.payload['device_id'],now=NOW)
    assert not s.db.in_transaction()
    monkeypatch.setattr(s.db,'commit',original)
    record=await s.db.scalar(select(VoiceCallCreateIdempotency))
    assert record.ticket_consumed_at is None and s.leases.owners[1]==result['call_id']

@pytest.mark.asyncio
@pytest.mark.parametrize('condition',['quota','allowlist','soft_stop','maintenance','disabled','cooldown','browser','microphone','capacity','provider','db_ban','redis_ban'])
async def test_block_preserves_existing_card_sort_and_all_storage_projections(state,condition):
    from backend.models.conversation_log import ConversationLog
    s=state;metrics=[]
    s.service.metric=lambda key,value:metrics.append((key,value))
    async with s.db.bind.begin() as conn:await conn.run_sync(Base.metadata.create_all,tables=[ConversationLog.__table__])
    s.db.add(ConversationLog(user_id=1,role='assistant',content='existing-sentinel',delivery_status='delivered',sort_seq=777))
    s.db.add(VoiceCall(call_id=str(uuid4()),user_id=1,initiated_by='user',status='ended',end_reason='user_hangup',
        ended_at=NOW.replace(tzinfo=None)-timedelta(seconds=10),sort_seq=778,summary_status='ready',
        config_snapshot={},capability_snapshot={},transcript_retention_days=180,generated_retention_days=30))
    await s.db.commit()
    config=s.loader.bundle.value
    if condition=='quota':config['quota']['daily_free_seconds']=0
    elif condition=='allowlist':config['global']['rollout']['user_ids']=[]
    elif condition=='disabled':s.loader.bundle.master_switch_enabled=False
    elif condition in ('soft_stop','maintenance'):
        config['global'][{'soft_stop':'soft_stop','maintenance':'maintenance_mode','disabled':'enabled'}[condition]]=condition!='disabled'
    elif condition=='cooldown':s.leases.cooldown=True
    elif condition in ('browser','microphone'):s.payload['browser_supported' if condition=='browser' else 'microphone_granted']=False
    elif condition=='capacity':s.leases.reason='capacity_full'
    elif condition=='db_ban':(await s.db.get(User,1)).is_banned=True;await s.db.commit()
    elif condition=='redis_ban':s.cache.data['user_banned:1']='1'
    elif condition=='provider':
        async def unavailable(config):return False
        s.service.provider_preflight=unavailable
    models=(VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger,VoiceCrisisRecord,ConversationLog)
    async def projection():
        return {m.__tablename__:sorted([repr(tuple(row)) for row in (await s.db.execute(select(m.__table__))).all()]) for m in models}
    before=await projection()
    with pytest.raises(VoicePreflightError):await create(s)
    assert await projection()==before
    assert not s.leases.owners
    assert len(metrics)==1 and metrics[0][0].startswith("voice.preflight.block.") and metrics[0][1]==1
    assert "sentinel" not in str(metrics) and "777" not in str(metrics)

@pytest.mark.asyncio
@pytest.mark.parametrize('elapsed,new_call',[(86399,False),(86400,True),(86401,True)])
async def test_replay_record_twenty_four_hour_boundary(state,elapsed,new_call):
    s=state;metrics=[];s.service.metric=lambda key,value:metrics.append(key)
    key=str(uuid4());first=await create(s,key)
    row=await s.db.scalar(select(VoiceCall));row.status='ended';row.ended_at=NOW.replace(tzinfo=None)
    await s.db.commit();s.leases.owners.clear()
    result=await create(s,key,now=NOW+timedelta(seconds=elapsed))
    assert (result['call_id']!=first['call_id'])==new_call
    assert await s.db.scalar(select(func.count()).select_from(VoiceCallCreateIdempotency))==1
    assert metrics==['voice.preflight.created','voice.preflight.created' if new_call else 'voice.preflight.replay']

@pytest.mark.asyncio
@pytest.mark.parametrize('wrong',['user','call'])
async def test_ticket_wrong_user_or_call_cannot_consume_or_change_owner(state,wrong):
    from backend.services.realtime_voice_ticket_service import consume_voice_ticket,TicketError
    s=state;result=await create(s)
    record=await s.db.scalar(select(VoiceCallCreateIdempotency))
    s.db.add(User(id=2,username='ticket-other-user',password_hash='unused'));await s.db.commit()
    ticket=result['call_ticket'];call_id=result['call_id']
    if wrong=='user':
        ticket=s.service.ticket_codec.issue(user_id=2,call_id=call_id,jti=record.ticket_jti,device_id=s.payload['device_id'],expires_ms=int((NOW+timedelta(seconds=30)).timestamp()*1000))
    else:call_id=str(uuid4())
    owners=dict(s.leases.owners)
    async def owner_matches(**kwargs):return owners.get(kwargs['user_id'])==kwargs['call_id']
    s.leases.owner_matches=owner_matches
    with pytest.raises(TicketError):
        await consume_voice_ticket(s.db,codec=s.service.ticket_codec,cache=s.cache,leases=s.leases,ticket=ticket,call_id=call_id,device_id=s.payload['device_id'],now=NOW)
    saved=await s.db.scalar(select(VoiceCallCreateIdempotency))
    assert saved.ticket_consumed_at is None and s.leases.owners==owners
    assert (await s.db.scalar(select(VoiceCall))).status=='deciding'
