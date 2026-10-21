"""One anonymous catalog snapshot, finite Redis freshness and bounded origin work."""
import asyncio,json,math,time
from urllib.parse import urlsplit
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from sqlalchemy import and_,select
from sqlalchemy.orm import aliased
from backend.constants.bgm import AUDIO_OUTPUT_MAX_BYTES,AUDIO_MAX_SECONDS
from backend.models.bgm import BgmCatalog,BgmTrack,BgmAsset
from backend.redis_client import get_redis

CACHE_KEY='bgm:catalog:v1'
FLOOR_KEY='bgm:catalog:version-floor:v1'
TTL_SECONDS=60
REDIS_SECONDS=0.25
ORIGIN_SECONDS=1.5
REQUEST_SECONDS=3
LOCAL_SECONDS=1
ORIGIN_INTERVAL=2

PUT_SCRIPT='''
local floor = tonumber(redis.call('GET', KEYS[2]) or '0')
local version = tonumber(ARGV[2])
if version < floor then return 0 end
local old = redis.call('GET', KEYS[1])
if old then
  local ok, value = pcall(cjson.decode, old)
  if ok and type(value) == 'table' and type(value.data) == 'table' and tonumber(value.data.catalog_version) and tonumber(value.data.catalog_version) > version then return 0 end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
return 1
'''
INVALIDATE_SCRIPT='''
local floor = tonumber(redis.call('GET', KEYS[2]) or '0')
local version = tonumber(ARGV[1])
if version < floor then return 0 end
redis.call('SET', KEYS[2], ARGV[1])
local old = redis.call('GET', KEYS[1])
if old then
  local ok, value = pcall(cjson.decode, old)
  if not ok or type(value) ~= 'table' or type(value.data) ~= 'table' or not tonumber(value.data.catalog_version) or tonumber(value.data.catalog_version) < version then
    redis.call('DEL', KEYS[1])
  end
end
return 1
'''


class CatalogUnavailable(Exception):pass


