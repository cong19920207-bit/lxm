# -*- coding: utf-8 -*-
# APScheduler 定时任务调度：日记生成、Agent 主动消息扫描

import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_daily_diary_task() -> None:
    """每日日记生成任务包装器（run_daily_diary_task 内部自行创建 session）"""
    from backend.database import async_session_maker
    from backend.services.diary_service import DiaryService

    logger.info("[定时任务] 触发每日日记生成")
    try:
        async with async_session_maker() as db:
            svc = DiaryService(db)
            await svc.run_daily_diary_task()
    except Exception as e:
        logger.error("[定时任务] 日记生成任务异常: %s", str(e), exc_info=True)


async def _run_agent_scan() -> None:
    """Agent 主动消息扫描任务包装器"""
    logger.info("[定时任务] 触发 Agent 主动消息扫描")
    try:
        from backend.services.agent_service import AgentService
        await AgentService().run_agent_scan()
    except Exception as e:
        logger.error("[定时任务] Agent 扫描任务异常: %s", str(e), exc_info=True)


def start_scheduler(diary_hour: int = 0, diary_minute: int = 30) -> None:
    """注册并启动所有定时任务。日记 Cron 使用 UTC，时刻由 diary_rules 在启动时解析后传入。"""
    # 与 DiaryService「今日」日界一致，使用 UTC（见 docs/diary-refactor-plan.md §0.7）
    scheduler.add_job(
        _run_daily_diary_task,
        trigger=CronTrigger(
            hour=diary_hour,
            minute=diary_minute,
            timezone=ZoneInfo("UTC"),
        ),
        id="daily_diary_task",
        name="每日AI日记生成",
        replace_existing=True,
    )

    # 每6小时执行 Agent 主动消息扫描
    scheduler.add_job(
        _run_agent_scan,
        trigger=IntervalTrigger(hours=6),
        id="agent_scan_task",
        name="Agent主动消息扫描",
        replace_existing=True,
    )

    scheduler.start()
    jobs = scheduler.get_jobs()
    logger.info("[定时任务] 调度器已启动，已注册 %d 个任务", len(jobs))
    for j in jobs:
        if j.id == "daily_diary_task" and j.next_run_time:
            nrt = j.next_run_time
            if nrt.tzinfo is not None:
                nrt = nrt.astimezone(ZoneInfo("UTC"))
            logger.info(
                "[定时任务] 每日日记下次执行（UTC）: %s",
                nrt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )


def shutdown_scheduler() -> None:
    """优雅停止调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[定时任务] 调度器已停止")
