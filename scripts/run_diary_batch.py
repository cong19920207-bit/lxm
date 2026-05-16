# -*- coding: utf-8 -*-
"""
运维脚本：手动触发与定时任务相同的「每日 AI 日记」批跑（M2a / TD-013）。

使用方法（项目根目录）：
  PYTHONPATH=. python -m scripts.run_diary_batch

容器内（工作目录为应用根，与 docker compose 中一致）：
  python -m scripts.run_diary_batch

说明：
  1. 语义与 APScheduler 调用的 DiaryService.run_daily_diary_task 一致，见 docs/ops-diary.md。
  2. 补跑锚点为「当前上海日历日」，统计窗为前一自然日，不可指定历史漏跑日（M1）。
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import async_session_maker, engine  # noqa: E402
from backend.services.diary_service import DiaryService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        logger.info("开始手动执行每日日记批跑（run_daily_diary_task）")
        async with async_session_maker() as db:
            svc = DiaryService(db)
            await svc.run_daily_diary_task()
        logger.info("手动每日日记批跑已结束")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
