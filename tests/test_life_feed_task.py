# -*- coding: utf-8 -*-
"""生活流定时任务的日期目标回归测试。"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from backend.tasks import life_feed_task as task_mod


_CURRENT_DAY = date(2026, 7, 13)  # 周一：覆盖周大纲切换边界


class _FrozenDate(date):
    @classmethod
    def today(cls) -> date:
        return _CURRENT_DAY


@pytest.mark.asyncio
async def test_daily_scenes_task_generates_current_day(monkeypatch):
    monkeypatch.setattr(task_mod, "date", _FrozenDate)
    generate = AsyncMock(return_value={"status": "ready", "scenes": 2})

    with patch(
        "backend.services.life_planner_service.life_planner_service.generate_daily_scenes",
        generate,
    ):
        await task_mod.daily_scenes_task()

    generate.assert_awaited_once_with(_CURRENT_DAY)


@pytest.mark.asyncio
async def test_daily_scenes_retry_task_retries_current_day(monkeypatch):
    monkeypatch.setattr(task_mod, "date", _FrozenDate)
    generate = AsyncMock(return_value={"status": "ready", "scenes": 2})

    with patch(
        "backend.services.life_planner_service.life_planner_service.generate_daily_scenes",
        generate,
    ):
        await task_mod.daily_scenes_retry_task()

    generate.assert_awaited_once_with(_CURRENT_DAY)
