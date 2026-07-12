#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生活流图片链路冒烟测试（LiblibAI → 下载 → OSS → CDN 拉取）

不修改业务代码；读取项目根 .env，逐步验证配置与外部服务连通性。
用法：
  python scripts/smoke_liblib_oss_path.py           # 全量
  python scripts/smoke_liblib_oss_path.py --skip-liblib  # 仅 OSS + 参考图
  python scripts/smoke_liblib_oss_path.py --img-type daily  # text2img，不依赖参考图
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# 延迟导入 backend 模块（依赖 dotenv 已加载）
from backend.config import (  # noqa: E402
    get_feed_image_reference_public_url,
    get_liblib_access_key,
    get_liblib_base_url,
    get_liblib_secret_key,
    get_oss_access_key_id,
    get_oss_access_key_secret,
    get_oss_bucket,
    get_oss_cdn_domain,
    get_oss_endpoint,
)
from backend.utils.liblib_client import liblib_client  # noqa: E402

_TEXT2IMG_URI = "/api/generate/webui/text2img"
_IMG2IMG_URI = "/api/generate/webui/img2img"
_STATUS_URI = "/api/generate/webui/status"
_SMOKE_OSS_KEY = "lxm/smoke-test/liblib-oss-path.webp"

# 与业务默认一致（TB-LF-001）；img2img UUID 可从环境变量覆盖以便联调
_DEFAULT_TEXT2IMG_TEMPLATE_UUID = "6f7c4652458d4802969f8d089cf5b91f"
_DEFAULT_IMG2IMG_TEMPLATE_UUID = os.getenv("LIBLIB_IMG2IMG_TEMPLATE_UUID", "").strip()


def _official_payload(
    prompt: str,
    negative: str,
    *,
    template_uuid: str,
    source_image: str | None = None,
    strength: float | None = None,
) -> dict:
    """与 feed_image_service._build_payload 对齐的官方 WebUI 结构。"""
    generate_params: dict = {
        "prompt": prompt,
        "negativePrompt": negative,
        "steps": 20,
        "width": 768,
        "height": 1024,
        "imgCount": 1,
        "seed": -1,
        "restoreFaces": 0,
    }
    if source_image is not None:
        generate_params["sourceImage"] = source_image
        generate_params["strength"] = 0.6 if strength is None else strength
        # 与 feed_image_service 图生图分支对齐（Liblib 参数完整度校验必填）
        generate_params["resizedWidth"] = 768
        generate_params["resizedHeight"] = 1024
    return {
        "templateUuid": template_uuid,
        "generateParams": generate_params,
    }


class StepResult:
    def __init__(self, name: str, ok: bool, detail: str = ""):
        self.name = name
        self.ok = ok
        self.detail = detail


def _mask(s: str, show: int = 4) -> str:
    if not s:
        return "(空)"
    if len(s) <= show * 2:
        return "*" * len(s)
    return f"{s[:show]}...{s[-show:]}"


def check_env_config() -> list[StepResult]:
    """检查 .env 中生活流图片相关配置是否齐全、格式是否合理。"""
    results: list[StepResult] = []

    pairs = [
        ("LIBLIB_ACCESS_KEY", get_liblib_access_key()),
        ("LIBLIB_SECRET_KEY", get_liblib_secret_key()),
        ("LIBLIB_BASE_URL", get_liblib_base_url()),
        ("OSS_ACCESS_KEY_ID", get_oss_access_key_id()),
        ("OSS_ACCESS_KEY_SECRET", get_oss_access_key_secret()),
        ("OSS_ENDPOINT", get_oss_endpoint()),
        ("OSS_BUCKET", get_oss_bucket()),
        ("OSS_CDN_DOMAIN", get_oss_cdn_domain()),
        ("FEED_IMAGE_REFERENCE_PUBLIC_URL", get_feed_image_reference_public_url()),
    ]
    for key, val in pairs:
        ok = bool(val and val.strip())
        results.append(StepResult(f"env.{key}", ok, _mask(val) if ok else "未配置"))

    ref = get_feed_image_reference_public_url()
    if ref:
        if ref.startswith(("http://", "https://")):
            results.append(StepResult("ref_url.scheme", True, "HTTPS/HTTP 公网 URL"))
        else:
            results.append(StepResult(
                "ref_url.scheme", False,
                f"当前为 {ref[:30]}... — LiblibAI 需要 https:// 公网 URL，oss:// 协议不可用",
            ))

    cdn = get_oss_cdn_domain()
    if cdn and (cdn.startswith("http://") or cdn.startswith("https://")):
        results.append(StepResult(
            "cdn_domain.format", False,
            "OSS_CDN_DOMAIN 应不含协议，仅域名（代码会拼 https://{cdn}/...）",
        ))
    elif cdn:
        results.append(StepResult("cdn_domain.format", True, cdn))

    return results


