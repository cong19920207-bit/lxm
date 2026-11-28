from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Text = Annotated[str, Field(min_length=1, max_length=80)]
Dimension = Annotated[int, Field(gt=0, le=100000)]
Entry = Literal["main/index", "main/chat", "main/feed", "main/diary", "main/memory",
                "main/relationship", "main/settings", "main/login", "main/pet", "public/feed"]


class DeviceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device: Text | None = None
    os: Text | None = None
    os_version: Text | None = None
    model: Text | None = None
    browser: Text | None = None
    browser_version: Text | None = None
    environment: Text | None = None
    screen_width: Dimension | None = None
    screen_height: Dimension | None = None
    viewport_width: Dimension | None = None
    viewport_height: Dimension | None = None
    orientation: Literal["横屏", "竖屏"] | None = None
    pixel_ratio: Annotated[float, Field(gt=0, le=100)] | None = None
    processors: Dimension | None = None


class OpenReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    visitor_id: UUID | None = None
    occurred_at: datetime
    entry: Entry

    @field_validator("occurred_at")
    @classmethod
    def utc_instant(cls, value):
        if value.tzinfo is None:
            raise ValueError("发生时间须包含时区")
        return value.astimezone(timezone.utc).replace(tzinfo=None)


class VisitorInput(OpenReference):
    kind: Literal["open", "return", "navigate", "interaction", "identity"]
    replay: bool = False
    witness: Annotated[str, Field(max_length=1200)] | None = None
    profile: DeviceProfile | None = None
