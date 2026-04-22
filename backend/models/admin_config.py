# -*- coding: utf-8 -*-
# 管理配置表 admin_config 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AdminConfig(Base):
    """管理配置表"""

    __tablename__ = "admin_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 同一 config_key 可有多行（草稿 is_draft=True + 生效/历史 is_draft=False）；库表勿对 config_key 单列 UNIQUE
    config_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_draft: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="True=草稿版本, False=正式/历史版本",
    )
    updated_by: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="操作人账号名")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
