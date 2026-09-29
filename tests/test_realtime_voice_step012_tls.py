"""Opt-in real loopback TLS transport. Provider is explicitly controlled."""
import asyncio,json,os,socket,ssl,subprocess
from datetime import datetime,timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest,pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
import uvicorn,websockets
from tests.test_realtime_voice_step010_create import create,Loader,Leases,Cache
from backend.database import Base
from backend.models.relationship import Relationship
from backend.models.life_plan import LifePlan
from backend.models.realtime_voice import VoiceCall
from backend.constants.realtime_voice_config import get_default_voice_call_script
from backend.services.realtime_voice_gateway_service import VoiceGatewaySession
from backend.services.realtime_voice_provider_service import ProviderEvent


@pytest_asyncio.fixture
async def state(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
    from backend.models.user import User
    from backend.models.realtime_voice import VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger,VoiceCallTurn,VoiceCrisisRecord,VoiceFollowupJob
    from backend.models.user_timeline_seq import UserTimelineSeq
    from backend.models.relationship_growth_log import RelationshipGrowthLog
    from backend.models.relationship_level_history import RelationshipLevelHistory
    from backend.services.realtime_voice_create_service import VoiceCreateService
    from backend.services.realtime_voice_ticket_service import VoiceTicketCodec
    engine=create_async_engine('sqlite+aiosqlite:///'+str(tmp_path/'tls.sqlite'))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[m.__table__ for m in (User,VoiceCall,VoiceCallCreateIdempotency,VoiceQuotaAccount,VoiceUsageLedger,VoiceCallTurn,VoiceCrisisRecord,VoiceFollowupJob,UserTimelineSeq,RelationshipGrowthLog,RelationshipLevelHistory)])
    async with async_sessionmaker(engine,expire_on_commit=False)() as db:
        db.add(User(id=1,username='tls',password_hash='unused'));await db.commit()
        cache=Cache();leases=Leases();loader=Loader()
        async def health(config):return True
        service=VoiceCreateService(loader=loader,cache=cache,leases=leases,ticket_codec=VoiceTicketCodec(b'x'*32),provider_preflight=health)
        yield SimpleNamespace(db=db,cache=cache,leases=leases,loader=loader,service=service,
            payload=dict(source='home',device_id=str(uuid4()),browser_supported=True,microphone_granted=True))
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('VOICE_LOOPBACK_TLS_TEST')!='1',reason='Explicit local socket test only')
async def test_verified_tls_single_ticket_actual_gateway_and_audio_envelope(state,tmp_path,monkeypatch):
    from backend.routers import realtime_voice as route
    from sqlalchemy.ext.asyncio import async_sessionmaker
    s=state
    async with s.db.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[Relationship.__table__,LifePlan.__table__])
    result=await create(s,now=datetime.now(timezone.utc));cid=result['call_id']
    row=await s.db.scalar(select(VoiceCall))
    script=get_default_voice_call_script();script['call_answer']['prompt_template']='接听测试'
    row.config_snapshot={**row.config_snapshot,'resolved_script':script};await s.db.commit()
    factory=async_sessionmaker(s.db.bind,expire_on_commit=False)
    async def owner(**kw):return s.leases.owners.get(kw['user_id'])==kw['call_id']
    s.leases.owner_matches=owner
    async def cache():return s.cache
    # Only external Provider/context/model and Redis transport are controlled.
    # Ticket SQL consumption, WSS Origin/TLS, gateway states/frame parser are real.
    class Cache:
        async def get(self,key):return None
        async def eval(self,*args):return 1
        async def publish(self,*args):pass
    runtime_cache=Cache()
    async def cache():return runtime_cache
    class Adapter:
        def __init__(self,**kw):self.session_id=str(uuid4());self.call_id=kw['call_id'];self.audio=asyncio.Queue()
        async def create_connection(self):pass
        async def inject_context(self,*args):pass
        async def start_session(self):return self.session_id
        async def say_hello(self,content):pass
        async def send_audio(self,pcm):await self.audio.put(pcm)
        async def receive_event(self):return ProviderEvent('audio',self.call_id,self.session_id,1,'q','r',await self.audio.get())
        async def finish_session(self):pass
    async def context(**kw):kw['barrier'].set();return SimpleNamespace(persona='受控人格',dynamic='受控上下文')
    async def model(prompt):return '{"answer":true,"delay_seconds":4,"opening_text":"喂"}'
    class Gateway(VoiceGatewaySession):
        def __init__(self,**kw):super().__init__(**kw,adapter_factory=Adapter,context_builder=context,decision_model=model)
    monkeypatch.setattr(route,'async_session_maker',factory)
    monkeypatch.setattr(route,'get_redis',cache)
    monkeypatch.setattr(route,'VoiceLeaseService',lambda *args,**kw:s.leases)
    monkeypatch.setattr(route,'ticket_codec_from_environment',lambda:s.service.ticket_codec)
    monkeypatch.setattr(route,'VoiceGatewaySession',Gateway)
    monkeypatch.setenv('VOICE_ALLOWED_ORIGINS','https://localhost')
    monkeypatch.delenv('VOICE_ALLOW_INSECURE_LOCAL',raising=False)
    cert=tmp_path/'cert.pem';key=tmp_path/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
        '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1',
        '-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    from tests.test_realtime_voice_step031_metrics import CounterCache
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    metric_cache=CounterCache()
    app=FastAPI();app.state.voice_metrics=VoiceMetrics(metric_cache);app.include_router(route.router)
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,ssl_certfile=str(cert),ssl_keyfile=str(key),lifespan='off',access_log=False,log_level='critical'))
    task=asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:await asyncio.sleep(.02)
        tls=ssl.create_default_context(cafile=str(cert))
        protocols=['voice.v1','ticket.'+result['call_ticket'],'device.'+s.payload['device_id']]
        url=f'wss://127.0.0.1:{port}/api/voice/calls/{cid}/stream'
        with pytest.raises(websockets.exceptions.InvalidStatus):
            async with websockets.connect(url,ssl=tls,origin='https://evil.invalid',subprotocols=protocols):pass
        statuses=[]
        async with websockets.connect(url,ssl=tls,origin='https://localhost',subprotocols=protocols) as ws:
            async with asyncio.timeout(10):
                while 'connected' not in statuses:
                    frame=json.loads(await ws.recv())
                    if frame['type']=='state':statuses.append(frame['status'])
                await ws.send(json.dumps({'v':1,'seq':1,'type':'audio','pcm_base64':'AAA='}))
                while True:
                    frame=json.loads(await ws.recv())
                    if frame['type']=='audio':break
                assert frame['pcm_base64']=='AAA=' and frame['metadata']['call_id']==cid
                await ws.send(json.dumps({'v':1,'seq':2,'type':'cancel'}))
                await ws.wait_closed()
        assert statuses==['deciding','ringing','connected']
        with pytest.raises(websockets.exceptions.InvalidStatus):
            async with websockets.connect(url,ssl=tls,origin='https://localhost',subprotocols=protocols):pass
        async with asyncio.timeout(5):
            while True:
                async with factory() as db:
                    final=await db.scalar(select(VoiceCall))
                    if final.status=='ended':break
                await asyncio.sleep(.02)
        assert final.end_reason=='user_hangup' and final.provider_session_id
        async with asyncio.timeout(2):
            while ('voice.ws.connection',{'channel':'initial','result':'disconnected'},1) not in [e for b in metric_cache.batches for e in b]:
                await asyncio.sleep(.01)
        events=[e for b in metric_cache.batches for e in b]
        assert events.count(('voice.ws.connection',{'channel':'initial','result':'accepted'},1))==1
        assert events.count(('voice.ws.connection',{'channel':'initial','result':'disconnected'},1))==1
        assert ('voice.ws.rejection',{'channel':'initial','reason':'origin'},1) in events
        assert ('voice.ws.rejection',{'channel':'initial','reason':'ticket'},1) in events

    finally:
        server.should_exit=True
        await asyncio.wait_for(task,5)
        listener.close()
