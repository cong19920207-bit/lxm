"""Private feed video storage and decoder validation."""
import asyncio
import fcntl
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from pathlib import Path


MAX_BYTES = 200 * 1024**2
MAX_SECONDS = 180
decoder_lock_fd = ContextVar("feed_video_decoder_lock", default=None)


class InvalidMedia(ValueError):
    pass


class UnusableSource(InvalidMedia):
    """The operator must select a new source before retrying this task."""


async def blocking_work(function, *args):
    # Cancelling an asyncio waiter does not stop a running executor thread.
    # Keep the caller's ownership until the underlying file/remote operation ends.
    worker = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await asyncio.gather(worker, return_exceptions=True)
        raise


def runtime_root():
    root = Path(os.environ.get("FEED_VIDEO_RUNTIME_ROOT", "/var/lib/lxm-feed-video-runtime"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


@contextmanager
def try_lock(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield None
        else:
            yield fd
    finally:
        # close, not LOCK_UN: a surviving decoder inherits this open description.
        os.close(fd)


async def media_command(*command, timeout=180, capture=False):
    fd = decoder_lock_fd.get()
    proc = await asyncio.create_subprocess_exec(
        *command, pass_fds=(() if fd is None else (fd,)), stdin=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL)
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except BaseException:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise
    if proc.returncode:
        raise InvalidMedia("无法解码媒体，请检查文件是否损坏")
    return stdout


async def probe(path):
    data = await media_command("ffprobe", "-v", "error", "-protocol_whitelist", "file",
                               "-show_entries", "format=format_name,duration,size:format_tags=major_brand:"
                               "stream=index,codec_type,codec_name,width,height,duration,avg_frame_rate,"
                               "pix_fmt,color_space,color_primaries,color_transfer,bit_rate,sample_aspect_ratio,r_frame_rate:stream_side_data:"
                               "stream_disposition=attached_pic", "-of", "json", str(path), timeout=30, capture=True)
    return json.loads(data)


async def validate_source(path):
    data = await probe(path)
    fmt = data.get("format", {})
    if "mov" not in fmt.get("format_name", "").split(","):
        raise InvalidMedia("仅支持 MP4 或 MOV 视频")
    # The mov demuxer also accepts audio-only and 3GP family containers.
    brand = fmt.get("tags", {}).get("major_brand", "").strip().lower()
    if brand.startswith(("3g", "m4a", "m4b", "mj2", "heic", "avif")):
        raise InvalidMedia("仅支持 MP4 或 MOV 视频")
    video = next((s for s in data.get("streams", []) if s["codec_type"] == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if not video:
        raise InvalidMedia("文件没有可播放的视频轨")
    try:
        duration = Decimal(fmt["duration"])
        if not duration.is_finite() or duration <= 0:
            raise InvalidOperation
    except (KeyError, InvalidOperation):
        raise InvalidMedia("视频缺少有效的播放时长") from None
    if duration > MAX_SECONDS:
        raise InvalidMedia("视频时长超过 180 秒")
    await media_command("ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file",
                        "-threads", "2", "-i", str(path), "-map", f"0:{video['index']}",
                        "-map", "0:a:0?", "-f", "null", "-")
    return data
