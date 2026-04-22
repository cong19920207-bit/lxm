# -*- coding: utf-8 -*-
# AI 日记表 ai_diary 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AiDiary(Base):
    """AI 日记表"""

    __tablename__ = "ai_diary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    relationship_level_at_creation: Mapped[int] = mapped_column(Integer, nullable=False)  # 生成时的关系等级

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
