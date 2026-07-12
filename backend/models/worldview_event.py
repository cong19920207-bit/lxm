# -*- coding: utf-8 -*-
# 生活流·她的宇宙事件库 worldview_event 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# event_name UNIQUE：LLM-03 生成事件时走 INSERT ON DUPLICATE KEY UPDATE / INSERT IGNORE
# 首次写入时间即固定观点，不覆盖历史版本（详见 STEP-009）

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class WorldviewEvent(Base):
    """她的宇宙·事件库：event_name 描述性短语 UNIQUE"""

    __tablename__ = "worldview_event"
    __table_args__ = (
        Index("idx_worldview_event_event_name", "event_name"),
        Index("idx_worldview_event_source_scene_id", "source_scene_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        comment='话题名称（唯一键，描述性短语，如"在人多景区的感受与应对方式"）',
    )
    event_view: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=(
            "林小梦对该话题的固定看法（100-200字，"
            "含核心态度[喜欢/排斥/矛盾/无感，v1.8]/典型场景/行为倾向）"
        ),
    )
    source_scene_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="首次触发生成的 scene_id，可溯源至来源场景"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="首次写入时间，可用于后台按时间溯源"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
