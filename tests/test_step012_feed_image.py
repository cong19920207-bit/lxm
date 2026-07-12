# -*- coding: utf-8 -*-
# STEP-012 单元测试：LiblibAI 图片生成服务 feed_image_service
# 覆盖场景（对应 steps.md STEP-012 单测要求表）：
#   - 张数=0 抽签 → 返回 []，不调 LiblibAI
#   - selfie 3 张 → 提交 3 个 img2img 任务
#   - venue 未命中 → 回落 category_img_keyword
#   - emotion 自由词 → 用 fallback 兜底组
#   - 单张超时 → 该张失败，其余继续
#   - 全批失败 → 返回 []
#   - WebP 压缩临时清理 → 临时文件 os.unlink 被调用
#   - 统计写入 → liblib_stats total/success +1
#   - TB-LF-001：payload 含 templateUuid + generateParams.imgCount==1

from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from backend.constants.life_feed_config import (
    DEFAULT_LIBLIB_GEN_HEIGHT,
    DEFAULT_LIBLIB_GEN_STEPS,
    DEFAULT_LIBLIB_GEN_WIDTH,
    DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT,
    DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH,
    DEFAULT_LIBLIB_IMG2IMG_STRENGTH,
    DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID,
)
from backend.services import feed_image_service as fis_mod
from backend.services.feed_image_service import FeedImageService, _time_period_light

_CTX = {
    "post_id": 123, "venue_type": "咖啡馆", "category": "工作",
    "city": "杭州", "time_range": "09:00-10:30", "emotion": "平静", "season": "夏",
}

_TEST_IMG2IMG_UUID = "test-img2img-template-uuid"


def _cfg_default(key, default=None):
    # 单测为 selfie 提供非空 img2img UUID（生产默认空，需后台配置）
    if key == "liblib_img2img_template_uuid":
        return _TEST_IMG2IMG_UUID
    if key == "liblib_text2img_template_uuid":
        return DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID
    if key == "liblib_gen_steps":
        return DEFAULT_LIBLIB_GEN_STEPS
    if key == "liblib_gen_width":
        return DEFAULT_LIBLIB_GEN_WIDTH
    if key == "liblib_gen_height":
        return DEFAULT_LIBLIB_GEN_HEIGHT
    if key == "liblib_img2img_strength":
        return DEFAULT_LIBLIB_IMG2IMG_STRENGTH
    if key == "liblib_img2img_resized_width":
        return DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH
    if key == "liblib_img2img_resized_height":
        return DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT
    return default


def _patch_common(count_override=None, type_override=None):
    """打桩 config / render_prompt / submit / poll / _record_stats。"""
    return patch.multiple(
        fis_mod,
        get_life_feed_config=AsyncMock(side_effect=_cfg_default),
        render_prompt=AsyncMock(return_value="PROMPT"),
    )


# ============ 纯逻辑 ============

class TestPureHelpers:
    def test_time_period_light_morning(self):
        assert "morning" in _time_period_light("06:30-08:00")

    def test_time_period_light_default(self):
        assert _time_period_light("bad") == "bright natural daylight"


# ============ 关键词映射兜底 ============

class TestKeywordFallback:
    @pytest.mark.asyncio
    async def test_venue_hit(self):
        svc = FeedImageService()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default):
            kw = await svc._venue_keyword("咖啡馆", "工作")
        assert "cafe" in kw

    @pytest.mark.asyncio
    async def test_venue_miss_falls_to_category(self):
        svc = FeedImageService()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default):
            kw = await svc._venue_keyword("宠物店", "探店美食")
        assert "cafe or restaurant" in kw  # category_img_keyword["探店美食"]

    @pytest.mark.asyncio
    async def test_emotion_free_word_fallback_p12(self):
        svc = FeedImageService()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default):
            kw = await svc._emotion_keyword_p12("温柔")  # 非核心词
        assert "candid" in kw  # 兜底组

    @pytest.mark.asyncio
    async def test_emotion_free_word_fallback_p13c(self):
        svc = FeedImageService()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default):
            kw = await svc._emotion_atmosphere_p13c("温柔")
        assert "natural light" in kw


# ============ payload 结构（TB-LF-001）============

