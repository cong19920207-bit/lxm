# -*- coding: utf-8 -*-
# Open API Key 元数据表（仅存 hash + 脱敏前缀，不存明文）

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class UserApiKey(Base):
    """每用户最多一行 Open API Key 记录。"""

    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_api_keys_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
