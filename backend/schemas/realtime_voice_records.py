"""Public admin export contract: effective transcript fields only."""
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    call_ids: list[Annotated[str, StringConstraints(min_length=1,max_length=64)]] = Field(min_length=1,max_length=100)


class EffectiveExportTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    call_id: str
    turn_index: int
    user_text_final: str | None
    assistant_text_effective: str | None
    effective_text_expires_at: datetime


class EffectiveExportData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[EffectiveExportTurn]
    snapshot_at: datetime


class EffectiveExportResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: Literal[0]
    data: EffectiveExportData
