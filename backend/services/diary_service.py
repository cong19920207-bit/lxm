# -*- coding: utf-8 -*-
# AI 日记业务逻辑：日记生成规则、LLM 生成、批量任务

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError
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

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_UTC_TZ = ZoneInfo("UTC")


def compute_shanghai_diary_batch_window(
    now_sh: datetime | None = None,
) -> tuple[date, date, datetime, datetime]:
    """
    以当前上海时刻的日历日为锚点 D，日记覆盖日为 D-1。
    对话统计窗为 [D-1 00:00, D 00:00)（上海），返回 naive UTC 与库中 created_at 对齐。
    """
    if now_sh is None:
        now_sh = datetime.now(_SHANGHAI_TZ)
    elif now_sh.tzinfo is None:
        now_sh = now_sh.replace(tzinfo=_SHANGHAI_TZ)
    else:
        now_sh = now_sh.astimezone(_SHANGHAI_TZ)

    anchor_d = now_sh.date()
    covers_d = anchor_d - timedelta(days=1)
    win_start_sh = datetime.combine(covers_d, time.min, tzinfo=_SHANGHAI_TZ)
    win_end_sh = datetime.combine(anchor_d, time.min, tzinfo=_SHANGHAI_TZ)
    win_start_utc = win_start_sh.astimezone(_UTC_TZ).replace(tzinfo=None)
    win_end_utc = win_end_sh.astimezone(_UTC_TZ).replace(tzinfo=None)
    return anchor_d, covers_d, win_start_utc, win_end_utc


