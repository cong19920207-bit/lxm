# -*- coding: utf-8 -*-
# 生活流·点赞/已读感知排队表 agent_aware_queue 的 SQLAlchemy 模型定义（PRD v1.9.4 §11.4）
#
# v1.9 新增。与现有 agent_message、relationship（Future 槽字段）表完全独立，
# 不共用字段、不共用索引。支持同一用户同时存在多条 pending 记录。
# 生成成功后写入 agent_message 表并将 sent/agent_message_id 回写至本表，
# 供 10.8 节后台管理页面（M3 STEP-035）联合查询展示。
#
# M1 期间本表已建但仅由 M2 使用（STEP-019/020/021）；M1 交付 stub 保留结构。

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AgentAwareQueue(Base):
    """点赞/已读感知排队表（v1.9 新增；M2 主用）"""

    __tablename__ = "agent_aware_queue"
    __table_args__ = (
        Index("idx_agent_aware_queue_user_id", "user_id"),
        Index("idx_agent_aware_queue_due_at_status", "due_at", "status"),
        Index("idx_agent_aware_queue_post_id", "post_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="触发用户 ID",
    )
    # ENUM('LIKE_AWARE','READ_AWARE')
    trigger_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="触发类型：LIKE_AWARE / READ_AWARE"
    )
    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("feed_post.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 feed_post.id",
    )
    relationship_stage: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="入队时的关系阶段快照（stranger/friend/intimate/soulmate），生成时使用，阶段升级不重算",
    )
    due_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="计划发送时间，由触发时刻+对应延迟窗口计算得出",
    )
    # ENUM('pending','sent','failed')
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        comment="记录状态：pending / sent / failed",
    )
    # M2 STEP-019 新增：入队时确定使用的 Prompt config_key（LIKE_AWARE 恒为 prompt_p07；
    # READ_AWARE 特殊档 prompt_p14 / 常规档按关系档 prompt_p08~p11），消费时直接使用，避免重算档位
    prompt_key: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="生成使用的 Prompt config_key（入队时确定）"
    )
    # M2 STEP-019 新增：入队快照的附加上下文（如 is_special / snapshot_summary），JSON
    extra_context: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="入队附加上下文快照（is_special / snapshot_summary 等）"
    )
    agent_message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="生成成功后关联的 agent_message.id，便于后台联合查询展示",
    )
    fail_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="失败原因，生成失败时记录",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="触发/入队时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
