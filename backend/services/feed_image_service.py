# -*- coding: utf-8 -*-
# 生活流·朋友圈图片生成服务（STEP-012）
#
# 职责：张数/类型抽签 → 关键词映射与兜底 → LiblibAI 提交+轮询 → WebP 压缩 → OSS 上传
#        → 返回 CDN URL 数组（可能为空 = 纯文字帖）。超时降级、临时文件即时清理、liblib 统计。
#
# 说明：Pillow / oss2 采用函数内惰性导入，避免测试/未装依赖环境在导入期即失败。

import asyncio
import copy
import datetime
import logging
import os
import random
import uuid

from backend.config import (
    get_feed_image_reference_public_url,
    get_oss_access_key_id,
    get_oss_access_key_secret,
    get_oss_bucket,
    get_oss_cdn_domain,
    get_oss_endpoint,
)
from backend.constants.life_feed_config import (
    CONFIG_FEED_IMAGE_COUNT_0_WEIGHT,
    CONFIG_FEED_IMAGE_COUNT_1_WEIGHT,
    CONFIG_FEED_IMAGE_COUNT_2_3_WEIGHT,
    CONFIG_FEED_IMAGE_COUNT_4_WEIGHT,
    CONFIG_FEED_IMAGE_TYPE_DAILY_WEIGHT,
    CONFIG_FEED_IMAGE_TYPE_EMOTION_WEIGHT,
    CONFIG_FEED_IMAGE_TYPE_SCENERY_WEIGHT,
    CONFIG_FEED_IMAGE_TYPE_SELFIE_WEIGHT,
    CONFIG_LIBLIB_GEN_HEIGHT,
    CONFIG_LIBLIB_GEN_STEPS,
    CONFIG_LIBLIB_GEN_WIDTH,
    CONFIG_LIBLIB_IMG2IMG_RESIZED_HEIGHT,
    CONFIG_LIBLIB_IMG2IMG_RESIZED_WIDTH,
    CONFIG_LIBLIB_IMG2IMG_STRENGTH,
    CONFIG_LIBLIB_IMG2IMG_TEMPLATE_UUID,
    CONFIG_LIBLIB_TEXT2IMG_TEMPLATE_UUID,
    CONFIG_LXM_IMG1_CHARACTER_DESC,
    CONFIG_LXM_IMG1_NEGATIVE_BASE,
    DEFAULT_FEED_IMAGE_COUNT_0_WEIGHT,
    DEFAULT_FEED_IMAGE_COUNT_1_WEIGHT,
    DEFAULT_FEED_IMAGE_COUNT_2_3_WEIGHT,
    DEFAULT_FEED_IMAGE_COUNT_4_WEIGHT,
    DEFAULT_FEED_IMAGE_TYPE_DAILY_WEIGHT,
    DEFAULT_FEED_IMAGE_TYPE_EMOTION_WEIGHT,
    DEFAULT_FEED_IMAGE_TYPE_SCENERY_WEIGHT,
    DEFAULT_FEED_IMAGE_TYPE_SELFIE_WEIGHT,
    DEFAULT_LIBLIB_GEN_HEIGHT,
    DEFAULT_LIBLIB_GEN_STEPS,
    DEFAULT_LIBLIB_GEN_WIDTH,
    DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT,
    DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH,
    DEFAULT_LIBLIB_IMG2IMG_STRENGTH,
    DEFAULT_LIBLIB_IMG2IMG_TEMPLATE_UUID,
    DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID,
    DEFAULT_LXM_IMG1_CHARACTER_DESC,
    DEFAULT_LXM_IMG1_NEGATIVE_BASE,
)
from backend.constants.life_feed_prompts import (
    CATEGORY_IMG_KEYWORD,
    EMOTION_ATMOSPHERE_DESC,
    EMOTION_FALLBACK_ATMOSPHERE_DESC,
    EMOTION_FALLBACK_IMG_KEYWORD,
    EMOTION_IMG_KEYWORD,
    VENUE_TYPE_IMG_KEYWORD,
)
from backend.redis_client import get_redis
from backend.services.life_feed_config_service import get_life_feed_config
from backend.services.life_prompt_service import render_prompt
from backend.utils.liblib_client import liblib_client

logger = logging.getLogger(__name__)

# 单张轮询上限 3 分钟；整批 15 分钟（PRD 4.4.3）
_SINGLE_POLL_TIMEOUT = 180.0
_BATCH_TIMEOUT = 900.0

