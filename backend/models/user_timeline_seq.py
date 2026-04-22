# -*- coding: utf-8 -*-
# 用户时间线序号表：为每个用户维护一个单调递增的 sort_seq 计数器，
# 保证 conversation_log 和 agent_message 跨表全局有序

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class UserTimelineSeq(Base):
    """用户时间线序号表，per-user 原子递增计数器"""

    __tablename__ = "user_timeline_seq"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
