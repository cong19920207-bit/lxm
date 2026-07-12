# -*- coding: utf-8 -*-
# 生活流·每日发布整合服务（STEP-013 · LIFE001 01:00）
#
# 编排：读当日 ready life_plan → 抽发布数量 → 逐条（文案 + 图片）→ 落库 feed_post。
# actual_publish_time 落 NULL（§0.5：STEP-015 首次到点懒写回）；scheduled_publish_time 控制可见。

import logging
import random
from datetime import date, datetime, timedelta

from sqlalchemy import select

from backend.config import get_feed_image_reference_public_url
from backend.constants.life_feed_config import (
    CONFIG_FEED_AUTO_PUBLISH_ENABLED,
    CONFIG_FEED_BASE_LIKES_MAX,
    CONFIG_FEED_BASE_LIKES_MIN,
    CONFIG_FEED_DAILY_POST_COUNT_2_WEIGHT,
    CONFIG_FEED_DAILY_POST_COUNT_3_WEIGHT,
    CONFIG_FEED_LIKE_MULTIPLIER_MAX,
    CONFIG_FEED_LIKE_MULTIPLIER_MIN,
    CONFIG_FEED_PUBLISH_WINDOW_1,
    CONFIG_FEED_PUBLISH_WINDOW_2,
    CONFIG_FEED_PUBLISH_WINDOW_3,
    CONFIG_SOUTHERN_HEMISPHERE_CITIES,
    DEFAULT_FEED_AUTO_PUBLISH_ENABLED,
    DEFAULT_FEED_BASE_LIKES_MAX,
    DEFAULT_FEED_BASE_LIKES_MIN,
    DEFAULT_FEED_DAILY_POST_COUNT_2_WEIGHT,
    DEFAULT_FEED_DAILY_POST_COUNT_3_WEIGHT,
    DEFAULT_FEED_LIKE_MULTIPLIER_MAX,
    DEFAULT_FEED_LIKE_MULTIPLIER_MIN,
    DEFAULT_FEED_PUBLISH_WINDOW_1,
    DEFAULT_FEED_PUBLISH_WINDOW_2,
    DEFAULT_FEED_PUBLISH_WINDOW_3,
    DEFAULT_SOUTHERN_HEMISPHERE_CITIES,
)
from backend.database import async_session_maker
from backend.models.feed_post import FeedPost
from backend.models.life_plan import LifePlan
from backend.models.worldview_snapshot import WorldviewSnapshot
from backend.services.feed_content_service import (
    ContentSafetyException,
    DedupHitException,
    FeedContentError,
    SimilarityHitException,
    feed_content_service,
)
from backend.services.feed_image_service import feed_image_service
from backend.services.life_feed_config_service import get_life_feed_config
from backend.utils.season_utils import compute_season

logger = logging.getLogger(__name__)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


