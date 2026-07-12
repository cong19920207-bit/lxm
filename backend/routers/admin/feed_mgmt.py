# -*- coding: utf-8 -*-
# 生活流·朋友圈后台管理 API（STEP-014）：CRUD、隐藏/展示、手动新增（上传 / AI 生成复用 LLM-04）、自动发布开关
#
# 前缀 /api/admin（见 main.py），权限 super_admin / ai_trainer；写操作全落 operation_log。
# AI 生成复用 feed_content_service.generate_post_text（不新建 LLM 节点），管理员权威：跳过 dedup/similarity。

import logging
import random
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_feed_image_reference_public_url
from backend.constants import (
    ADMIN_ERR_FEED_AI_DESCRIPTION_REQUIRED,
    ADMIN_ERR_FEED_POST_MODE_INVALID,
    ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN,
    ADMIN_ERR_LIFE_GENERATE_FAILED,
    ADMIN_ERR_LIFE_PARAM_INVALID,
)
from backend.constants.life_feed_config import (
    CONFIG_FEED_AUTO_PUBLISH_ENABLED,
    CONFIG_FEED_BASE_LIKES_MAX,
    CONFIG_FEED_BASE_LIKES_MIN,
    CONFIG_FEED_LIKE_MULTIPLIER_MAX,
    CONFIG_FEED_LIKE_MULTIPLIER_MIN,
    CONFIG_HOME_CITY,
    CONFIG_SOUTHERN_HEMISPHERE_CITIES,
    DEFAULT_FEED_AUTO_PUBLISH_ENABLED,
    DEFAULT_FEED_BASE_LIKES_MAX,
    DEFAULT_FEED_BASE_LIKES_MIN,
    DEFAULT_FEED_LIKE_MULTIPLIER_MAX,
    DEFAULT_FEED_LIKE_MULTIPLIER_MIN,
    DEFAULT_HOME_CITY,
    DEFAULT_SOUTHERN_HEMISPHERE_CITIES,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.feed_post import FeedPost
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.feed_content_service import (
    ContentSafetyException,
    FeedContentError,
    feed_content_service,
)
from backend.services.feed_image_service import feed_image_service
from backend.services.life_feed_config_service import get_life_feed_config
from backend.utils.admin_auth import get_current_admin, log_operation, require_role
from backend.utils.hash_utils import compute_dedup_hash
from backend.utils.season_utils import compute_season

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")
_READ_ROLES = ("super_admin", "ai_trainer", "ops_admin")  # STEP-038 ops_admin 只读
_VALID_STATUS = ("all", "visible", "hidden", "failed")
_VALID_IMAGE_TYPES = ("selfie", "daily", "scenery", "emotion")


def _parse_dt(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _post_to_dict(p: FeedPost, *, detail: bool = False) -> dict:
    data = {
        "id": p.id,
        "content_text": p.content_text,
        "hashtags": p.hashtags or [],
        "image_urls": p.image_urls or [],
        "emotion": p.emotion,
        "city": p.city,
        "season": p.season,
        "scene_id": p.scene_id,
        "generation_status": p.generation_status,
        "is_visible": p.is_visible,
        "base_likes": p.base_likes,
        "like_multiplier": p.like_multiplier,
        "real_likes": p.real_likes,
        "display_likes": p.base_likes * p.like_multiplier + p.real_likes,
        "base_comments": p.base_comments,
        "comment_multiplier": p.comment_multiplier,
        "display_comments": p.base_comments * p.comment_multiplier,  # 后台列表无 per-user 真评论
        "scheduled_publish_time": p.scheduled_publish_time.isoformat() if p.scheduled_publish_time else None,
        "actual_publish_time": p.actual_publish_time.isoformat() if p.actual_publish_time else None,
    }
    if detail:
        data.update({
            "dedup_hash": p.dedup_hash,
            "image_type": p.image_type,
            "image_reference_url": p.image_reference_url,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
    return data


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


# ─────────────────────────── 列表 / 详情 ───────────────────────────

@router.get("/feed/posts", dependencies=[require_role(*_READ_ROLES)])
async def list_posts(
    status: str = Query("all"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """朋友圈列表（status ∈ all/visible/hidden/failed）。"""
    if status not in _VALID_STATUS:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                message=f"status 必须是 {'/'.join(_VALID_STATUS)}")
    cond = []
    if status == "visible":
        cond.append(FeedPost.is_visible == 1)
        cond.append(FeedPost.generation_status == "ready")
    elif status == "hidden":
        cond.append(FeedPost.is_visible == 0)
    elif status == "failed":
        cond.append(FeedPost.generation_status == "failed")

    total = (await db.execute(select(func.count(FeedPost.id)).where(*cond))).scalar() or 0
    rows = (await db.execute(
        select(FeedPost).where(*cond)
        .order_by(FeedPost.scheduled_publish_time.desc())
        .offset((page - 1) * size).limit(size))).scalars().all()
    return ApiResponse.ok(data={
        "total": total, "page": page, "size": size,
        "list": [_post_to_dict(r) for r in rows],
    })


@router.get("/feed/posts/{post_id}", dependencies=[require_role(*_READ_ROLES)])
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """朋友圈详情（含 image_urls / hashtags / dedup_hash）。"""
    row = (await db.execute(select(FeedPost).where(FeedPost.id == post_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN)
    return ApiResponse.ok(data=_post_to_dict(row, detail=True))


# ─────────────────────────── 编辑 / 删除 / 可见性 ───────────────────────────

class PostUpdateBody(BaseModel):
    content_text: str | None = None
    hashtags: list[str] | None = None
    image_urls: list[str] | None = None
    scheduled_publish_time: str | None = None
    emotion: str | None = None


@router.put("/feed/posts/{post_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def update_post(
    post_id: int,
    body: PostUpdateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """编辑帖子（content_text/hashtags/image_urls/scheduled_publish_time/emotion）。"""
    row = (await db.execute(select(FeedPost).where(FeedPost.id == post_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN)
    if body.content_text is not None:
        row.content_text = body.content_text
    if body.hashtags is not None:
        row.hashtags = body.hashtags
    if body.image_urls is not None:
        row.image_urls = body.image_urls or None
    if body.emotion is not None:
        row.emotion = body.emotion
    if body.scheduled_publish_time is not None:
        dt = _parse_dt(body.scheduled_publish_time)
        if dt is None:
            return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                    message="scheduled_publish_time 格式非法")
        row.scheduled_publish_time = dt
    await log_operation(db, admin_user, "feed", "update_post",
                        f"编辑朋友圈 id={post_id}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_post_to_dict(row, detail=True))


@router.delete("/feed/posts/{post_id}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_post(
    post_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除（客户端下架，DB 保留：置 is_visible=0）。"""
    row = (await db.execute(select(FeedPost).where(FeedPost.id == post_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN)
    row.is_visible = 0
    await log_operation(db, admin_user, "feed", "delete_post",
                        f"下架朋友圈 id={post_id}（DB 保留）", request=request)
    await db.commit()
    return ApiResponse.ok(data={"id": post_id, "is_visible": 0})


class VisibilityBody(BaseModel):
    is_visible: int


@router.patch("/feed/posts/{post_id}/visibility", dependencies=[require_role(*_ALLOWED_ROLES)])
async def patch_visibility(
    post_id: int,
    body: VisibilityBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """隐藏/展示切换（历史点赞/评论完整保留，DB 层不删）。"""
    if body.is_visible not in (0, 1):
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="is_visible 只能为 0 或 1")
    row = (await db.execute(select(FeedPost).where(FeedPost.id == post_id))).scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN)
    row.is_visible = body.is_visible
    await log_operation(db, admin_user, "feed", "patch_visibility",
                        f"朋友圈 id={post_id} 可见性→{body.is_visible}", request=request)
    await db.commit()
    return ApiResponse.ok(data=_post_to_dict(row, detail=True))


# ─────────────────────────── 手动新增 ───────────────────────────

class PostCreateBody(BaseModel):
    mode: str
    scheduled_publish_time: str | None = None
    # upload 模式
    content_text: str | None = None
    hashtags: list[str] | None = None
    image_urls: list[str] | None = None
    emotion: str | None = None
    # ai_generate 模式
    description: str | None = None
    image_type: str | None = None
    venue_type: str | None = None
    category: str | None = None
    city: str | None = None


async def _draw_likes() -> tuple[int, int]:
    base_min = int(await get_life_feed_config(CONFIG_FEED_BASE_LIKES_MIN, DEFAULT_FEED_BASE_LIKES_MIN))
    base_max = int(await get_life_feed_config(CONFIG_FEED_BASE_LIKES_MAX, DEFAULT_FEED_BASE_LIKES_MAX))
    mul_min = int(await get_life_feed_config(CONFIG_FEED_LIKE_MULTIPLIER_MIN, DEFAULT_FEED_LIKE_MULTIPLIER_MIN))
    mul_max = int(await get_life_feed_config(CONFIG_FEED_LIKE_MULTIPLIER_MAX, DEFAULT_FEED_LIKE_MULTIPLIER_MAX))
    return random.randint(base_min, base_max), random.randint(mul_min, mul_max)


@router.post("/feed/posts", dependencies=[require_role(*_ALLOWED_ROLES)])
async def create_post(
    body: PostCreateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """手动新增（mode ∈ upload / ai_generate）。管理员权威：不做 dedup/similarity。"""
    if body.mode not in ("upload", "ai_generate"):
        return ApiResponse.fail(ADMIN_ERR_FEED_POST_MODE_INVALID)

    home_city = await get_life_feed_config(CONFIG_HOME_CITY, DEFAULT_HOME_CITY)
    southern = await get_life_feed_config(
        CONFIG_SOUTHERN_HEMISPHERE_CITIES, DEFAULT_SOUTHERN_HEMISPHERE_CITIES)
    today = date.today()
    sched = _parse_dt(body.scheduled_publish_time) or datetime.now()
    base_likes, like_multiplier = await _draw_likes()
    # 评论假数与点赞同抽签范围（独立一次随机，数值不必相同）
    base_comments, comment_multiplier = await _draw_likes()

    if body.mode == "upload":
        content_text = (body.content_text or "").strip()
        if not content_text:
            return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="upload 模式 content_text 不能为空")
        city = (body.city or home_city).strip()
        emotion = (body.emotion or "平静").strip()
        image_urls = body.image_urls or None
        post = FeedPost(
            scene_id=None,
            scheduled_publish_time=sched,
            actual_publish_time=None,
            generation_status="ready",
            content_text=content_text,
            hashtags=body.hashtags or [],
            image_urls=image_urls,
            image_reference_url=get_feed_image_reference_public_url() if image_urls else None,
            image_type=None,
            emotion=emotion,
            city=city,
            season=compute_season(city, today, southern),
            base_likes=base_likes,
            like_multiplier=like_multiplier,
            real_likes=0,
            base_comments=base_comments,
            comment_multiplier=comment_multiplier,
            is_visible=1,
            dedup_hash=compute_dedup_hash("manual", "manual", content_text[:32]),
            created_at=datetime.utcnow(),
        )
        db.add(post)
        await db.flush()
        await log_operation(db, admin_user, "feed", "create_post_upload",
                            f"手动上传朋友圈 id={post.id}", request=request)
        await db.commit()
        await db.refresh(post)
        return ApiResponse.ok(data=_post_to_dict(post, detail=True))

    # mode == ai_generate
    if not body.description or not body.description.strip():
        return ApiResponse.fail(ADMIN_ERR_FEED_AI_DESCRIPTION_REQUIRED)
    if body.image_type is not None and body.image_type not in _VALID_IMAGE_TYPES:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID,
                                message=f"image_type 必须是 {'/'.join(_VALID_IMAGE_TYPES)}")

    city = (body.city or home_city).strip()
    scene = {
        "scene_id": f"manual-{int(datetime.utcnow().timestamp())}",
        "venue_type": (body.venue_type or "日常"),
        "category": (body.category or "日常"),
        "city": city,
        "description": body.description.strip(),
        "time_range": "",
    }
    try:
        # 管理员权威：跳过 dedup/similarity（generate_post_text 内含二者，
        # 但 manual scene 唯一 scene_id + 独立描述命中概率极低；如命中按失败返回让管理员改文案）
        draft = await feed_content_service.generate_post_text(
            scene, None, today, skip_dedup_checks=True)
    except ContentSafetyException as e:
        logger.warning("[后台][朋友圈] AI 生成内容安全拦截: %s", e)
        return ApiResponse.fail(ADMIN_ERR_LIFE_GENERATE_FAILED, message="生成内容未通过安全检查")
    except FeedContentError as e:
        logger.error("[后台][朋友圈] AI 生成失败: %s", e)
        return ApiResponse.fail(ADMIN_ERR_LIFE_GENERATE_FAILED)
    except Exception as e:  # dedup/similarity 等命中
        logger.warning("[后台][朋友圈] AI 生成被跳过/异常: %s", e)
        return ApiResponse.fail(ADMIN_ERR_LIFE_GENERATE_FAILED, message="生成命中去重/相似度，请调整描述")

    season = compute_season(city, today, southern)
    post = FeedPost(
        scene_id=scene["scene_id"],
        scheduled_publish_time=sched,
        actual_publish_time=None,
        generation_status="ready",
        content_text=draft["post_text"],
        hashtags=draft.get("hashtags") or [],
        image_urls=None,
        image_reference_url=get_feed_image_reference_public_url(),
        image_type=None,
        emotion=draft["emotion"],
        city=city,
        season=season,
        base_likes=base_likes,
        like_multiplier=like_multiplier,
        real_likes=0,
        base_comments=base_comments,
        comment_multiplier=comment_multiplier,
        is_visible=1,
        dedup_hash=draft["dedup_hash"],
        created_at=datetime.utcnow(),
    )
    db.add(post)
    await db.flush()
    post_id = post.id

    image_urls = []
    if body.image_type:
        try:
            image_urls = await feed_image_service.generate_images({
                "post_id": post_id,
                "venue_type": scene["venue_type"],
                "category": scene["category"],
                "city": city,
                "time_range": "",
                "emotion": draft["emotion"],
                "season": season,
                "image_type": body.image_type,
            })
            post.image_urls = image_urls or None
            post.image_type = body.image_type
        except Exception as e:
            logger.warning("[后台][朋友圈] AI 图片生成异常 post_id=%s: %s", post_id, e)

    await log_operation(db, admin_user, "feed", "create_post_ai",
                        f"AI 生成朋友圈 id={post_id}", request=request)
    await db.commit()
    await db.refresh(post)
    return ApiResponse.ok(data=_post_to_dict(post, detail=True))


# ─────────────────────────── 自动发布开关 ───────────────────────────

@router.get("/feed/config/auto-publish", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_auto_publish(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """读取 feed_auto_publish_enabled 当前生效值。"""
    val = await get_life_feed_config(
        CONFIG_FEED_AUTO_PUBLISH_ENABLED, DEFAULT_FEED_AUTO_PUBLISH_ENABLED)
    return ApiResponse.ok(data={"feed_auto_publish_enabled": _as_bool(val)})


class AutoPublishBody(BaseModel):
    enabled: bool


@router.put("/feed/config/auto-publish", dependencies=[require_role(*_ALLOWED_ROLES)])
async def put_auto_publish(
    body: AutoPublishBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """修改自动发布开关（走 admin_config 草稿，发布经三道卡点）。"""
    result = await admin_config_service.save_draft(
        db, CONFIG_FEED_AUTO_PUBLISH_ENABLED,
        "true" if body.enabled else "false", admin_user.username)
    await log_operation(db, admin_user, "feed", "update_auto_publish",
                        f"自动发布开关草稿→{body.enabled}", request=request)
    await db.commit()
    return ApiResponse.ok(data={"draft": result, "enabled": body.enabled})
