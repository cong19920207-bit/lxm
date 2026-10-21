"""Bounded static cover decoder, executed only inside the isolated BGM worker."""
import hashlib
from pathlib import Path
import time
import warnings
from backend.services.bgm_media import MediaError
from backend.constants.bgm import COVER_SOURCE_MAX_BYTES,COVER_MAX_EDGE,COVER_OUTPUT_EDGE

FORMATS={'.jpg':('JPEG','image/jpeg'),'.jpeg':('JPEG','image/jpeg'),'.png':('PNG','image/png'),'.webp':('WEBP','image/webp')}


def validate_cover_type(extension,mime):
    if extension not in FORMATS or mime.lower() not in {FORMATS[extension][1],'application/octet-stream',''}:
        raise MediaError('invalid_cover_type')


def convert_cover(source:Path,output:Path,extension,mime,deadline):
    from PIL import Image,ImageOps,UnidentifiedImageError
    validate_cover_type(extension,mime)
    if not 0<source.stat().st_size<=COVER_SOURCE_MAX_BYTES:raise MediaError('cover_size_limit')
    if time.monotonic()>=deadline:raise MediaError('processing_timeout')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(source) as probe:
                if probe.format!=FORMATS[extension][0]:raise MediaError('invalid_cover_type')
                if min(probe.size)<=0 or max(probe.size)>COVER_MAX_EDGE:raise MediaError('cover_pixel_limit')
                if getattr(probe,'n_frames',1)!=1 or getattr(probe,'is_animated',False):raise MediaError('animated_cover')
                probe.verify()
            with Image.open(source) as decoded:
                decoded.load()
                oriented=ImageOps.exif_transpose(decoded)
                mode='RGBA' if 'A' in oriented.getbands() or 'transparency' in oriented.info else 'RGB'
                pixels=oriented.convert(mode)
                normalized=ImageOps.fit(pixels,(COVER_OUTPUT_EDGE,COVER_OUTPUT_EDGE),method=Image.Resampling.LANCZOS,centering=(.5,.5))
                normalized.info.clear()
                for quality in [85,75,65]:
                    if time.monotonic()>=deadline:raise MediaError('processing_timeout')
                    normalized.save(output,format='WEBP',quality=quality,method=4)
                    if output.stat().st_size<=200*1024:break
            with Image.open(output) as verified:
                verified.load()
                if verified.format!='WEBP' or verified.size!=(COVER_OUTPUT_EDGE,COVER_OUTPUT_EDGE) or getattr(verified,'n_frames',1)!=1:
                    raise MediaError('invalid_cover_output')
    except MediaError:
        raise
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise MediaError('invalid_cover') from None
    blob=output.read_bytes()
    return dict(size_bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),mime_type='image/webp')
