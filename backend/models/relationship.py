# -*- coding: utf-8 -*-
# 关系状态表 relationship 的 SQLAlchemy 模型定义

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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

    # ── Step6 记忆写回扩展字段（R-MEM-05 / R-MEM-07） ──
    relation_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_real_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_hobby_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    character_purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    character_attitude: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Step8 Future 槽机制扩展字段（R-FUT-02 / R-FUT-03） ──
    future_timestamp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    future_action: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    proactive_times: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
