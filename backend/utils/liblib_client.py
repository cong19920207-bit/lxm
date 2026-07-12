# -*- coding: utf-8 -*-
# LiblibAI 图像生成客户端（生活流 STEP-012）
#
# 签名：HMAC-SHA1(secret, "{uri}&{timestamp}&{nonce}") → urlsafe base64（去 =），
#   随请求以 query 参数 AccessKey / Signature / Timestamp / SignatureNonce 传递。
# 限速：QPS ≤ 1/s（_qps_sem + 提交后 sleep 1s）；进行中任务并发 = 1（concurrency_sem，
#   与账号侧「进行中任务上限」对齐，供服务层包裹单张「提交+轮询」流程）。

import asyncio
import base64
import hashlib
import hmac
import logging
import time
import uuid

import httpx

from backend.config import (
    get_liblib_access_key,
    get_liblib_base_url,
    get_liblib_secret_key,
)

logger = logging.getLogger(__name__)

_SUBMIT_TIMEOUT = 30.0
_POLL_HTTP_TIMEOUT = 30.0
_POLL_INTERVAL_SEC = 5.0


class LiblibError(Exception):
    """LiblibAI 调用失败"""
    pass


class LiblibClient:
    """LiblibAI 异步客户端（提交 + 轮询）"""

    # QPS ≤ 1：串行提交并在每次提交后间隔 1s
    _qps_sem = asyncio.Semaphore(1)
    # 进行中任务并发：账号侧实测同时进行中任务上限为 1，故整段「提交+轮询」串行，
    # 避免多图帖后几张报「当前进行中任务数量已达到并发任务上限」
    concurrency_sem = asyncio.Semaphore(1)

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=_SUBMIT_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _sign(uri: str) -> dict:
        """按 uri 生成签名 query 参数。"""
        secret = get_liblib_secret_key()
        timestamp = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        content = f"{uri}&{timestamp}&{nonce}"
        digest = hmac.new(secret.encode("utf-8"), content.encode("utf-8"), hashlib.sha1).digest()
        signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
        return {
            "AccessKey": get_liblib_access_key(),
            "Signature": signature,
            "Timestamp": timestamp,
            "SignatureNonce": nonce,
        }

    async def submit_task(self, uri: str, payload: dict) -> str:
        """
        提交生成任务，返回 generateUuid（任务 ID）。QPS 限速在此。

        Args:
            uri: 任务提交接口路径（如 /api/generate/webui/img2img）
            payload: 请求体
        """
        async with self._qps_sem:
            try:
                client = await self._get_client()
                resp = await client.post(
                    f"{get_liblib_base_url()}{uri}",
                    params=self._sign(uri),
                    json=payload,
                    timeout=_SUBMIT_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as e:
                raise LiblibError(f"LiblibAI 提交失败: {e}") from e
            finally:
                # QPS ≤ 1/s：无论成功失败都保证与下一次提交间隔 ≥1s
                await asyncio.sleep(1)

        if data.get("code") not in (0, None):
            raise LiblibError(f"LiblibAI 提交返回错误: {data.get('msg') or data}")
        task_id = (data.get("data") or {}).get("generateUuid") or data.get("generateUuid")
        if not task_id:
            raise LiblibError(f"LiblibAI 提交未返回 generateUuid: {data}")
        return task_id

    async def poll_task(self, status_uri: str, generate_uuid: str, timeout_sec: float) -> str | None:
        """
        轮询任务结果，返回首个图片 URL；超时或失败返回 None。

        Args:
            status_uri: 查询接口路径（如 /api/generate/webui/status）
            generate_uuid: submit_task 返回的任务 ID
            timeout_sec: 单张轮询上限（秒）
        """
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            try:
                client = await self._get_client()
                resp = await client.post(
                    f"{get_liblib_base_url()}{status_uri}",
                    params=self._sign(status_uri),
                    json={"generateUuid": generate_uuid},
                    timeout=_POLL_HTTP_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as e:
                logger.warning("LiblibAI 轮询异常 uuid=%s: %s", generate_uuid, e)
                await asyncio.sleep(_POLL_INTERVAL_SEC)
                continue

            body = data.get("data") or {}
            status = body.get("generateStatus")
            # LiblibAI: 5=成功, 6/7=失败（不同接口略有差异，非成功且有 images 即取）
            images = body.get("images") or []
            if images:
                url = images[0].get("imageUrl") if isinstance(images[0], dict) else images[0]
                if url:
                    return url
            if status in (6, 7):  # 失败终态
                logger.warning("LiblibAI 任务失败 uuid=%s status=%s", generate_uuid, status)
                return None
            await asyncio.sleep(_POLL_INTERVAL_SEC)

        logger.warning("LiblibAI 轮询超时 uuid=%s", generate_uuid)
        return None


# 全局单例
liblib_client = LiblibClient()
