# -*- coding: utf-8 -*-
# 主动消息表 agent_message 的 SQLAlchemy 模型定义
#
# v1.9 生活流扩展（M1 STEP-001）：
#   - trigger_type 由 String(10) 扩为 String(16)，为 LIKE_AWARE / READ_AWARE 预留
#   - TriggerType 常量类新增 LIKE_AWARE / READ_AWARE 两项（M2 STEP-020/021 消费）

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class TriggerType:
    """主动消息触发类型常量：
    P0情绪跟进/P1长期沉默/P2日常问候/P3凌晨在线/P4轻度沉默/FUTURE Future槽/
    LIKE_AWARE 点赞感知/READ_AWARE 已读感知（v1.9 生活流新增，M2 STEP-020/021 落库）
    """

    P0 = "P0"  # 情绪跟进
    P1 = "P1"  # 长期沉默
    P2 = "P2"  # 日常问候
    P3 = "P3"  # 凌晨在线
    P4 = "P4"  # 轻度沉默
    FUTURE = "FUTURE"  # Future 槽到期消费
    LIKE_AWARE = "LIKE_AWARE"  # 点赞感知（生活流，M2 STEP-020）
    READ_AWARE = "READ_AWARE"  # 已读感知（生活流，M2 STEP-021）


class AgentMessage(Base):
    """主动消息表"""

    __tablename__ = "agent_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # v1.9 生活流扩展：String(10) → String(16)，为 LIKE_AWARE / READ_AWARE 预留（各 10 字符顶满原字段）
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)  # P0 / P1 / P2 / P3 / P4 / FUTURE / LIKE_AWARE / READ_AWARE
    content: Mapped[str] = mapped_column(Text, nullable=False)
    action_score: Mapped[float] = mapped_column(Float, nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    # 统一时间线排序序号，per-user 单调递增，跨 conversation_log 和 agent_message 全局唯一
    sort_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
