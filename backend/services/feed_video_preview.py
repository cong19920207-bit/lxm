"""Silent, independently playable timeline preview derived only from the normalized master."""
import math
from fractions import Fraction

from backend.services.feed_video_master import dimensions, faststart, publish_local, tracks
from backend.services.feed_video_media import InvalidMedia, media_command, probe, validate_source

MAX_PREVIEW_BYTES = 204800


async def check_preview(path, master):
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_PREVIEW_BYTES or not faststart(path):
        return False
    data = await validate_source(path)
    v, audio = tracks(data)
    original, _ = tracks(master)
    width, height = dimensions(original, 360, 640)
    duration = float(data["format"]["duration"])
    frame_time = 1 / float(Fraction(v["avg_frame_rate"]))
    expected_duration = min(float(master["format"]["duration"]), 5)
    return (audio is None and v["codec_name"] == "h264" and 0 < duration <= 5.001
            and abs(duration-expected_duration) <= max(.05, frame_time)
            and v["width"] <= width and v["height"] <= height
            and abs(v["width"] / v["height"] - width / height) <= 2/min(v["height"],height))


async def ensure_preview(master):
    data = await probe(master)
    final = master.with_name("preview.mp4")
    try:
        if await check_preview(final, data):
            return final
    except InvalidMedia:
        pass
    duration = min(5.0, float(data["format"]["duration"]))
    bitrate = min(560, math.floor((MAX_PREVIEW_BYTES-4096)*8/1000/duration))
    part = final.with_suffix(".partial")
    video, _ = tracks(data)
    try:
        for short, long, factor in [(360,640,.94), (288,512,.76), (180,320,.55)]:
            width,height = dimensions(video, short, long)
            rate = max(24,int(bitrate*factor))
            await media_command("ffmpeg","-nostdin","-v","error","-xerror","-y","-threads","2",
                "-protocol_whitelist","file","-i",str(master),"-t",str(duration),"-map","0:v:0",
                "-map_metadata","-1","-map_chapters","-1","-an","-vf",f"scale={width}:{height},setsar=1",
                "-c:v","libx264","-pix_fmt","yuv420p","-preset","fast","-threads","2",
                "-b:v",f"{rate}k","-maxrate",f"{rate}k","-bufsize",f"{rate}k",
                "-movflags","+faststart","-f","mp4",str(part))
            if await check_preview(part,data):
                publish_local(part,final)
                return final
    finally:
        part.unlink(missing_ok=True)
    raise InvalidMedia("短预览规格校验失败，请重试")
