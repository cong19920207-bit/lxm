# -*- coding: utf-8 -*-
# 关系模块的 Pydantic 请求/响应模型

from pydantic import BaseModel


class RelationshipStatusData(BaseModel):
    """关系状态响应数据"""
    level: int
    level_name: str
    growth_value: int
    next_threshold: int | None
    progress_percent: int
    silence_days: int
    ai_current_emotion: str


class GrowthHistoryItem(BaseModel):
    """成长历史条目"""
    action_type: str
    earned_today: int
    daily_limit: int
    points_per_action: int
