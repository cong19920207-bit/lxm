# -*- coding: utf-8 -*-
# 生活流·日生活计划表 life_plan 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class LifePlan(Base):
    """日生活计划表：LLM-02 每日 00:20 生成场景数组"""

    __tablename__ = "life_plan"
    __table_args__ = (
        Index("idx_life_plan_plan_date", "plan_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, comment="计划日期，关联 life_plan_outline.plan_date"
    )
    scenes: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        comment=(
            "场景列表（scene_id/time_range/city/category/venue_type/description）；"
            "venue_type 自由发挥不受枚举约束"
        ),
    )
    # ENUM('generating','ready','failed')
    gen_status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="生成状态：generating / ready / failed"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
