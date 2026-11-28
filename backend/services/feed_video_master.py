"""Normalize feed masters and commit durable recovery evidence before removing the source."""
import asyncio
import hashlib
import os
import struct
from datetime import datetime
from fractions import Fraction

from sqlalchemy import select
from backend.models.feed_video import FeedVideoAsset, FeedVideoTask
from backend.services.feed_video_media import InvalidMedia, UnusableSource, blocking_work, media_command, probe, runtime_root, validate_source

HDR_ERROR = "无法可靠转换此 HDR 视频，请导出 SDR 版本后重新上传"
MISSING = "没有可恢复的成片或原片，请重新选择视频文件"


def tracks(data):
    streams = data["streams"]
    video = next(s for s in streams if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic"))
    return video, next((s for s in streams if s["codec_type"] == "audio"), None)


def fraction(value, default):
    try:
        return Fraction(value.replace(":", "/"))
    except (AttributeError, ValueError, ZeroDivisionError):
        return Fraction(default)


def dimensions(video, short, long):
    width, height = video["width"], video["height"]
    aspect = fraction(video.get("sample_aspect_ratio"), 1)
    # Fit the display aspect inside the original pixel budget as well as the output box.
    width, height = min(width, width * aspect), min(height, height / aspect)
    rotation = next((s["rotation"] for s in video.get("side_data_list", []) if "rotation" in s), 0)
    if rotation % 180 == 90:
        width, height = height, width
    max_w, max_h = (long, short) if width >= height else (short, long)
    scale = min(1, max_w / width, max_h / height)
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def faststart(path):
    with path.open("rb") as stream:
        end = os.fstat(stream.fileno()).st_size
        pos = 0
        while pos + 8 <= end:
            size, kind = struct.unpack(">I4s", stream.read(8))
            header = 8
            if size == 1:
                size, = struct.unpack(">Q", stream.read(8))
                header = 16
            if kind == b"moov":
                return True
            if kind == b"mdat" or size < header or pos + size > end:
                return False
            pos += size
            stream.seek(pos)
    return False


def publish_local(part, target):
    with part.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(part, target)
    directory = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


async def encode(source, part, data):
    v, audio = tracks(data)
    sides = v.get("side_data_list", [])
    transfer = v.get("color_transfer")
    if any("dovi" in str(s.get("side_data_type", "")).lower() or
           "dolby vision" in str(s.get("side_data_type", "")).lower() for s in sides):
        raise UnusableSource(HDR_ERROR)
    hdr = transfer in ("smpte2084", "arib-std-b67")
    if (hdr and (v.get("color_primaries") != "bt2020" or v.get("color_space") != "bt2020nc")
        or not hdr and (v.get("color_space") in ("bt2020nc","bt2020c") or v.get("color_primaries") == "bt2020" or any("Mastering display" in str(s) for s in sides))):
        raise UnusableSource(HDR_ERROR)
    width, height = dimensions(v, 720, 1280)
    rate = fraction(v.get("avg_frame_rate"), 0)
    peak_rate = fraction(v.get("r_frame_rate"), rate)
    copy = (not hdr and v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p"
            and (v["width"], v["height"]) == (width, height) and 0 < rate <= 30 and peak_rate <= 30
            and not any(s.get("rotation", 0) for s in sides) and fraction(v.get("sample_aspect_ratio"), 1) == 1
            and int(v.get("bit_rate") or 0) <= 2_000_000)
    args = ["-map", f"0:{v['index']}", "-map", "0:a:0?", "-map_metadata", "-1", "-map_chapters", "-1"]
    if copy:
        args += ["-c:v", "copy"]
    else:
        filters = []
        if hdr:
            filters += ["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709",
                        "tonemap=tonemap=mobius:desat=2", "zscale=t=bt709:m=bt709:r=tv"]
        filters += [f"scale={width}:{height}", "setsar=1", "format=yuv420p"]
        args += ["-vf", ",".join(filters), "-c:v", "libx264", "-threads", "2", "-preset", "fast",
                 "-b:v", "1500k", "-maxrate", "2000k", "-bufsize", "3000k", "-fpsmax", "30"]
        if hdr:
            args += ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                     "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1"]
    if audio:
        args += ["-c:a", "copy" if audio["codec_name"] == "aac" else "aac"]
    await media_command("ffmpeg", "-nostdin", "-v", "error", "-xerror", "-y", "-filter_threads", "2",
                        "-protocol_whitelist", "file", "-threads", "2", "-i", str(source), *args,
                        "-movflags", "+faststart", "-f", "mp4", str(part), timeout=900)
    out = await validate_source(part)
    video, sound = tracks(out)
    if ((video["width"], video["height"]) != (width, height) or video["codec_name"] != "h264" or
        bool(sound) != bool(audio) or sound and sound["codec_name"] != "aac" or not faststart(part)
        or hdr and video.get("color_transfer") != "bt709" or
        abs(float(out["format"]["duration"]) - float(data["format"]["duration"])) > 0.25):
        raise InvalidMedia("成片规格校验失败，请重新选择视频文件")
    return out


async def ensure_master(sessions, task_id):
    root = runtime_root()
    async with sessions() as db:
        task = await db.get(FeedVideoTask, task_id)
        base = root / task.media_version
        source, master = base / "source", base / "video.mp4"
        saved_hash = task.master_sha256 if task.master_verified_at else None
        remote = None
        if saved_hash and not source.is_file() and not master.is_file():
            remote = await db.scalar(select(FeedVideoAsset).where(
                FeedVideoAsset.media_version==task.media_version,FeedVideoAsset.kind=="video",
                FeedVideoAsset.verified_at.is_not(None),FeedVideoAsset.sha256==saved_hash))
    if remote and remote.public_url:
        from backend.services.feed_video_delivery import cdn_url, fetch_verified_master
        part = base / "restore.partial"
        try:
            if remote.public_url != cdn_url(remote.object_key):
                raise InvalidMedia("成片地址与所属版本不符")
            await blocking_work(fetch_verified_master,remote.public_url,part,remote.size_bytes,saved_hash)
            publish_local(part,master)
        finally:
            part.unlink(missing_ok=True)
    if not (saved_hash and master.is_file() and await asyncio.to_thread(digest, master) == saved_hash):
        if not source.is_file():
            raise InvalidMedia(MISSING)
        try:
            data = await probe(source)
        except InvalidMedia as exc:
            raise UnusableSource(str(exc)) from None
        part = base / "master.partial"
        try:
            await encode(source, part, data)
            checksum = await asyncio.to_thread(digest, part)
            publish_local(part, master)
            async with sessions.begin() as db:
                task = await db.get(FeedVideoTask, task_id, with_for_update=True)
                task.master_path = str(master.relative_to(root))
                task.master_sha256, task.master_verified_at = checksum, datetime.utcnow()
        finally:
            part.unlink(missing_ok=True)
    source.unlink(missing_ok=True)
    async with sessions.begin() as db:
        task = await db.get(FeedVideoTask, task_id, with_for_update=True)
        task.source_path = None
        task.master_path = str(master.relative_to(root))
    return master
