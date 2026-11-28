"""Generate a matched pair of WebP covers from one decoded, oriented frame."""
import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import warnings

from PIL import Image, ImageFilter, ImageOps, ImageStat
from backend.services.feed_video_master import publish_local
from backend.services.feed_video_media import InvalidMedia, media_command

NO_COVER = "视频开头未找到合适封面，请选择一张图片"
MAX_COVER_BYTES = 5 * 1024**2


def decode_cover(blob):
    if not 0 < len(blob) <= MAX_COVER_BYTES:
        raise InvalidMedia("封面不能为空，且不能超过 5 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(blob)) as image:
                if image.format not in {"JPEG","PNG","WEBP"} or getattr(image,"n_frames",1) != 1:
                    raise InvalidMedia("请选择一张静态 JPEG、PNG 或 WebP 图片")
                if max(image.size) > 4096:
                    raise InvalidMedia("封面最长边不能超过 4096 像素")
                image.verify()
            with Image.open(BytesIO(blob)) as image:
                return ImageOps.exif_transpose(image).convert("RGB")
    except InvalidMedia:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise InvalidMedia("封面文件损坏或尺寸无效") from None


def make_pair(image, directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    small = ImageOps.fit(image,(240,180),method=Image.Resampling.LANCZOS)
    large = image
    if image.width > 720:
        large = image.resize((720,max(1,round(image.height*720/image.width))),Image.Resampling.LANCZOS)
    for name, output in (("cover_small",small),("cover_large",large)):
        final = directory/(name+".webp")
        part = final.with_suffix(".partial")
        output.save(part,format="WEBP",quality=83,method=4)
        with Image.open(part) as check:
            check.load()
            if check.format != "WEBP" or check.size != output.size or check.n_frames != 1:
                raise InvalidMedia("封面生成失败，请重试")
        publish_local(part,final)
    return directory


def clear_frame(path):
    with Image.open(path) as image:
        thumb = image.convert("L")
        thumb.thumbnail((160,160))
        histogram = thumb.histogram()
        if sum(histogram[28:]) < .10*sum(histogram):
            return None
        # Ignore the border added by FIND_EDGES so a flat grey frame cannot pass.
        edges = thumb.filter(ImageFilter.FIND_EDGES)
        if min(edges.size)>2:
            edges = edges.crop((1,1,edges.width-1,edges.height-1))
        if ImageStat.Stat(edges).mean[0] < 4:
            return None
        return image.convert("RGB")


async def default_pair(master):
    directory = master.parent/"default"
    if all((directory/(kind+".webp")).is_file() for kind in ("cover_small","cover_large")):
        return directory
    with tempfile.TemporaryDirectory(dir=master.parent) as tmp:
        # Keep the first source frame even for sub-second movies. Work on the verified SDR master.
        pattern = Path(tmp)/"%03d.png"
        await media_command("ffmpeg","-nostdin","-v","error","-threads","2","-protocol_whitelist","file",
            "-i",str(master),"-an","-t","3","-vf",
            r"select=isnan(prev_selected_t)+gte(t-prev_selected_t\,0.24),scale='min(720,iw)':-1",
            "-fps_mode","vfr","-threads","1",str(pattern))
        candidates = []
        for path in sorted(Path(tmp).glob("*.png")):
            frame = await asyncio.to_thread(clear_frame,path)
            if frame is not None:
                luminance = ImageStat.Stat(frame.convert("L")).mean[0]
                candidates.append((path,luminance))
        if candidates:
            # During a fade the first outlined face can still look almost black.
            # Relative exposure also preserves legitimately dark scenes.
            minimum = .72 * max(level for _,level in candidates)
            path = next(path for path,level in candidates if level >= minimum)
            with Image.open(path) as frame:
                return await asyncio.to_thread(make_pair,frame.convert("RGB"),directory)
    raise InvalidMedia(NO_COVER)
