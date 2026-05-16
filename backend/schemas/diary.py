# -*- coding: utf-8 -*-
# AI 日记模块的 Pydantic 请求/响应模型

from datetime import date, datetime

from pydantic import BaseModel, Field


class DiaryItem(BaseModel):
    """日记列表单条记录"""
    id: int
    content: str
    relationship_level_at_creation: int
    is_read: bool
    created_at: datetime
    # 日记内容覆盖的北京日历日；旧数据可能为 null（不回填），H5 可回退用 created_at
    covers_beijing_date: date | None = None


class DiaryListResponse(BaseModel):
    """日记列表响应"""
    items: list[DiaryItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
