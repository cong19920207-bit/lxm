# -*- coding: utf-8 -*-
# 记忆模块的 Pydantic 请求/响应模型

from pydantic import BaseModel, Field


class MemoryAddRequest(BaseModel):
    """手动添加记忆"""
    content: str = Field(..., min_length=1, max_length=500, description="记忆内容")


class MemoryUpdateRequest(BaseModel):
    """编辑记忆"""
    content: str = Field(..., min_length=1, max_length=500, description="新的记忆内容")


class AdminMemoryUpdateRequest(BaseModel):
    """后台编辑用户记忆：content 校验与用户端 MemoryUpdateRequest 一致；importance_score 预留"""

    content: str = Field(..., min_length=1, max_length=500, description="新的记忆内容")
    importance_score: float | None = Field(None, ge=0.0, le=1.0, description="重要性 0–1，预留")
