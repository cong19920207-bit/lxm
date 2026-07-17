# -*- coding: utf-8 -*-
# 管理员用户表 admin_users 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AdminUser(Base):
    """管理员用户表"""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="角色：super_admin/ops_admin/ai_trainer/tech_ops/observer",
    )
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="备注说明")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_locked: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="True=账号已锁定，需超级管理员手动解锁",
    )
    login_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="管理员会话版本",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_password_change_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="创建者账号名")
