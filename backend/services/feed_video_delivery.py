"""Version-bound immutable OSS objects and anonymous client-origin CDN verification."""
import hashlib
import os
import re
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from backend import config
from backend.services.bgm_asset_service import _bucket
from backend.services.feed_video_media import InvalidMedia


def prefix():
    name = os.getenv("FEED_VIDEO_OSS_PREFIX", "lxm/feed-videos")
    if name != "lxm/feed-videos" and not re.fullmatch(r"lxm/acceptance/feed-v8/[a-z0-9-]{12,64}", name):
        raise InvalidMedia("朋友圈媒体前缀配置无效")
    return name


def asset_key(version, kind, variant="default"):
    version = str(UUID(version))
    if kind in ("video", "preview") and variant == "default":
        leaf = kind + ".mp4"
    elif kind in ("cover_small", "cover_large"):
        variant = "default" if variant == "default" else str(UUID(variant))
        leaf = variant + "/" + kind + ".webp"
    else:
        raise ValueError("unknown asset")
    return f"{prefix()}/{version}/{leaf}"


def cdn_url(key):
    domain = config.get_oss_cdn_domain().strip()
    parsed = urlsplit(domain if "://" in domain else "https://" + domain)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.password or parsed.username or
        parsed.path not in ("","/") or parsed.query or parsed.fragment):
        raise InvalidMedia("请配置媒体 CDN 的 HTTPS 域名")
    return "https://" + parsed.netloc + "/" + key


def origins():
    configured = os.getenv("FEED_VIDEO_MEDIA_ORIGINS") or os.getenv("BGM_MEDIA_ORIGINS") or ""
    values = list(dict.fromkeys(item.strip() for item in configured.split(",") if item.strip()))
    if not values:
        raise InvalidMedia("请配置朋友圈实际客户端来源")
    for value in values:
        url = urlsplit(value)
        if (not url.hostname or "*" in value or url.path or url.query or url.fragment or url.username or
                url.password or not (url.scheme == "https" or url.scheme == "http" and
                                     url.hostname in ("127.0.0.1","localhost","::1"))):
            raise InvalidMedia("朋友圈客户端来源配置无效")
    return values


def owned(head, meta):
    return (head.headers.get("x-oss-meta-feed-owner") == meta["version"] and
            head.headers.get("x-oss-meta-feed-sha256") == meta["sha256"] and
            head.content_length == meta["size_bytes"])


def put_file(path, meta):
    import oss2
    origins()
    cdn_url(meta["key"])
    bucket, key = _bucket(), meta["key"]
    try:
        exists = bucket.object_exists(key)
        if not exists:
            try:
                bucket.put_object_from_file(key,str(path),headers={"Content-Type":meta["mime_type"],
                    "Cache-Control":"public, max-age=2592000, immutable",
                    "x-oss-meta-feed-sha256":meta["sha256"],"x-oss-meta-feed-owner":meta["version"],
                    "x-oss-forbid-overwrite":"true"})
            except oss2.exceptions.OssError:
                # Reconcile an ambiguous PUT at the original immutable key.
                if not bucket.object_exists(key):
                    raise
        if not owned(bucket.head_object(key),meta):
            raise InvalidMedia("OSS 已有对象与当前媒体版本不匹配")
    except oss2.exceptions.OssError:
        raise InvalidMedia("OSS 上传或对象核验失败，请重试") from None


def verify_file(path, meta):
    url = cdn_url(meta["key"])
    size = meta["size_bytes"]
    try:
        with httpx.Client(timeout=httpx.Timeout(20,connect=8), follow_redirects=False) as client:
            for origin in origins():
                headers = {"Accept-Encoding":"identity","Origin":origin}
                requests = [(None,None)]
                if meta["kind"]=="video":
                    start = size//2
                    requests.append((start,min(start+1023,size-1)))
                for start,end in requests:
                    requested = headers if start is None else {**headers,"Range":f"bytes={start}-{end}"}
                    with client.stream("GET", url, headers=requested) as response:
                        if response.status_code != (200 if start is None else 206):
                            raise InvalidMedia(f"CDN 返回 HTTP {response.status_code}，请检查分发及分段读取")
                        if response.headers.get("access-control-allow-origin") not in ("*",origin):
                            raise InvalidMedia("CDN 未允许此客户端来源跨域读取")
                        if response.headers.get("content-type","").split(";")[0] != meta["mime_type"]:
                            raise InvalidMedia("CDN 媒体类型与文件不符")
                        if start is not None and response.headers.get("content-range") != f"bytes {start}-{end}/{size}":
                            raise InvalidMedia("CDN 分段读取的字节区间不符")
                        with path.open("rb") as local:
                            local.seek(start or 0)
                            remaining = size if start is None else end-start+1
                            for chunk in response.iter_bytes(65536):
                                if len(chunk)>remaining or chunk != local.read(len(chunk)):
                                    raise InvalidMedia("CDN 内容与本地校验文件不符")
                                remaining -= len(chunk)
                            if remaining:
                                raise InvalidMedia("CDN 返回内容不完整")
    except httpx.HTTPError:
        raise InvalidMedia("CDN HTTPS 读取失败，请检查域名、证书和网络") from None
    return url


def fetch_verified_master(url, target, size, checksum):
    """Restore a previously verified object when later local work needs the master again."""
    written = 0
    hasher = hashlib.sha256()
    try:
        with httpx.stream("GET",url,headers={"Accept-Encoding":"identity"},timeout=30) as response:
            if response.status_code!=200 or response.headers.get("content-type","").split(";")[0]!="video/mp4":
                raise InvalidMedia("远端成片暂不可恢复，请重试")
            with target.open("wb") as output:
                for chunk in response.iter_bytes(65536):
                    written += len(chunk)
                    if written > size:
                        raise InvalidMedia("远端成片大小与已校验版本不符")
                    hasher.update(chunk)
                    output.write(chunk)
    except httpx.HTTPError:
        raise InvalidMedia("远端成片读取失败，请重试") from None
    if written!=size or hasher.hexdigest()!=checksum:
        raise InvalidMedia("远端成片内容与已校验版本不符")
