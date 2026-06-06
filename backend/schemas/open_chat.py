# -*- coding: utf-8 -*-
# Open API v1 对话 Schema

from pydantic import BaseModel, Field


class OpenChatSendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
