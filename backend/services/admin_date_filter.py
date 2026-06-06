# -*- coding: utf-8 -*-
# 管理端列表按 created_at 筛选的日期解析（与 admin_diary_query / agent_mgmt 语义一致）

from datetime import datetime, timedelta
from typing import Any

from backend.constants import ADMIN_ERR_QUERY_DATE_FORMAT_INVALID
from backend.schemas.common import ApiResponse


def parse_admin_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None, ApiResponse | None]:
    """
    解析管理端 YYYY-MM-DD 日期区间。

    :return: (start_dt 含当日 00:00:00, end_exclusive 为结束日次日 00:00:00, 错误响应)
    """
    start_dt: datetime | None = None
    end_exclusive: datetime | None = None

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return (
                None,
                None,
                ApiResponse.fail(
                    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
                    message="start_date 格式错误，应为 YYYY-MM-DD",
                ),
            )

    if end_date:
        try:
            end_exclusive = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            return (
                None,
                None,
                ApiResponse.fail(
                    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
                    message="end_date 格式错误，应为 YYYY-MM-DD",
                ),
            )

    if start_dt is not None and end_exclusive is not None and start_dt >= end_exclusive:
        return (
            None,
            None,
            ApiResponse.fail(
                ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
                message="结束日期不能早于开始日期",
            ),
        )

    return start_dt, end_exclusive, None


def append_created_at_range(
    filters: list[Any],
    column: Any,
    start_dt: datetime | None,
    end_exclusive: datetime | None,
) -> None:
    """向 SQLAlchemy 过滤列表追加 created_at 区间条件。"""
    if start_dt is not None:
        filters.append(column >= start_dt)
    if end_exclusive is not None:
        filters.append(column < end_exclusive)
