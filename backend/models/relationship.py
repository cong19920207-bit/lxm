# -*- coding: utf-8 -*-
# 关系状态表 relationship 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Relationship(Base):
    """关系状态表"""

    __tablename__ = "relationship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-3
    growth_value: Mapped[int] = mapped_column(Integer, nullable=False)

    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consecutive_login_days: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
