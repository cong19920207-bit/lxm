# -*- coding: utf-8 -*-
# 世界状态表 world_state 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class WorldState(Base):
    """世界状态表"""

    __tablename__ = "world_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    trigger_conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    relevance_weight: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
