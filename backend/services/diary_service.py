# -*- coding: utf-8 -*-
# AI 日记业务逻辑：日记生成规则、LLM 生成、批量任务

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models.ai_diary import AiDiary
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.services.relationship_service import LEVEL_CONFIG
from backend.utils.llm_client import llm_client
from backend.services.diary_rules_loader import (
    DEFAULT_PROMPT_WITHOUT_INTERACTION,
    DEFAULT_PROMPT_WITH_INTERACTION,
    fill_diary_prompt_template,
    get_resolved_diary_rules,
)

logger = logging.getLogger(__name__)


class DiaryService:
    """AI 日记生成服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_diary_llm_with_fallback(
        self,
        user_id: int,
        primary_prompt: str,
        has_interaction: bool,
        level_name: str,
        conversation_summary: str,
        recent_emotion: str,
        max_len: int,
    ) -> str | None:
        """调用 LLM 生成日记；失败或空内容时用硬编码模板再试一次。"""
        try:
            text = await llm_client.chat_sync(primary_prompt)
            if text and text.strip():
                return text.strip()
            logger.warning("用户 %d 日记 LLM 返回空，尝试硬编码模板重试", user_id)
        except Exception as e:
            logger.warning("用户 %d 日记 LLM 首次失败，使用硬编码模板重试: %s", user_id, str(e))

        fb_tpl = DEFAULT_PROMPT_WITH_INTERACTION if has_interaction else DEFAULT_PROMPT_WITHOUT_INTERACTION
        fallback_prompt = fill_diary_prompt_template(
            fb_tpl,
            relationship_level_name=level_name,
            conversation_summary=conversation_summary,
            recent_emotion=recent_emotion,
            recent_thought="（暂无）",
            max_length=max_len,
        )
        try:
            text2 = await llm_client.chat_sync(fallback_prompt)
            if text2 and text2.strip():
                return text2.strip()
        except Exception as e:
            logger.error("用户 %d 日记 LLM 硬编码模板仍失败: %s", user_id, str(e))
        return None

    async def generate_diary_for_user(self, user_id: int) -> bool:
        """
        为单个用户生成当日 AI 日记。

        生成规则（两条独立规则）：
        - 规则一：关系等级≥1 且当日有互动 → 生成（内容围绕互动）
        - 规则二：关系等级≥2 且当日无互动 → 生成（内容为想念用户）
        - 1级且无互动 → 不生成
        - 0级 → 不生成

        Returns:
            True 表示成功生成，False 表示不满足条件或生成失败
        """
        # 获取关系状态
        stmt = select(Relationship).where(Relationship.user_id == user_id)
        result = await self.db.execute(stmt)
        relationship = result.scalar_one_or_none()

        if not relationship or relationship.level < 1:
            logger.debug("用户 %d 关系等级为 0，跳过日记生成", user_id)
            return False

        level = relationship.level
        level_name = LEVEL_CONFIG.get(level, {}).get("name", "未知")

        # 检查今日是否已生成日记（避免重复生成）
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        existing_stmt = select(func.count()).select_from(AiDiary).where(
            and_(
                AiDiary.user_id == user_id,
                AiDiary.created_at >= today_start,
                AiDiary.created_at < today_end,
            )
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar() > 0:
            logger.debug("用户 %d 今日已有日记，跳过", user_id)
            return False

        # 获取当日对话记录（最多5轮用户消息）
        has_interaction, conversation_summary = await self._get_today_conversation_summary(user_id)

        # 应用规则判断
        if level == 1 and not has_interaction:
            logger.debug("用户 %d 关系等级1且无互动，不生成日记", user_id)
            return False

        # level>=1 且有互动 → 生成
        # level>=2 且无互动 → 生成（想念用户）

        # 获取用户最近情绪
        recent_emotion = await self._get_recent_emotion(user_id)

        rules = await get_resolved_diary_rules(use_cache=True)
        if rules.used_fallback:
            logger.warning("用户 %d 日记生成使用部分默认规则（配置缺失或非法字段已回退）", user_id)

        max_len = rules.max_length
        template = rules.prompt_with_interaction if has_interaction else rules.prompt_without_interaction
        prompt = fill_diary_prompt_template(
            template,
            relationship_level_name=level_name,
            conversation_summary=conversation_summary,
            recent_emotion=recent_emotion,
            recent_thought="（暂无）",
            max_length=max_len,
        )

        diary_content = await self._generate_diary_llm_with_fallback(
            user_id=user_id,
            primary_prompt=prompt,
            has_interaction=has_interaction,
            level_name=level_name,
            conversation_summary=conversation_summary,
            recent_emotion=recent_emotion,
            max_len=max_len,
        )
        if not diary_content:
            return False

        diary_content = diary_content.strip()
        if len(diary_content) > max_len:
            diary_content = diary_content[:max_len]

        # 写入数据库
        diary = AiDiary(
            user_id=user_id,
            content=diary_content,
            relationship_level_at_creation=level,
        )
        self.db.add(diary)
        await self.db.flush()

        logger.info("用户 %d 日记生成成功，日记 ID=%d", user_id, diary.id)
        return True

    async def run_daily_diary_task(self) -> None:
        """
        批量为所有符合条件的用户生成日记。

        定时任务调用入口，使用 Semaphore 控制并发，避免同时发起太多 LLM 调用。
        """
        logger.info("开始执行每日日记批量生成任务")

        # 查询所有关系等级≥1的用户
        async with async_session_maker() as db:
            stmt = select(Relationship.user_id).where(Relationship.level >= 1)
            result = await db.execute(stmt)
            user_ids = [row[0] for row in result.all()]

        if not user_ids:
            logger.info("无符合条件的用户，日记任务结束")
            return

        logger.info("日记任务：共 %d 个候选用户", len(user_ids))

        semaphore = asyncio.Semaphore(10)
        success_count = 0
        fail_count = 0

        async def _generate_for_user(uid: int) -> bool:
            async with semaphore:
                try:
                    async with async_session_maker() as session:
                        svc = DiaryService(session)
                        generated = await svc.generate_diary_for_user(uid)
                        await session.commit()
                        return generated
                except Exception as e:
                    logger.error("用户 %d 日记生成异常: %s", uid, str(e))
                    return False

        tasks = [_generate_for_user(uid) for uid in user_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for uid, res in zip(user_ids, results):
            if isinstance(res, Exception):
                logger.error("用户 %d 日记任务异常: %s", uid, str(res))
                fail_count += 1
            elif res:
                success_count += 1
            # res 为 False 表示不满足条件或已生成，不计入失败

        logger.info(
            "每日日记任务完成：成功=%d，失败=%d，总候选=%d",
            success_count, fail_count, len(user_ids),
        )

    async def _get_today_conversation_summary(self, user_id: int) -> tuple[bool, str]:
        """
        获取用户当日对话摘要。

        Returns:
            (是否有互动, 摘要字符串)
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        stmt = (
            select(ConversationLog)
            .where(
                and_(
                    ConversationLog.user_id == user_id,
                    ConversationLog.created_at >= today_start,
                )
            )
            .order_by(ConversationLog.created_at.asc())
            .limit(10)  # 最多取10条（5轮 = 用户+AI 各5条）
        )
        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        if not conversations:
            return False, ""

        # 拼接摘要：取前5轮用户消息内容
        user_messages = [c.content for c in conversations if c.role == "user"][:5]
        summary = "；".join(user_messages)

        # 限制摘要长度
        if len(summary) > 500:
            summary = summary[:500] + "..."

        return True, summary

    async def _get_recent_emotion(self, user_id: int) -> str:
        """获取用户最近一条情绪标签"""
        stmt = (
            select(EmotionLog.emotion_label)
            .where(EmotionLog.user_id == user_id)
            .order_by(EmotionLog.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        label = result.scalar_one_or_none()
        return label or "平静"
