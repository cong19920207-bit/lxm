# -*- coding: utf-8 -*-
# 操作日志表 admin_operation_logs 的 SQLAlchemy 模型定义
# 此表数据永久保留，不可删除，不可修改

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AdminOperationLog(Base):
    """操作日志表（永久保留，不可删除/修改）"""

    __tablename__ = "admin_operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="账号被删后仍保留日志",
    )
    admin_username: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="冗余存储，确保日志可追溯",
    )
    module: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="操作模块，如：人格管理/Prompt管理/用户管理",
    )
    action: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="操作类型：create/edit/delete/view/publish/rollback/login/logout/unlock",
    )
    target_description: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="操作对象描述",
    )
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="修改前内容")
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="修改后内容")
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
