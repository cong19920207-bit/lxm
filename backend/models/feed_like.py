# -*- coding: utf-8 -*-
# 生活流·用户点赞关系表 feed_like 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# UNIQUE (user_id, post_id) 保证幂等；点赞 IM 同帖去重仍查 agent_aware_queue

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FeedLike(Base):
    """用户点赞关系表（v1.9.1 新增）"""

    __tablename__ = "feed_like"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uk_feed_like_user_post"),
        Index("idx_feed_like_post_id", "post_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="点赞用户 ID",
    )
    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("feed_post.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 feed_post.id",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
