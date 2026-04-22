# -*- coding: utf-8 -*-
# 主动消息表 agent_message 的 SQLAlchemy 模型定义

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class TriggerType:
    """主动消息触发类型常量：P0情绪跟进/P1长期沉默/P2日常问候/P3凌晨在线/P4轻度沉默"""

    P0 = "P0"  # 情绪跟进
    P1 = "P1"  # 长期沉默
    P2 = "P2"  # 日常问候
    P3 = "P3"  # 凌晨在线
    P4 = "P4"  # 轻度沉默


class AgentMessage(Base):
    """主动消息表"""

    __tablename__ = "agent_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    trigger_type: Mapped[str] = mapped_column(String(10), nullable=False)  # P0 / P1 / P2 / P3 / P4
    content: Mapped[str] = mapped_column(Text, nullable=False)
    action_score: Mapped[float] = mapped_column(Float, nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    # 统一时间线排序序号，per-user 单调递增，跨 conversation_log 和 agent_message 全局唯一
    sort_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
