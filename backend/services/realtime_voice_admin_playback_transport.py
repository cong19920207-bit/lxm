"""Short-lived admin playback delivery; Redis carries identity/ACK, never PCM.

The streaming request owns Provider/audio. A different worker may accept the
browser's authenticated ACK. No evidence or production capability is written.
"""
import asyncio
import base64
import json
from uuid import UUID,uuid4

TTL_SECONDS=60
ACK_ONCE="""
if redis.call('GET',KEYS[3]) ~= ARGV[3] then return 0 end
if redis.call('GET',KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('DEL',KEYS[1])
redis.call('RPUSH',KEYS[2],ARGV[2])
redis.call('EXPIRE',KEYS[2],60)
return 1
"""
CLOSE_TARGET="""
redis.call('DEL',KEYS[1],KEYS[2])
if redis.call('GET',KEYS[3]) == ARGV[1] then redis.call('DEL',KEYS[3]) end
return 1
"""


class PlaybackTargetError(ValueError):
    def __init__(self,category='playback_target_invalid'):
        self.category=category
        super().__init__(category)


def keys(test_id):
    try:
        if str(UUID(test_id))!=test_id:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise PlaybackTargetError() from None
    return f'voice:admin_playback:test:{test_id}',f'voice:admin_playback:ack:{test_id}'


async def acknowledge_playback(cache,*,test_id,admin_id,ack):
    state_key,ack_key=keys(test_id)
    raw=await cache.get(state_key)
    try:
        state=json.loads(raw)
        if state['admin_id']!=admin_id or state['expected']!=ack:
            raise ValueError()
        if type(ack.get('audio_bytes')) is not int:raise ValueError()
    except (ValueError,TypeError,KeyError,AttributeError):raise PlaybackTargetError() from None
    # Check-and-consume prevents both duplicate ACK and close-after-read revival.
    if not await cache.eval(ACK_ONCE,3,state_key,ack_key,
                            f'voice:admin_playback:owner:{admin_id}',raw,
                            json.dumps(ack,sort_keys=True),test_id):
        raise PlaybackTargetError()


class RedisPlaybackTarget:
    def __init__(self,cache,admin_id,test_id):
        self.cache,self.admin_id,self.test_id=cache,admin_id,test_id
        self.state_key,self.ack_key=keys(test_id)
        self.owner_key=f'voice:admin_playback:owner:{admin_id}'
        self.events=asyncio.Queue(maxsize=16)
        self.closed=False

    @classmethod
    async def open(cls,cache,*,admin_id):
        target=cls(cache,admin_id,str(uuid4()))
        if not await cache.set(target.owner_key,target.test_id,ex=TTL_SECONDS,nx=True):
            raise PlaybackTargetError('playback_test_busy')
        return target

    async def write_audio(self,event):
        if self.closed:raise PlaybackTargetError()
        await self.events.put(dict(type='audio',test_id=self.test_id,
            pcm_base64=base64.b64encode(event.payload).decode(),**event.public_metadata()))

    async def wait_played(self,**expected):
        if self.closed:raise PlaybackTargetError()
        await self.cache.setex(self.state_key,TTL_SECONDS,json.dumps(dict(admin_id=self.admin_id,expected=expected),sort_keys=True))
        await self.events.put(dict(type='playback_end',test_id=self.test_id,**expected))
        value=await self.cache.blpop(self.ack_key,timeout=45)
        if not value:raise PlaybackTargetError('playback_ack_timeout')
        try:return json.loads(value[1])
        except (ValueError,TypeError,IndexError):raise PlaybackTargetError() from None

    async def wait_stopped(self,**expected):
        if self.closed:raise PlaybackTargetError()
        await self.cache.setex(self.state_key,TTL_SECONDS,json.dumps(dict(admin_id=self.admin_id,expected=expected),sort_keys=True))
        await self.events.put(dict(type='playback_end',test_id=self.test_id,stop_after_playback=True,**expected))
        value=await self.cache.blpop(self.ack_key,timeout=45)
        if not value:raise PlaybackTargetError('playback_ack_timeout')
        try:return json.loads(value[1])
        except (ValueError,TypeError,IndexError):raise PlaybackTargetError() from None

    async def aclose(self):
        self.closed=True
        await self.cache.eval(CLOSE_TARGET,3,self.state_key,self.ack_key,self.owner_key,self.test_id)
