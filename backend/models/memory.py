# -*- coding: utf-8 -*-
# 长期记忆表 memory 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Memory(Base):
    """长期记忆表"""

    __tablename__ = "memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False)

    source: Mapped[str] = mapped_column(String(20), nullable=False)  # auto / manual / admin
    dashvector_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # 软删除

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 普通记忆 180 天，重要记忆为 NULL
