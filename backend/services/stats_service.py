# -*- coding: utf-8 -*-
# 数据统计服务：仪表盘、趋势、报表

import asyncio
import datetime
import json
import logging

from sqlalchemy import Date, and_, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.redis_client import get_redis

logger = logging.getLogger(__name__)

# 关系等级名称映射
_LEVEL_NAMES = {0: "陌生", 1: "朋友", 2: "亲密", 3: "知己"}


class StatsService:
    """数据统计服务"""

    # ==================== 仪表盘 ====================

    async def get_dashboard_data(self, role: str, db: AsyncSession) -> dict:
        """
        获取仪表盘数据，按角色过滤返回。
        结果缓存到 Redis，TTL=300s。
        """
        # tech_ops 通过系统监控接口获取数据
        if role == "tech_ops":
            return {}

        # 检查 Redis 缓存
        cache_key = f"stats:dashboard:{role}"
        try:
            r = await get_redis()
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("读取仪表盘缓存失败: %s", e)

        today = datetime.date.today()
        today_start = datetime.datetime.combine(today, datetime.time.min)

        if role == "ai_trainer":
            # ai_trainer 仅返回AI性能数据
            ai_data = await self._get_ai_performance_data(today, today_start, db)
            result = {"ai_performance": ai_data}
        else:
            # super_admin / ops_admin 返回全部数据
            (
                user_data,
                retention_data,
                conversation_data,
                agent_data,
                ai_data,
            ) = await asyncio.gather(
                self._get_user_data(today, today_start, db),
                self._get_retention_data(today, db),
                self._get_conversation_data(today, today_start, db),
                self._get_agent_data(today, today_start, db),
                self._get_ai_performance_data(today, today_start, db),
            )
            result = {
                "user": user_data,
                "retention": retention_data,
                "conversation": conversation_data,
                "agent": agent_data,
                "ai_performance": ai_data,
            }

        # 写入 Redis 缓存
        try:
            r = await get_redis()
            await r.set(cache_key, json.dumps(result, ensure_ascii=False), ex=300)
        except Exception as e:
            logger.warning("写入仪表盘缓存失败: %s", e)

        return result

    async def _get_user_data(
        self, today: datetime.date, today_start: datetime.datetime, db: AsyncSession
    ) -> dict:
        """用户数据统计"""
        day7_start = today - datetime.timedelta(days=6)
        day30_start = today - datetime.timedelta(days=29)

        day7_dt = datetime.datetime.combine(day7_start, datetime.time.min)
        day30_dt = datetime.datetime.combine(day30_start, datetime.time.min)

        # 并行查询
        (
            new_today_r,
            new_7d_r,
            new_30d_r,
            active_today_r,
            active_7d_r,
        ) = await asyncio.gather(
            db.execute(
                select(func.count(User.id)).where(
                    cast(User.created_at, Date) == today
                )
            ),
            db.execute(
                select(func.count(User.id)).where(User.created_at >= day7_dt)
            ),
            db.execute(
                select(func.count(User.id)).where(User.created_at >= day30_dt)
            ),
            db.execute(
                select(func.count(distinct(ConversationLog.user_id))).where(
                    and_(
                        ConversationLog.role == "user",
                        cast(ConversationLog.created_at, Date) == today,
                    )
                )
            ),
            db.execute(
                select(func.count(distinct(ConversationLog.user_id))).where(
                    and_(
                        ConversationLog.role == "user",
                        ConversationLog.created_at >= day7_dt,
                    )
                )
            ),
        )

        return {
            "new_users_today": new_today_r.scalar() or 0,
            "new_users_7days": new_7d_r.scalar() or 0,
            "new_users_30days": new_30d_r.scalar() or 0,
            "active_users_today": active_today_r.scalar() or 0,
            "active_users_7days": active_7d_r.scalar() or 0,
        }

    async def _get_retention_data(
        self, today: datetime.date, db: AsyncSession
    ) -> dict:
        """留存率计算"""
        today_start = datetime.datetime.combine(today, datetime.time.min)
        yesterday = today - datetime.timedelta(days=1)
        day7_ago = today - datetime.timedelta(days=7)
        day30_ago = today - datetime.timedelta(days=30)

        # 次日留存：昨日注册用户中，今日有登录的比例
        next_day_ret = await self._calc_retention(yesterday, today_start, db)
        # 7日留存：7天前注册的用户中，今日有登录的比例
        day7_ret = await self._calc_retention(day7_ago, today_start, db)
        # 30日留存：30天前注册的用户中，今日有登录的比例
        day30_ret = await self._calc_retention(day30_ago, today_start, db)

        return {
            "next_day_retention": next_day_ret,
            "day7_retention": day7_ret,
            "day30_retention": day30_ret,
        }

    async def _calc_retention(
        self, register_date: datetime.date,
        today_start: datetime.datetime, db: AsyncSession
    ) -> float | None:
        """计算特定日期注册用户在今日的留存率"""
        # 该日期注册总数
        total_r = await db.execute(
            select(func.count(User.id)).where(
                cast(User.created_at, Date) == register_date
            )
        )
        total = total_r.scalar() or 0
        if total == 0:
            return None

        # 其中今日有登录的数量
        retained_r = await db.execute(
            select(func.count(User.id)).where(
                and_(
                    cast(User.created_at, Date) == register_date,
                    User.last_login_at >= today_start,
                )
            )
        )
        retained = retained_r.scalar() or 0

        return round(retained / total * 100, 1)

    async def _get_conversation_data(
        self, today: datetime.date, today_start: datetime.datetime,
        db: AsyncSession
    ) -> dict:
        """对话数据统计"""
        total_r, today_r, active_today_r = await asyncio.gather(
            db.execute(
                select(func.count(ConversationLog.id)).where(
                    ConversationLog.role == "user"
                )
            ),
            db.execute(
                select(func.count(ConversationLog.id)).where(
                    and_(
                        ConversationLog.role == "user",
                        cast(ConversationLog.created_at, Date) == today,
                    )
                )
            ),
            db.execute(
                select(func.count(distinct(ConversationLog.user_id))).where(
                    and_(
                        ConversationLog.role == "user",
                        cast(ConversationLog.created_at, Date) == today,
                    )
                )
            ),
        )

        total_rounds = total_r.scalar() or 0
        today_rounds = today_r.scalar() or 0
        active_today = active_today_r.scalar() or 0

        avg_rounds = None
        if active_today > 0:
            avg_rounds = round(today_rounds / active_today, 1)

        return {
            "total_conversation_rounds": total_rounds,
            "avg_rounds_today": avg_rounds,
        }

    async def _get_agent_data(
        self, today: datetime.date, today_start: datetime.datetime,
        db: AsyncSession
    ) -> dict:
        """主动消息数据统计"""
        sent_r, opened_r = await asyncio.gather(
            db.execute(
                select(func.count(AgentMessage.id)).where(
                    cast(AgentMessage.created_at, Date) == today
                )
            ),
            db.execute(
                select(func.count(AgentMessage.id)).where(
                    and_(
                        cast(AgentMessage.created_at, Date) == today,
                        AgentMessage.is_read == True,  # noqa: E712
                    )
                )
            ),
        )

        sent_today = sent_r.scalar() or 0
        opened_today = opened_r.scalar() or 0

        open_rate = None
        if sent_today > 0:
            open_rate = round(opened_today / sent_today * 100, 1)

        return {
            "agent_sent_today": sent_today,
            "agent_open_count_today": opened_today,
            "agent_open_rate": open_rate,
        }

    async def _get_ai_performance_data(
        self, today: datetime.date, today_start: datetime.datetime,
        db: AsyncSession
    ) -> dict:
        """AI性能数据统计（从 Redis + 数据库）"""
        today_str = today.strftime("%Y%m%d")

        # 并行查询数据库部分和 Redis 部分
        risk_r, total_assistant_r = await asyncio.gather(
            db.execute(
                select(func.count(ConversationLog.id)).where(
                    and_(
                        ConversationLog.persona_risk_flag == True,  # noqa: E712
                        cast(ConversationLog.created_at, Date) == today,
                    )
                )
            ),
            db.execute(
                select(func.count(ConversationLog.id)).where(
                    and_(
                        ConversationLog.role == "assistant",
                        cast(ConversationLog.created_at, Date) == today,
                    )
                )
            ),
        )

        risk_count = risk_r.scalar() or 0
        total_assistant = total_assistant_r.scalar() or 0

        # 人格偏离率
        persona_deviation_rate = 0.0
        if total_assistant > 0:
            persona_deviation_rate = round(risk_count / total_assistant * 100, 1)

        # 从 Redis 读取 LLM 性能数据
        # 无样本时为 None，与真实平均 0ms 区分
        llm_avg_response_ms: float | None = None
        llm_success_rate = None
        content_block_rate = 0.0

        try:
            r = await get_redis()

            # LLM 平均响应时间（仅当 Redis 列表有样本时返回数值）
            response_times = await r.lrange("llm_response_times", 0, 999)
            if response_times:
                times = [float(t) for t in response_times]
                llm_avg_response_ms = round(sum(times) / len(times), 1)

            # LLM 成功率
            total_calls = await r.hget(f"llm_stats:{today_str}", "total")
            success_calls = await r.hget(f"llm_stats:{today_str}", "success")
            if total_calls and int(total_calls) > 0:
                llm_success_rate = round(
                    int(success_calls or 0) / int(total_calls) * 100, 1
                )

            # 内容拦截率
            block_count_raw = await r.get(f"content_block_count:{today_str}")
            block_count = int(block_count_raw) if block_count_raw else 0
            if total_assistant > 0 and block_count > 0:
                content_block_rate = round(
                    block_count / total_assistant * 100, 1
                )

        except Exception as e:
            logger.warning("读取 Redis LLM 统计数据失败: %s", e)

        return {
            "llm_avg_response_ms": llm_avg_response_ms,
            "llm_success_rate": llm_success_rate,
            "persona_deviation_rate": persona_deviation_rate,
            "content_block_rate": content_block_rate,
        }

    # ==================== 趋势数据 ====================

    async def get_trend_data(
        self, metric: str, days: int, db: AsyncSession
    ) -> list:
        """
        获取趋势数据。
        metric: new_users / active_users / conversation_rounds
        days: 7 / 30
        """
        today = datetime.date.today()
        result = []

        if metric == "new_users":
            result = await self._trend_new_users(today, days, db)
        elif metric == "active_users":
            result = await self._trend_active_users(today, days, db)
        elif metric == "conversation_rounds":
            result = await self._trend_conversation_rounds(today, days, db)

        return result

    async def _trend_new_users(
        self, today: datetime.date, days: int, db: AsyncSession
    ) -> list:
        """新增用户趋势"""
        start_date = today - datetime.timedelta(days=days - 1)
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)

        stmt = (
            select(
                cast(User.created_at, Date).label("date"),
                func.count(User.id).label("count"),
            )
            .where(User.created_at >= start_dt)
            .group_by(cast(User.created_at, Date))
        )
        r = await db.execute(stmt)
        rows = r.all()
        date_map = {str(row.date): row.count for row in rows}

        return [
            {
                "date": str(today - datetime.timedelta(days=days - 1 - i)),
                "value": date_map.get(
                    str(today - datetime.timedelta(days=days - 1 - i)), 0
                ),
            }
            for i in range(days)
        ]

    async def _trend_active_users(
        self, today: datetime.date, days: int, db: AsyncSession
    ) -> list:
        """活跃用户趋势"""
        start_date = today - datetime.timedelta(days=days - 1)
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)

        stmt = (
            select(
                cast(ConversationLog.created_at, Date).label("date"),
                func.count(distinct(ConversationLog.user_id)).label("count"),
            )
            .where(
                and_(
                    ConversationLog.role == "user",
                    ConversationLog.created_at >= start_dt,
                )
            )
            .group_by(cast(ConversationLog.created_at, Date))
        )
        r = await db.execute(stmt)
        rows = r.all()
        date_map = {str(row.date): row.count for row in rows}

        return [
            {
                "date": str(today - datetime.timedelta(days=days - 1 - i)),
                "value": date_map.get(
                    str(today - datetime.timedelta(days=days - 1 - i)), 0
                ),
            }
            for i in range(days)
        ]

    async def _trend_conversation_rounds(
        self, today: datetime.date, days: int, db: AsyncSession
    ) -> list:
        """对话轮次趋势"""
        start_date = today - datetime.timedelta(days=days - 1)
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)

        stmt = (
            select(
                cast(ConversationLog.created_at, Date).label("date"),
                func.count(ConversationLog.id).label("count"),
            )
            .where(
                and_(
                    ConversationLog.role == "user",
                    ConversationLog.created_at >= start_dt,
                )
            )
            .group_by(cast(ConversationLog.created_at, Date))
        )
        r = await db.execute(stmt)
        rows = r.all()
        date_map = {str(row.date): row.count for row in rows}

        return [
            {
                "date": str(today - datetime.timedelta(days=days - 1 - i)),
                "value": date_map.get(
                    str(today - datetime.timedelta(days=days - 1 - i)), 0
                ),
            }
            for i in range(days)
        ]

    # ==================== 报表数据 ====================

    async def get_report_data(
        self, report_type: str,
        start_date: datetime.date, end_date: datetime.date,
        page: int, page_size: int, db: AsyncSession
    ) -> dict:
        """获取报表数据"""
        if report_type == "user":
            return await self._report_user(start_date, end_date, page, page_size, db)
        elif report_type == "conversation":
            return await self._report_conversation(start_date, end_date, page, page_size, db)
        elif report_type == "feature":
            return await self._report_feature(start_date, end_date, page, page_size, db)
        elif report_type == "ai_performance":
            return await self._report_ai_performance(start_date, end_date, page, page_size, db)
        return {"list": [], "total": 0, "page": page, "page_size": page_size, "extra": {}}

    async def _report_user(
        self, start_date: datetime.date, end_date: datetime.date,
        page: int, page_size: int, db: AsyncSession
    ) -> dict:
        """用户报表"""
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        end_dt = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # 新增用户按日期分组
        new_users_stmt = (
            select(
                cast(User.created_at, Date).label("date"),
                func.count(User.id).label("count"),
            )
            .where(and_(User.created_at >= start_dt, User.created_at < end_dt))
            .group_by(cast(User.created_at, Date))
        )

        # 活跃用户按日期分组
        active_users_stmt = (
            select(
                cast(ConversationLog.created_at, Date).label("date"),
                func.count(distinct(ConversationLog.user_id)).label("count"),
            )
            .where(
                and_(
                    ConversationLog.role == "user",
                    ConversationLog.created_at >= start_dt,
                    ConversationLog.created_at < end_dt,
                )
            )
            .group_by(cast(ConversationLog.created_at, Date))
        )

        # 关系等级分布（按 relationship.level 分组，无行用户计入 level=0）
        level_dist_stmt = (
            select(
                func.coalesce(Relationship.level, 0).label("level"),
                func.count(User.id).label("count"),
            )
            .select_from(User)
            .outerjoin(Relationship, User.id == Relationship.user_id)
            .group_by(func.coalesce(Relationship.level, 0))
        )

        new_r, active_r, level_r = await asyncio.gather(
            db.execute(new_users_stmt),
            db.execute(active_users_stmt),
            db.execute(level_dist_stmt),
        )

        new_map = {str(row.date): row.count for row in new_r.all()}
        active_map = {str(row.date): row.count for row in active_r.all()}

        # 生成日期序列
        all_dates = []
        d = start_date
        while d <= end_date:
            all_dates.append(str(d))
            d += datetime.timedelta(days=1)

        total = len(all_dates)

        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_dates = all_dates[start_idx:end_idx]

        items = [
            {
                "date": dt,
                "new_users": new_map.get(dt, 0),
                "active_users": active_map.get(dt, 0),
            }
            for dt in paged_dates
        ]

        # 关系等级分布
        level_rows = level_r.all()
        level_distribution = []
        for lv in range(4):
            count = 0
            for row in level_rows:
                if row.level == lv:
                    count = row.count
                    break
            level_distribution.append({
                "level": lv,
                "name": _LEVEL_NAMES.get(lv, f"等级{lv}"),
                "count": count,
            })

        return {
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "extra": {"level_distribution": level_distribution},
        }

    async def _report_conversation(
        self, start_date: datetime.date, end_date: datetime.date,
        page: int, page_size: int, db: AsyncSession
    ) -> dict:
        """对话报表"""
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        end_dt = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # 对话轮次按日期分组
        rounds_stmt = (
            select(
                cast(ConversationLog.created_at, Date).label("date"),
                func.count(ConversationLog.id).label("count"),
            )
            .where(
                and_(
                    ConversationLog.role == "user",
                    ConversationLog.created_at >= start_dt,
                    ConversationLog.created_at < end_dt,
                )
            )
            .group_by(cast(ConversationLog.created_at, Date))
        )

        # 情绪分布
        emotion_stmt = (
            select(
                EmotionLog.emotion_label.label("emotion"),
                func.count(EmotionLog.id).label("count"),
            )
            .where(
                and_(
                    EmotionLog.created_at >= start_dt,
                    EmotionLog.created_at < end_dt,
                )
            )
            .group_by(EmotionLog.emotion_label)
        )

        rounds_r, emotion_r = await asyncio.gather(
            db.execute(rounds_stmt),
            db.execute(emotion_stmt),
        )

        rounds_map = {str(row.date): row.count for row in rounds_r.all()}

        # 日期序列
        all_dates = []
        d = start_date
        while d <= end_date:
            all_dates.append(str(d))
            d += datetime.timedelta(days=1)

        total = len(all_dates)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_dates = all_dates[start_idx:end_idx]

        items = [
            {
                "date": dt,
                "conversation_rounds": rounds_map.get(dt, 0),
            }
            for dt in paged_dates
        ]

        # 情绪分布
        emotion_rows = emotion_r.all()
        emotion_total = sum(row.count for row in emotion_rows)
        emotion_distribution = [
            {
                "emotion": row.emotion,
                "count": row.count,
                "percent": round(row.count / emotion_total * 100, 1) if emotion_total > 0 else 0,
            }
            for row in emotion_rows
        ]
        emotion_distribution.sort(key=lambda x: x["count"], reverse=True)

        return {
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "extra": {"emotion_distribution": emotion_distribution},
        }

    async def _report_feature(
        self, start_date: datetime.date, end_date: datetime.date,
        page: int, page_size: int, db: AsyncSession
    ) -> dict:
        """主动消息/功能报表"""
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        end_dt = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # 主动消息发送数按日期分组
        sent_stmt = (
            select(
                cast(AgentMessage.created_at, Date).label("date"),
                func.count(AgentMessage.id).label("count"),
            )
            .where(
                and_(
                    AgentMessage.created_at >= start_dt,
                    AgentMessage.created_at < end_dt,
                )
            )
            .group_by(cast(AgentMessage.created_at, Date))
        )

        # 已读数按日期分组
        opened_stmt = (
            select(
                cast(AgentMessage.created_at, Date).label("date"),
                func.count(AgentMessage.id).label("count"),
            )
            .where(
                and_(
                    AgentMessage.created_at >= start_dt,
                    AgentMessage.created_at < end_dt,
                    AgentMessage.is_read == True,  # noqa: E712
                )
            )
            .group_by(cast(AgentMessage.created_at, Date))
        )

        sent_r, opened_r = await asyncio.gather(
            db.execute(sent_stmt),
            db.execute(opened_stmt),
        )

        sent_map = {str(row.date): row.count for row in sent_r.all()}
        opened_map = {str(row.date): row.count for row in opened_r.all()}

        # 回复率：发送主动消息后30分钟内该user_id有新conversation_log记录的比例
        # 获取时间范围内所有主动消息
        agent_msgs_stmt = (
            select(AgentMessage.id, AgentMessage.user_id, AgentMessage.created_at)
            .where(
                and_(
                    AgentMessage.created_at >= start_dt,
                    AgentMessage.created_at < end_dt,
                )
            )
        )
        agent_msgs_r = await db.execute(agent_msgs_stmt)
        agent_msgs = agent_msgs_r.all()

        reply_count_by_date = {}
        sent_count_by_date = {}

        for msg in agent_msgs:
            msg_date = str(msg.created_at.date())
            sent_count_by_date[msg_date] = sent_count_by_date.get(msg_date, 0) + 1

            # 检查30分钟内是否有该用户的回复
            window_end = msg.created_at + datetime.timedelta(minutes=30)
            reply_stmt = select(func.count(ConversationLog.id)).where(
                and_(
                    ConversationLog.user_id == msg.user_id,
                    ConversationLog.role == "user",
                    ConversationLog.created_at > msg.created_at,
                    ConversationLog.created_at <= window_end,
                )
            )
            reply_r = await db.execute(reply_stmt)
            if (reply_r.scalar() or 0) > 0:
                reply_count_by_date[msg_date] = reply_count_by_date.get(msg_date, 0) + 1

        # 日期序列
        all_dates = []
        d = start_date
        while d <= end_date:
            all_dates.append(str(d))
            d += datetime.timedelta(days=1)

        total = len(all_dates)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_dates = all_dates[start_idx:end_idx]

        items = []
        for dt in paged_dates:
            sent = sent_map.get(dt, 0)
            opened = opened_map.get(dt, 0)
            sc = sent_count_by_date.get(dt, 0)
            rc = reply_count_by_date.get(dt, 0)
            reply_rate = None
            if sc > 0:
                reply_rate = round(rc / sc * 100, 1)
            items.append({
                "date": dt,
                "agent_sent": sent,
                "agent_opened": opened,
                "reply_rate": reply_rate,
            })

        return {
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "extra": {},
        }

    async def _report_ai_performance(
        self, start_date: datetime.date, end_date: datetime.date,
        page: int, page_size: int, db: AsyncSession
    ) -> dict:
        """AI性能报表"""
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        end_dt = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # persona_risk_flag 按日期分组
        risk_stmt = (
            select(
                cast(ConversationLog.created_at, Date).label("date"),
                func.count(ConversationLog.id).label("count"),
            )
            .where(
                and_(
                    ConversationLog.persona_risk_flag == True,  # noqa: E712
                    ConversationLog.created_at >= start_dt,
                    ConversationLog.created_at < end_dt,
                )
            )
            .group_by(cast(ConversationLog.created_at, Date))
        )

        # 总对话数按日期分组（role='assistant'）
        total_stmt = (
            select(
                cast(ConversationLog.created_at, Date).label("date"),
                func.count(ConversationLog.id).label("count"),
            )
            .where(
                and_(
                    ConversationLog.role == "assistant",
                    ConversationLog.created_at >= start_dt,
                    ConversationLog.created_at < end_dt,
                )
            )
            .group_by(cast(ConversationLog.created_at, Date))
        )

        risk_r, total_r = await asyncio.gather(
            db.execute(risk_stmt),
            db.execute(total_stmt),
        )

        risk_map = {str(row.date): row.count for row in risk_r.all()}
        total_map = {str(row.date): row.count for row in total_r.all()}

        # 日期序列
        all_dates = []
        d = start_date
        while d <= end_date:
            all_dates.append(str(d))
            d += datetime.timedelta(days=1)

        total_days = len(all_dates)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_dates = all_dates[start_idx:end_idx]

        items = []
        for dt in paged_dates:
            rc = risk_map.get(dt, 0)
            tc = total_map.get(dt, 0)
            deviation_rate = 0.0
            if tc > 0:
                deviation_rate = round(rc / tc * 100, 1)
            items.append({
                "date": dt,
                "persona_risk_count": rc,
                "total_count": tc,
                "deviation_rate": deviation_rate,
            })

        return {
            "list": items,
            "total": total_days,
            "page": page,
            "page_size": page_size,
            "extra": {},
        }


# 全局单例
stats_service = StatsService()