# LiblibAI 接口路径（img2img=selfie，text2img=daily/scenery/emotion）
_IMG2IMG_URI = "/api/generate/webui/img2img"
_TEXT2IMG_URI = "/api/generate/webui/text2img"
_STATUS_URI = "/api/generate/webui/status"

# 系统内置映射（提示词规格 6.2，非 Prompt 内容，随代码维护）
_SEASON_KEYWORD = {
    "春": "spring, fresh greenery, soft light",
    "夏": "summer, lush green, strong sunlight",
    "秋": "autumn, golden foliage, warm tones",
    "冬": "winter, bare branches, cool tones",
}
_TIME_PERIOD_LIGHT = [
    (6 * 60, 9 * 60, "soft morning light, golden hour glow"),
    (9 * 60, 12 * 60, "bright natural daylight"),
    (12 * 60, 14 * 60, "midday light, slightly high contrast"),
    (14 * 60, 17 * 60, "warm afternoon light"),
    (17 * 60, 19 * 60, "golden hour, sunset warm tones"),
    (19 * 60, 20 * 60, "dusk, blue hour ambient light"),
]
_DEFAULT_LIGHT = "bright natural daylight"

_IMAGE_TYPES = ("selfie", "daily", "scenery", "emotion")

# 同帖多图轻量构图变体（B）：主场景不变，仅按 seq 追加机位/构图后缀
_VARIANT_SELFIE = (
    "close-up face, slight camera angle",
    "medium shot, half body portrait",
    "side angle, candid over-shoulder feel",
    "subject smaller in frame, more environment visible",
)
_VARIANT_NON_SELFIE = (
    "wide establishing shot of the scene",
    "detail close-up of objects in the scene",
    "alternate camera angle of the same place",
    "different framing, another corner of the same setting",
)


def _time_period_light(time_range: str) -> str:
    """由 time_range 起点推导光线关键词。"""
    try:
        start = time_range.split("-")[0].strip()
        hh, mm = start.split(":")
        minutes = int(hh) * 60 + int(mm)
    except (ValueError, IndexError, AttributeError):
        return _DEFAULT_LIGHT
    for lo, hi, kw in _TIME_PERIOD_LIGHT:
        if lo <= minutes < hi:
            return kw
    return _DEFAULT_LIGHT


def _join_kw(value) -> str:
    """兜底关键词组（list）拼接为逗号串；字符串原样返回。"""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


