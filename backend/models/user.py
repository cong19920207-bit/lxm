# -*- coding: utf-8 -*-
# 用户表 users 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    relationship_level: Mapped[int] = mapped_column(Integer, default=0)  # 0-3
    growth_value: Mapped[int] = mapped_column(Integer, default=0)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    login_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── 生活流扩展字段（PRD v1.9.4 §11.4；M1 STEP-001 新增）──
    # 用户最近一次进入朋友圈页的时间；用于首页 [New] 徽标判定（NULL=从未进入）
    last_feed_entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
