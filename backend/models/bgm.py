"""BGM public assets and recoverable operations; never stores H5 preferences."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id():
    return str(uuid4())


UTC_TIME = DateTime().with_variant(DATETIME(fsp=6), 'mysql')
BGM_TABLE_NAMES = frozenset({'bgm_track', 'bgm_catalog', 'bgm_operation', 'bgm_asset', 'bgm_processing_slot'})


class BgmTrack(Base):
    __tablename__ = 'bgm_track'
    __table_args__ = (
        CheckConstraint('record_version >= 1', name='ck_bgm_track_revision'),
        CheckConstraint("audio_state IN ('receiving','processing','ready','failed','deleting','delete_failed','deleted')", name='ck_bgm_track_state'),
        CheckConstraint("enabled = 0 OR audio_state = 'ready'", name='ck_bgm_enabled_ready'),
        Index('ix_bgm_track_listing', 'audio_state', 'created_at', 'id'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    record_version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    audio_state: Mapped[str] = mapped_column(String(24), default='receiving', nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_position: Mapped[int | None] = mapped_column(Integer)
    ever_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hidden_at: Mapped[datetime | None] = mapped_column(UTC_TIME)
    audio_asset_id: Mapped[str | None] = mapped_column(String(36))
    cover_asset_id: Mapped[str | None] = mapped_column(String(36))
    media_version: Mapped[str | None] = mapped_column(String(36))
    cover_version: Mapped[str | None] = mapped_column(String(36))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_operation_id: Mapped[str | None] = mapped_column(String(36))
    failure_category: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, onupdate=utcnow, nullable=False)


class BgmCatalog(Base):
    __tablename__ = 'bgm_catalog'
    __table_args__ = (CheckConstraint('id = 1', name='ck_bgm_catalog_singleton'),
                      CheckConstraint('catalog_version >= 0', name='ck_bgm_catalog_version'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    catalog_version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    default_track_id: Mapped[str | None] = mapped_column(String(36))


class BgmOperation(Base):
    __tablename__ = 'bgm_operation'
    __table_args__ = (Index('ix_bgm_operation_recovery', 'state', 'deadline_at'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    track_id: Mapped[str | None] = mapped_column(String(36), index=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    source_size: Mapped[int | None] = mapped_column(BigInteger)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24), default='accepted', nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(UTC_TIME)
    receive_deadline_at: Mapped[datetime | None] = mapped_column(UTC_TIME)
    result: Mapped[dict | None] = mapped_column(JSON)
    failure_category: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTC_TIME)


class BgmAsset(Base):
    __tablename__ = 'bgm_asset'
    __table_args__ = (
        CheckConstraint("kind IN ('audio','cover')", name='ck_bgm_asset_kind'),
        Index('ix_bgm_asset_owner', 'track_id', 'state'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    track_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(36), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    mime_type: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    public_url: Mapped[str | None] = mapped_column(String(2048))
    state: Mapped[str] = mapped_column(String(24), default='planned', nullable=False)
    cleanup_state: Mapped[str] = mapped_column(String(24), default='not_requested', nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(64))
    retired_at: Mapped[datetime | None] = mapped_column(UTC_TIME)
    not_before: Mapped[datetime | None] = mapped_column(UTC_TIME)
    created_at: Mapped[datetime] = mapped_column(UTC_TIME, default=utcnow, nullable=False)


class BgmProcessingSlot(Base):
    __tablename__ = 'bgm_processing_slot'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    owner_id: Mapped[str | None] = mapped_column(String(64))
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(24), default='free', nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(UTC_TIME)
    deadline_at: Mapped[datetime | None] = mapped_column(UTC_TIME)
