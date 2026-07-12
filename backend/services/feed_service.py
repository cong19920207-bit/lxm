# -*- coding: utf-8 -*-
# 生活流·朋友圈用户端服务（STEP-015 列表/enter/badge、STEP-016 点赞、STEP-017 评论）
#
# 逻辑集中在此服务层，routers/feed.py 为薄封装。所有查询强制 is_visible=1 + 已到点，
# 隐藏帖对用户完全不可见（PRD 5.8）。
# scheduled_publish_time 与到点比较均为 Asia/Shanghai 墙钟（见 feed_now）。

import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ERR_COMMENT_EMPTY,
    ERR_COMMENT_RATE_LIMIT,
    ERR_COMMENT_TOO_LONG,
    ERR_CONTENT_SAFETY_VIOLATION,
    ERR_FEED_COMMENT_FORBIDDEN,
    ERR_FEED_POST_NOT_FOUND,
)
from backend.constants.life_feed_config import (
    CONFIG_FEED_HISTORY_VISIBLE_RANGE,
    CONFIG_FEED_PAGE_DISPLAY_NICKNAME,
    CONFIG_FEED_PAGE_HEADER_AVATAR_URL,
    CONFIG_FEED_PAGE_HEADER_BG_URL,
    CONFIG_FEED_PAGE_SIGNATURE,
    CONFIG_HOME_CITY,
    DEFAULT_COMMENT_REPLY_DELAY_SEC,
    DEFAULT_FEED_HISTORY_VISIBLE_RANGE,
    DEFAULT_FEED_PAGE_DISPLAY_NICKNAME,
    DEFAULT_FEED_PAGE_HEADER_AVATAR_URL,
    DEFAULT_FEED_PAGE_HEADER_BG_URL,
    DEFAULT_FEED_PAGE_SIGNATURE,
    DEFAULT_HOME_CITY,
    comment_reply_delay_key,
    level_to_stage,
)
from backend.models.feed_comment import FeedComment
from backend.models.feed_like import FeedLike
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.services import content_safety_service
from backend.services import like_aware_service
from backend.services.life_feed_config_service import get_life_feed_config

logger = logging.getLogger(__name__)

_MAX_COMMENT_LEN = 200
_COMMENT_RATE_WINDOW_SEC = 30
_FIRST_COMMENT_OVERRIDE_SEC = 30
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 50
_RANGE_DAYS = {"7d": 7, "30d": 30, "180d": 180}
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class FeedError(Exception):
    """朋友圈业务错误，携带统一错误码。"""
    def __init__(self, code: int):
        self.code = code
        super().__init__(f"feed error code={code}")


def feed_now() -> datetime:
    """朋友圈业务当前时间：Asia/Shanghai 墙钟（naive，与 scheduled_publish_time 对齐）。"""
    return datetime.now(_SHANGHAI_TZ).replace(tzinfo=None)


def _display_likes(post: FeedPost) -> int:
    return post.base_likes * post.like_multiplier + post.real_likes


def _display_comments(post: FeedPost, real_count: int) -> int:
    """展示评论数 = base_comments × comment_multiplier + 当前用户可见评论条数。"""
    return post.base_comments * post.comment_multiplier + max(0, int(real_count or 0))


async def _get_visible_post(db: AsyncSession, post_id: int, now: datetime) -> FeedPost:
    """取一条对用户可见（is_visible=1 且已到点）的帖子；否则抛 FeedError。"""
    post = (await db.execute(
        select(FeedPost).where(FeedPost.id == post_id)
    )).scalars().first()
    if post is None or post.is_visible != 1 or post.scheduled_publish_time > now:
        raise FeedError(ERR_FEED_POST_NOT_FOUND)
    return post


