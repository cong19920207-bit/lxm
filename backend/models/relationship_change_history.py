# -*- coding: utf-8 -*-
# 关系扩展字段变更历史表 relationship_change_history 的 SQLAlchemy 模型定义
# 需求来源：R-L1L3-05 / R-MEM-05（append-only，仅 Step6 自动更新触发写入）

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class RelationshipChangeHistory(Base):
    """关系扩展字段变更历史表（append-only）"""

    __tablename__ = "relationship_change_history"
    __table_args__ = (
        Index("ix_rel_change_user_created", "user_id", "created_at"),
        {"mysql_charset": "utf8mb4"},
    )

    # MySQL 用 BIGINT，SQLite 测试用 INTEGER（仅 INTEGER 支持 autoincrement）
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True,
    )
    relationship_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("relationship.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="step6", server_default="step6"
    )
    round_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
