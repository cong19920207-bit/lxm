# -*- coding: utf-8 -*-
"""
数据回填脚本：为 conversation_log 和 agent_message 的历史数据填充 sort_seq，
并初始化 user_timeline_seq 表。

使用方法：
  cd 项目根目录
  python -m scripts.backfill_sort_seq

注意：
  1. 执行前请先完成 DDL（应用启动会自动补齐；亦可手动执行 scripts/migrate_add_sort_seq.sql）
  2. 逻辑与 backend.services.timeline_backfill_service 一致，可重复执行
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import engine  # noqa: E402
from backend.services.timeline_backfill_service import run_full_backfill  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    try:
        await run_full_backfill()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