class TestBuildPayload:
    @pytest.mark.asyncio
    async def test_daily_official_structure(self):
        svc = FeedImageService()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default):
            payload = await svc._build_payload("daily", "POS", "NEG")
        assert payload is not None
        assert payload["templateUuid"] == DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID
        gp = payload["generateParams"]
        assert gp["prompt"] == "POS"
        assert gp["negativePrompt"] == "NEG"
        assert gp["imgCount"] == 1
        assert "sourceImage" not in gp

    @pytest.mark.asyncio
    async def test_selfie_has_source_image_in_generate_params(self):
        svc = FeedImageService()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod, "get_feed_image_reference_public_url",
                          return_value="https://example.com/base.png"):
            payload = await svc._build_payload("selfie", "POS", "NEG")
        assert payload is not None
        assert payload["templateUuid"] == _TEST_IMG2IMG_UUID
        gp = payload["generateParams"]
        assert gp["imgCount"] == 1
        assert gp["sourceImage"] == "https://example.com/base.png"
        assert gp["strength"] == DEFAULT_LIBLIB_IMG2IMG_STRENGTH
        assert gp["resizedWidth"] == DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH
        assert gp["resizedHeight"] == DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT

    @pytest.mark.asyncio
    async def test_selfie_empty_uuid_returns_none(self):
        svc = FeedImageService()

        async def _empty_img2img(key, default=None):
            if key == "liblib_img2img_template_uuid":
                return ""
            return _cfg_default(key, default)

        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_empty_img2img):
            payload = await svc._build_payload("selfie", "POS", "NEG")
        assert payload is None


# ============ generate_images ============

class TestGenerateImages:
    @pytest.mark.asyncio
    async def test_count_zero_no_liblib(self):
        svc = FeedImageService()
        submit = AsyncMock()
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod.liblib_client, "submit_task", submit):
            ctx = dict(_CTX)
            ctx["image_count"] = 0
            result = await svc.generate_images(ctx)
        assert result == []
        submit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_selfie_three_submits(self):
        svc = FeedImageService()
        submit = AsyncMock(return_value="uuid")
        poll = AsyncMock(return_value="http://img")
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod, "render_prompt", new_callable=AsyncMock, return_value="P"), \
             patch.object(fis_mod, "get_feed_image_reference_public_url",
                          return_value="https://example.com/base.png"), \
             patch.object(fis_mod.liblib_client, "submit_task", submit), \
             patch.object(fis_mod.liblib_client, "poll_task", poll), \
             patch.object(svc, "_download_compress_upload", new_callable=AsyncMock,
                          return_value="https://cdn/x.webp"), \
             patch.object(svc, "_record_stats", new_callable=AsyncMock):
            ctx = dict(_CTX, image_count=3, image_type="selfie")
            result = await svc.generate_images(ctx)
        assert len(result) == 3
        assert submit.await_count == 3
        # img2img uri
        assert submit.await_args_list[0].args[0] == "/api/generate/webui/img2img"
        body = submit.await_args_list[0].args[1]
        assert body["templateUuid"] == _TEST_IMG2IMG_UUID
        assert body["generateParams"]["imgCount"] == 1
        assert body["generateParams"]["sourceImage"] == "https://example.com/base.png"
        assert body["generateParams"]["resizedWidth"] == DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH
        assert body["generateParams"]["resizedHeight"] == DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT
        # 多图：每张有变体后缀与独立 seed
        prompts = [c.args[1]["generateParams"]["prompt"] for c in submit.await_args_list]
        seeds = [c.args[1]["generateParams"]["seed"] for c in submit.await_args_list]
        assert len(set(prompts)) == 3
        assert all(p.startswith("P, ") for p in prompts)
        assert len(set(seeds)) == 3

    @pytest.mark.asyncio
    async def test_daily_submit_payload_structure(self):
        svc = FeedImageService()
        submit = AsyncMock(return_value="uuid")
        poll = AsyncMock(return_value="http://img")
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod, "render_prompt", new_callable=AsyncMock, return_value="P"), \
             patch.object(fis_mod.liblib_client, "submit_task", submit), \
             patch.object(fis_mod.liblib_client, "poll_task", poll), \
             patch.object(svc, "_download_compress_upload", new_callable=AsyncMock,
                          return_value="https://cdn/x.webp"), \
             patch.object(svc, "_record_stats", new_callable=AsyncMock):
            ctx = dict(_CTX, image_count=1, image_type="daily")
            result = await svc.generate_images(ctx)
        assert len(result) == 1
        assert submit.await_args_list[0].args[0] == "/api/generate/webui/text2img"
        body = submit.await_args_list[0].args[1]
        assert body["templateUuid"] == DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID
        assert body["generateParams"]["imgCount"] == 1
        assert body["generateParams"]["prompt"] == "P"  # 单图无变体后缀
        assert body["generateParams"]["seed"] == -1
        assert "sourceImage" not in body["generateParams"]

    @pytest.mark.asyncio
    async def test_multi_image_variants_differ(self):
        """同帖 4 张：构图后缀不同、seed 不同；主 prompt 前缀相同。"""
        svc = FeedImageService()
        submit = AsyncMock(return_value="uuid")
        poll = AsyncMock(return_value="http://img")
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod, "render_prompt", new_callable=AsyncMock, return_value="BASE_PROMPT"), \
             patch.object(fis_mod.liblib_client, "submit_task", submit), \
             patch.object(fis_mod.liblib_client, "poll_task", poll), \
             patch.object(svc, "_download_compress_upload", new_callable=AsyncMock,
                          return_value="https://cdn/x.webp"), \
             patch.object(svc, "_record_stats", new_callable=AsyncMock):
            ctx = dict(_CTX, image_count=4, image_type="daily")
            result = await svc.generate_images(ctx)
        assert len(result) == 4
        prompts = [c.args[1]["generateParams"]["prompt"] for c in submit.await_args_list]
        seeds = [c.args[1]["generateParams"]["seed"] for c in submit.await_args_list]
        assert len(set(prompts)) == 4
        assert len(set(seeds)) == 4
        assert all(p.startswith("BASE_PROMPT, ") for p in prompts)
        assert all(s != -1 for s in seeds)
        assert all(c.args[1]["generateParams"]["imgCount"] == 1 for c in submit.await_args_list)

    @pytest.mark.asyncio
    async def test_single_timeout_partial(self):
        svc = FeedImageService()
        submit = AsyncMock(return_value="uuid")
        poll = AsyncMock(side_effect=["http://a", None, "http://c"])  # 恰一张超时
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod, "render_prompt", new_callable=AsyncMock, return_value="P"), \
             patch.object(fis_mod.liblib_client, "submit_task", submit), \
             patch.object(fis_mod.liblib_client, "poll_task", poll), \
             patch.object(svc, "_download_compress_upload", new_callable=AsyncMock,
                          return_value="https://cdn/x.webp"), \
             patch.object(svc, "_record_stats", new_callable=AsyncMock):
            ctx = dict(_CTX, image_count=3, image_type="daily")
            result = await svc.generate_images(ctx)
        assert len(result) == 2  # 恰一张失败

    @pytest.mark.asyncio
    async def test_all_fail_returns_empty(self):
        svc = FeedImageService()
        submit = AsyncMock(return_value="uuid")
        poll = AsyncMock(return_value=None)  # 全超时
        with patch.object(fis_mod, "get_life_feed_config", new_callable=AsyncMock,
                          side_effect=_cfg_default), \
             patch.object(fis_mod, "render_prompt", new_callable=AsyncMock, return_value="P"), \
             patch.object(fis_mod.liblib_client, "submit_task", submit), \
             patch.object(fis_mod.liblib_client, "poll_task", poll), \
             patch.object(svc, "_record_stats", new_callable=AsyncMock):
            ctx = dict(_CTX, image_count=2, image_type="scenery")
            result = await svc.generate_images(ctx)
        assert result == []