class PublicTrack(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id:str
    name:str
    media_version:str
    audio_url:str
    duration_seconds:float=Field(gt=0,le=AUDIO_MAX_SECONDS,allow_inf_nan=False)
    cover_url:str|None
    cover_version:str|None

    @field_validator('audio_url','cover_url')
    @classmethod
    def https_only(cls,value):
        if value is None:return value
        url=urlsplit(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Invalid public URL')
        return value


class PublicCatalog(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    catalog_version:int=Field(ge=0)
    default_track_id:str|None
    tracks:list[PublicTrack]

    @model_validator(mode='after')
    def complete_snapshot(self):
        ids=[t.id for t in self.tracks]
        if len(ids)!=len(set(ids)) or (ids and self.default_track_id not in ids) or (not ids and self.default_track_id is not None):
            raise ValueError('Invalid catalog snapshot')
        return self


def decode_envelope(raw):
    try:
        envelope=json.loads(raw)
        created=envelope['created_at']
        if type(created) not in (int,float) or not math.isfinite(created) or not 0<=time.time()-created<TTL_SECONDS:return None
        data=PublicCatalog.model_validate(envelope['data']).model_dump()
        return dict(created_at=created,data=data)
    except (ValueError,KeyError,TypeError):return None


async def origin_snapshot(sessions):
    audio,cover=aliased(BgmAsset),aliased(BgmAsset)
    # All rows, versions, default and independent cover data come from one SQL
    # statement; no per-row media download, decoding or secondary ORM queries.
    statement=(select(BgmCatalog,BgmTrack,audio,cover).select_from(BgmCatalog)
        .outerjoin(BgmTrack,and_(BgmTrack.enabled.is_(True),BgmTrack.audio_state=='ready'))
        .outerjoin(audio,audio.id==BgmTrack.audio_asset_id)
        .outerjoin(cover,cover.id==BgmTrack.cover_asset_id)
        .where(BgmCatalog.id==1).order_by(BgmTrack.sort_position,BgmTrack.id))
    async with sessions() as db:
        rows=(await db.execute(statement)).all()
        if not rows:raise CatalogUnavailable()
        tracks=[]
        for head,track,a,c in rows:
            if not track:continue
            if not (a and a.track_id==track.id and a.kind=='audio' and a.state=='ready' and a.version==track.media_version
                    and a.cleanup_state=='not_requested' and a.retired_at is None and a.mime_type=='audio/mp4'
                    and a.sha256 and len(a.sha256)==64 and a.size_bytes==track.size_bytes
                    and track.size_bytes and 0<track.size_bytes<=AUDIO_OUTPUT_MAX_BYTES):raise CatalogUnavailable()
            cover_url=c.public_url if (c and c.track_id==track.id and c.kind=='cover' and c.state=='ready'
                and c.version==track.cover_version and c.cleanup_state=='not_requested' and c.retired_at is None) else None
            tracks.append(dict(id=track.id,name=track.name,media_version=track.media_version,audio_url=a.public_url,
                duration_seconds=track.duration_seconds,cover_url=cover_url,cover_version=track.cover_version))
        return PublicCatalog(catalog_version=rows[0][0].catalog_version,default_track_id=rows[0][0].default_track_id,tracks=tracks).model_dump()


class CatalogCache:
    def __init__(self):
        self.flight=None;self.local=None;self.local_until=0;self.next_origin=0;self.retry_after=0;self.generation=0

    async def get(self,sessions):
        if self.local and time.monotonic()<self.local_until and decode_envelope(json.dumps(self.local)):
            return self.local['data']
        if self.flight is None or self.flight.done():
            self.flight=asyncio.create_task(self._load(sessions))
            self.flight.add_done_callback(lambda task:task.exception() if not task.cancelled() else None)
        try:
            async with asyncio.timeout(REQUEST_SECONDS):return await asyncio.shield(self.flight)
        except Exception as exc:
            if isinstance(exc,CatalogUnavailable):raise
            raise CatalogUnavailable() from None

    def remember(self,envelope,generation):
        if generation==self.generation:
            self.local=envelope;self.local_until=time.monotonic()+LOCAL_SECONDS

    async def _load(self,sessions):
        generation=self.generation;redis=None;healthy=False
        try:
            async with asyncio.timeout(REDIS_SECONDS):
                redis=await get_redis();raw=await redis.get(CACHE_KEY)
            envelope=decode_envelope(raw) if raw else None
            healthy=not raw or envelope is not None
            if envelope:
                self.remember(envelope,generation);return envelope['data']
        except Exception:pass
        now=time.monotonic()
        if now<self.retry_after or (not healthy and now<self.next_origin):raise CatalogUnavailable()
        self.next_origin=now+ORIGIN_INTERVAL
        created=time.time()
        try:
            async with asyncio.timeout(ORIGIN_SECONDS):data=await origin_snapshot(sessions)
        except Exception:
            self.retry_after=time.monotonic()+ORIGIN_INTERVAL
            raise CatalogUnavailable() from None
        envelope=dict(created_at=created,data=data)
        if generation==self.generation:
            if redis is not None:
                try:
                    async with asyncio.timeout(REDIS_SECONDS):
                        await redis.eval(PUT_SCRIPT,2,CACHE_KEY,FLOOR_KEY,json.dumps(envelope,ensure_ascii=False),data['catalog_version'],max(1,int(TTL_SECONDS-(time.time()-created))))
                except Exception:pass
            self.remember(envelope,generation)
        return data

    async def invalidate(self,version):
        self.generation+=1;self.local=None;self.local_until=0
        try:
            async with asyncio.timeout(REDIS_SECONDS):
                redis=await get_redis()
                await redis.eval(INVALIDATE_SCRIPT,2,CACHE_KEY,FLOOR_KEY,version)
            return True
        except Exception:return False


cache=CatalogCache()


async def invalidate(version):
    # Runs strictly after durable business commit. Failure cannot undo that fact.
    return await cache.invalidate(version)
