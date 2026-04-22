# -*- coding: utf-8 -*-
# 对话记录表 conversation_log 的 SQLAlchemy 模型定义（含 persona_risk_flag）

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ConversationLog(Base):
    """对话记录表"""

    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 用户消息才有
    emotion_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emotion_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 注入的记忆内容，JSON 格式
    memory_injected: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    persona_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    persona_risk_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 统一时间线排序序号，per-user 单调递增，跨 conversation_log 和 agent_message 全局唯一
    sort_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True)

    # TD-015：用户行送达/失败态（英文蛇形，与 constants 中单点枚举一致）；助手行在 DB 中可为 NULL，序列化时按 A1 输出 null
    delivery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Q14：超过 10 条打包窗口时最旧 user 行仍落库但本轮未进入 Prompt
    skipped_in_prompt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # TD-016 / V2-A：一轮多 user + 单 assistant 共享的 UUID 文本；旧数据与 V2-B 前写入均为 NULL，由后续切片写入
    round_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
