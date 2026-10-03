#!/usr/bin/env python3
"""Export STEP-001 assets without changing decoded visible pixels or geometry."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, features
import PIL


ASSETS = (
    ("background", "background.webp", None),
    ("character", "character.webp", None),
    ("hair_front", "hair_front_physics.png", {
        "left_percent": 26.7292, "top_percent": 7.6464,
        "width_percent": 53.4584, "height_percent": 22.6139,
        "transform_origin_percent": [50, 10],
    }),
    ("hair_side", "hair_side_physics.png", {
        "left_percent": 72.8019, "top_percent": 11.8221,
        "width_percent": 25.7913, "height_percent": 27.7657,
        "transform_origin_percent": [15, 8],
    }),
    ("hair_back", "hair_back_physics.png", {
        "left_percent": 21.3365, "top_percent": 9.4902,
        "width_percent": 19.6952, "height_percent": 24.1323,
        "transform_origin_percent": [74, 9],
    }),
    ("blink", "blink_crop.png", {
        "left_percent": 35.990621, "top_percent": 19.143167,
        "width_percent": 30.832356, "height_percent": 7.266811,
    }),
    ("lamp", "lamp_glow.webp", None),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_once(path, data):
    """Never replace different bytes behind an existing versioned URL."""
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refusing to overwrite existing export: {path}")
    else:
        path.write_bytes(data)


def check_pixels(source, exported):
    if source.size != exported.size:
        raise ValueError("Export changed the image canvas")
    original, decoded = source.convert("RGBA"), exported.convert("RGBA")
    alpha = original.getchannel("A")
    if ImageChops.difference(alpha, decoded.getchannel("A")).getbbox():
        raise ValueError("Export changed alpha or transparent padding")
    mask = alpha.point(lambda value: 255 if value else 0).convert("RGB")
    rgb_diff = ImageChops.difference(original.convert("RGB"), decoded.convert("RGB"))
    if ImageChops.multiply(rgb_diff, mask).getbbox():
        raise ValueError("Export changed visible RGB pixels")
    for color in ("black", "white"):
        background = Image.new("RGBA", original.size, color)
        a = Image.alpha_composite(background, original).convert("RGB")
        b = Image.alpha_composite(background, decoded).convert("RGB")
        if ImageChops.difference(a, b).getbbox():
            raise ValueError(f"Export changed transparent edges on {color}")
    return {
        "alpha_equal": True,
        "visible_rgb_equal": True,
        "black_white_composites_equal": True,
        "alpha_sha256": sha256(alpha.tobytes()),
        "alpha_bbox": alpha.getbbox(),
    }


def export(source_dir, output_dir):
    if not features.check("webp"):
        raise RuntimeError("This Pillow installation cannot encode WebP")
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for role, name, placement in ASSETS:
        source_path = source_dir / name
        original_bytes = source_path.read_bytes()
        with Image.open(source_path) as original:
            original.load()
            if source_path.suffix == ".png":
                from io import BytesIO
                buffer = BytesIO()
                original.save(buffer, "WEBP", lossless=True, quality=100,
                              method=6, exact=False)
                data = buffer.getvalue()
                parameters = {"lossless": True, "quality": 100, "method": 6,
                              "exact": False}
                # exact=False may clear RGB under alpha=0 only; verify all visible
                # pixels and alpha, rather than claiming hidden RGB is identical.
            else:
                data = original_bytes
                parameters = {"operation": "copy_original_bytes"}
            output_name = f"{Path(name).stem}.{sha256(data)[:12]}.webp"
            output_path = output_dir / output_name
            write_once(output_path, data)
            with Image.open(output_path) as decoded:
                decoded.load()
                checks = check_pixels(original, decoded)
                records.append({
                    "role": role,
                    "source": str(source_path.resolve()),
                    "source_sha256": sha256(original_bytes),
                    "source_bytes": len(original_bytes),
                    "source_format": original.format,
                    "source_mode": original.mode,
                    "file": output_name,
                    "url": f"/static/images/home-scene/v4/{output_name}",
                    "sha256": sha256(data),
                    "bytes": len(data),
                    "size": list(original.size),
                    "mode": decoded.mode,
                    "parameters": parameters,
                    "placement_in_character_canvas": placement,
                    "verification": checks,
                })
        if source_path.read_bytes() != original_bytes:
            raise ValueError(f"Source changed during export: {source_path}")
    source_total = sum(row["source_bytes"] for row in records)
    output_total = sum(row["bytes"] for row in records)
    core_total = sum(row["bytes"] for row in records[:2])
    manifest = {
        "version": "v4",
        "canvas": [853, 1844],
        "geometry": "Original canvas, padding, placement and rotation anchors preserved",
        "tools": {"pillow": PIL.__version__, "libwebp": features.version("webp")},
        "assets": records,
        "budget": {
            "source_bytes": source_total,
            "export_bytes": output_total,
            "saved_bytes": source_total - output_total,
            "core_bytes": core_total,
            "core_target_bytes": 350 * 1024,
            "core_target_met": core_total <= 350 * 1024,
            "whole_target_range_bytes": [800 * 1024, 900 * 1024],
            "whole_upper_target_met": output_total <= 900 * 1024,
        },
        "quality_scope": "Pixel verification only; browser and target-device evidence tracked in steps-verified.md section 9",
    }
    write_once(output_dir / "manifest.json",
               (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(manifest["budget"], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "frontend/static/images/home-scene/v4")
    args = parser.parse_args()
    export(args.source, args.output)


if __name__ == "__main__":
    main()
