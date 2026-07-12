# -*- coding: utf-8 -*-
# 生活流·朋友圈文案生成服务（STEP-011 · LLM-04）
#
# 只负责「单条文案」核心逻辑，不含图片、不含定时发布整合、不落库（落库由 STEP-013）。
# 覆盖：emotion 双路径 / 结构化去重 / 文本相似度过滤 / 旅游叙事阶段 / hashtag 抽签 / 内容安全。

import json
import logging
import random
import re
from datetime import date, datetime, timedelta

from sqlalchemy import select

from backend.constants.life_feed_config import (
    CONFIG_EMOTION_VOCAB,
    CONFIG_FEED_HASHTAG_COUNT_0_WEIGHT,
    CONFIG_FEED_HASHTAG_COUNT_1_WEIGHT,
    CONFIG_FEED_HASHTAG_COUNT_2_WEIGHT,
    CONFIG_FEED_HASHTAG_COUNT_3_WEIGHT,
    CONFIG_FEED_TEXT_SIMILARITY_THRESHOLD,
    CONFIG_HOME_CITY,
    CONFIG_LXM_CONTENT_LIMITS,
    CONFIG_LXM_WRITING_STYLE,
    DEFAULT_EMOTION_VOCAB,
    DEFAULT_FEED_HASHTAG_COUNT_0_WEIGHT,
    DEFAULT_FEED_HASHTAG_COUNT_1_WEIGHT,
    DEFAULT_FEED_HASHTAG_COUNT_2_WEIGHT,
    DEFAULT_FEED_HASHTAG_COUNT_3_WEIGHT,
    DEFAULT_FEED_TEXT_SIMILARITY_THRESHOLD,
    DEFAULT_HOME_CITY,
    DEFAULT_LXM_CONTENT_LIMITS,
    DEFAULT_LXM_WRITING_STYLE,
)
from backend.database import async_session_maker
from backend.models.feed_post import FeedPost
from backend.models.life_plan_outline import LifePlanOutline
from backend.services.content_safety_service import check_content
from backend.services.deepseek_llm_service import deepseek_llm_service
from backend.services.life_feed_config_service import get_life_feed_config
from backend.services.life_prompt_service import render_prompt
from backend.utils.hash_utils import compute_dedup_hash

logger = logging.getLogger(__name__)

_DEDUP_WINDOW_DAYS = 7
_SIMILARITY_WINDOW_DAYS = 7

# 旅游阶段 → 中文标签 / P-05 prompt key
_TRAVEL_STAGE_LABEL = {
    "departure": "出发", "transit": "途中", "return": "返回", "oneday": "一日游",
}
_TRAVEL_STAGE_PROMPT_KEY = {
    "departure": "prompt_p05_departure",
    "transit": "prompt_p05_transit",
    "return": "prompt_p05_return",
    "oneday": "prompt_p05_oneday",
}

_FENCE_HEAD = re.compile(r"^```[a-zA-Z]*\s*")
_FENCE_TAIL = re.compile(r"\s*```$")


class FeedContentError(Exception):
    """文案生成/解析失败（技术失败，调用方放弃该条）"""
    pass


class DedupHitException(Exception):
    """结构化去重命中（PRD 4.5.1）"""
    def __init__(self, scene_id: str, hit_post_id: int):
        self.scene_id = scene_id
        self.hit_post_id = hit_post_id
        super().__init__(f"dedup 命中 scene_id={scene_id} hit_post_id={hit_post_id}")


class SimilarityHitException(Exception):
    """文本相似度命中（PRD 4.5.2）"""
    def __init__(self, scene_id: str, hit_post_id: int, score: float):
        self.scene_id = scene_id
        self.hit_post_id = hit_post_id
        self.score = score
        super().__init__(
            f"相似度命中 scene_id={scene_id} hit_post_id={hit_post_id} score={score:.3f}"
        )


class ContentSafetyException(Exception):
    """内容安全违规（项目惯例）"""
    def __init__(self, scene_id: str, reason: str):
        self.scene_id = scene_id
        self.reason = reason
        super().__init__(f"内容安全违规 scene_id={scene_id}: {reason}")


# ──────────────────── 纯函数：相似度 ────────────────────

def bi_gram_set(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text or "")
    return {text[i:i + 2] for i in range(len(text) - 1)}


def jaccard(a: str, b: str) -> float:
    sa, sb = bi_gram_set(a), bi_gram_set(b)
    return len(sa & sb) / max(len(sa | sb), 1)


def _strip_fence(text: str) -> str:
    s = (text or "").strip()
    s = _FENCE_HEAD.sub("", s)
    s = _FENCE_TAIL.sub("", s)
    return s.strip()


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _snapshot_field(snapshot, field: str):
    if snapshot is None:
        return None
    if isinstance(snapshot, dict):
        return snapshot.get(field)
    return getattr(snapshot, field, None)


def _snapshot_ready(snapshot) -> bool:
    return _snapshot_field(snapshot, "gen_status") == "ready"


