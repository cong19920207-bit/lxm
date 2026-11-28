"""Resume local stages and the four registered assets for the selected feed media."""
from datetime import datetime

from PIL import Image
from sqlalchemy import select

from backend.models.feed_video import FeedVideoAsset, FeedVideoSelection, FeedVideoTask
from backend.services.feed_video_covers import NO_COVER, default_pair
from backend.services.feed_video_delivery import asset_key, put_file, verify_file
from backend.services.feed_video_master import digest, ensure_master, tracks
from backend.services.feed_video_media import InvalidMedia, blocking_work, probe
from backend.services.feed_video_preview import ensure_preview


async def asset_details(path, kind):
    if kind in ("video","preview"):
        data = await probe(path)
        video,audio = tracks(data)
        width,height = video["width"],video["height"]
        duration = round(float(data["format"]["duration"])*1000)
        mime = "video/mp4"
        stream = {"codec":video["codec_name"],"fps":video["avg_frame_rate"],
                  "audio":audio["codec_name"] if audio else None,"format":"mp4"}
    else:
        with Image.open(path) as image:
            image.load()
            if image.format!="WEBP" or image.n_frames!=1:
                raise InvalidMedia("封面文件校验失败")
            width,height = image.size
        duration,mime,stream = None,"image/webp",{"format":"webp"}
    return dict(width=width,height=height,size_bytes=path.stat().st_size,sha256=await blocking_work(digest,path),
                duration_ms=duration,mime_type=mime,stream_info=stream)


async def deliver(sessions, version, kind, variant, path):
    values = await asset_details(path,kind)
    key = asset_key(version,kind,variant)
    stmt = select(FeedVideoAsset).where(FeedVideoAsset.media_version==version,FeedVideoAsset.kind==kind,
                                        FeedVideoAsset.variant==variant)
    async with sessions.begin() as db:
        asset = await db.scalar(stmt.with_for_update())
        if asset is None:
            asset = FeedVideoAsset(media_version=version,kind=kind,variant=variant,object_key=key,
                                  unreferenced_at=datetime.utcnow() if variant!="default" else None,**values)
            db.add(asset)
        elif asset.sha256!=values["sha256"] or asset.object_key!=key:
            raise InvalidMedia("媒体内容或对象键与已登记版本不一致")
    meta = dict(version=version,kind=kind,key=key,**values)
    await blocking_work(put_file,path,meta)
    url = await blocking_work(verify_file,path,meta)
    async with sessions.begin() as db:
        asset = await db.scalar(stmt.with_for_update())
        asset.public_url,asset.verified_at = url,datetime.utcnow()


async def process(sessions, task_id):
    master = await ensure_master(sessions,task_id)
    preview = await ensure_preview(master)
    async with sessions() as db:
        task = await db.get(FeedVideoTask,task_id)
        selection = await db.get(FeedVideoSelection,task.edit_id)
        if not selection or selection.media_version != task.media_version:
            return "cancelled"
        variant, version = selection.cover_variant, task.media_version
    try:
        await default_pair(master)
    except InvalidMedia as exc:
        if str(exc)!=NO_COVER or variant=="default":
            raise
    for kind,path in (("video",master),("preview",preview),("cover_small",master.parent/variant/"cover_small.webp"),
                      ("cover_large",master.parent/variant/"cover_large.webp")):
        await deliver(sessions,version,kind,variant if kind.startswith("cover_") else "default",path)
    # Remote bytes and all current derivatives have been verified. A later cover edit
    # can recover this exact SHA from the immutable object if it needs the master.
    async with sessions.begin() as db:
        task = await db.get(FeedVideoTask,task_id,with_for_update=True)
        task.master_path = None
    master.unlink(missing_ok=True)
    return "ready"
