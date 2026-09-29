# -*- coding: utf-8 -*-
# 成长值获取记录表 relationship_growth_log 的 SQLAlchemy 模型定义

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class RelationshipGrowthLog(Base):
    """成长值获取记录表"""

    __tablename__ = "relationship_growth_log"
    __table_args__ = (
        Index("uk_growth_source", "source_type", "source_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eligible_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
