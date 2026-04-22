# -*- coding: utf-8 -*-
# TD-020 / V3-A：用户短期情绪属性 DB 真相源（Redis miss 时冷读）

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class UserShortTermEmotion(Base):
    """每用户一行：短期情绪画像（与 emotion_log 轮级、句级字段分层）。"""

    __tablename__ = "user_short_term_emotion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    emotion_label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # 可选：存本轮原始 emotion JSON，便于审计扩展
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
