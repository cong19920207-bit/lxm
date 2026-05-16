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


async def _run_future_slot_scan() -> None:
    """Future 槽消费轮询：扫描到期 Future 槽并触发主动消息子链路"""
    logger.info("[定时任务] 触发 Future 槽轮询")
    try:
        from backend.services.future_handler import future_handler
        consumed = await future_handler.scan_and_consume()
        # 顺带清理超出 30 分钟窗口的过期槽位
        cleaned = await future_handler.cleanup_expired_slots()
        if consumed or cleaned:
            logger.info(
                "[定时任务] Future 槽轮询完成: 消费=%d, 清理过期=%d",
                consumed, cleaned,
            )
    except Exception as e:
        logger.error("[定时任务] Future 槽轮询异常: %s", str(e), exc_info=True)


async def _run_inactive_reset() -> None:
    """R-FUT-03④：30 天无活动自动清零 proactive_times + Future 槽"""
    logger.info("[定时任务] 触发 30 天无活动清零检查")
    try:
        from backend.services.agent_service import AgentService
        count = await AgentService().reset_inactive_proactive_times()
        logger.info("[定时任务] 30 天无活动清零完成，共 %d 人", count)
    except Exception as e:
        logger.error("[定时任务] 30 天无活动清零任务异常: %s", str(e), exc_info=True)


def start_scheduler(diary_hour: int = 0, diary_minute: int = 15) -> None:
    """注册并启动所有定时任务。日记 Cron 使用 Asia/Shanghai，时刻由 diary_rules 在启动时解析后传入。"""
    scheduler.add_job(
        _run_daily_diary_task,
        trigger=CronTrigger(
            hour=diary_hour,
            minute=diary_minute,
            timezone=ZoneInfo("Asia/Shanghai"),
        ),
        id="daily_diary_task",
        name="每日AI日记生成",
        replace_existing=True,
    )

    # 每 30 分钟执行 Agent 主动消息扫描（§2.2 变更 8.2：间隔 ≥30min）
    scheduler.add_job(
        _run_agent_scan,
        trigger=IntervalTrigger(minutes=30),
        id="agent_scan_task",
        name="Agent主动消息扫描",
        replace_existing=True,
    )

    # Future 槽消费轮询（每 60 秒扫描一次到期 Future 槽）
    scheduler.add_job(
        _run_future_slot_scan,
        trigger=IntervalTrigger(seconds=60),
        id="future_slot_scan_task",
        name="Future槽消费轮询",
        replace_existing=True,
    )

    # R-FUT-03④：每日凌晨 1:00 (UTC) 执行 30 天无活动清零
    scheduler.add_job(
        _run_inactive_reset,
        trigger=CronTrigger(hour=1, minute=0, timezone=ZoneInfo("UTC")),
        id="inactive_proactive_reset_task",
        name="30天无活动proactive_times清零",
        replace_existing=True,
    )

    scheduler.start()
    jobs = scheduler.get_jobs()
    logger.info("[定时任务] 调度器已启动，已注册 %d 个任务", len(jobs))
    for j in jobs:
        if j.id == "daily_diary_task" and j.next_run_time:
            nrt = j.next_run_time
            if nrt.tzinfo is not None:
                nrt = nrt.astimezone(ZoneInfo("Asia/Shanghai"))
            logger.info(
                "[定时任务] 每日日记下次执行（Asia/Shanghai）: %s",
                nrt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )


def shutdown_scheduler() -> None:
    """优雅停止调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[定时任务] 调度器已停止")
