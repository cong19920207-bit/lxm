# -*- coding: utf-8 -*-
# 对话模块的 Pydantic 请求/响应模型

from pydantic import BaseModel, Field


class ChatSendRequest(BaseModel):
    """发送消息请求体"""
    content: str = Field(..., min_length=1, max_length=2000, description="用户消息内容")
    client_message_id: str | None = Field(
        default=None,
        max_length=64,
        description="客户端幂等键（UUID 等）；可选，后续与 Idempotency-Key 对齐",
    )


class ChatResendRequest(BaseModel):
    """叹号重发请求体（锚定字段可扩展；当前可不传 Body）。"""
    client_resend_id: str | None = Field(
        default=None,
        max_length=128,
        description="客户端重发幂等键，可选",
    )


class EmotionData(BaseModel):
    """情绪数据"""
    label: str = Field(default="平静", description="情绪标签")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")


class ChatDeltaEvent(BaseModel):
    """SSE 流式增量事件"""
    type: str = "delta"
    content: str = ""


class ChatDoneEvent(BaseModel):
    """SSE 流式结束事件"""
    type: str = "done"
    emotion: EmotionData = Field(default_factory=EmotionData)