def check_reference_image_reachable() -> StepResult:
    """HTTP GET 参考图 URL，验证 LiblibAI 能否拉取。"""
    import httpx

    ref = get_feed_image_reference_public_url()
    if not ref or not ref.startswith(("http://", "https://")):
        return StepResult("ref_url.reachable", False, "跳过：参考图 URL 非 HTTP(S)")

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(ref)
            ct = resp.headers.get("content-type", "")
            ok = resp.status_code == 200 and resp.content[:8] != b"<html"
            size = len(resp.content)
            detail = f"status={resp.status_code} content-type={ct} size={size}B"
            if not ok:
                detail += "（非 200 或返回 HTML 错误页）"
            return StepResult("ref_url.reachable", ok, detail)
    except Exception as e:
        return StepResult("ref_url.reachable", False, str(e))


def check_oss_rw() -> tuple[StepResult, StepResult, bytes | None]:
    """OSS 写入测试对象并读回。"""
    import oss2

    endpoint = get_oss_endpoint()
    bucket_name = get_oss_bucket()
    if not all([get_oss_access_key_id(), get_oss_access_key_secret(), endpoint, bucket_name]):
        r = StepResult("oss.put", False, "OSS 凭证或桶未配置")
        return r, StepResult("oss.get", False, "跳过"), None

    # 最小 WebP 头（1x1 像素占位，仅验证读写）
    webp_stub = (
        b"RIFF$\x00\x00\x00WEBPVP8 \x18\x00\x00\x00\xd0\x01\x00\x9d\x01*\x01\x01"
        b">\xd4B\xa0\x88\x0b\xb0\x00\xfe\x05\x04\x00\x00\x00"
    )
    try:
        auth = oss2.Auth(get_oss_access_key_id(), get_oss_access_key_secret())
        bucket = oss2.Bucket(auth, endpoint, bucket_name)
        bucket.put_object(_SMOKE_OSS_KEY, webp_stub)
        put_ok = StepResult("oss.put", True, f"oss://{bucket_name}/{_SMOKE_OSS_KEY}")
    except Exception as e:
        return StepResult("oss.put", False, str(e)), StepResult("oss.get", False, "跳过"), None

    try:
        result = bucket.get_object(_SMOKE_OSS_KEY)
        data = result.read()
        get_ok = StepResult("oss.get", data == webp_stub, f"读回 {len(data)}B")
        return put_ok, get_ok, webp_stub
    except Exception as e:
        return put_ok, StepResult("oss.get", False, str(e)), webp_stub


def check_cdn_fetch() -> StepResult:
    """通过 CDN 域名拉取冒烟测试对象。"""
    import httpx

    cdn = get_oss_cdn_domain()
    if not cdn:
        return StepResult("cdn.fetch", False, "OSS_CDN_DOMAIN 未配置")

    url = f"https://{cdn.rstrip('/')}/{_SMOKE_OSS_KEY}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            ok = resp.status_code == 200
            detail = f"GET {url} → {resp.status_code} size={len(resp.content)}B"
            if resp.status_code == 403:
                detail += "（Bucket 私有且 CDN 未开回源鉴权时可能 403，属预期需运维配置）"
            return StepResult("cdn.fetch", ok, detail)
    except Exception as e:
        return StepResult("cdn.fetch", False, str(e))


