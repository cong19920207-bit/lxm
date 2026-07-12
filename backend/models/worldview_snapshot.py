# -*- coding: utf-8 -*-
# 生活流·她的宇宙动态快照表 worldview_snapshot 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# v1.9 命名说明：中文业务概念改名为"她的宇宙"，表名沿用不变。

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class WorldviewSnapshot(Base):
    """她的宇宙·动态快照表：LLM-03 每日 00:45 按 scene 生成"""

    __tablename__ = "worldview_snapshot"
    __table_args__ = (
        Index("idx_worldview_snapshot_plan_date", "plan_date"),
        Index("idx_worldview_snapshot_scene_id", "scene_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False, comment="关联计划日期")
    scene_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联场景 ID")

    feeling_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="自然语言感受描述（A）"
    )
    emotion_value: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment=(
            "情绪值标签（B），优先取自 emotion_vocab 核心词表（当前14个），"
            "LLM 可视场景生成更贴切的自由词（核心词优先+自由兜底机制，v1.8）"
        ),
    )
    focus_tag: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="当前关注点（B）"
    )
    worldview_trigger: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="触发的价值观标签（B），用于写入她的宇宙事件库 event_name",
    )
    # ENUM('generating','ready','failed')
    gen_status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="生成状态：generating / ready / failed"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
