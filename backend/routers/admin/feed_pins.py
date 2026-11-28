"""Ordered membership of the admin pin list. One catalog row serializes all writers."""
import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN, ADMIN_ERR_LIFE_PARAM_INVALID
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.feed_post import FeedPost
from backend.models.feed_video import FeedPin, FeedPinOrder
from backend.schemas.common import ApiResponse
from backend.services import feed_service as feed
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

router = APIRouter()
READ = require_role("super_admin", "ai_trainer", "ops_admin", "observer")
WRITE = require_role("super_admin", "ai_trainer")


class PinOrderBody(BaseModel):
    version: int = Field(ge=0)
    post_ids: list[int]


def post_type(post):
    if post.media_kind == "video":
        return "视频"
    count = len(post.image_urls or [])
    return "纯文字" if not count else "单图" if count == 1 else "相册"


@router.get("/feed/pins", dependencies=[READ])
async def list_pins(db: AsyncSession = Depends(get_db)):
    now = feed.feed_now()
    visible = await feed.visible_post_condition(now)
    # Version and rows must come from the same read, including an empty catalog.
    rows = (await db.execute(
        select(FeedPinOrder.version, FeedPost, visible.label("visible"),
               feed.submitted_media_condition().label("submitted"))
        .select_from(FeedPinOrder).outerjoin(FeedPin, true())
        .outerjoin(FeedPost, FeedPost.id == FeedPin.post_id)
        .where(FeedPinOrder.id == 1).order_by(FeedPin.position)
    )).all()
    items = []
    for _, post, is_public, submitted in rows:
        if post is None:
            continue
        if not post.is_visible:
            status = "隐藏"
        elif post.generation_status != "ready" or not submitted:
            status = "未就绪"
        elif post.scheduled_publish_time > now:
            status = "待发布"
        else:
            status = "可见" if is_public else "超出范围"
        items.append(dict(id=post.id, summary=post.content_text[:60], type=post_type(post),
                          scheduled_publish_time=post.scheduled_publish_time.isoformat(), status=status))
    return ApiResponse.ok(data={"version":rows[0].version, "posts":items})


async def locked_order(db):
    # A current read is required even if authentication opened an older MySQL snapshot.
    if db.get_bind().dialect.name == "sqlite":
        await db.execute(update(FeedPinOrder).where(FeedPinOrder.id == 1).values(version=FeedPinOrder.version))
    head = await db.scalar(select(FeedPinOrder).where(FeedPinOrder.id == 1).with_for_update())
    members = list((await db.scalars(select(FeedPin.post_id).order_by(FeedPin.position).with_for_update())).all())
    return head, members


async def persist_order(db, actor, request, head, before, after, action, target):
    if before != after:
        # Delete and reinsert atomically; swapped unique positions never collide.
        await db.execute(delete(FeedPin))
        db.add_all(FeedPin(post_id=pid, position=i) for i, pid in enumerate(after, 1))
        head.version += 1
    await log_operation(db, actor, "feed", action, target + " 成功",
                        json.dumps(before), json.dumps(after), request)
    await db.commit()
    return ApiResponse.ok(data={"version":head.version, "post_ids":after})


@router.put("/feed/pins/order", dependencies=[WRITE])
async def reorder(body: PinOrderBody, request: Request, db: AsyncSession = Depends(get_db),
                  actor: AdminUser = Depends(get_current_admin)):
    head, before = await locked_order(db)
    if (body.version != head.version or len(body.post_ids) != len(before)
            or set(body.post_ids) != set(before)):
        await log_operation(db, actor, "feed", "pin_order", "置顶排序失败：版本或成员不符",
                            json.dumps(before), json.dumps(body.post_ids), request)
        await db.commit()
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="置顶列表已更新，请刷新后重排")
    return await persist_order(db, actor, request, head, before, body.post_ids, "pin_order", "置顶排序")


@router.put("/feed/pins/{post_id}", dependencies=[WRITE])
async def pin(post_id: int, request: Request, db: AsyncSession = Depends(get_db),
              actor: AdminUser = Depends(get_current_admin)):
    head, before = await locked_order(db)
    row = (await db.execute(select(FeedPost.id, and_(FeedPost.generation_status == "ready",
            feed.submitted_media_condition())).where(FeedPost.id == post_id).with_for_update())).first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_FEED_POST_NOT_FOUND_ADMIN)
    if post_id not in before and not row[1]:
        return ApiResponse.fail(ADMIN_ERR_LIFE_PARAM_INVALID, message="仅已提交且就绪的帖子可置顶")
    after = before if post_id in before else [*before, post_id]
    return await persist_order(db, actor, request, head, before, after, "pin_post", f"置顶帖子 {post_id}")


@router.delete("/feed/pins/{post_id}", dependencies=[WRITE])
async def unpin(post_id: int, request: Request, db: AsyncSession = Depends(get_db),
                actor: AdminUser = Depends(get_current_admin)):
    head, before = await locked_order(db)
    after = [pid for pid in before if pid != post_id]
    return await persist_order(db, actor, request, head, before, after, "unpin_post", f"取消置顶 {post_id}")