def check_clock_skew() -> StepResult:
    """检测本机时钟与阿里云 OSS 服务器偏差（偏差 >15min 会导致 OSS 签名失败）。"""
    import httpx

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.head(f"https://{get_oss_bucket()}.{get_oss_endpoint()}/")
        server_date = resp.headers.get("date", "")
        if not server_date:
            return StepResult("clock.skew", True, "无法读取 OSS Date 头，跳过")
        from email.utils import parsedate_to_datetime
        import datetime

        server_utc = parsedate_to_datetime(server_date)
        local_utc = datetime.datetime.now(datetime.timezone.utc)
        skew_sec = abs((server_utc - local_utc).total_seconds())
        ok = skew_sec <= 900  # 15 分钟
        detail = f"本地 UTC 与 OSS 差 {int(skew_sec)}s（阈值 900s）"
        if not ok:
            detail += " — 请同步 macOS 系统时间（系统设置 → 日期与时间 → 自动设置）"
        return StepResult("clock.skew", ok, detail)
    except Exception as e:
        return StepResult("clock.skew", False, str(e))


async def check_liblib_credentials() -> StepResult:
    """用官方 templateUuid+generateParams 结构验证 AK/SK 与签名（非业务 payload）。"""
    payload = {
        "templateUuid": "6f7c4652458d4802969f8d089cf5b91f",
        "generateParams": {
            "prompt": "a cozy cafe interior, warm light, photorealistic",
            "negativePrompt": "blurry, low quality",
            "steps": 20,
            "width": 768,
            "height": 768,
            "imgCount": 1,
            "seed": -1,
            "restoreFaces": 0,
        },
    }
    try:
        task_id = await liblib_client.submit_task(_TEXT2IMG_URI, payload)
        image_url = await liblib_client.poll_task(_STATUS_URI, task_id, timeout_sec=180.0)
        if image_url:
            return StepResult(
                "liblib.credentials",
                True,
                f"AK/SK 有效 task={task_id[:8]}...（使用官方 template 结构）",
            )
        return StepResult("liblib.credentials", False, f"任务超时 task={task_id}")
    except Exception as e:
        return StepResult("liblib.credentials", False, str(e))
    finally:
        await liblib_client.close()


async def check_liblib_business_payload() -> StepResult:
    """模拟 feed_image_service 当前发出的官方 payload（templateUuid + generateParams）。"""
    payload = _official_payload(
        "a cozy cafe interior, warm light, photorealistic",
        "blurry, low quality",
        template_uuid=_DEFAULT_TEXT2IMG_TEMPLATE_UUID,
    )
    try:
        task_id = await liblib_client.submit_task(_TEXT2IMG_URI, payload)
        image_url = await liblib_client.poll_task(_STATUS_URI, task_id, timeout_sec=180.0)
        if image_url:
            return StepResult("liblib.business_payload", True, f"task={task_id[:8]}...")
        return StepResult("liblib.business_payload", False, f"任务超时 task={task_id}")
    except Exception as e:
        return StepResult(
            "liblib.business_payload",
            False,
            f"{e}（若仍提示参数完整度校验，检查 templateUuid/generateParams 是否与控制台一致）",
        )
    finally:
        await liblib_client.close()


async def check_liblib_img2img() -> StepResult:
    """IMG1 图生图（依赖 FEED_IMAGE_REFERENCE_PUBLIC_URL 公网可达 + img2img templateUuid）。"""
    ref = get_feed_image_reference_public_url()
    if not ref.startswith(("http://", "https://")):
        return StepResult("liblib.img2img", False, "跳过：参考图 URL 非 HTTP(S)")

    img2img_uuid = _DEFAULT_IMG2IMG_TEMPLATE_UUID
    if not img2img_uuid:
        return StepResult(
            "liblib.img2img",
            False,
            "跳过：未设置 LIBLIB_IMG2IMG_TEMPLATE_UUID（或后台 liblib_img2img_template_uuid）",
        )

    payload = _official_payload(
        "young woman selfie, natural smile, soft lighting",
        "blurry, distorted",
        template_uuid=img2img_uuid,
        source_image=ref,
    )
    try:
        task_id = await liblib_client.submit_task(_IMG2IMG_URI, payload)
        image_url = await liblib_client.poll_task(_STATUS_URI, task_id, timeout_sec=180.0)
        if image_url:
            return StepResult("liblib.img2img", True, f"task={task_id[:8]}... url={image_url[:60]}...")
        return StepResult("liblib.img2img", False, f"任务超时或失败 task={task_id}")
    except Exception as e:
        return StepResult("liblib.img2img", False, str(e))
    finally:
        await liblib_client.close()