class FeedPublishService:
    """每日发布整合（LIFE001）"""

    async def _draw_post_count(self) -> int:
        w2 = int(await get_life_feed_config(
            CONFIG_FEED_DAILY_POST_COUNT_2_WEIGHT, DEFAULT_FEED_DAILY_POST_COUNT_2_WEIGHT))
        w3 = int(await get_life_feed_config(
            CONFIG_FEED_DAILY_POST_COUNT_3_WEIGHT, DEFAULT_FEED_DAILY_POST_COUNT_3_WEIGHT))
        if w2 + w3 <= 0:
            return 2
        return random.choices([2, 3], weights=[w2, w3], k=1)[0]

    async def _load_windows(self) -> list[str]:
        return [
            await get_life_feed_config(CONFIG_FEED_PUBLISH_WINDOW_1, DEFAULT_FEED_PUBLISH_WINDOW_1),
            await get_life_feed_config(CONFIG_FEED_PUBLISH_WINDOW_2, DEFAULT_FEED_PUBLISH_WINDOW_2),
            await get_life_feed_config(CONFIG_FEED_PUBLISH_WINDOW_3, DEFAULT_FEED_PUBLISH_WINDOW_3),
        ]

    @staticmethod
    def _random_time_in_window(plan_date: date, window: str) -> datetime:
        """在 'HH:MM-HH:MM' 窗口内随机取一时刻（Asia/Shanghai 本地日期）。"""
        try:
            start_s, end_s = window.split("-")
            sh, sm = (int(x) for x in start_s.strip().split(":"))
            eh, em = (int(x) for x in end_s.strip().split(":"))
        except (ValueError, AttributeError):
            sh, sm, eh, em = 10, 0, 12, 0
        start_dt = datetime(plan_date.year, plan_date.month, plan_date.day, sh, sm)
        end_dt = datetime(plan_date.year, plan_date.month, plan_date.day, eh, em)
        span = max(int((end_dt - start_dt).total_seconds()), 0)
        return start_dt + timedelta(seconds=random.randint(0, span) if span else 0)

    async def _load_snapshots(self, plan_date: date) -> dict:
        async with async_session_maker() as db:
            rows = (await db.execute(
                select(WorldviewSnapshot).where(WorldviewSnapshot.plan_date == plan_date)
            )).scalars().all()
        return {r.scene_id: r for r in rows}

    async def _insert_post(self, scene: dict, draft: dict, sched: datetime,
                           season: str, plan_date: date) -> int:
        base_min = int(await get_life_feed_config(CONFIG_FEED_BASE_LIKES_MIN, DEFAULT_FEED_BASE_LIKES_MIN))
        base_max = int(await get_life_feed_config(CONFIG_FEED_BASE_LIKES_MAX, DEFAULT_FEED_BASE_LIKES_MAX))
        mul_min = int(await get_life_feed_config(CONFIG_FEED_LIKE_MULTIPLIER_MIN, DEFAULT_FEED_LIKE_MULTIPLIER_MIN))
        mul_max = int(await get_life_feed_config(CONFIG_FEED_LIKE_MULTIPLIER_MAX, DEFAULT_FEED_LIKE_MULTIPLIER_MAX))
        async with async_session_maker() as db:
            post = FeedPost(
                scene_id=scene.get("scene_id"),
                scheduled_publish_time=sched,
                actual_publish_time=None,
                generation_status="generating",
                content_text=draft["post_text"],
                hashtags=draft.get("hashtags") or [],
                image_urls=None,
                image_reference_url=get_feed_image_reference_public_url(),
                image_type=None,
                emotion=draft["emotion"],
                city=scene.get("city", ""),
                season=season,
                base_likes=random.randint(base_min, base_max),
                like_multiplier=random.randint(mul_min, mul_max),
                real_likes=0,
                # 评论展示假数与点赞共用同一组 min/max 配置
                base_comments=random.randint(base_min, base_max),
                comment_multiplier=random.randint(mul_min, mul_max),
                is_visible=1,
                dedup_hash=draft["dedup_hash"],
                created_at=datetime.utcnow(),
            )
            db.add(post)
            await db.commit()
            await db.refresh(post)
            return post.id

    async def _finalize_post(self, post_id: int, image_urls: list, image_type: str | None) -> None:
        async with async_session_maker() as db:
            post = (await db.execute(
                select(FeedPost).where(FeedPost.id == post_id)
            )).scalars().first()
            if post is None:
                return
            post.image_urls = image_urls or None
            post.image_type = image_type
            post.generation_status = "ready"
            await db.commit()

    async def run_daily_publish(self, plan_date: date) -> dict:
        """01:00 每日发布整合。返回 {status, success, skipped, failed}。"""
        logger.info("[LIFE001] 发布任务触发 plan_date=%s", plan_date)

        enabled = await get_life_feed_config(
            CONFIG_FEED_AUTO_PUBLISH_ENABLED, DEFAULT_FEED_AUTO_PUBLISH_ENABLED)
        if not _as_bool(enabled):
            logger.info("[LIFE001] 自动发布开关关闭，跳过 plan_date=%s", plan_date)
            return {"status": "skipped_disabled", "success": 0, "skipped": 0, "failed": 0}

        async with async_session_maker() as db:
            life_plan = (await db.execute(
                select(LifePlan).where(LifePlan.plan_date == plan_date)
            )).scalars().first()
        if life_plan is None or life_plan.gen_status != "ready":
            logger.info("[LIFE001] 当日无 ready 生活计划，跳过 plan_date=%s", plan_date)
            return {"status": "skipped_no_plan", "success": 0, "skipped": 0, "failed": 0}

        scenes = sorted(life_plan.scenes or [], key=lambda s: s.get("time_range", ""))
        if not scenes:
            logger.info("[LIFE001] 当日场景为空，跳过 plan_date=%s", plan_date)
            return {"status": "done", "success": 0, "skipped": 0, "failed": 0}

        target = await self._draw_post_count()
        n = min(target, len(scenes))
        selected = scenes[:n]
        logger.info("[LIFE001] 发布数量：随机=%d 可用场景=%d 最终=%d", target, len(scenes), n)

        windows = await self._load_windows()
        snap_map = await self._load_snapshots(plan_date)
        southern = await get_life_feed_config(
            CONFIG_SOUTHERN_HEMISPHERE_CITIES, DEFAULT_SOUTHERN_HEMISPHERE_CITIES)

        success = skipped = failed = 0
        for i, scene in enumerate(selected):
            scene_id = scene.get("scene_id", "?")
            snapshot = snap_map.get(scene_id)
            # 快照 generating 视同 failed 降级（feed_content 非 ready 路径自然处理）

            dh = None
            try:
                draft = await feed_content_service.generate_post_text(scene, snapshot, plan_date)
            except (DedupHitException, SimilarityHitException, ContentSafetyException) as e:
                logger.info("[LIFE001] 场景跳过 scene_id=%s: %s", scene_id, e)
                skipped += 1
                continue
            except FeedContentError as e:
                logger.error("[LIFE001] 文案生成失败 scene_id=%s: %s", scene_id, e)
                failed += 1
                continue

            window = windows[i] if i < len(windows) else windows[-1]
            sched = self._random_time_in_window(plan_date, window)
            season = compute_season(scene.get("city", ""), plan_date, southern)

            post_id = await self._insert_post(scene, draft, sched, season, plan_date)

            post_ctx = {
                "post_id": post_id,
                "venue_type": scene.get("venue_type", ""),
                "category": scene.get("category", ""),
                "city": scene.get("city", ""),
                "time_range": scene.get("time_range", ""),
                "emotion": draft["emotion"],
                "season": season,
            }
            try:
                urls = await feed_image_service.generate_images(post_ctx)
            except Exception as e:
                logger.warning("[LIFE001] 图片生成异常 post_id=%s: %s", post_id, e)
                urls = []

            await self._finalize_post(post_id, urls, post_ctx.get("image_type"))
            logger.info(
                "[LIFE001] Feed 落库成功 post_id=%s scheduled=%s 图片=%d 张",
                post_id, sched, len(urls),
            )
            success += 1

        logger.info(
            "[LIFE001] 整体完成 plan_date=%s 成功=%d 跳过=%d 失败=%d",
            plan_date, success, skipped, failed,
        )
        return {"status": "done", "success": success, "skipped": skipped, "failed": failed}


# 全局单例
feed_publish_service = FeedPublishService()
