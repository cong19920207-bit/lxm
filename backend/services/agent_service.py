# -*- coding: utf-8 -*-
# 主动消息业务逻辑：触发判定、行动评分、消息生成与保存

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import MEMORY_TYPE_USER, PERSONA_RISK_KEYWORDS
from backend.database import async_session_maker
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.login_log import LoginLog
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.redis_client import get_redis
from backend.services.embedding_service import embedding_service
from backend.services.llm_service import llm_service
from backend.services.prompt_builder import PromptBuilder
from backend.services.timeline_seq_service import allocate_sort_seq
from backend.services.vector_service import vector_service

logger = logging.getLogger(__name__)

# P0 关注的负面情绪标签
NEGATIVE_EMOTIONS = {"悲伤", "焦虑", "愤怒", "孤独"}

# P3 默认凌晨关键词
DEFAULT_NIGHT_KEYWORDS = ["失眠", "睡不着", "睡不好", "熬夜", "加班", "好晚", "还没睡"]

# 主动消息兜底回复
AGENT_FALLBACK_REPLIES = {
    TriggerType.P0: "我一直在想你，你现在还好吗？",
    TriggerType.P1: "好久不见，突然想你了。",
    TriggerType.P2: "今天过得怎么样呀？",
    TriggerType.P3: "这么晚了还没睡呀，早点休息嘛。",
    TriggerType.P4: "想你了，你最近忙什么呢？",
    TriggerType.FUTURE: "突然想起一件事想跟你说~",
}

# 触发类型权重
TRIGGER_WEIGHTS = {
    TriggerType.P0: 4,
    TriggerType.P1: 3,
    TriggerType.P2: 2,
    TriggerType.P3: 3,
    TriggerType.P4: 2,
    TriggerType.FUTURE: 3,
}

# 关系等级权重（0级→1, 1级→2, 2级→3, 3级→4）
LEVEL_WEIGHTS = {0: 1, 1: 2, 2: 3, 3: 4}


