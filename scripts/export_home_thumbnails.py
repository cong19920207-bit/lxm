#!/usr/bin/env python3
"""Create proportional home-only thumbnails; keep every original image intact."""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'frontend/static/images/home-thumbnails/v2'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    images = [(p, 126) for p in sorted((ROOT / 'frontend/static/images/avatar').glob('*.png'))
              if p.name != 'bbbase.png']
    images += [(ROOT / 'frontend/static/images/Index/loader_avatar.jpg', 256),
               (ROOT / 'frontend/static/images/Index/in_diary/diary_1.png', 168)]
    records = []
    for source, width in images:
        source_bytes = source.read_bytes()
        with Image.open(source) as original:
            pixels = original.convert('RGBA')
            size = (width, round(original.height * width / original.width))
            resized = pixels.resize(size, Image.Resampling.LANCZOS)
            from io import BytesIO
            data = BytesIO()
            resized.save(data, 'WEBP', lossless=True, quality=100, method=6, exact=False)
            encoded = source_bytes if source.suffix == '.jpg' else data.getvalue()
            digest = hashlib.sha256(encoded).hexdigest()
            suffix = '.jpg' if source.suffix == '.jpg' else '.webp'
            filename = f'{source.stem}.{digest[:12]}{suffix}'
            target = OUTPUT / filename
            if target.exists() and target.read_bytes() != encoded:
                raise ValueError('Refusing to replace content at a versioned URL')
            target.write_bytes(encoded)
            records.append({'source':str(source.relative_to(ROOT)),
                            'source_sha256':hashlib.sha256(source_bytes).hexdigest(),
                            'source_bytes':len(source_bytes),'source_size':original.size,
                            'file':filename,'sha256':digest,'bytes':len(encoded),'size':size,
                            'url':'/static/images/home-thumbnails/v2/'+filename})
        assert source.read_bytes() == source_bytes
    (OUTPUT / 'manifest.json').write_text(json.dumps({'assets':records},ensure_ascii=False,indent=2)+'\n')
    for asset in records:
        print(asset['source'],asset['source_bytes'],'->',asset['bytes'],asset['size'],asset['url'])


if __name__ == '__main__':
    main()
