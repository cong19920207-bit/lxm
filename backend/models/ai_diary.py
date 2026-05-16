# -*- coding: utf-8 -*-
# AI 日记表 ai_diary 的 SQLAlchemy 模型定义

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AiDiary(Base):
    """AI 日记表"""

    __tablename__ = "ai_diary"
    __table_args__ = (
        UniqueConstraint("user_id", "covers_beijing_date", name="ix_ai_diary_user_covers_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    relationship_level_at_creation: Mapped[int] = mapped_column(Integer, nullable=False)  # 生成时的关系等级

    # 本日记内容所覆盖的「北京日历日」（统计窗为 [该日 00:00, 次日 00:00) 上海）；旧数据可为 NULL（H2 不回填）
    covers_beijing_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