class FeedImageService:
    """朋友圈图片生成（LiblibAI）"""

    # ---------- 抽签 ----------
    async def _draw_count(self) -> int:
        w0 = int(await get_life_feed_config(CONFIG_FEED_IMAGE_COUNT_0_WEIGHT, DEFAULT_FEED_IMAGE_COUNT_0_WEIGHT))
        w1 = int(await get_life_feed_config(CONFIG_FEED_IMAGE_COUNT_1_WEIGHT, DEFAULT_FEED_IMAGE_COUNT_1_WEIGHT))
        w23 = int(await get_life_feed_config(CONFIG_FEED_IMAGE_COUNT_2_3_WEIGHT, DEFAULT_FEED_IMAGE_COUNT_2_3_WEIGHT))
        w4 = int(await get_life_feed_config(CONFIG_FEED_IMAGE_COUNT_4_WEIGHT, DEFAULT_FEED_IMAGE_COUNT_4_WEIGHT))
        buckets = ["0", "1", "2-3", "4"]
        weights = [w0, w1, w23, w4]
        if sum(weights) <= 0:
            return 0
        bucket = random.choices(buckets, weights=weights, k=1)[0]
        if bucket == "0":
            return 0
        if bucket == "1":
            return 1
        if bucket == "4":
            return 4
        return random.choice([2, 3])  # 2-3 等概率

    async def _draw_type(self) -> str:
        ws = int(await get_life_feed_config(CONFIG_FEED_IMAGE_TYPE_SELFIE_WEIGHT, DEFAULT_FEED_IMAGE_TYPE_SELFIE_WEIGHT))
        wd = int(await get_life_feed_config(CONFIG_FEED_IMAGE_TYPE_DAILY_WEIGHT, DEFAULT_FEED_IMAGE_TYPE_DAILY_WEIGHT))
        wsc = int(await get_life_feed_config(CONFIG_FEED_IMAGE_TYPE_SCENERY_WEIGHT, DEFAULT_FEED_IMAGE_TYPE_SCENERY_WEIGHT))
        we = int(await get_life_feed_config(CONFIG_FEED_IMAGE_TYPE_EMOTION_WEIGHT, DEFAULT_FEED_IMAGE_TYPE_EMOTION_WEIGHT))
        weights = [ws, wd, wsc, we]
        if sum(weights) <= 0:
            return "selfie"
        return random.choices(list(_IMAGE_TYPES), weights=weights, k=1)[0]

    # ---------- 关键词映射与兜底 ----------
    async def _venue_keyword(self, venue_type: str, category: str) -> str:
        venue_map = await get_life_feed_config("venue_type_img_keyword", VENUE_TYPE_IMG_KEYWORD) or {}
        if venue_type in venue_map:
            return venue_map[venue_type]
        cat_map = await get_life_feed_config("category_img_keyword", CATEGORY_IMG_KEYWORD) or {}
        if category in cat_map:
            logger.info("[LLM-IMG] venue 未命中，回落 category=%s", category)
            return cat_map[category]
        return category or venue_type or ""

    async def _emotion_keyword_p12(self, emotion: str) -> str:
        emap = await get_life_feed_config("emotion_img_keyword", EMOTION_IMG_KEYWORD) or {}
        if emotion in emap:
            return emap[emotion]
        logger.info("[LLM-IMG] emotion 未命中（P-12），启用兜底")
        fb = await get_life_feed_config("emotion_fallback_img_keyword", EMOTION_FALLBACK_IMG_KEYWORD)
        return _join_kw(fb)

    async def _emotion_atmosphere_p13c(self, emotion: str) -> str:
        amap = await get_life_feed_config("emotion_atmosphere_desc", EMOTION_ATMOSPHERE_DESC) or {}
        if emotion in amap:
            return amap[emotion]
        logger.info("[LLM-IMG] emotion 未命中（P-13c），启用兜底")
        fb = await get_life_feed_config("emotion_fallback_atmosphere_desc", EMOTION_FALLBACK_ATMOSPHERE_DESC)
        return _join_kw(fb)

    # ---------- 组装 prompt ----------
    async def _build_prompt(self, image_type: str, ctx: dict) -> tuple[str, str, str]:
        """返回 (pos_prompt, neg_prompt, submit_uri)。"""
        season_kw = _SEASON_KEYWORD.get(ctx.get("season", ""), "")
        light_kw = _time_period_light(ctx.get("time_range", ""))
        venue_kw = await self._venue_keyword(ctx.get("venue_type", ""), ctx.get("category", ""))

        if image_type == "selfie":
            char_desc = await get_life_feed_config(
                CONFIG_LXM_IMG1_CHARACTER_DESC, DEFAULT_LXM_IMG1_CHARACTER_DESC)
            neg_base = await get_life_feed_config(
                CONFIG_LXM_IMG1_NEGATIVE_BASE, DEFAULT_LXM_IMG1_NEGATIVE_BASE)
            emo_kw = await self._emotion_keyword_p12(ctx.get("emotion", ""))
            pos = await render_prompt("prompt_p12_pos", {
                "lxm_img1_character_desc": char_desc,
                "venue_type_img_keyword": venue_kw,
                "season_keyword": season_kw,
                "time_period_light": light_kw,
                "emotion_img_keyword": emo_kw,
            })
            neg = await render_prompt("prompt_p12_neg", {"lxm_img1_negative_base": neg_base})
            return pos, neg, _IMG2IMG_URI

        if image_type == "daily":
            pos = await render_prompt("prompt_p13a_pos", {
                "venue_type_img_keyword": venue_kw,
                "season_keyword": season_kw, "time_period_light": light_kw,
            })
            neg = await render_prompt("prompt_p13a_neg", {})
            return pos, neg, _TEXT2IMG_URI

        if image_type == "scenery":
            pos = await render_prompt("prompt_p13b_pos", {
                "city": ctx.get("city", ""),
                "venue_type_img_keyword": venue_kw,
                "season_keyword": season_kw, "time_period_light": light_kw,
            })
            neg = await render_prompt("prompt_p13b_neg", {})
            return pos, neg, _TEXT2IMG_URI

        # emotion
        atmo = await self._emotion_atmosphere_p13c(ctx.get("emotion", ""))
        pos = await render_prompt("prompt_p13c_pos", {
            "emotion_atmosphere_desc": atmo,
            "season_keyword": season_kw, "time_period_light": light_kw,
        })
        neg = await render_prompt("prompt_p13c_neg", {})
        return pos, neg, _TEXT2IMG_URI

    async def _build_payload(self, image_type: str, pos: str, neg: str) -> dict | None:
        """组装 Liblib WebUI 官方结构；UUID 缺失时返回 None（调用方记失败并降级）。"""
        if image_type == "selfie":
            template_uuid = str(await get_life_feed_config(
                CONFIG_LIBLIB_IMG2IMG_TEMPLATE_UUID, DEFAULT_LIBLIB_IMG2IMG_TEMPLATE_UUID) or "").strip()
        else:
            template_uuid = str(await get_life_feed_config(
                CONFIG_LIBLIB_TEXT2IMG_TEMPLATE_UUID, DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID) or "").strip()

        if not template_uuid:
            logger.error(
                "[LLM-IMG] templateUuid 未配置 image_type=%s（请在后台填写 liblib_*_template_uuid）",
                image_type,
            )
            return None

        steps = int(await get_life_feed_config(CONFIG_LIBLIB_GEN_STEPS, DEFAULT_LIBLIB_GEN_STEPS))
        width = int(await get_life_feed_config(CONFIG_LIBLIB_GEN_WIDTH, DEFAULT_LIBLIB_GEN_WIDTH))
        height = int(await get_life_feed_config(CONFIG_LIBLIB_GEN_HEIGHT, DEFAULT_LIBLIB_GEN_HEIGHT))

        generate_params: dict = {
            "prompt": pos,
            "negativePrompt": neg,
            "steps": steps,
            "width": width,
            "height": height,
            "imgCount": 1,
            "seed": -1,
            "restoreFaces": 0,
        }
        if image_type == "selfie":
            generate_params["sourceImage"] = get_feed_image_reference_public_url()
            strength = await get_life_feed_config(
                CONFIG_LIBLIB_IMG2IMG_STRENGTH, DEFAULT_LIBLIB_IMG2IMG_STRENGTH)
            try:
                generate_params["strength"] = float(strength)
            except (TypeError, ValueError):
                generate_params["strength"] = DEFAULT_LIBLIB_IMG2IMG_STRENGTH
            # 图生图必填：参考图缩放目标尺寸（与出图 width/height 独立可配）
            generate_params["resizedWidth"] = int(await get_life_feed_config(
                CONFIG_LIBLIB_IMG2IMG_RESIZED_WIDTH, DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH))
            generate_params["resizedHeight"] = int(await get_life_feed_config(
                CONFIG_LIBLIB_IMG2IMG_RESIZED_HEIGHT, DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT))

        return {
            "templateUuid": template_uuid,
            "generateParams": generate_params,
        }

    @staticmethod
    def _composition_variant(image_type: str, seq: int) -> str:
        """按 seq（从 1 起）取构图变体短句。"""
        variants = _VARIANT_SELFIE if image_type == "selfie" else _VARIANT_NON_SELFIE
        return variants[(seq - 1) % len(variants)]

    def _payload_for_seq(
        self, base_payload: dict, base_pos: str, image_type: str, seq: int, count: int,
    ) -> dict:
        """
        单张任务 payload：深拷贝后按张数决定是否追加构图变体与独立 seed。
        count==1 时保持步骤①行为（无变体后缀，seed=-1）。
        """
        payload = copy.deepcopy(base_payload)
        gp = payload["generateParams"]
        if count >= 2:
            variant = self._composition_variant(image_type, seq)
            gp["prompt"] = f"{base_pos}, {variant}"
            gp["seed"] = random.randint(1, 2**31 - 1)
            logger.info(
                "[LLM-IMG] 多图变体 seq=%d seed=%s variant=%s",
                seq, gp["seed"], variant,
            )
        else:
            gp["prompt"] = base_pos
            gp["seed"] = -1
        gp["imgCount"] = 1
        return payload

    # ---------- 下载 + 压缩 + 上传 ----------
    async def _download_compress_upload(self, image_url: str, post_id: int, seq: int) -> str | None:
        """下载 LiblibAI 图片 → WebP(q85) → OSS，返回 CDN URL。临时文件 try/finally 清理。"""
        import httpx  # 惰性导入

        tmp_path = f"/tmp/lxm-feed-{uuid.uuid4().hex}.jpg"
        oss_key = f"lxm/posts/{post_id}/{seq:02d}.webp"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)

            webp_bytes = await asyncio.to_thread(self._to_webp, tmp_path)
            await asyncio.to_thread(self._oss_put, oss_key, webp_bytes)

            cdn = get_oss_cdn_domain()
            return f"https://{cdn}/{oss_key}"
        except Exception as e:
            logger.warning("[LLM-IMG] 下载/压缩/上传失败 seq=%d: %s", seq, e)
            return None
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _to_webp(jpg_path: str) -> bytes:
        import io

        from PIL import Image  # 惰性导入

        with Image.open(jpg_path) as im:
            buf = io.BytesIO()
            im.save(buf, format="WEBP", quality=85)
            return buf.getvalue()

    @staticmethod
    def _oss_put(oss_key: str, data: bytes) -> None:
        import oss2  # 惰性导入

        auth = oss2.Auth(get_oss_access_key_id(), get_oss_access_key_secret())
        bucket = oss2.Bucket(auth, get_oss_endpoint(), get_oss_bucket())
        bucket.put_object(oss_key, data)

    # ---------- 单张流程 ----------
    async def _gen_one(self, seq: int, image_type: str, pos: str, neg: str,
                       uri: str, payload: dict, post_id: int) -> str | None:
        async with liblib_client.concurrency_sem:
            await self._record_stats("total")
            try:
                task_id = await liblib_client.submit_task(uri, payload)
                image_url = await liblib_client.poll_task(_STATUS_URI, task_id, _SINGLE_POLL_TIMEOUT)
            except Exception as e:
                logger.warning("[LLM-IMG] 提交/轮询失败 seq=%d: %s", seq, e)
                await self._record_stats("failed")
                return None

            if not image_url:
                await self._record_stats("failed")
                return None

            cdn_url = await self._download_compress_upload(image_url, post_id, seq)
            await self._record_stats("success" if cdn_url else "failed")
            return cdn_url

    # ---------- 统计 ----------
    async def _record_stats(self, field: str, points: int = 0) -> None:
        today = datetime.date.today().strftime("%Y%m%d")
        try:
            r = await get_redis()
            await r.hincrby(f"liblib_stats:{today}", field, 1)
            if points:
                await r.hincrby(f"liblib_stats:{today}", "points_used", points)
            await r.expire(f"liblib_stats:{today}", 172800)
        except Exception as e:
            logger.error("liblib stats 写入失败: %s", e)

    # ---------- 主入口 ----------
    async def generate_images(self, post_context: dict) -> list[str]:
        """
        为一条朋友圈生成图片，返回 CDN URL 数组（可能为空 = 纯文字帖）。

        post_context 需含：post_id / venue_type / category / city / time_range / emotion / season
        可选：image_count / image_type（外部指定则跳过抽签，主要供测试与 STEP-013 记录）
        """
        post_id = post_context.get("post_id")
        count = post_context.get("image_count")
        if count is None:
            count = await self._draw_count()
        if count <= 0:
            logger.info("[LLM-IMG] 张数抽签=0，纯文字帖 post_id=%s", post_id)
            return []

        image_type = post_context.get("image_type") or await self._draw_type()
        post_context["image_type"] = image_type  # 回写供 STEP-013 落库
        logger.info("[LLM-IMG] 开始生成 post_id=%s 类型=%s 张数=%d", post_id, image_type, count)

        pos, neg, uri = await self._build_prompt(image_type, post_context)
        payload = await self._build_payload(image_type, pos, neg)
        if payload is None:
            logger.warning("[LLM-IMG] payload 无法组装，降级纯文字 post_id=%s", post_id)
            return []

        tasks = [
            asyncio.create_task(
                self._gen_one(
                    seq, image_type, pos, neg, uri,
                    self._payload_for_seq(payload, pos, image_type, seq, count),
                    post_id,
                )
            )
            for seq in range(1, count + 1)
        ]
        try:
            await asyncio.wait(tasks, timeout=_BATCH_TIMEOUT)
        except Exception as e:
            logger.error("[LLM-IMG] 整批等待异常 post_id=%s: %s", post_id, e)

        urls: list[str] = []
        for t in tasks:
            if not t.done():
                t.cancel()
                logger.warning("[LLM-IMG] 整批超时未完成，取消一张 post_id=%s", post_id)
                continue
            try:
                r = t.result()
            except Exception:
                r = None
            if r:
                urls.append(r)

        if not urls:
            logger.warning("[LLM-IMG] 全部图片失败，降级纯文字 post_id=%s", post_id)
        else:
            logger.info("[LLM-IMG] 完成 post_id=%s 成功 %d/%d 张", post_id, len(urls), count)
        return urls


# 全局单例
feed_image_service = FeedImageService()
