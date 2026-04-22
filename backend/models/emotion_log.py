# -*- coding: utf-8 -*-
# 情绪日志表 emotion_log 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class EmotionLog(Base):
    """情绪日志表"""

    __tablename__ = "emotion_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    emotion_label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation_log.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # TD-016 / V2-A：与本轮 conversation_log 行相同的 round_id；旧数据与 V2-B 前写入均为 NULL
    round_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
