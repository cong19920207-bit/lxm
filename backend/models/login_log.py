# -*- coding: utf-8 -*-
# 登录日志表 login_log 的 SQLAlchemy 模型定义，用于 Agent P2 触发的登录习惯分析

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class LoginLog(Base):
    """登录日志表，每次用户登录写入一条记录"""

    __tablename__ = "login_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    login_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 时段：morning=7-9点 / evening=20-22点 / other
    time_period: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
