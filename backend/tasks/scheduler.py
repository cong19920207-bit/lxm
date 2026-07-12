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


async def _run_weekly_outline() -> None:
    """LLM-01 周大纲首次生成（周日 23:00）"""
    try:
        from backend.tasks.life_feed_task import weekly_outline_task
        await weekly_outline_task()
    except Exception as e:
        logger.error("[定时任务] 周大纲生成任务异常: %s", str(e), exc_info=True)


async def _run_weekly_outline_retry() -> None:
    """LLM-01 周大纲重试（周日 23:30，仅当 23:00 未落库时实际生成）"""
    try:
        from backend.tasks.life_feed_task import weekly_outline_retry_task
        await weekly_outline_retry_task()
    except Exception as e:
        logger.error("[定时任务] 周大纲重试任务异常: %s", str(e), exc_info=True)


async def _run_daily_scenes() -> None:
    """LLM-02 日场景首次生成（每日 00:20，为次日生成）"""
    try:
        from backend.tasks.life_feed_task import daily_scenes_task
        await daily_scenes_task()
    except Exception as e:
        logger.error("[定时任务] 日场景生成任务异常: %s", str(e), exc_info=True)


async def _run_daily_scenes_retry() -> None:
    """LLM-02 日场景重试（每日 00:30，仅当 00:20 未 ready 时实际生成）"""
    try:
        from backend.tasks.life_feed_task import daily_scenes_retry_task
        await daily_scenes_retry_task()
    except Exception as e:
        logger.error("[定时任务] 日场景重试任务异常: %s", str(e), exc_info=True)


async def _run_daily_her_universe() -> None:
    """LLM-03 她的宇宙（每日 00:45，处理当日 ready 场景）"""
    try:
        from backend.tasks.life_feed_task import daily_her_universe_task
        await daily_her_universe_task()
    except Exception as e:
        logger.error("[定时任务] 她的宇宙任务异常: %s", str(e), exc_info=True)


async def _run_daily_feed_publish() -> None:
    """LIFE001 每日发布整合（每日 01:00，整合文案+图片落库 feed_post）"""
    try:
        from backend.tasks.life_feed_task import daily_feed_publish_task
        await daily_feed_publish_task()
    except Exception as e:
        logger.error("[定时任务] 每日发布整合任务异常: %s", str(e), exc_info=True)


async def _run_comment_reply_poll() -> None:
    """LLM-05 评论回复延迟消费（每 30s，扫 due_at 到期 pending 评论）"""
    try:
        from backend.services.comment_reply_service import comment_reply_poll_task
        await comment_reply_poll_task()
    except Exception as e:
        logger.error("[定时任务] 评论回复轮询任务异常: %s", str(e), exc_info=True)


async def _run_agent_aware_poll() -> None:
    """LLM-06/07 点赞/已读感知 IM 延迟消费（每 60s，扫 agent_aware_queue 到期 pending）"""
    try:
        from backend.tasks.agent_aware_task import agent_aware_poll_task
        await agent_aware_poll_task()
    except Exception as e:
        logger.error("[定时任务] 感知 IM 轮询任务异常: %s", str(e), exc_info=True)


async def _run_feed_new_broadcast() -> None:
    """STEP-026 SSE 新帖广播调度（每 30s，扫 ready+visible+到点+未广播帖子）"""
    try:
        from backend.tasks.feed_new_broadcast_task import feed_new_broadcast_task
        await feed_new_broadcast_task()
    except Exception as e:
        logger.error("[定时任务] SSE 新帖广播任务异常: %s", str(e), exc_info=True)


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

    # LLM-01 周大纲：周日 23:00 首次 + 23:30 重试（Asia/Shanghai）
    scheduler.add_job(
        _run_weekly_outline,
        trigger=CronTrigger(
            day_of_week="sun", hour=23, minute=0, timezone=ZoneInfo("Asia/Shanghai"),
        ),
        id="weekly_outline_task",
        name="LLM-01周大纲生成",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_weekly_outline_retry,
        trigger=CronTrigger(
            day_of_week="sun", hour=23, minute=30, timezone=ZoneInfo("Asia/Shanghai"),
        ),
        id="weekly_outline_retry_task",
        name="LLM-01周大纲重试",
        replace_existing=True,
    )

    # LLM-02 日场景：每日 00:20 首次 + 00:30 重试（Asia/Shanghai），为次日生成
    scheduler.add_job(
        _run_daily_scenes,
        trigger=CronTrigger(hour=0, minute=20, timezone=ZoneInfo("Asia/Shanghai")),
        id="daily_scenes_task",
        name="LLM-02日场景生成",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_daily_scenes_retry,
        trigger=CronTrigger(hour=0, minute=30, timezone=ZoneInfo("Asia/Shanghai")),
        id="daily_scenes_retry_task",
        name="LLM-02日场景重试",
        replace_existing=True,
    )

    # LLM-03 她的宇宙：每日 00:45（Asia/Shanghai），单条内 3 次立即重试，无独立重试 cron
    scheduler.add_job(
        _run_daily_her_universe,
        trigger=CronTrigger(hour=0, minute=45, timezone=ZoneInfo("Asia/Shanghai")),
        id="daily_her_universe_task",
        name="LLM-03她的宇宙生成",
        replace_existing=True,
    )

    # LIFE001 每日发布整合：每日 01:00（Asia/Shanghai），整合文案+图片落库 feed_post
    scheduler.add_job(
        _run_daily_feed_publish,
        trigger=CronTrigger(hour=1, minute=0, timezone=ZoneInfo("Asia/Shanghai")),
        id="daily_feed_publish_task",
        name="LIFE001每日发布整合",
        replace_existing=True,
    )

    # LLM-05 评论回复延迟消费：每 30 秒轮询（override 最小 30s 需 30s 精度）
    scheduler.add_job(
        _run_comment_reply_poll,
        trigger=IntervalTrigger(seconds=30),
        id="comment_reply_poll_task",
        name="LLM-05评论回复轮询",
        replace_existing=True,
    )

    # LLM-06/07 点赞/已读感知 IM 延迟消费：每 60 秒轮询（STEP-019）
    scheduler.add_job(
        _run_agent_aware_poll,
        trigger=IntervalTrigger(seconds=60),
        id="agent_aware_poll_task",
        name="感知IM(点赞/已读)轮询",
        replace_existing=True,
    )

    # SSE 新帖广播调度：每 30 秒扫描到点可见的新帖并广播（STEP-026）
    scheduler.add_job(
        _run_feed_new_broadcast,
        trigger=IntervalTrigger(seconds=30),
        id="feed_new_broadcast_task",
        name="SSE新帖广播调度",
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
