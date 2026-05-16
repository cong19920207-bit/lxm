# -*- coding: utf-8 -*-
# scripts/run_diary_batch：仅验证调用链，不连真实 MySQL、不调用 LLM

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.diary_service import DiaryService


@pytest.mark.asyncio
async def test_run_diary_batch_main_calls_run_daily_diary_task(monkeypatch):
    """main 应打开 session、调用 run_daily_diary_task，并在 finally 中 dispose 引擎。"""
    import scripts.run_diary_batch as mod

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(mod, "async_session_maker", MagicMock(return_value=mock_cm))

    fake_engine = MagicMock()
    dispose_mock = AsyncMock()
    fake_engine.dispose = dispose_mock
    monkeypatch.setattr(mod, "engine", fake_engine)

    run_mock = AsyncMock()
    monkeypatch.setattr(DiaryService, "run_daily_diary_task", run_mock)

    await mod.main()

    run_mock.assert_awaited_once()
    dispose_mock.assert_awaited_once()
    mod.async_session_maker.assert_called_once()