# ============ 临时文件清理 + 统计 ============

class TestDownloadAndStats:
    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self):
        svc = FeedImageService()
        resp = MagicMock()
        resp.content = b"jpgbytes"
        resp.raise_for_status = MagicMock()
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        unlink = MagicMock()
        with patch("httpx.AsyncClient", return_value=client), \
             patch("builtins.open", mock_open()), \
             patch.object(fis_mod.os.path, "exists", return_value=True), \
             patch.object(fis_mod.os, "unlink", unlink), \
             patch.object(FeedImageService, "_to_webp", return_value=b"webp"), \
             patch.object(FeedImageService, "_oss_put", return_value=None), \
             patch.object(fis_mod, "get_oss_cdn_domain", return_value="cdn.example.com"):
            url = await svc._download_compress_upload("http://img", 5, 1)
        assert url == "https://cdn.example.com/lxm/posts/5/01.webp"
        unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_total_success(self):
        svc = FeedImageService()
        r = MagicMock()
        r.hincrby = AsyncMock()
        r.expire = AsyncMock()
        with patch.object(fis_mod, "get_redis", new_callable=AsyncMock, return_value=r):
            await svc._record_stats("total")
            await svc._record_stats("success")
        fields = [c.args[1] for c in r.hincrby.await_args_list]
        assert "total" in fields
        assert "success" in fields
