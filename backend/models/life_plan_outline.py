# -*- coding: utf-8 -*-
# 生活流·周大纲表 life_plan_outline 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# 字段说明按 PRD 11.4 原文 COMMENT 保留，便于后台 DB 排查
# categories 由应用层（Prompt 注入 + 后台校验）约束取值，不在 DB 层建外键

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class LifePlanOutline(Base):
    """周大纲表：LLM-01 每周日 23:00 生成，days_count 参数化"""

    __tablename__ = "life_plan_outline"
    __table_args__ = (
        Index("idx_life_plan_outline_week_start_date", "week_start_date"),
        Index("idx_life_plan_outline_plan_date", "plan_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="所属自然周周一日期")
    plan_date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, comment="自然日日期"
    )
    city: Mapped[str] = mapped_column(String(50), nullable=False, comment="当天所在城市")
    categories: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="当天内容分类，多个用\\n分隔；取值受后台 categories_vocab 固定枚举表约束（v1.8）",
    )
    # ENUM('auto','manual')：本项目沿用 String + 应用层校验，避免 MySQL ENUM 变更复杂性
    gen_status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="生成来源：auto=自动生成 / manual=人工补录"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
