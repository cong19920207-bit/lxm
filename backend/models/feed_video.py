"""Feed edits and media are independent of the public post and its interactions."""
from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FeedVideoEdit(Base):
    __tablename__ = "feed_video_edit"
    __table_args__ = (UniqueConstraint("post_id", "id", name="uq_feed_edit_owner"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("feed_post.id"))
    admin_id: Mapped[int] = mapped_column(Integer)
    base_post_version: Mapped[int] = mapped_column(Integer)
    edit_version: Mapped[int] = mapped_column(default=1, server_default="1")
    state: Mapped[str] = mapped_column(String(24), default="draft")
    content_text: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list | None] = mapped_column(JSON)
    emotion: Mapped[str] = mapped_column(String(20), default="平静", server_default="平静")
    scheduled_publish_time: Mapped[datetime | None] = mapped_column(DateTime)
    frame_mode: Mapped[str] = mapped_column(String(16), default="crop")
    frame_position: Mapped[int] = mapped_column(default=50)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_edited_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    media_expired_at: Mapped[datetime | None] = mapped_column(DateTime)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime)


class FeedVideoTask(Base):
    __tablename__ = "feed_video_task"
    __table_args__ = (
        ForeignKeyConstraint(["post_id", "edit_id"], ["feed_video_edit.post_id", "feed_video_edit.id"]),
        UniqueConstraint("post_id", "media_version", name="uq_feed_task_owner_version"),
        Index("ix_feed_task_queue", "state", "received_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer)
    edit_id: Mapped[int] = mapped_column(Integer)
    media_version: Mapped[str] = mapped_column(String(36), unique=True)
    state: Mapped[str] = mapped_column(String(24))
    attempt: Mapped[int] = mapped_column(default=0, server_default="0")
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    first_failed_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_path: Mapped[str | None] = mapped_column(String(512))
    master_path: Mapped[str | None] = mapped_column(String(512))
    master_sha256: Mapped[str | None] = mapped_column(String(64))
    master_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    failure_reason: Mapped[str | None] = mapped_column(String(512))


class FeedVideoAsset(Base):
    __tablename__ = "feed_video_asset"
    __table_args__ = (
        UniqueConstraint("media_version", "kind", "variant", name="uq_feed_asset_variant"),
        CheckConstraint("kind IN ('video','preview','cover_small','cover_large')", name="ck_feed_asset_kind"),
        CheckConstraint("kind IN ('cover_small','cover_large') OR variant = 'default'", name="ck_feed_asset_variant"),
        Index("ix_feed_asset_cleanup", "unreferenced_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    media_version: Mapped[str] = mapped_column(ForeignKey("feed_video_task.media_version"))
    kind: Mapped[str] = mapped_column(String(16))
    # Both cover sizes share a variant. Movie and preview retain their original bytes.
    variant: Mapped[str] = mapped_column(String(36), default="default", server_default="default")
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    public_url: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    stream_info: Mapped[dict | None] = mapped_column(JSON)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    unreferenced_at: Mapped[datetime | None] = mapped_column(DateTime)


class FeedVideoSelection(Base):
    """One selected movie and one matched pair of covers per edit."""
    __tablename__ = "feed_video_selection"
    __table_args__ = (
        ForeignKeyConstraint(["post_id", "edit_id"], ["feed_video_edit.post_id", "feed_video_edit.id"]),
        ForeignKeyConstraint(["post_id", "media_version"], ["feed_video_task.post_id", "feed_video_task.media_version"]),
    )
    edit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    post_id: Mapped[int] = mapped_column(Integer)
    media_version: Mapped[str] = mapped_column(String(36))
    cover_variant: Mapped[str] = mapped_column(String(36), default="default", server_default="default")


class FeedPublication(Base):
    """Only this pointer selects a submitted video edit for public reads."""
    __tablename__ = "feed_publication"
    __table_args__ = (
        ForeignKeyConstraint(["post_id", "edit_id"], ["feed_video_edit.post_id", "feed_video_edit.id"]),
        ForeignKeyConstraint(["edit_id"], ["feed_video_selection.edit_id"]),
    )
    post_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    edit_id: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class FeedPin(Base):
    __tablename__ = "feed_pin"
    post_id: Mapped[int] = mapped_column(ForeignKey("feed_post.id"), primary_key=True, autoincrement=False)
    position: Mapped[int] = mapped_column(Integer, unique=True)


class FeedPinOrder(Base):
    __tablename__ = "feed_pin_order"
    __table_args__ = (CheckConstraint("id = 1", name="ck_feed_pin_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


FEED_VIDEO_TABLE_NAMES = frozenset(model.__tablename__ for model in (
    FeedVideoEdit, FeedVideoTask, FeedVideoAsset, FeedVideoSelection, FeedPublication, FeedPin, FeedPinOrder,
))