async def check_full_path(img_type: str) -> list[StepResult]:
    """完整链路：LiblibAI 出图 → 下载 → WebP → OSS → CDN URL 可访问。"""
    import httpx
    import oss2
    from PIL import Image
    import io

    results: list[StepResult] = []
    post_id = int(time.time()) % 100000
    oss_key = f"lxm/posts/{post_id}/01.webp"

    if img_type == "selfie":
        ref = get_feed_image_reference_public_url()
        if not ref.startswith(("http://", "https://")):
            results.append(StepResult("full_path", False, "selfie 需要有效 HTTPS 参考图 URL"))
            return results
        img2img_uuid = _DEFAULT_IMG2IMG_TEMPLATE_UUID
        if not img2img_uuid:
            results.append(StepResult(
                "full_path", False,
                "selfie 需要 LIBLIB_IMG2IMG_TEMPLATE_UUID（图生图 templateUuid）",
            ))
            return results
        uri, payload = _IMG2IMG_URI, _official_payload(
            "young woman selfie, cafe background, natural light",
            "blurry",
            template_uuid=img2img_uuid,
            source_image=ref,
        )
    else:
        uri, payload = _TEXT2IMG_URI, _official_payload(
            "sunset over city skyline, cinematic",
            "blurry",
            template_uuid=_DEFAULT_TEXT2IMG_TEMPLATE_UUID,
        )

    try:
        task_id = await liblib_client.submit_task(uri, payload)
        liblib_url = await liblib_client.poll_task(_STATUS_URI, task_id, timeout_sec=180.0)
        if not liblib_url:
            results.append(StepResult("full_path.liblib", False, "LiblibAI 未返回图片"))
            return results
        results.append(StepResult("full_path.liblib", True, liblib_url[:80] + "..."))

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(liblib_url)
            resp.raise_for_status()
            jpg_bytes = resp.content
        results.append(StepResult("full_path.download", True, f"{len(jpg_bytes)}B"))

        with Image.open(io.BytesIO(jpg_bytes)) as im:
            buf = io.BytesIO()
            im.save(buf, format="WEBP", quality=85)
            webp_bytes = buf.getvalue()
        results.append(StepResult("full_path.webp", True, f"{len(webp_bytes)}B"))

        auth = oss2.Auth(get_oss_access_key_id(), get_oss_access_key_secret())
        bucket = oss2.Bucket(auth, get_oss_endpoint(), get_oss_bucket())
        bucket.put_object(oss_key, webp_bytes)
        results.append(StepResult("full_path.oss_put", True, oss_key))

        cdn_url = f"https://{get_oss_cdn_domain().rstrip('/')}/{oss_key}"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            cdn_resp = await client.get(cdn_url)
        cdn_ok = cdn_resp.status_code == 200 and len(cdn_resp.content) > 100
        detail = f"{cdn_url} → {cdn_resp.status_code} size={len(cdn_resp.content)}B"
        if cdn_resp.status_code == 403:
            detail += "（OSS 私有桶需 CDN 回源鉴权；OSS 直读仍可用）"
            # 回退：OSS SDK 验证对象存在
            obj = bucket.get_object(oss_key)
            oss_ok = len(obj.read()) > 100
            results.append(StepResult("full_path.cdn_fetch", False, detail))
            results.append(StepResult(
                "full_path.oss_verify_fallback", oss_ok,
                f"OSS SDK 读回 {oss_key}" if oss_ok else "OSS 读回失败",
            ))
        else:
            results.append(StepResult("full_path.cdn_fetch", cdn_ok, detail))

        return results
    except Exception as e:
        results.append(StepResult("full_path", False, str(e)))
        return results
    finally:
        await liblib_client.close()


def check_docker_env_hint() -> StepResult:
    """若在容器内运行则跳过；在宿主机提示是否需要 recreate。"""
    in_docker = Path("/.dockerenv").exists()
    if in_docker:
        ak = os.getenv("LIBLIB_ACCESS_KEY", "")
        return StepResult(
            "docker.env_loaded",
            bool(ak),
            "容器内 LIBLIB_ACCESS_KEY 已加载" if ak else "容器内 LIBLIB_ACCESS_KEY 为空，需 recreate backend",
        )
    return StepResult("docker.hint", True, "宿主机运行；改 .env 后须 docker compose up -d --force-recreate backend")


