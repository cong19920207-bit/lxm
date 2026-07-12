# -*- coding: utf-8 -*-
# 生活流·评论与回复表 feed_comment 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# v1.5 新增；v1.8 明确 lxm_reply 为纯文本直接写入（非 JSON）
# 本 STEP 新增 due_at：LLM-05 计划回复时间，供 STEP-018 DB 轮询消费（§0.5 二选一定案）

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FeedComment(Base):
    """评论与回复表：用户评论 + LXM 回复（LLM-05）"""

    __tablename__ = "feed_comment"
    __table_args__ = (
        Index("idx_feed_comment_post_id", "post_id"),
        Index("idx_feed_comment_user_id", "user_id"),
        Index("idx_feed_comment_gen_status", "gen_status"),
        # due_at 上查询频繁（STEP-018 30s 轮询扫描），加索引
        Index("idx_feed_comment_due_at_gen_status", "due_at", "gen_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("feed_post.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联朋友圈 feed_post.id",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="评论用户 ID",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="用户评论内容")

    # 用户点击「林小梦回复」后发出的连续互动标记；仅影响 H5 落款展示，LLM-05 仍按单条评论回复
    reply_to_lxm: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="是否回复林小梦（0=普通发评/1=点小梦回复发出）；H5 展示「我回复 林小梦」",
    )

    lxm_reply: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="LXM 回复内容（由 LLM-05 生成，纯文本直接写入，无 JSON 包装，v1.8 明确）",
    )
    lxm_reply_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="LXM 回复发出时间"
    )
    lxm_reply_read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment=(
            "用户已读 LXM 回复时间（NULL=未读，计入首页角标；"
            "有时间戳=已读，不计入角标）"
        ),
    )

    # ENUM('pending','generating','ready','failed')
    gen_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        comment="LXM 回复生成状态（LLM-05）：pending/generating/ready/failed；failed 时管理员可手动补发",
    )

    # 本 STEP 补齐字段（§0.5 二选一定案，LLM-05 走 DB 轮询消费）
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="LLM-05 计划回复时间；轮询消费用（STEP-018 每 30s 扫 due_at<=NOW() AND gen_status='pending'）",
    )

    # M3 STEP-034 新增：后台评论软删标记（0=正常/1=已隐藏）；
    # 隐藏后不在用户端 Feed 展示，DB 记录保留，可后台恢复
    is_hidden: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="后台软删标记（0=正常/1=已隐藏），STEP-034 使用",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
