"""Explicit safe projections; internal operation/asset objects are never serialized."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from pydantic import Field, field_validator, model_validator
from typing import Annotated, Literal
import unicodedata
from uuid import UUID


def utc_iso(value: datetime | None):
    return value.isoformat(timespec='microseconds') + 'Z' if value else None


BgmAudioFailureCategory = Literal[
    'size_limit', 'duration_limit', 'unsupported_format', 'mime_mismatch',
    'processing_timeout', 'dependency_unavailable', 'decode_failed', 'probe_limit',
    'invalid_audio', 'format_mismatch', 'invalid_output', 'worker_stopped',
    'processing_failed', 'termination_unconfirmed', 'stale_attempt', 'invalid_asset',
    'storage_unavailable', 'storage_configuration', 'remote_cors', 'remote_mismatch',
    'remote_unreadable', 'remote_mime', 'remote_range', 'storage_unknown',
    'source_mismatch', 'receive_timeout', 'authorization_changed', 'interrupted',
    'deadline_expired', 'worker_interrupted',
]


class BgmCleanupCounts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pending: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)


class BgmTrackCleanupSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')
    audio: BgmCleanupCounts = Field(default_factory=BgmCleanupCounts)
    cover: BgmCleanupCounts = Field(default_factory=BgmCleanupCounts)


class BgmTrackRead(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    name: str
    record_version: int
    audio_state: str
    enabled: bool
    is_default: bool
    sort_position: int | None
    media_version: str | None
    cover_version: str | None
    audio_url: str | None
    cover_url: str | None
    duration_seconds: float | None
    size_bytes: int | None
    ever_published: bool
    hidden_at: str | None
    deletable_at: str | None
    created_at: str
    updated_at: str
    failure_category: BgmAudioFailureCategory | None = None
    cleanup_summary: BgmTrackCleanupSummary = Field(default_factory=BgmTrackCleanupSummary)


class BgmDirectoryResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    catalog_version: int
    default_track_id: str | None
    ordered_track_ids: list[str]
    track_id: str | None
    record_version: int | None


class BgmCoverResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    track_id: str
    record_version: int
    cover_version: str
    cover_url: str | None
    catalog_version: int
    association_removed: bool
    cleanup_state: Literal['pending','not_requested']


class BgmAssetCleanupResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    kind: Literal['audio','cover']
    cleanup_state: str
    failure_category: str | None


class BgmCleanupResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    track_id: str
    record_version: int
    mode: Literal['delete_track','cleanup_assets']
    track_deleted: bool
    remaining_count: int
    assets: list[BgmAssetCleanupResult]


class BgmCleanupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID
    expected_revision: int = Field(ge=1,strict=True)
    expected_catalog_version: int = Field(ge=0,strict=True)


class BgmOperationRead(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    track_id: str | None
    action: str
    state: str
    attempt: int
    deadline_at: str | None
    created_at: str
    finished_at: str | None
    failure_category: str | None = None
    result: BgmDirectoryResult | BgmCoverResult | BgmCleanupResult | None = None


def normalized_name(value):
    if any(unicodedata.category(c) in {'Cc', 'Cs'} for c in value):
        raise ValueError('名称不能含控制字符')
    value = value.strip()
    if not 1 <= len(value) <= 60 or any(unicodedata.category(c) in {'Cc', 'Cs'} for c in value):
        raise ValueError('名称须为1～60个Unicode码点，不能含控制字符')
    return value


class BgmAudioPrepare(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID
    action: Literal['upload_audio', 'retry_audio']
    name: str
    extension: Literal['.mp3', '.m4a', '.aac', '.wav']
    mime_type: str = Field(max_length=64)
    source_size: int = Field(gt=0, le=100*1024*1024, strict=True)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    track_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1, strict=True)

    _name = field_validator('name')(normalized_name)

    @model_validator(mode='after')
    def validate_request(self):
        from backend.services.bgm_media import MediaError, validate_source_type
        try:
            validate_source_type(self.extension, self.mime_type)
        except MediaError as exc:
            raise ValueError(str(exc)) from None
        if self.action == 'upload_audio' and (self.track_id is not None or self.expected_revision is not None):
            raise ValueError('新上传不能指定曲目或记录版本')
        if self.action == 'retry_audio' and (self.track_id is None or self.expected_revision is None):
            raise ValueError('重试需要原曲目与记录版本')
        return self


class BgmTrackMutation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID
    action: Literal['rename', 'enable', 'hide', 'set_default']
    expected_catalog_version: int = Field(ge=0, strict=True)
    expected_revision: int = Field(ge=1, strict=True)
    name: str | None = None
    replacement_default_id: UUID | None = None

    @field_validator('name')
    @classmethod
    def name_boundary(cls, value):
        return normalized_name(value) if value is not None else None

    @model_validator(mode='after')
    def action_fields(self):
        if (self.action == 'rename') != (self.name is not None):
            raise ValueError('只有改名动作需要name')
        if self.replacement_default_id is not None and self.action != 'hide':
            raise ValueError('只有隐藏动作可指定替代默认')
        return self


class BgmOrderMutation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID
    expected_catalog_version: int = Field(ge=0, strict=True)
    track_ids: list[UUID]


class BgmCoverPrepare(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID
    action: Literal['upload_cover']
    track_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    expected_catalog_version: int = Field(ge=0, strict=True)
    extension: Literal['.jpg','.jpeg','.png','.webp']
    mime_type: str = Field(max_length=64)
    source_size: int = Field(gt=0,le=5*1024*1024,strict=True)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def cover_type(self):
        from backend.services.bgm_cover_media import validate_cover_type
        from backend.services.bgm_media import MediaError
        try:validate_cover_type(self.extension,self.mime_type)
        except MediaError as exc:raise ValueError(str(exc)) from None
        return self


class BgmCoverRemoval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    expected_catalog_version: int = Field(ge=0, strict=True)


BgmPrepare = Annotated[BgmAudioPrepare | BgmCoverPrepare, Field(discriminator='action')]
