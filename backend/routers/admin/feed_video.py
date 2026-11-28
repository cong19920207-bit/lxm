"""Manual feed video edit and raw upload endpoints."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.database import get_db
from backend.models.feed_video import FeedVideoEdit
from backend.schemas.common import ApiResponse
from backend.services import feed_video_drafts as drafts
from backend.services.feed_video_receive import receive
from backend.utils.admin_auth import require_role, log_operation

router = APIRouter()
read = require_role("super_admin", "ai_trainer", "ops_admin", "observer")
write = require_role("super_admin", "ai_trainer")


class DraftFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_text: str = ""
    hashtags: list[str] = Field(default_factory=list)
    emotion: str = Field(default="平静", max_length=20)
    scheduled_publish_time: NaiveDatetime | None = None

    @field_validator("emotion", mode="before")
    @classmethod
    def default_blank_emotion(cls, value):
        return (value.strip() or "平静") if isinstance(value, str) else value

    @field_validator("hashtags")
    @classmethod
    def trim_hashtags(cls, tags):
        return [tag.strip() for tag in tags if tag.strip()]


class DraftCreate(DraftFields):
    request_id: UUID


class DraftUpdate(DraftFields):
    version: int = Field(ge=1)
    frame_mode: Literal["crop", "contain"] = "crop"
    frame_position: int = Field(default=50, ge=0, le=100)


class Reservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=-(2**63), le=2**63-1)
    version: int | None = Field(default=None, ge=1)


class KeepSelected(BaseModel):
    version: int = Field(ge=1)
    media_version: UUID


@router.post("/edits")
async def create(body: DraftCreate, actor=write, db: AsyncSession = Depends(get_db)):
    result = await drafts.create_edit(db, actor, body)
    await db.commit()
    return ApiResponse.ok(result)


@router.get("/edits")
async def list_edits(actor=read, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(FeedVideoEdit).where(FeedVideoEdit.state == "draft")
                             .order_by(FeedVideoEdit.last_edited_at.desc(), FeedVideoEdit.id.desc()))).all()
    return ApiResponse.ok([await drafts.edit_view(db, await drafts.edit_row(db, edit.id)) for edit in rows])


@router.get("/edits/{eid}")
async def detail(eid: int, actor=read, db: AsyncSession = Depends(get_db)):
    return ApiResponse.ok(await drafts.edit_view(db, await drafts.edit_row(db, eid)))


@router.patch("/edits/{eid}")
async def save(eid: int, body: DraftUpdate, actor=write, db: AsyncSession = Depends(get_db)):
    result = await drafts.save_edit(db, actor, eid, body)
    await db.commit()
    return ApiResponse.ok(result)


@router.delete("/edits/{eid}")
async def abandon(eid: int, actor=write, db: AsyncSession = Depends(get_db)):
    result = await drafts.abandon(db, actor, eid)
    await db.commit()
    return ApiResponse.ok(result)


@router.post("/edits/{eid}/uploads")
async def reserve(eid: int, body: Reservation, actor=write, db: AsyncSession = Depends(get_db)):
    result = await drafts.reserve(db, actor, eid, body)
    await db.commit()
    if result["state"] == "rejected":
        reason = result["failure_reason"]
        raise HTTPException(507 if reason == drafts.NO_SPACE else 422, reason)
    if result["state"] not in ("reserved", "receiving", "validating", "accepted"):
        raise HTTPException(409, "接收操作已结束，请重新选择文件")
    return ApiResponse.ok(result)


@router.put("/uploads/{operation_id}/content")
async def content(operation_id: UUID, request: Request, actor=write, db: AsyncSession = Depends(get_db)):
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)
    actor_id = actor.id
    await db.rollback()
    return ApiResponse.ok(await receive(sessions, actor_id, str(operation_id), request))


@router.post("/edits/{eid}/uploads/{operation_id}/retry")
async def retry(eid: int, operation_id: UUID, actor=write, db: AsyncSession = Depends(get_db)):
    result = await drafts.retry_task(db, eid, str(operation_id))
    await db.commit()
    return ApiResponse.ok(result)


@router.post("/edits/{eid}/uploads/{operation_id}/keep-selected")
async def keep_selected(eid: int, operation_id: UUID, body: KeepSelected, actor=write,
                        db: AsyncSession = Depends(get_db)):
    result = await drafts.keep_selected(db, actor, eid, str(operation_id), body.version, str(body.media_version))
    await db.commit()
    return ApiResponse.ok(result)


@router.put("/edits/{eid}/uploads/{operation_id}/cover")
async def cover(eid: int, operation_id: UUID, version: int, request: Request,
                actor=write, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    from backend.services.feed_video_covers import MAX_COVER_BYTES
    blob = bytearray()
    async for chunk in request.stream():
        if len(blob) + len(chunk) > MAX_COVER_BYTES:
            raise HTTPException(422, "封面不能超过 5 MiB")
        blob.extend(chunk)
    result = await drafts.choose_cover(db, eid, str(operation_id), version, blob)
    await log_operation(db,actor,"feed","video_cover",f"更换编辑 {eid} 封面，成功")
    await db.commit()
    return ApiResponse.ok(result)


@router.post("/edits/{eid}/uploads/{operation_id}/cover/default")
async def default_cover(eid: int, operation_id: UUID, version: int, actor=write, db: AsyncSession = Depends(get_db)):
    result = await drafts.choose_cover(db, eid, str(operation_id), version)
    await log_operation(db,actor,"feed","video_cover_default",f"恢复编辑 {eid} 默认封面，成功")
    await db.commit()
    return ApiResponse.ok(result)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    version: int = Field(ge=1)


@router.post("/edits/{eid}/submit")
async def submit(eid: int, body: Submission, actor=write, db: AsyncSession = Depends(get_db)):
    from backend.services.feed_video_publish import submit as commit_edit
    result = await commit_edit(db, actor, eid, body)
    await db.commit()
    return ApiResponse.ok(result)


@router.post("/posts/{post_id}/edits")
async def replacement(post_id: int, body: Submission, actor=write, db: AsyncSession = Depends(get_db)):
    from backend.services.feed_video_publish import begin_replacement
    result = await begin_replacement(db,actor,post_id,body)
    await db.commit()
    return ApiResponse.ok(result)