class FeedService:
    """朋友圈用户端服务"""

    # ---------- STEP-022 Header 配置 ----------
    async def get_header_config(self) -> dict:
        """朋友圈页 Header 配置，缺失回落默认（供 GET /api/feed/config/header）。
        含封面/头像/签名/昵称 + 主场城市 home_city（与后台生活计划设置同源）。"""
        return {
            "header_bg_url": await get_life_feed_config(
                CONFIG_FEED_PAGE_HEADER_BG_URL, DEFAULT_FEED_PAGE_HEADER_BG_URL),
            "header_avatar_url": await get_life_feed_config(
                CONFIG_FEED_PAGE_HEADER_AVATAR_URL, DEFAULT_FEED_PAGE_HEADER_AVATAR_URL),
            "signature": await get_life_feed_config(
                CONFIG_FEED_PAGE_SIGNATURE, DEFAULT_FEED_PAGE_SIGNATURE),
            "display_nickname": await get_life_feed_config(
                CONFIG_FEED_PAGE_DISPLAY_NICKNAME, DEFAULT_FEED_PAGE_DISPLAY_NICKNAME),
            "home_city": await get_life_feed_config(
                CONFIG_HOME_CITY, DEFAULT_HOME_CITY),
        }

    # ---------- STEP-015 列表 ----------
    async def list_feed(self, db: AsyncSession, user_id: int,
                        cursor: str | None, size: int) -> dict:
        now = feed_now()
        size = max(1, min(size or _DEFAULT_PAGE_SIZE, _MAX_PAGE_SIZE))

        stmt = select(FeedPost).where(
            FeedPost.scheduled_publish_time <= now,
            FeedPost.is_visible == 1,
            FeedPost.generation_status == "ready",
        )

        # 可见范围过滤
        range_cfg = await get_life_feed_config(
            CONFIG_FEED_HISTORY_VISIBLE_RANGE, DEFAULT_FEED_HISTORY_VISIBLE_RANGE)
        days = _RANGE_DAYS.get(str(range_cfg))
        if days:
            stmt = stmt.where(FeedPost.scheduled_publish_time >= now - timedelta(days=days))

        # 游标分页
        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                stmt = stmt.where(FeedPost.scheduled_publish_time < cursor_dt)
            except ValueError:
                logger.warning("[Feed] 非法 cursor=%s，忽略", cursor)

        stmt = stmt.order_by(FeedPost.scheduled_publish_time.desc()).limit(size)
        posts = (await db.execute(stmt)).scalars().all()

        # actual_publish_time 懒惰写回（首次到点，幂等）
        null_ids = [p.id for p in posts if p.actual_publish_time is None]
        if null_ids:
            await db.execute(
                update(FeedPost)
                .where(FeedPost.id.in_(null_ids), FeedPost.actual_publish_time.is_(None))
                .values(actual_publish_time=now)
            )
            await db.flush()

        # 私有评论：仅当前用户
        comments_by_post: dict[int, list] = {}
        if posts:
            post_ids = [p.id for p in posts]
            rows = (await db.execute(
                select(FeedComment)
                .where(FeedComment.post_id.in_(post_ids),
                       FeedComment.user_id == user_id,
                       FeedComment.is_hidden == 0)  # STEP-034：后台隐藏的评论不对用户展示
                .order_by(FeedComment.created_at.asc())
            )).scalars().all()
            for c in rows:
                comments_by_post.setdefault(c.post_id, []).append({
                    "id": c.id,
                    "content": c.content,
                    "reply_to_lxm": bool(c.reply_to_lxm),
                    "lxm_reply": c.lxm_reply,
                    "lxm_reply_at": c.lxm_reply_at.isoformat() if c.lxm_reply_at else None,
                    "lxm_reply_read_at": (
                        c.lxm_reply_read_at.isoformat() if c.lxm_reply_read_at else None),
                })

        items = [{
            "id": p.id,
            "content_text": p.content_text,
            "hashtags": p.hashtags or [],
            "image_urls": p.image_urls or [],
            "scheduled_publish_time": p.scheduled_publish_time.isoformat(),
            "emotion": p.emotion,
            "city": p.city or "",
            "display_likes": _display_likes(p),
            "display_comments": _display_comments(
                p, len(comments_by_post.get(p.id, []))),
            "user_liked": False,  # 由下方批量填充
            "comments": comments_by_post.get(p.id, []),
        } for p in posts]

        # user_liked 批量查询
        if posts:
            liked_ids = set((await db.execute(
                select(FeedLike.post_id).where(
                    FeedLike.post_id.in_([p.id for p in posts]),
                    FeedLike.user_id == user_id)
            )).scalars().all())
            for it in items:
                it["user_liked"] = it["id"] in liked_ids

        next_cursor = (
            posts[-1].scheduled_publish_time.isoformat() if len(posts) == size else None)
        return {"posts": items, "next_cursor": next_cursor}

    # ---------- STEP-015 enter ----------
    async def enter_feed(self, db: AsyncSession, user_id: int) -> dict:
        # last_feed_entered_at 与 scheduled_publish_time 比较，须同为北京墙钟
        now = feed_now()
        await db.execute(
            update(User).where(User.id == user_id).values(last_feed_entered_at=now))
        anchor = (await db.execute(
            select(FeedComment.id)
            .where(FeedComment.user_id == user_id,
                   FeedComment.lxm_reply.is_not(None),
                   FeedComment.lxm_reply_read_at.is_(None))
            .order_by(FeedComment.lxm_reply_at.desc())
            .limit(1)
        )).scalars().first()
        await db.flush()
        return {"anchor_comment_id": anchor}

    # ---------- STEP-015 badge ----------
    async def get_badge(self, db: AsyncSession, user_id: int) -> dict:
        """首页朋友圈入口数据：新帖数 + 未读回复数。

        new_post_count 与 has_new 同源（相对 last_feed_entered_at），并与 list 对齐历史可见窗。
        从未进入朋友圈（last_feed_entered_at IS NULL）时：has_new 仍按是否有可见帖判定，
        但 new_post_count 固定为 0，避免首页底栏展示「全量历史 N 条」。
        """
        now = feed_now()
        last_entered = (await db.execute(
            select(User.last_feed_entered_at).where(User.id == user_id)
        )).scalars().first()

        new_stmt = select(func.count()).select_from(FeedPost).where(
            FeedPost.scheduled_publish_time <= now,
            FeedPost.is_visible == 1,
            FeedPost.generation_status == "ready",
        )
        # 与 list_feed 对齐可见窗，避免 N 大于列表实际可刷到的帖
        range_cfg = await get_life_feed_config(
            CONFIG_FEED_HISTORY_VISIBLE_RANGE, DEFAULT_FEED_HISTORY_VISIBLE_RANGE)
        days = _RANGE_DAYS.get(str(range_cfg))
        if days:
            new_stmt = new_stmt.where(
                FeedPost.scheduled_publish_time >= now - timedelta(days=days))
        if last_entered is not None:
            new_stmt = new_stmt.where(FeedPost.scheduled_publish_time > last_entered)
        raw_new_count = int((await db.execute(new_stmt)).scalar() or 0)
        has_new = raw_new_count > 0
        # 从未进入：不暴露巨大 N，前端底栏走「快来看看」
        new_post_count = 0 if last_entered is None else raw_new_count

        unread = (await db.execute(
            select(func.count()).select_from(FeedComment).where(
                FeedComment.user_id == user_id,
                FeedComment.lxm_reply.is_not(None),
                FeedComment.lxm_reply_read_at.is_(None),
            )
        )).scalar() or 0
        return {
            "has_new": has_new,
            "new_post_count": new_post_count,
            "unread_reply_count": int(unread),
        }

    # ---------- STEP-016 点赞 ----------
    async def like_post(self, db: AsyncSession, user_id: int, post_id: int) -> dict:
        post = await _get_visible_post(db, post_id, feed_now())

        exists = (await db.execute(
            select(FeedLike.id).where(
                FeedLike.user_id == user_id, FeedLike.post_id == post_id)
        )).scalars().first()

        if exists is None:
            db.add(FeedLike(user_id=user_id, post_id=post_id))
            post.real_likes = post.real_likes + 1
            await db.flush()
            logger.info("[Feed] 用户点赞 user_id=%s post_id=%s real_likes=%s",
                        user_id, post_id, post.real_likes)
        else:
            logger.info("[Feed] 重复点赞幂等 user_id=%s post_id=%s", user_id, post_id)

        # 先提交点赞事务，释放 feed_post 行锁，再入队感知 IM（避免 FK 校验 Lock wait）
        await db.commit()
        await like_aware_service.on_like_hook(user_id=user_id, post_id=post_id)
        return {"user_liked": True, "display_likes": _display_likes(post)}

    async def unlike_post(self, db: AsyncSession, user_id: int, post_id: int) -> dict:
        post = await _get_visible_post(db, post_id, feed_now())

        res = await db.execute(
            delete(FeedLike).where(
                FeedLike.user_id == user_id, FeedLike.post_id == post_id))
        if res.rowcount and res.rowcount > 0:
            # 原子减且防负
            await db.execute(
                update(FeedPost)
                .where(FeedPost.id == post_id, FeedPost.real_likes > 0)
                .values(real_likes=FeedPost.real_likes - 1))
            await db.flush()
            await db.refresh(post)
            logger.info("[Feed] 取消点赞 user_id=%s post_id=%s real_likes=%s",
                        user_id, post_id, post.real_likes)
        else:
            logger.info("[Feed] 取消未点过帖子幂等 user_id=%s post_id=%s", user_id, post_id)

        return {"user_liked": False, "display_likes": _display_likes(post)}

    # ---------- STEP-017 评论 ----------
    async def create_comment(self, db: AsyncSession, user_id: int,
                             post_id: int, content: str,
                             reply_to_lxm: bool = False) -> dict:
        # 到点校验用北京墙钟；created_at/due_at 仍用 UTC（与评论回复轮询对齐）
        await _get_visible_post(db, post_id, feed_now())
        now = datetime.utcnow()

        content = content if content is not None else ""
        if len(content.strip()) == 0:
            raise FeedError(ERR_COMMENT_EMPTY)
        if len(content) > _MAX_COMMENT_LEN:
            raise FeedError(ERR_COMMENT_TOO_LONG)
        # 仅作展示标记：1=点小梦回复发出；不影响 LLM-05
        reply_flag = 1 if reply_to_lxm else 0

        # 频控：30s 内同帖同用户
        recent = (await db.execute(
            select(func.count()).select_from(FeedComment).where(
                FeedComment.user_id == user_id,
                FeedComment.post_id == post_id,
                FeedComment.created_at >= now - timedelta(seconds=_COMMENT_RATE_WINDOW_SEC),
            )
        )).scalar() or 0
        if recent >= 1:
            raise FeedError(ERR_COMMENT_RATE_LIMIT)

        # 内容安全
        safe = await content_safety_service.check_content(content)
        if not safe.get("is_safe", True):
            raise FeedError(ERR_CONTENT_SAFETY_VIOLATION)

        # 首次评论 override 竞态：原子 UPDATE
        res = await db.execute(
            update(Relationship)
            .where(Relationship.user_id == user_id,
                   Relationship.has_ever_commented_feed == 0)
            .values(has_ever_commented_feed=1))
        is_first = bool(res.rowcount and res.rowcount == 1)

        if is_first:
            due_at = now + timedelta(seconds=_FIRST_COMMENT_OVERRIDE_SEC)
        else:
            level = (await db.execute(
                select(Relationship.level).where(Relationship.user_id == user_id)
            )).scalars().first() or 0
            stage = level_to_stage(int(level))
            d_default = DEFAULT_COMMENT_REPLY_DELAY_SEC.get(stage, (300, 600))
            dmin = int(await get_life_feed_config(
                comment_reply_delay_key(stage, "min"), d_default[0]))
            dmax = int(await get_life_feed_config(
                comment_reply_delay_key(stage, "max"), d_default[1]))
            if dmax < dmin:
                dmax = dmin
            due_at = now + timedelta(seconds=random.randint(dmin, dmax))

        comment = FeedComment(
            post_id=post_id, user_id=user_id, content=content,
            reply_to_lxm=reply_flag,
            gen_status="pending", due_at=due_at, created_at=now)
        db.add(comment)
        await db.flush()
        await db.refresh(comment)

        logger.info(
            "[Feed] 用户评论 user_id=%s post_id=%s comment_id=%s is_first=%s "
            "reply_to_lxm=%s due_at=%s",
            user_id, post_id, comment.id, is_first, reply_flag, due_at)
        return {
            "comment_id": comment.id,
            "created_at": comment.created_at.isoformat(),
            "gen_status": "pending",
            "reply_to_lxm": bool(reply_flag),
        }

    # ---------- STEP-029 已读上报 ----------
    async def mark_comment_reply_read(
        self, db: AsyncSession, user_id: int, comment_id: int
    ) -> dict:
        """
        单条评论回复已读上报：写 lxm_reply_read_at（幂等）。
        校验评论归属当前用户，防越权；仅对有 LXM 回复且未读的记录生效。
        """
        comment = (await db.execute(
            select(FeedComment).where(FeedComment.id == comment_id)
        )).scalars().first()
        if comment is None:
            raise FeedError(ERR_FEED_COMMENT_FORBIDDEN)
        if comment.user_id != user_id:
            logger.warning("[Feed] 越权已读上报 user_id=%s comment_id=%s owner=%s",
                           user_id, comment_id, comment.user_id)
            raise FeedError(ERR_FEED_COMMENT_FORBIDDEN)

        res = await db.execute(
            update(FeedComment)
            .where(FeedComment.id == comment_id,
                   FeedComment.user_id == user_id,
                   FeedComment.lxm_reply.is_not(None),
                   FeedComment.lxm_reply_read_at.is_(None))
            .values(lxm_reply_read_at=datetime.utcnow()))
        await db.commit()
        affected = res.rowcount or 0
        logger.info("[Feed] 评论回复已读上报 user_id=%s comment_id=%s affected=%s",
                    user_id, comment_id, affected)
        return {"affected": affected}

    async def mark_feed_post_read(
        self, db: AsyncSession, user_id: int, post_id: int
    ) -> dict:
        """
        单帖已读上报：校验可见+到点后触发已读感知 IM 判定与入队（STEP-021）。
        """
        # 校验可见+到点（不可见/未到点抛 ERR_FEED_POST_NOT_FOUND）
        _get = await _get_visible_post(db, post_id, feed_now())  # noqa: F841

        from backend.services.read_aware_service import read_aware_service
        await read_aware_service.on_feed_read(user_id, post_id)

        logger.info("[Feed] 帖子已读上报 user_id=%s post_id=%s", user_id, post_id)
        return {}


# 全局单例
feed_service = FeedService()