class AgentService:
    """主动消息服务：扫描用户、匹配触发条件、评分、生成消息"""

    # ================================================================
    #  1. run_agent_scan —— 全量扫描入口
    # ================================================================

    async def run_agent_scan(self) -> None:
        """
        全量扫描用户，对每个符合条件的用户检查主动消息触发。
        只扫描注册超过1天的活跃用户（未封禁）。
        使用 Semaphore(5) 控制并发。
        """
        logger.info("[Agent] 开始全量扫描")
        try:
            async with async_session_maker() as db:
                one_day_ago = datetime.utcnow() - timedelta(days=1)
                stmt = select(User.id).where(
                    and_(
                        User.created_at <= one_day_ago,
                        User.is_banned == False,  # noqa: E712
                    )
                )
                result = await db.execute(stmt)
                user_ids = [row[0] for row in result.all()]

            if not user_ids:
                logger.info("[Agent] 无符合条件的用户，扫描结束")
                return

            logger.info("[Agent] 待扫描用户数: %d", len(user_ids))

            semaphore = asyncio.Semaphore(5)

            async def _scan_user(uid: int) -> None:
                async with semaphore:
                    try:
                        await self.check_and_trigger(uid)
                    except Exception as e:
                        logger.error("[Agent] 扫描用户 %d 异常: %s", uid, str(e))

            await asyncio.gather(*[_scan_user(uid) for uid in user_ids])
            logger.info("[Agent] 全量扫描完成")

        except Exception as e:
            logger.error("[Agent] 全量扫描异常: %s", str(e), exc_info=True)

    # ================================================================
    #  2. check_and_trigger —— 触发判定主流程
    # ================================================================

    async def check_and_trigger(self, user_id: int) -> bool:
        """
        按优先级从高到低匹配触发条件，同一用户只匹配最高优先级。
        匹配后检查频率限制、黑名单、行动评分，通过则生成消息。

        Returns:
            是否成功触发并生成消息
        """
        async with async_session_maker() as db:
            # 按 P0 → P4 顺序依次检查
            trigger_type = None

            if await self._check_p0(user_id, db):
                trigger_type = TriggerType.P0
            elif await self._check_p1(user_id, db):
                trigger_type = TriggerType.P1
            elif await self._check_p2(user_id, db):
                trigger_type = TriggerType.P2
            elif await self._check_p3(user_id, db):
                trigger_type = TriggerType.P3
            elif await self._check_p4(user_id, db):
                trigger_type = TriggerType.P4

        if not trigger_type:
            return False

        # ── 路 B 优先级保护：Future 槽未过期时跳过定时扫描写入 ──
        if await self._has_pending_future_slot(user_id):
            logger.info(
                "[Agent] 用户 %d 存在未过期 Future 槽，跳过定时扫描写入 (trigger=%s)",
                user_id, trigger_type,
            )
            return False

        logger.info("[Agent] 用户 %d 命中触发: %s", user_id, trigger_type)

        # 频率限制检查
        r = await get_redis()
        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        # a. 每日上限 8 次（含 Future 槽消费计入，§2.2 变更 8.2）
        count_key = f"agent:count:{user_id}:{today_str}"
        daily_count = await r.get(count_key)
        if daily_count and int(daily_count) >= 8:
            logger.info("[Agent] 用户 %d 今日已触发 %s 次，跳过", user_id, daily_count)
            return False

        # b. 两次间隔 ≥30 分钟（§2.2 变更 8.2）
        async with async_session_maker() as db:
            stmt = (
                select(AgentMessage)
                .where(AgentMessage.user_id == user_id)
                .order_by(desc(AgentMessage.created_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            latest_msg = result.scalar_one_or_none()
            if latest_msg and (now - latest_msg.created_at) < timedelta(minutes=30):
                logger.info("[Agent] 用户 %d 距上次主动消息不足30分钟，跳过", user_id)
                return False

        # c. 黑名单检查（P0 不受限制）
        if trigger_type != TriggerType.P0:
            blacklist_key = f"agent:blacklist:{user_id}"
            is_blacklisted = await r.exists(blacklist_key)
            if is_blacklisted:
                logger.info("[Agent] 用户 %d 在黑名单中，跳过（触发类型: %s）", user_id, trigger_type)
                return False

        # d. 计算行动评分
        score = await self.calculate_action_score(user_id, trigger_type)
        logger.info("[Agent] 用户 %d 行动评分: %.1f", user_id, score)

        # e. 评分≥6才发起
        if score < 6:
            logger.info("[Agent] 用户 %d 评分 %.1f < 6，跳过", user_id, score)
            return False

        return await self.generate_and_save_message(user_id, trigger_type)

    # ================================================================
    #  3. calculate_action_score —— 行动评分
    # ================================================================

    async def calculate_action_score(self, user_id: int, trigger_type: str) -> float:
        """
        ActionScore = 关系等级权重 + 触发类型权重 + 活跃度权重 + 历史回复率权重
        """
        async with async_session_maker() as db:
            # 关系等级权重
            rel_stmt = select(Relationship).where(Relationship.user_id == user_id)
            rel_result = await db.execute(rel_stmt)
            rel = rel_result.scalar_one_or_none()
            level = rel.level if rel else 0
            level_weight = LEVEL_WEIGHTS.get(level, 1)

            # 触发类型权重
            trigger_weight = TRIGGER_WEIGHTS.get(trigger_type, 2)

            # 活跃度权重：近7天活跃天数
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            active_stmt = (
                select(func.count(func.distinct(func.date(ConversationLog.created_at))))
                .where(
                    and_(
                        ConversationLog.user_id == user_id,
                        ConversationLog.role == "user",
                        ConversationLog.created_at >= seven_days_ago,
                    )
                )
            )
            active_result = await db.execute(active_stmt)
            active_days = active_result.scalar() or 0

            if active_days >= 4:
                active_weight = 2
            elif active_days >= 2:
                active_weight = 1
            else:
                active_weight = 0

            # 历史回复率权重
            total_stmt = select(func.count()).select_from(AgentMessage).where(
                AgentMessage.user_id == user_id
            )
            total_result = await db.execute(total_stmt)
            total_agent = total_result.scalar() or 0

            if total_agent > 0:
                read_stmt = select(func.count()).select_from(AgentMessage).where(
                    and_(
                        AgentMessage.user_id == user_id,
                        AgentMessage.is_read == True,  # noqa: E712
                    )
                )
                read_result = await db.execute(read_stmt)
                read_count = read_result.scalar() or 0
                reply_rate = read_count / total_agent
            else:
                reply_rate = 0.5  # 无历史数据给中间值

            if reply_rate >= 0.6:
                reply_weight = 2
            elif reply_rate >= 0.3:
                reply_weight = 1
            else:
                reply_weight = 0

        score = level_weight + trigger_weight + active_weight + reply_weight
        return float(score)

    # ================================================================
    #  4. generate_and_save_message —— 生成并保存主动消息
    # ================================================================

    async def generate_and_save_message(self, user_id: int, trigger_type: str) -> bool:
        """
        生成主动消息：
        1. 获取 Top3 相关记忆（用最近情绪作为检索词）
        2. 构建 Prompt
        3. 调用 LLM 生成
        4. 关键词扫描
        5. 保存到 agent_message
        6. Redis 计数器 +1
        7. 黑名单更新
        """
        try:
            async with async_session_maker() as db:
                # 获取最新情绪记录
                emotion_stmt = (
                    select(EmotionLog)
                    .where(EmotionLog.user_id == user_id)
                    .order_by(desc(EmotionLog.created_at))
                    .limit(5)
                )
                emotion_result = await db.execute(emotion_stmt)
                emotion_history = list(emotion_result.scalars().all())

                # 获取关系信息
                rel_stmt = select(Relationship).where(Relationship.user_id == user_id)
                rel_result = await db.execute(rel_stmt)
                relationship_info = rel_result.scalar_one_or_none()

            # 用最近情绪作为检索词查找相关记忆
            query_text = "用户的近期状态"
            if emotion_history:
                query_text = f"用户最近的情绪是{emotion_history[0].emotion_label}"

            user_memories = await self._search_memories_for_agent(user_id, query_text, top_k=3)

            # 构建主动消息 Prompt
            async with async_session_maker() as db:
                builder = PromptBuilder(db)
                prompt = await builder.build_active_message_prompt(
                    user_id=user_id,
                    trigger_type=trigger_type,
                    user_memories=user_memories,
                    emotion_history=emotion_history,
                    relationship_info=relationship_info,
                )

            # 调用 LLM 生成消息
            fallback = AGENT_FALLBACK_REPLIES.get(trigger_type, "想你了，你还好吗？")
            async with async_session_maker() as db:
                llm_result = await llm_service.generate_with_fallback(
                    prompt=prompt,
                    fallback_reply=fallback,
                    db=db,
                )

            reply = llm_result.get("reply", fallback)

            # 关键词扫描（persona_risk_flag）
            persona_risk = self._check_persona_risk(reply)
            if persona_risk:
                logger.warning("[Agent] 主动消息触发人格风险，使用兜底: user_id=%d", user_id)
                reply = fallback

            # 计算行动评分（用于存储）
            score = await self.calculate_action_score(user_id, trigger_type)

            # 保存到 agent_message 表（含 sort_seq 分配）
            async with async_session_maker() as db:
                seqs = await allocate_sort_seq(user_id, count=1, db=db)
                agent_msg = AgentMessage(
                    user_id=user_id,
                    trigger_type=trigger_type,
                    content=reply,
                    action_score=score,
                    sort_seq=seqs[0],
                )
                db.add(agent_msg)
                await db.commit()
                logger.info(
                    "[Agent] 主动消息已保存: user_id=%d, trigger=%s, score=%.1f, sort_seq=%d",
                    user_id, trigger_type, score, seqs[0],
                )

            # Redis 计数器 +1
            r = await get_redis()
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            count_key = f"agent:count:{user_id}:{today_str}"
            await r.incr(count_key)
            # TTL 到今日结束
            now = datetime.utcnow()
            end_of_day = now.replace(hour=23, minute=59, second=59)
            ttl_seconds = max(int((end_of_day - now).total_seconds()), 60)
            await r.expire(count_key, ttl_seconds)

            # R-FUT-03：proactive_times +1（上限 3）
            try:
                async with async_session_maker() as pt_db:
                    pt_stmt = select(Relationship).where(Relationship.user_id == user_id)
                    pt_result = await pt_db.execute(pt_stmt)
                    pt_rel = pt_result.scalar_one_or_none()
                    if pt_rel is not None and pt_rel.proactive_times < 3:
                        pt_rel.proactive_times += 1
                        await pt_db.commit()
                        logger.info(
                            "[Agent] proactive_times +1: user_id=%d, now=%d",
                            user_id, pt_rel.proactive_times,
                        )
            except Exception:
                logger.exception("[Agent] proactive_times +1 失败: user_id=%d", user_id)

            # 黑名单更新：最近2条 agent_message 都未读则加入黑名单
            await self._update_blacklist(user_id)

            return True

        except Exception as e:
            logger.error("[Agent] 生成主动消息失败: user_id=%d, error=%s", user_id, str(e), exc_info=True)
            return False

    # ================================================================
    #  5. increment_agent_count_for_future —— Future 槽消费后计入频控计数器
    # ================================================================

    async def increment_agent_count_for_future(self, user_id: int) -> None:
        """
        R-AGT-02：Future 槽消费成功后，额外计入 agent:count:{user_id}:{date} 计数器，
        让定时扫描 P0~P4 看到正确剩余次数。

        Future 槽消费绕过「8 次/天 + 30min 间隔」频控限制，
        但消费成功后须计入计数器。
        """
        try:
            r = await get_redis()
            now = datetime.utcnow()
            today_str = now.strftime("%Y-%m-%d")
            count_key = f"agent:count:{user_id}:{today_str}"
            await r.incr(count_key)
            end_of_day = now.replace(hour=23, minute=59, second=59)
            ttl_seconds = max(int((end_of_day - now).total_seconds()), 60)
            await r.expire(count_key, ttl_seconds)
            logger.info("[Agent] Future 槽消费计入计数器: user_id=%d, key=%s", user_id, count_key)
        except Exception:
            logger.exception("[Agent] Future 槽消费计入计数器失败: user_id=%d", user_id)

    # ================================================================
    #  6. reset_inactive_proactive_times —— 30 天无活动清零
    # ================================================================

    async def reset_inactive_proactive_times(self) -> int:
        """
        R-FUT-03④：连续 30 天无任何对话或登录活动的用户，
        自动清零 proactive_times 并清空 Future 槽，停止 Step8 触发。

        Returns:
            被清零的用户数量
        """
        reset_count = 0
        threshold = datetime.utcnow() - timedelta(days=30)
        try:
            async with async_session_maker() as db:
                stmt = select(Relationship).where(
                    and_(
                        Relationship.proactive_times > 0,
                        (
                            (Relationship.last_interaction_at == None)  # noqa: E711
                            | (Relationship.last_interaction_at < threshold)
                        ),
                    )
                )
                result = await db.execute(stmt)
                rels = list(result.scalars().all())

                for rel in rels:
                    rel.proactive_times = 0
                    rel.future_timestamp = None
                    rel.future_action = None
                    reset_count += 1
                    logger.info(
                        "[Agent] 30天无活动清零: user_id=%d, proactive_times→0, future→cleared",
                        rel.user_id,
                    )

                if reset_count > 0:
                    await db.commit()

            logger.info("[Agent] 30天无活动清零完成，共 %d 人", reset_count)
        except Exception:
            logger.exception("[Agent] 30天无活动清零任务异常")

        return reset_count

    # ================================================================
    #  触发条件检查方法
    # ================================================================

    async def _check_p0(self, user_id: int, db: AsyncSession) -> bool:
        """
        P0 情绪跟进触发：
        - 最新 emotion_log 的 label 在负面情绪中
        - 且该记录距今超过24小时
        - 且这24小时内无新的 conversation_log
        """
        stmt = (
            select(EmotionLog)
            .where(EmotionLog.user_id == user_id)
            .order_by(desc(EmotionLog.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        latest_emotion = result.scalar_one_or_none()
        if not latest_emotion:
            return False

        if latest_emotion.emotion_label not in NEGATIVE_EMOTIONS:
            return False

        now = datetime.utcnow()
        if (now - latest_emotion.created_at) < timedelta(hours=24):
            return False

        # 检查24小时内是否有新对话
        twenty_four_hours_ago = now - timedelta(hours=24)
        conv_stmt = (
            select(func.count())
            .select_from(ConversationLog)
            .where(
                and_(
                    ConversationLog.user_id == user_id,
                    ConversationLog.created_at >= twenty_four_hours_ago,
                )
            )
        )
        conv_result = await db.execute(conv_stmt)
        conv_count = conv_result.scalar() or 0

        return conv_count == 0

    async def _check_p1(self, user_id: int, db: AsyncSession) -> bool:
        """
        P1 长期沉默触发：
        - last_interaction_at 距今超过3天
        - 且 conversation_log 总条数≥10
        """
        rel_stmt = select(Relationship).where(Relationship.user_id == user_id)
        rel_result = await db.execute(rel_stmt)
        rel = rel_result.scalar_one_or_none()
        if not rel or not rel.last_interaction_at:
            return False

        now = datetime.utcnow()
        if (now - rel.last_interaction_at) < timedelta(days=3):
            return False

        conv_count_stmt = (
            select(func.count())
            .select_from(ConversationLog)
            .where(ConversationLog.user_id == user_id)
        )
        conv_result = await db.execute(conv_count_stmt)
        total = conv_result.scalar() or 0

        return total >= 10

    async def _check_p2(self, user_id: int, db: AsyncSession) -> bool:
        """
        P2 日常问候触发：
        - 注册满14天
        - 过去14天内 login_log 有≥8天记录 time_period 为 morning 或 evening
        - 今日的 login_log 中没有 morning 或 evening 的记录
        """
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if not user:
            return False

        now = datetime.utcnow()
        if (now - user.created_at) < timedelta(days=14):
            return False

        # 过去14天有习惯时段登录的天数
        fourteen_days_ago = now - timedelta(days=14)
        habit_stmt = (
            select(func.count(func.distinct(func.date(LoginLog.login_at))))
            .where(
                and_(
                    LoginLog.user_id == user_id,
                    LoginLog.login_at >= fourteen_days_ago,
                    LoginLog.time_period.in_(["morning", "evening"]),
                )
            )
        )
        habit_result = await db.execute(habit_stmt)
        habit_days = habit_result.scalar() or 0

        if habit_days < 8:
            return False

        # 今日是否有 morning 或 evening 登录
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_stmt = (
            select(func.count())
            .select_from(LoginLog)
            .where(
                and_(
                    LoginLog.user_id == user_id,
                    LoginLog.login_at >= today_start,
                    LoginLog.time_period.in_(["morning", "evening"]),
                )
            )
        )
        today_result = await db.execute(today_stmt)
        today_count = today_result.scalar() or 0

        return today_count == 0

    async def _check_p3(self, user_id: int, db: AsyncSession) -> bool:
        """
        P3 凌晨在线触发：
        - 最新一条 conversation_log 的 created_at 小时数在 0≤hour<6
        - 且 content 包含凌晨关键词
        """
        stmt = (
            select(ConversationLog)
            .where(
                and_(
                    ConversationLog.user_id == user_id,
                    ConversationLog.role == "user",
                )
            )
            .order_by(desc(ConversationLog.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        latest_conv = result.scalar_one_or_none()
        if not latest_conv:
            return False

        hour = latest_conv.created_at.hour
        if not (0 <= hour < 6):
            return False

        # 从 Redis 读取凌晨关键词
        keywords = await self._get_night_keywords()
        content = latest_conv.content
        return any(kw in content for kw in keywords)

    async def _check_p4(self, user_id: int, db: AsyncSession) -> bool:
        """
        P4 轻度沉默触发：
        - last_interaction_at 距今超过24小时
        - 且关系等级≥2
        """
        rel_stmt = select(Relationship).where(Relationship.user_id == user_id)
        rel_result = await db.execute(rel_stmt)
        rel = rel_result.scalar_one_or_none()
        if not rel or not rel.last_interaction_at:
            return False

        now = datetime.utcnow()
        if (now - rel.last_interaction_at) < timedelta(hours=24):
            return False

        return rel.level >= 2

    # ================================================================
    #  辅助方法
    # ================================================================

    async def _get_night_keywords(self) -> list[str]:
        """从 Redis 读取凌晨关键词，未配置则返回默认列表"""
        try:
            r = await get_redis()
            raw = await r.get("agent:night_keywords")
            if raw:
                keywords = json.loads(raw)
                if isinstance(keywords, list) and keywords:
                    return keywords
        except Exception as e:
            logger.warning("[Agent] 读取凌晨关键词失败: %s", str(e))
        return DEFAULT_NIGHT_KEYWORDS

    async def _search_memories_for_agent(
        self, user_id: int, query_text: str, top_k: int = 3
    ) -> list:
        """检索用户相关记忆，返回类 Memory 对象列表供 PromptBuilder 使用

        P1（长记忆第一套下线）：仅走 DashVector 向量检索，不依赖 MySQL memory 表校验，
        且一律不过滤 mem_* 前缀文档；旧脏数据依赖 M2 人工清理（STEP-016），运行时不过滤，请勿误加。
        """
        try:
            query_embedding = await embedding_service.get_embedding(query_text)
            if not query_embedding:
                return []

            dv_results = await vector_service.search(
                query_embedding=query_embedding,
                memory_type=MEMORY_TYPE_USER,
                user_id=user_id,
                top_k=top_k,
                threshold=0.7,
            )
            if not dv_results:
                return []

            class _MemoryProxy:
                """代理对象，模拟 Memory 模型供 PromptBuilder 使用"""
                def __init__(self, content: str):
                    self.content = content

            return [_MemoryProxy(m["content"]) for m in dv_results if m.get("content")]

        except Exception as e:
            logger.warning("[Agent] 记忆检索失败 user_id=%d: %s", user_id, str(e))
            return []

    @staticmethod
    def _check_persona_risk(text: str) -> bool:
        """检查生成的主动消息是否包含人格风险关键词"""
        text_lower = text.lower()
        for _, keywords in PERSONA_RISK_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return True
        return False

    async def _has_pending_future_slot(self, user_id: int) -> bool:
        """
        路 B 优先级保护：检查用户是否有未过期的 Future 槽。
        未过期 = future_timestamp 不为空 且 > 当前时间。
        """
        try:
            now_ts = int(time.time())
            async with async_session_maker() as db:
                stmt = select(Relationship.future_timestamp).where(
                    Relationship.user_id == user_id
                )
                result = await db.execute(stmt)
                future_ts = result.scalar_one_or_none()
                if future_ts is not None and future_ts > now_ts:
                    return True
        except Exception:
            logger.exception(
                "[Agent] 检查 Future 槽状态失败: user_id=%d", user_id
            )
        return False

    async def _update_blacklist(self, user_id: int) -> None:
        """
        黑名单更新：查询最近2条 agent_message，
        若 is_read 都为 False 则设置黑名单 TTL=15天。
        """
        try:
            async with async_session_maker() as db:
                stmt = (
                    select(AgentMessage)
                    .where(AgentMessage.user_id == user_id)
                    .order_by(desc(AgentMessage.created_at))
                    .limit(2)
                )
                result = await db.execute(stmt)
                recent_msgs = list(result.scalars().all())

            if len(recent_msgs) >= 2 and all(not msg.is_read for msg in recent_msgs):
                r = await get_redis()
                blacklist_key = f"agent:blacklist:{user_id}"
                await r.set(blacklist_key, "1", ex=15 * 86400)  # 15天
                logger.info("[Agent] 用户 %d 加入黑名单（连续2条未读）", user_id)

        except Exception as e:
            logger.warning("[Agent] 黑名单更新失败 user_id=%d: %s", user_id, str(e))


# 全局单例
agent_service = AgentService()
