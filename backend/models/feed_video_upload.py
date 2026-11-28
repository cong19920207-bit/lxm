"""Durable draft receipts and admission records for the shared feed media volume."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FeedVideoAdmission(Base):
    __tablename__ = "feed_video_admission"
    __table_args__ = (CheckConstraint("id = 1", name="ck_feed_video_admission_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    last_sequence: Mapped[int] = mapped_column(BigInteger, server_default="0")


class FeedDraftRequest(Base):
    __tablename__ = "feed_video_draft_request"
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    edit_id: Mapped[int] = mapped_column(ForeignKey("feed_video_edit.id"), unique=True)
    actor_id: Mapped[int]
    request_digest: Mapped[str] = mapped_column(String(64))


class FeedVideoUpload(Base):
    __tablename__ = "feed_video_upload"
    __table_args__ = (Index("ix_feed_upload_edit", "edit_id", "state"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    edit_id: Mapped[int] = mapped_column(ForeignKey("feed_video_edit.id"))
    actor_id: Mapped[int]
    filename: Mapped[str] = mapped_column(String(255))
    expected_size: Mapped[int] = mapped_column(BigInteger)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(24))
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    arrival_sequence: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_info: Mapped[dict | None] = mapped_column(JSON)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("feed_video_task.id"), unique=True)
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    unreferenced_at: Mapped[datetime | None] = mapped_column(DateTime)


UPLOAD_TABLE_NAMES = {table.__tablename__ for table in (FeedVideoAdmission, FeedDraftRequest, FeedVideoUpload)}


class FeedVideoSubmission(Base):
    __tablename__ = "feed_video_submission"
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    edit_id: Mapped[int] = mapped_column(ForeignKey("feed_video_edit.id"), unique=True)
    actor_id: Mapped[int]
    edit_version: Mapped[int]
    result: Mapped[dict] = mapped_column(JSON)


UPLOAD_TABLE_NAMES.add(FeedVideoSubmission.__tablename__)