def _print_results(results: list[StepResult]) -> int:
    failed = 0
    for r in results:
        mark = "✅" if r.ok else "❌"
        print(f"  {mark} {r.name}: {r.detail}")
        if not r.ok:
            failed += 1
    return failed


async def main() -> int:
    parser = argparse.ArgumentParser(description="LiblibAI + OSS 冒烟测试")
    parser.add_argument("--skip-liblib", action="store_true", help="跳过 LiblibAI 调用（仅测 OSS）")
    parser.add_argument("--skip-full", action="store_true", help="跳过完整链路")
    parser.add_argument(
        "--img-type", choices=("daily", "selfie"), default="daily",
        help="完整链路图片类型（daily=text2img，selfie=img2img）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("生活流图片链路冒烟测试")
    print(f"LIBLIB_BASE_URL = {get_liblib_base_url()}")
    print(f"OSS_BUCKET      = {get_oss_bucket()}")
    print("=" * 60)

    all_results: list[StepResult] = []

    print("\n[1] 环境变量检查")
    all_results.extend(check_env_config())
    all_results.append(check_docker_env_hint())
    _print_results(all_results[-len(check_env_config()) - 1 :])

    print("\n[2] 参考图公网可达性")
    ref_r = check_reference_image_reachable()
    all_results.append(ref_r)
    _print_results([ref_r])

    print("\n[3] 系统时钟（OSS 签名依赖）")
    clock_r = check_clock_skew()
    all_results.append(clock_r)
    _print_results([clock_r])

    print("\n[4] OSS 读写")
    put_r, get_r, _ = check_oss_rw()
    all_results.extend([put_r, get_r])
    _print_results([put_r, get_r])

    print("\n[5] CDN 拉取冒烟对象")
    cdn_r = check_cdn_fetch()
    all_results.append(cdn_r)
    _print_results([cdn_r])

    if not args.skip_liblib:
        print("\n[6] LiblibAI 凭证（官方 template 结构）")
        cred = await check_liblib_credentials()
        all_results.append(cred)
        _print_results([cred])

        print("\n[7] LiblibAI 业务 payload（feed_image_service 当前结构）")
        t2i = await check_liblib_business_payload()
        all_results.append(t2i)
        _print_results([t2i])

        print("\n[8] LiblibAI img2img（需参考图 URL 有效）")
        i2i = await check_liblib_img2img()
        all_results.append(i2i)
        _print_results([i2i])

        if not args.skip_full and t2i.ok:
            print(f"\n[9] 完整链路（{args.img_type}）")
            full = await check_full_path(args.img_type)
            all_results.extend(full)
            _print_results(full)

    print("\n" + "=" * 60)
    total = len(all_results)
    failed = sum(1 for r in all_results if not r.ok)
    print(f"合计 {total} 项，失败 {failed} 项")
    if failed:
        print("\n⚠️  常见修复：")
        print("  1. 改 .env 后：docker compose up -d --force-recreate backend")
        print("  2. FEED_IMAGE_REFERENCE_PUBLIC_URL 改为 https:// 公网 URL（非 oss://）")
        print("     例：https://pj4-test.oss-cn-hangzhou.aliyuncs.com/base/frontend/static/images/avatar/character-ref/base.png")
        print("  3. 系统时钟偏差 >15min：同步 macOS 时间后重试 OSS")
        print("  4. FEED_IMAGE_REFERENCE_PUBLIC_URL：私有 OSS 对象 LiblibAI 无法拉取，需公网可读 HTTPS")
        print("  5. CDN 403：Bucket 私有时需阿里云 CDN 开启「私有 Bucket 回源授权」")
        print("  6. img2img 跳过/失败：设置环境变量 LIBLIB_IMG2IMG_TEMPLATE_UUID 或后台填写 liblib_img2img_template_uuid")
        print("  7. text2img 仍参数完整度失败：核对控制台 templateUuid 与 generateParams 字段名")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