class FeedContentService:
    """LLM-04 单条朋友圈文案生成"""

    # ---------- 去重 ----------
    async def _check_dedup(self, dedup_hash: str, scene_id: str, now: datetime) -> None:
        cutoff = now - timedelta(days=_DEDUP_WINDOW_DAYS)
        async with async_session_maker() as db:
            stmt = select(FeedPost).where(
                FeedPost.dedup_hash == dedup_hash,
                FeedPost.created_at >= cutoff,
            )
            rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            is_ready = row.generation_status == "ready"
            is_future = row.scheduled_publish_time and row.scheduled_publish_time > now
            if is_ready or is_future:
                raise DedupHitException(scene_id, row.id)

    # ---------- 相似度 ----------
    async def _check_similarity(
        self, post_text: str, scene_id: str, threshold: float, now: datetime
    ) -> None:
        cutoff = now - timedelta(days=_SIMILARITY_WINDOW_DAYS)
        async with async_session_maker() as db:
            stmt = select(FeedPost).where(
                FeedPost.generation_status == "ready",
                FeedPost.created_at >= cutoff,
            )
            rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            score = jaccard(post_text, row.content_text or "")
            if score >= threshold:
                raise SimilarityHitException(scene_id, row.id, score)

    # ---------- 旅游叙事 ----------
    async def _determine_travel(
        self, plan_date: date, today_city: str, home_city: str
    ) -> dict | None:
        """
        判定旅游阶段（PRD 4.6）。今日为主场城市返回 None（不注入旅游段）。
        返回 {stage, label, prompt_key, week_city_sequence, travel_day_index}。
        注：因长途旅游限定同一自然周内收尾（PRD 2.2.3），昨日/明日跨周一律按主场城市处理。
        """
        if today_city == home_city:
            return None

        monday = _monday_of(plan_date)
        async with async_session_maker() as db:
            stmt = select(LifePlanOutline).where(
                LifePlanOutline.week_start_date == monday
            ).order_by(LifePlanOutline.plan_date)
            rows = (await db.execute(stmt)).scalars().all()
        week_map = {r.plan_date: r.city for r in rows}

        y_city = week_map.get(plan_date - timedelta(days=1))
        m_city = week_map.get(plan_date + timedelta(days=1))
        y_home = (y_city is None) or (y_city == home_city)
        m_home = (m_city == home_city)

        if y_home and not m_home:
            stage = "departure"
        elif y_home and m_home:
            stage = "oneday"
        elif (not y_home) and m_home:
            stage = "return"
        else:
            stage = "transit"

        # 旅程第几天：从今日向前连续非主场天数
        idx = 1
        d = plan_date - timedelta(days=1)
        while True:
            c = week_map.get(d)
            if c is None or c == home_city:
                break
            idx += 1
            d -= timedelta(days=1)

        seq = "→".join(r.city for r in rows) if rows else today_city
        return {
            "stage": stage,
            "label": _TRAVEL_STAGE_LABEL[stage],
            "prompt_key": _TRAVEL_STAGE_PROMPT_KEY[stage],
            "week_city_sequence": seq,
            "travel_day_index": idx,
        }

    # ---------- hashtag 抽签 ----------
    async def _draw_hashtag_count(self) -> int:
        w0 = await get_life_feed_config(CONFIG_FEED_HASHTAG_COUNT_0_WEIGHT, DEFAULT_FEED_HASHTAG_COUNT_0_WEIGHT)
        w1 = await get_life_feed_config(CONFIG_FEED_HASHTAG_COUNT_1_WEIGHT, DEFAULT_FEED_HASHTAG_COUNT_1_WEIGHT)
        w2 = await get_life_feed_config(CONFIG_FEED_HASHTAG_COUNT_2_WEIGHT, DEFAULT_FEED_HASHTAG_COUNT_2_WEIGHT)
        w3 = await get_life_feed_config(CONFIG_FEED_HASHTAG_COUNT_3_WEIGHT, DEFAULT_FEED_HASHTAG_COUNT_3_WEIGHT)
        weights = [int(w0), int(w1), int(w2), int(w3)]
        if sum(weights) <= 0:
            return 0
        return random.choices([0, 1, 2, 3], weights=weights, k=1)[0]

    @staticmethod
    def _hashtag_hint(count: int) -> str:
        if count <= 0:
            return "这条朋友圈不生成任何话题标签，hashtags 字段返回空数组 []"
        return f"这条朋友圈请自然地带上约 {count} 个话题标签（#话题词）"

    # ---------- 主流程 ----------
    async def generate_post_text(
        self,
        scene: dict,
        snapshot,
        plan_date: date,
        *,
        skip_dedup_checks: bool = False,
    ) -> dict:
        """
        生成单条朋友圈文案草稿（不落库）。

        Args:
            skip_dedup_checks: True 时跳过结构化去重与文本相似度（后台 ai_generate 管理员权威）

        Returns:
            PostDraft = {post_text, hashtags: list[str], emotion: str, dedup_hash, travel_stage}

        Raises:
            DedupHitException / SimilarityHitException / ContentSafetyException / FeedContentError
        """
        scene_id = scene.get("scene_id", "?")
        venue_type = scene.get("venue_type", "")
        category = scene.get("category", "")
        city = scene.get("city", "")
        description = scene.get("description", "")
        time_range = scene.get("time_range", "")
        now = datetime.utcnow()

        # 1. 结构化去重（生成前；管理员 ai_generate 可跳过）
        dedup_hash = compute_dedup_hash(venue_type, category, city)
        if not skip_dedup_checks:
            await self._check_dedup(dedup_hash, scene_id, now)

        home_city = await get_life_feed_config(CONFIG_HOME_CITY, DEFAULT_HOME_CITY)
        emotion_vocab = await get_life_feed_config(CONFIG_EMOTION_VOCAB, DEFAULT_EMOTION_VOCAB)
        emotion_vocab_str = "、".join(emotion_vocab) if isinstance(emotion_vocab, list) else str(emotion_vocab)
        writing_style = await get_life_feed_config(CONFIG_LXM_WRITING_STYLE, DEFAULT_LXM_WRITING_STYLE)
        content_limits = await get_life_feed_config(CONFIG_LXM_CONTENT_LIMITS, DEFAULT_LXM_CONTENT_LIMITS)

        # 2. emotion 双路径
        snap_ready = _snapshot_ready(snapshot)
        emotion_source = "复制自快照" if snap_ready else "LLM-04 附带生成"

        # 5. 旅游叙事
        travel = await self._determine_travel(plan_date, city, home_city)

        # 6. hashtag 抽签
        hashtag_count = await self._draw_hashtag_count()

        logger.info(
            "[LLM-04] 文案生成开始 scene_id=%s 快照增强=%s emotion来源=%s 旅游阶段=%s hashtag=%d",
            scene_id, snap_ready, emotion_source,
            (travel["stage"] if travel else "无"), hashtag_count,
        )

        # 组装变量
        user_vars = {
            "time_range": time_range,
            "city": city,
            "category": category,
            "venue_type": venue_type,
            "description": description,
            "emotion_vocab": emotion_vocab_str,
            "hashtag_hint": self._hashtag_hint(hashtag_count),
        }
        if snap_ready:
            user_vars.update({
                "emotion_value": _snapshot_field(snapshot, "emotion_value") or "",
                "focus_tag": _snapshot_field(snapshot, "focus_tag") or "",
                "feeling_text": _snapshot_field(snapshot, "feeling_text") or "",
            })
        if travel:
            travel_hint = await render_prompt(travel["prompt_key"], {})
            user_vars.update({
                "week_city_sequence": travel["week_city_sequence"],
                "travel_day_index": travel["travel_day_index"],
                "travel_stage": travel["label"],
                "travel_stage_hint": travel_hint,
            })

        optional_segments = {
            "快照": snap_ready,
            "快照缺失": not snap_ready,
            "旅游": travel is not None,
        }

        system_prompt = await render_prompt(
            "prompt_p04_system",
            {"lxm_writing_style": writing_style, "lxm_content_limits": content_limits},
        )
        user_prompt = await render_prompt("prompt_p04_user", user_vars, optional_segments)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 调 LLM
        try:
            raw = await deepseek_llm_service.call_llm("llm_04", messages)
            data = json.loads(_strip_fence(raw))
        except Exception as e:
            logger.error("[LLM-04] 文案生成失败 scene_id=%s: %s", scene_id, e)
            raise FeedContentError(f"LLM-04 调用/解析失败: {e}") from e

        if not isinstance(data, dict):
            raise FeedContentError("LLM-04 输出顶层不是对象")
        post_text = str(data.get("post_text", "")).strip()
        if not post_text:
            raise FeedContentError("post_text 为空")
        hashtags = data.get("hashtags") or []
        if not isinstance(hashtags, list):
            hashtags = []

        # emotion 双路径取值
        if snap_ready:
            emotion = str(_snapshot_field(snapshot, "emotion_value") or "").strip()
            if not emotion:
                raise FeedContentError("快照 ready 但 emotion_value 为空")
        else:
            emotion = str(data.get("emotion", "")).strip()
            if not emotion:
                raise FeedContentError("快照缺失路径下 LLM-04 未输出 emotion")

        # 4. 文本相似度过滤（管理员 ai_generate 可跳过）
        if not skip_dedup_checks:
            threshold = await get_life_feed_config(
                CONFIG_FEED_TEXT_SIMILARITY_THRESHOLD, DEFAULT_FEED_TEXT_SIMILARITY_THRESHOLD
            )
            await self._check_similarity(post_text, scene_id, float(threshold), now)

        # 7. 内容安全
        result = await check_content(post_text)
        if not result.get("is_safe", True):
            raise ContentSafetyException(scene_id, result.get("reason", ""))

        logger.info("[LLM-04] 文案生成成功 scene_id=%s", scene_id)
        return {
            "post_text": post_text,
            "hashtags": [str(h).strip() for h in hashtags if str(h).strip()],
            "emotion": emotion,
            "dedup_hash": dedup_hash,
            "travel_stage": travel["stage"] if travel else None,
        }


# 全局单例
feed_content_service = FeedContentService()
