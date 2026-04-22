# -*- coding: utf-8 -*-
# 数据统计模块 Pydantic 模型

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DashboardUserData(BaseModel):
    """仪表盘用户数据"""
    new_users_today: int = 0
    new_users_7days: int = 0
    new_users_30days: int = 0
    active_users_today: int = 0
    active_users_7days: int = 0


class DashboardRetentionData(BaseModel):
    """仪表盘留存率数据"""
    next_day_retention: float | None = None
    day7_retention: float | None = None
    day30_retention: float | None = None


class DashboardConversationData(BaseModel):
    """仪表盘对话数据"""
    total_conversation_rounds: int = 0
    avg_rounds_today: float | None = None


class DashboardAgentData(BaseModel):
    """仪表盘主动消息数据"""
    agent_sent_today: int = 0
    agent_open_count_today: int = 0
    agent_open_rate: float | None = None


class DashboardAIPerformanceData(BaseModel):
    """仪表盘AI性能数据"""
    llm_avg_response_ms: float | None = None  # 无 Redis 样本时为 None，与 0ms 区分
    llm_success_rate: float | None = None
    persona_deviation_rate: float = 0
    content_block_rate: float = 0


class TrendItem(BaseModel):
    """趋势数据项"""
    date: str
    value: int


class ReportDailyItem(BaseModel):
    """报表每日数据项"""
    date: str
    new_users: int | None = None
    active_users: int | None = None
    conversation_rounds: int | None = None
    agent_sent: int | None = None
    agent_opened: int | None = None
    reply_rate: float | None = None
    persona_risk_count: int | None = None
    total_count: int | None = None
    deviation_rate: float | None = None


class LevelDistributionItem(BaseModel):
    """关系等级分布"""
    level: int
    name: str
    count: int


class EmotionDistributionItem(BaseModel):
    """情绪分布"""
    emotion: str
    count: int
    percent: float


class ReportResponse(BaseModel):
    """报表分页 data，与 GET /api/admin/stats/report 返回的 JSON 键一致。

    列表字段在 JSON 中为 ``list``；Python 属性名为 ``list_``（避免与内置 list 及注解冲突）。
    序列化与接口对齐时请使用 ``model_dump(by_alias=True)``。
    """

    model_config = ConfigDict(populate_by_name=True)

    list_: list[ReportDailyItem] = Field(default_factory=list, alias="list")
    total: int = 0
    page: int = 1
    page_size: int = 20
    extra: dict[str, Any] = Field(default_factory=dict)