def _format_zh_covers_day(d: date) -> str:
    """北京覆盖日的中文展示片段（如 5月15日），供 Prompt 与前端一致口径。"""
    return f"{d.month}月{d.day}日"


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
        covers_date_label_zh: str = "",
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
            covers_date_label_zh=covers_date_label_zh,
        )
        try:
            text2 = await llm_client.chat_sync(fallback_prompt)
            if text2 and text2.strip():
                return text2.strip()
        except Exception as e:
            logger.error("用户 %d 日记 LLM 硬编码模板仍失败: %s", user_id, str(e))
        return None

    async def generate_diary_for_user(
        self,
        user_id: int,
        *,
        covers_beijing_date: date | None = None,
        conv_start_naive_utc: datetime | None = None,
        conv_end_naive_utc: datetime | None = None,
    ) -> bool:
        """
        为单个用户生成 AI 日记（覆盖日为上海前一日 D-1，对话窗 [D-1 00:00, D 00:00)）。

        生成规则：
        - 关系等级≥1 且统计窗内有互动 → 生成（内容围绕该窗内互动）
        - 关系等级≥2 且统计窗内无互动 → 生成（想念用户）
        - 1 级且无互动 → 不生成
        - 0 级 → 不生成

        未传入时间窗参数时，按「当前上海时刻」现场计算（便于单用户手动试跑）。

        Returns:
            True 表示成功生成，False 表示不满足条件或生成失败
        """
        if covers_beijing_date is None or conv_start_naive_utc is None or conv_end_naive_utc is None:
            _, covers_beijing_date, conv_start_naive_utc, conv_end_naive_utc = compute_shanghai_diary_batch_window()

        stmt = select(Relationship).where(Relationship.user_id == user_id)
        result = await self.db.execute(stmt)
        relationship = result.scalar_one_or_none()

        if not relationship or relationship.level < 1:
            logger.debug("用户 %d 关系等级为 0，跳过日记生成", user_id)
            return False

        level = relationship.level
        level_name = LEVEL_CONFIG.get(level, {}).get("name", "未知")

        # 同一用户、同一覆盖日（北京）仅允许一条（幂等）
        existing_stmt = select(func.count()).select_from(AiDiary).where(
            and_(
                AiDiary.user_id == user_id,
                AiDiary.covers_beijing_date == covers_beijing_date,
            )
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar() > 0:
            logger.debug(
                "用户 %d 在覆盖日 %s 已有日记，跳过",
                user_id,
                covers_beijing_date.isoformat(),
            )
            return False

        has_interaction, conversation_summary = await self._get_conversation_summary_in_window(
            user_id, conv_start_naive_utc, conv_end_naive_utc
        )

        if level == 1 and not has_interaction:
            logger.debug("用户 %d 关系等级1且统计窗内无互动，不生成日记", user_id)
            return False

        recent_emotion = await self._get_recent_emotion(user_id)

        rules = await get_resolved_diary_rules(use_cache=True)
        if rules.used_fallback:
            logger.warning("用户 %d 日记生成使用部分默认规则（配置缺失或非法字段已回退）", user_id)

        max_len = rules.max_length
        template = rules.prompt_with_interaction if has_interaction else rules.prompt_without_interaction
        date_zh = _format_zh_covers_day(covers_beijing_date)
        prompt = fill_diary_prompt_template(
            template,
            relationship_level_name=level_name,
            conversation_summary=conversation_summary,
            recent_emotion=recent_emotion,
            recent_thought="（暂无）",
            max_length=max_len,
            covers_date_label_zh=date_zh,
        )

        diary_content = await self._generate_diary_llm_with_fallback(
            user_id=user_id,
            primary_prompt=prompt,
            has_interaction=has_interaction,
            level_name=level_name,
            conversation_summary=conversation_summary,
            recent_emotion=recent_emotion,
            max_len=max_len,
            covers_date_label_zh=date_zh,
        )
        if not diary_content:
            return False

        diary_content = diary_content.strip()
        if len(diary_content) > max_len:
            diary_content = diary_content[:max_len]

        diary = AiDiary(
            user_id=user_id,
            content=diary_content,
            relationship_level_at_creation=level,
            covers_beijing_date=covers_beijing_date,
        )
        self.db.add(diary)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            logger.warning(
                "用户 %d 覆盖日 %s 日记并发或唯一约束冲突，跳过",
                user_id,
                covers_beijing_date.isoformat(),
            )
            return False

        logger.info(
            "用户 %d 日记生成成功，日记 ID=%d，覆盖日(北京)=%s",
            user_id,
            diary.id,
            covers_beijing_date.isoformat(),
        )
        return True

    async def run_daily_diary_task(self) -> None:
        """
        批量为所有符合条件的用户生成日记。

        整批任务共用一次「上海锚点」时间窗，避免跨点误差。
        """
        logger.info("开始执行每日日记批量生成任务")

        anchor_d, covers_d, conv_start_utc, conv_end_utc = compute_shanghai_diary_batch_window()
        logger.info(
            "日记批跑：上海锚点日 D=%s，覆盖日=%s，对话窗 naive_UTC=[%s, %s)",
            anchor_d.isoformat(),
            covers_d.isoformat(),
            conv_start_utc.isoformat(),
            conv_end_utc.isoformat(),
        )

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
                        generated = await svc.generate_diary_for_user(
                            uid,
                            covers_beijing_date=covers_d,
                            conv_start_naive_utc=conv_start_utc,
                            conv_end_naive_utc=conv_end_utc,
                        )
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

        logger.info(
            "每日日记任务完成：成功=%d，失败=%d，总候选=%d",
            success_count,
            fail_count,
            len(user_ids),
        )

    async def _get_conversation_summary_in_window(
        self,
        user_id: int,
        start_naive_utc: datetime,
        end_naive_utc: datetime,
    ) -> tuple[bool, str]:
        """
        获取指定 naive UTC 时间窗内的对话摘要（与 conversation_log.created_at 对齐）。

        Returns:
            (是否有互动, 摘要字符串)
        """
        stmt = (
            select(ConversationLog)
            .where(
                and_(
                    ConversationLog.user_id == user_id,
                    ConversationLog.created_at >= start_naive_utc,
                    ConversationLog.created_at < end_naive_utc,
                )
            )
            .order_by(ConversationLog.created_at.asc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        if not conversations:
            return False, ""

        user_messages = [c.content for c in conversations if c.role == "user"][:5]
        summary = "；".join(user_messages)

        if len(summary) > 500:
            summary = summary[:500] + "..."

        return True, summary

    async def _get_recent_emotion(self, user_id: int) -> str:
        """获取用户最近一条情绪标签（全时间，不按统计窗裁剪）。"""
        stmt = (
            select(EmotionLog.emotion_label)
            .where(EmotionLog.user_id == user_id)
            .order_by(EmotionLog.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        label = result.scalar_one_or_none()
        return label or "平静"
