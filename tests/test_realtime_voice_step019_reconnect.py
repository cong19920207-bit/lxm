"""Same-owner reconnect ticket and bounded window; synthetic transports."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import asyncio
import pytest
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec, TicketError
from backend.services.realtime_voice_reconnect_service import ReconnectCoordinator


class Owner:
    def __init__(self):
        self.user_id=1;self.call_id='call';self.device_id='device';self.stopped=False
        self.events=[]
    async def disconnected(self, client_lost):self.events.append(('lost',client_lost))
    async def rebuild(self):self.events.append(('rebuild',))
    async def restored(self):self.events.append(('restored',))
    async def failed(self):self.events.append(('failed',));self.stopped=True


def coordinator(owner):
    return ReconnectCoordinator(owner, timeout_ms=1000, codec=VoiceTicketCodec(b'r'*32,purpose='voice_reconnect_v1'))

@pytest.mark.asyncio
async def test_same_call_device_single_use_ticket_and_no_deadline_extension():
    owner=Owner();c=coordinator(owner);await c.begin(client_lost=True)
    deadline=c.deadline
    ticket=await c.issue(user_id=1,device_id='device')
    assert c.deadline==deadline
    with pytest.raises(TicketError):await c.issue(user_id=2,device_id='device')
    with pytest.raises(TicketError):await c.issue(user_id=1,device_id='other')
    socket=object()
    await c.attach(socket,ticket=ticket['call_ticket'],device_id='device')
    with pytest.raises(TicketError):await c.attach(object(),ticket=ticket['call_ticket'],device_id='device')
    await c.task
    assert c.socket is socket
    assert owner.events==[('lost',True),('rebuild',),('restored',)]
    assert ticket['call_id']=='call'

@pytest.mark.asyncio
async def test_provider_only_loss_rebuilds_without_second_browser_or_call():
    owner=Owner();c=coordinator(owner)
    await c.begin(client_lost=False);await c.task
    assert owner.events==[('lost',False),('rebuild',),('restored',)]

@pytest.mark.asyncio
async def test_no_attachment_timeout_ends_once_and_replays_do_not_extend():
    owner=Owner();c=ReconnectCoordinator(owner,timeout_ms=20,codec=VoiceTicketCodec(b'r'*32,purpose='voice_reconnect_v1'))
    await c.begin(client_lost=True);deadline=c.deadline
    await c.begin(client_lost=True);assert c.deadline==deadline
    await c.task;assert owner.events.count(('failed',))==1
    with pytest.raises(TicketError):await c.issue(user_id=1,device_id='device')


def test_original_and_reconnect_tickets_are_not_interchangeable():
    original=VoiceTicketCodec(b'a'*32);reconnect=VoiceTicketCodec(b'a'*32,purpose='voice_reconnect_v1')
    now=datetime.now(timezone.utc)
    ticket=original.issue(user_id=1,call_id='call',jti='j1',device_id='device',expires_ms=int((now+timedelta(seconds=1)).timestamp()*1000))
    with pytest.raises(TicketError):reconnect.verify(ticket,call_id='call',device_id='device',now=now)

from tests.test_realtime_voice_step012_gateway import storage, session, Socket

class RebuildAdapter:
    instances=[]
    def __init__(self,**kwargs):
        from uuid import uuid4
        self.session_id=str(uuid4());self.dialog_id='dialog-'+self.session_id
        self.actions=[];self.sequence=0;self.instances.append(self)
    def capability_enabled(self,key):return False
    async def finish_session(self):self.actions.append('finish')
    async def create_connection(self):self.actions.append('connect')
    async def inject_context(self,persona,dynamic):
        assert 0<len(persona)<=5000 and 0<len(dynamic)<=2000
        self.actions.append('pack')
    async def start_session(self):
        assert self.actions==['connect','pack'];self.actions.append('start')
    async def say_hello(self,text):self.actions.append(text)

async def formal_pack(**kwargs):
    from backend.services.realtime_voice_context_pack_service import build_context_pack
    from tests.test_realtime_voice_step026_context_pack import persona,settings,Source
    raw,ref=persona()
    return await build_context_pack(user_id=kwargs['call'].user_id,persona_raw=raw,persona_ref=ref,
        settings=settings(),source=Source(),salutation='小林',relationship='朋友',
        now=kwargs['now'],ready_barrier=kwargs['barrier'])

@pytest.mark.asyncio
async def test_gateway_new_session_uses_formal_pack_and_exact_bridge_same_call(storage):
    from sqlalchemy import select,func
    from backend.models.realtime_voice import VoiceCall
    gateway=await session(storage)
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));row.status='connected';row.connected_at=datetime.now(timezone.utc).replace(tzinfo=None)
        anchor=row.connected_at;await db.commit()
    gateway.connected=True;gateway.device_id='device'
    gateway.cache.data[gateway.leases.user_key(1)]=gateway.call_id
    gateway.adapter=RebuildAdapter();old=gateway.adapter.session_id
    gateway.adapter_factory=RebuildAdapter;gateway.context_builder=formal_pack
    gateway.reconnector=coordinator(gateway)
    await gateway.observe(True)
    await gateway.reconnector.begin(client_lost=True)
    ticket=await gateway.reconnector.issue(user_id=1,device_id='device')
    await gateway.reconnector.attach(Socket(),ticket=ticket['call_ticket'],device_id='device')
    await gateway.reconnector.task
    assert gateway.connected and not gateway.stopped
    assert gateway.adapter.session_id!=old
    assert gateway.adapter.actions==['connect','pack','start','刚刚好像断了一下。你刚才说到哪儿了？']
    async with storage() as db:
        row=await db.scalar(select(VoiceCall));assert row.status=='connected' and row.connected_at==anchor
        assert await db.scalar(select(func.count()).select_from(VoiceCall))==1

@pytest.mark.asyncio
async def test_upstream_send_failure_enters_reconnect_without_replaying_pcm(storage):
    import json
    from backend.services.realtime_voice_provider_service import ProviderError
    gateway=await session(storage);gateway.connected=True
    frames=iter([{'v':1,'seq':1,'type':'audio','pcm_base64':'AAAAAA=='},
                 {'v':1,'seq':2,'type':'cancel'}])
    async def receive():return json.dumps(next(frames))
    gateway.socket.receive_text=receive
    calls=[]
    async def send_audio(pcm):calls.append(('pcm',pcm));raise ProviderError('upstream_unavailable')
    gateway.adapter.send_audio=send_audio
    async def begin(*,client_lost):
        calls.append(('reconnect',client_lost))
        gateway.reconnector.task=asyncio.create_task(asyncio.sleep(0))
    gateway.reconnector=SimpleNamespace(active=False,begin=begin)
    await gateway.receiver()
    assert calls==[('pcm',b'\0'*4),('reconnect',False)]
    assert gateway.user_cancelled
