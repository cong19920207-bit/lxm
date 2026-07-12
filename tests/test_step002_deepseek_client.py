# -*- coding: utf-8 -*-
# STEP-002 单元测试：DeepSeekClient + deepseek_llm_service
# 覆盖场景（对应 steps.md STEP-002 单测要求表）：
#   - mock HTTP 成功 → 返回 content
#   - 超时重试：前 2 次超时，第 3 次成功 → 返回 content，重试计数=2
#   - 完全超时：连续 3 次超时 → 抛 DeepSeekError
#   - 4xx 不重试：HTTP 401 → 立即抛 DeepSeekError，不重试
#   - 5xx 重试：前 2 次 500，第 3 次 200 → 返回 content
#   - 模型配置热加载：切换 admin_config → 下次调用使用新模型名
#   - Redis 统计：一次成功调用 → llm_stats total 与 success 各 +1

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.utils import deepseek_client as ds_mod
from backend.utils.deepseek_client import DeepSeekClient, DeepSeekError


class _FakeResponse:
    """模拟 httpx.Response：可指定 status_code 与 json 内容"""

    def __init__(self, status_code: int, content: str = "你好呀"):
        self.status_code = status_code
        self._content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=self
            )

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _make_client_with_post(side_effect) -> DeepSeekClient:
    """构造一个 DeepSeekClient，其内部 AsyncClient.post 用给定 side_effect 打桩"""
    client = DeepSeekClient()
    fake_httpx = AsyncMock()
    fake_httpx.is_closed = False
    fake_httpx.post = AsyncMock(side_effect=side_effect)
    client._client = fake_httpx
    return client


_MESSAGES = [{"role": "user", "content": "在吗"}]


@pytest.fixture(autouse=True)
def _no_sleep():
    """跳过指数退避真实等待，避免测试慢"""
    with patch.object(ds_mod.asyncio, "sleep", new_callable=AsyncMock):
        yield


class TestDeepSeekClientRetry:
    @pytest.mark.asyncio
    async def test_http_success(self):
        client = _make_client_with_post([_FakeResponse(200, "早呀")])
        result = await client.chat_sync(_MESSAGES, model="ddeepseek-v4-pro")
        assert result == "早呀"

    @pytest.mark.asyncio
    async def test_timeout_then_success_retry_twice(self):
        side = [
            httpx.TimeoutException("t1"),
            httpx.TimeoutException("t2"),
            _FakeResponse(200, "第三次成功"),
        ]
        client = _make_client_with_post(side)
        result = await client.chat_sync(_MESSAGES, model="deepseek-v4-pro")
        assert result == "第三次成功"
        # 总调用 3 次 = 首次 + 2 次重试
        assert client._client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_full_timeout_raises(self):
        side = [httpx.TimeoutException("t") for _ in range(3)]
        client = _make_client_with_post(side)
        with pytest.raises(DeepSeekError):
            await client.chat_sync(_MESSAGES, model="deepseek-v4-pro")
        assert client._client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_4xx_no_retry(self):
        side = [_FakeResponse(401)]
        client = _make_client_with_post(side)
        with pytest.raises(DeepSeekError):
            await client.chat_sync(_MESSAGES, model="deepseek-v4-pro")
        # 4xx 立即抛错，仅调用 1 次
        assert client._client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_5xx_then_success(self):
        side = [
            _FakeResponse(500),
            _FakeResponse(500),
            _FakeResponse(200, "恢复正常"),
        ]
        client = _make_client_with_post(side)
        result = await client.chat_sync(_MESSAGES, model="deepseek-v4-pro")
        assert result == "恢复正常"
        assert client._client.post.call_count == 3


class TestDeepSeekLLMService:
    @pytest.mark.asyncio
    async def test_model_hot_reload(self):
        """切换 admin_config 生效模型 → call_llm 传给 chat_sync 的 model 随之变化"""
        from backend.services.deepseek_llm_service import deepseek_llm_service

        captured = {}

        async def fake_chat_sync(messages, model, temperature=0.7):
            captured["model"] = model
            return "ok"

        with patch(
            "backend.services.deepseek_llm_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value="deepseek-reasoner",
        ), patch(
            "backend.services.deepseek_llm_service.deepseek_client.chat_sync",
            side_effect=fake_chat_sync,
        ), patch.object(
            deepseek_llm_service, "_record_stats", new_callable=AsyncMock,
        ):
            result = await deepseek_llm_service.call_llm("llm_04", _MESSAGES)

        assert result == "ok"
        assert captured["model"] == "deepseek-reasoner"

    @pytest.mark.asyncio
    async def test_default_model_when_config_missing(self):
        from backend.constants import DEEPSEEK_DEFAULT_MODEL
        from backend.services.deepseek_llm_service import deepseek_llm_service

        captured = {}

        async def fake_chat_sync(messages, model, temperature=0.7):
            captured["model"] = model
            return "ok"

        with patch(
            "backend.services.deepseek_llm_service.admin_config_service.get_active_config",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "backend.services.deepseek_llm_service.deepseek_client.chat_sync",
            side_effect=fake_chat_sync,
        ), patch.object(
            deepseek_llm_service, "_record_stats", new_callable=AsyncMock,
        ):
            await deepseek_llm_service.call_llm("llm_01", _MESSAGES)

        assert captured["model"] == DEEPSEEK_DEFAULT_MODEL

    @pytest.mark.asyncio
    async def test_invalid_node_key_raises(self):
        from backend.services.deepseek_llm_service import deepseek_llm_service

        with pytest.raises(ValueError):
            await deepseek_llm_service.call_llm("llm_99", _MESSAGES)

    @pytest.mark.asyncio
    async def test_record_stats_success_increments(self):
        """一次成功调用 → llm_stats total 与 success 各 +1，写 llm_response_times"""
        from backend.services.deepseek_llm_service import deepseek_llm_service

        fake_redis = AsyncMock()
        with patch(
            "backend.services.deepseek_llm_service.get_redis",
            new_callable=AsyncMock,
            return_value=fake_redis,
        ):
            await deepseek_llm_service._record_stats(123, True)

        fake_redis.lpush.assert_awaited()
        # 校验 llm_stats total 与 success 各 +1
        hincrby_fields = [c.args[1] for c in fake_redis.hincrby.await_args_list]
        assert "total" in hincrby_fields
        assert "success" in hincrby_fields
        assert "failed" not in hincrby_fields

    @pytest.mark.asyncio
    async def test_record_stats_failure_increments_failed(self):
        from backend.services.deepseek_llm_service import deepseek_llm_service

        fake_redis = AsyncMock()
        with patch(
            "backend.services.deepseek_llm_service.get_redis",
            new_callable=AsyncMock,
            return_value=fake_redis,
        ):
            await deepseek_llm_service._record_stats(456, False)

        hincrby_fields = [c.args[1] for c in fake_redis.hincrby.await_args_list]
        assert "total" in hincrby_fields
        assert "failed" in hincrby_fields
        assert "success" not in hincrby_fields
