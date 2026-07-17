# -*- coding: utf-8 -*-
# 生活流定时任务：LLM-01 周大纲生成（周日 23:00 / 23:30 重试）
#
# cron 注册见 backend/tasks/scheduler.py。
# 手动触发：python -m backend.tasks.life_feed_task weekly_outline_task

import asyncio
import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("Asia/Shanghai")
_WEEKLY_DAYS_COUNT = 7


def _next_week_monday(today: date) -> date:
    """返回 today 之后的下一个周一（周日 23:00 触发时即次日）。"""
    days_ahead = 7 - today.weekday()  # 周日 weekday=6 → 1；周一=0 → 7
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


async def _generate_next_week(is_retry: bool) -> None:
    """生成下一自然周大纲；失败按是否重试写 WARN / ERROR 日志。"""
    from backend.services.life_planner_service import (
        LifePlannerError,
        life_planner_service,
    )

    today = date.today()
    week_start = _next_week_monday(today)
    stage = "重试(23:30)" if is_retry else "首次(23:00)"
    logger.info("[定时任务][LLM-01] %s 周大纲生成 week_start=%s", stage, week_start)

    try:
        result = await life_planner_service.generate_week_outline(
            days_count=_WEEKLY_DAYS_COUNT,
            week_start_date=week_start,
            is_manual=False,
        )
        if result.get("status") == "skipped":
            logger.info("[定时任务][LLM-01] 已有落库，跳过 week_start=%s", week_start)
        else:
            logger.info(
                "[定时任务][LLM-01] 生成成功 week_start=%s 落库 %d 天",
                week_start, result.get("days", 0),
            )
    except LifePlannerError as e:
        if is_retry:
            logger.error(
                "[定时任务][LLM-01] 最终失败（23:30 重试后）week_start=%s: %s",
                week_start, e,
            )
        else:
            logger.warning(
                "[定时任务][LLM-01] 首次生成失败（待 23:30 重试）week_start=%s: %s",
                week_start, e,
            )
    except Exception as e:
        level = logger.error if is_retry else logger.warning
        level(
            "[定时任务][LLM-01] 生成异常（is_retry=%s）week_start=%s: %s",
            is_retry, week_start, e, exc_info=True,
        )


async def weekly_outline_task() -> None:
    """周日 23:00 首次生成。"""
    await _generate_next_week(is_retry=False)


async def weekly_outline_retry_task() -> None:
    """周日 23:30 重试：generate_week_outline 内部已做「已落库则跳过」，故成功后自动 skip。"""
    await _generate_next_week(is_retry=True)


async def _generate_current_day_scenes(is_retry: bool) -> None:
    """为「当日」生成日场景（LLM-02，PRD 2.3.1：00:20 生成当日）。"""
    from backend.services.life_planner_service import life_planner_service

    plan_date = date.today()
    stage = "重试(00:30)" if is_retry else "首次(00:20)"
    logger.info("[定时任务][LLM-02] %s 日场景生成 plan_date=%s", stage, plan_date)
    try:
        result = await life_planner_service.generate_daily_scenes(plan_date)
        status = result.get("status")
        if status == "ready":
            logger.info(
                "[定时任务][LLM-02] 生成成功 plan_date=%s 场景数=%d",
                plan_date, result.get("scenes", 0),
            )
        elif status in ("skipped_no_outline", "skipped_ready"):
            logger.info("[定时任务][LLM-02] 跳过(%s) plan_date=%s", status, plan_date)
        else:  # failed
            if is_retry:
                logger.error(
                    "[定时任务][LLM-02] 最终失败（00:30 重试后）plan_date=%s: %s",
                    plan_date, result.get("reason"),
                )
            else:
                logger.warning(
                    "[定时任务][LLM-02] 首次失败（待 00:30 重试）plan_date=%s: %s",
                    plan_date, result.get("reason"),
                )
    except Exception as e:
        level = logger.error if is_retry else logger.warning
        level(
            "[定时任务][LLM-02] 生成异常（is_retry=%s）plan_date=%s: %s",
            is_retry, plan_date, e, exc_info=True,
        )


async def daily_scenes_task() -> None:
    """每日 00:20 生成当日场景。"""
    await _generate_current_day_scenes(is_retry=False)


async def daily_scenes_retry_task() -> None:
    """每日 00:30 重试：generate_daily_scenes 内部对 ready 自动跳过，仅 failed 时重跑。"""
    await _generate_current_day_scenes(is_retry=True)


async def daily_her_universe_task() -> None:
    """每日 00:45 她的宇宙（LLM-03）：处理「当日」ready 场景。"""
    from backend.services.her_universe_service import her_universe_service

    plan_date = date.today()
    logger.info("[定时任务][LLM-03] 触发她的宇宙 plan_date=%s", plan_date)
    try:
        result = await her_universe_service.daily_her_universe_task(plan_date)
        if result.get("status") == "skipped":
            logger.info("[定时任务][LLM-03] 跳过（无 ready 计划）plan_date=%s", plan_date)
        else:
            logger.info(
                "[定时任务][LLM-03] 完成 plan_date=%s 成功=%d 失败=%d 新增事件=%d",
                plan_date, result.get("success", 0),
                result.get("failed", 0), result.get("events_new", 0),
            )
    except Exception as e:
        logger.error(
            "[定时任务][LLM-03] 任务异常 plan_date=%s: %s", plan_date, e, exc_info=True
        )


async def daily_feed_publish_task() -> None:
    """每日 01:00 发布整合（LIFE001，STEP-013）：整合文案 + 图片 → 落库 feed_post。"""
    from backend.services.feed_publish_service import feed_publish_service

    plan_date = date.today()
    logger.info("[定时任务][LIFE001] 触发每日发布整合 plan_date=%s", plan_date)
    try:
        result = await feed_publish_service.run_daily_publish(plan_date)
        logger.info(
            "[定时任务][LIFE001] 完成 plan_date=%s status=%s 成功=%d 跳过=%d 失败=%d",
            plan_date, result.get("status"),
            result.get("success", 0), result.get("skipped", 0), result.get("failed", 0),
        )
    except Exception as e:
        logger.error(
            "[定时任务][LIFE001] 任务异常 plan_date=%s: %s", plan_date, e, exc_info=True
        )


def _main() -> None:
    import sys

    tasks = {
        "weekly_outline_task": weekly_outline_task,
        "weekly_outline_retry_task": weekly_outline_retry_task,
        "daily_scenes_task": daily_scenes_task,
        "daily_scenes_retry_task": daily_scenes_retry_task,
        "daily_her_universe_task": daily_her_universe_task,
        "daily_feed_publish_task": daily_feed_publish_task,
    }
    name = sys.argv[1] if len(sys.argv) > 1 else "weekly_outline_task"
    fn = tasks.get(name)
    if fn is None:
        print(f"未知任务：{name}；可选：{', '.join(tasks)}")
        sys.exit(1)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(fn())


if __name__ == "__main__":
    _main()
