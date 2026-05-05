# -*- coding: utf-8 -*-
# 关系业务逻辑：成长值计算、等级判定、沉默天数、连续登录、Step6 标量回写

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.conversation_log import ConversationLog
from backend.models.relationship import Relationship
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.models.relationship_level_history import RelationshipLevelHistory
from backend.models.user import User
from backend.redis_client import get_redis
from backend.services.relationship_history_service import RelationshipHistoryService
from backend.utils.future_time_parser import parse_future_time

logger = logging.getLogger(__name__)

# 关系等级配置
LEVEL_CONFIG = {
    0: {
        "name": "陌生",
        "threshold": 0,
        "next_threshold": 200,
        "description": "初次相识，一切都是新鲜的开始",
        "ai_behavior": "礼貌温柔，主动提问了解你，保持适当边界感",
        "perks": ["基础对话陪伴"],
        "next_perks": ["解锁AI日记功能", "可使用亲昵称呼", "更强的情绪共情"],
    },
    1: {
        "name": "朋友",
        "threshold": 200,
        "next_threshold": 800,
        "description": "已经是熟悉的朋友，互相了解，建立了基础信任",
        "ai_behavior": "轻松自然，像朋友一样聊天，可以用亲昵称呼",
        "perks": ["基础对话陪伴", "AI日记功能已解锁", "亲昵称呼"],
        "next_perks": ["AI可表达想念与依赖", "无互动日也会收到日记", "更深层的情感表达"],
    },
    2: {
        "name": "亲密",
        "threshold": 800,
        "next_threshold": 2000,
        "description": "亲密的陪伴者，互相信任，建立了深度的情感连接",
        "ai_behavior": "温柔粘人，会表达想念，无话不谈",
        "perks": ["全部朋友权益", "AI主动表达想念", "无互动日收到想念日记", "更深的情感互动"],
        "next_perks": ["完全贴合你的情绪与习惯", "AI完全站在你这边", "灵魂级别的深度理解"],
    },
    3: {
        "name": "知己",
        "threshold": 2000,
        "next_threshold": None,
        "description": "灵魂知己，完全懂对方，是彼此最专属的陪伴者",
        "ai_behavior": "完全贴合你的情绪与习惯，永远站在你这边",
        "perks": ["所有权益已解锁", "最深度的情感陪伴", "完全个性化的互动体验"],
        "next_perks": [],
    },
}

# 成长值行为配置：(每次加分, 每日上限)
GROWTH_ACTIONS = {
    "dialog": {"points": 2, "daily_limit": 50},
    "long_session": {"points": 20, "daily_limit": 20},
    "daily_login": {"points": 5, "daily_limit": 10},
    "reply_agent": {"points": 10, "daily_limit": 20},
}

# 成长值行为描述映射
ACTION_LABELS = {
    "dialog": "完成一轮对话",
    "long_session": "深度聊天奖励",
    "daily_login": "今日登录",
    "reply_agent": "回复了林小梦的消息",
}

# Redis key 前缀映射（按 action_type 拆分存储）
_ACTION_REDIS_PREFIX = {
    "dialog": "growth_dialog",
    "long_session": "growth_session",
    "daily_login": "growth_login",
    "reply_agent": "growth_reply",
}


def _calc_level(growth_value: int) -> int:
    """根据总成长值计算当前等级"""
    if growth_value >= 2000:
        return 3
    if growth_value >= 800:
        return 2
    if growth_value >= 200:
        return 1
    return 0


def _seconds_until_midnight() -> int:
    """计算距离今日 23:59:59 的秒数"""
    now = datetime.utcnow()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 1)


class RelationshipService:
    """关系成长系统服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_relationship(self, user_id: int) -> Relationship:
        """获取关系记录，不存在则创建"""
        stmt = select(Relationship).where(Relationship.user_id == user_id)
        result = await self.db.execute(stmt)
        rel = result.scalar_one_or_none()
        if rel is None:
            rel = Relationship(user_id=user_id, level=0, growth_value=0)
            self.db.add(rel)
            await self.db.flush()
        return rel

    async def add_growth(self, user_id: int, action_type: str) -> dict:
        """
        增加成长值。

        Args:
            user_id: 用户 ID
            action_type: 行为类型（dialog / long_session / daily_login / reply_agent）

        Returns:
            包含升级信息的字典
        """
        action_cfg = GROWTH_ACTIONS.get(action_type)
        if action_cfg is None:
            raise ValueError(f"未知的 action_type: {action_type}")

        points = action_cfg["points"]
        daily_limit = action_cfg["daily_limit"]

        # 连续登录 7 天以上，daily_login 加成翻倍
        if action_type == "daily_login":
            rel_for_check = await self._get_or_create_relationship(user_id)
            if rel_for_check.consecutive_login_days > 7:
                points = 10

        redis = await get_redis()
        today_str = date.today().strftime("%Y%m%d")

        # 兼容旧 key 和新的分 action_type key
        old_redis_key = f"growth:{user_id}:{today_str}:{action_type}"
        prefix = _ACTION_REDIS_PREFIX.get(action_type, f"growth_{action_type}")
        new_redis_key = f"{prefix}:{user_id}:{today_str}"

        # 读取今日该行为已累计分值（优先读新 key，向下兼容旧 key）
        current_daily = await redis.get(new_redis_key)
        if current_daily is None:
            current_daily = await redis.get(old_redis_key)
        current_daily = int(current_daily) if current_daily else 0

        if current_daily >= daily_limit:
            rel = await self._get_or_create_relationship(user_id)
            level_cfg = LEVEL_CONFIG[rel.level]
            return {
                "leveled_up": False,
                "new_level": rel.level,
                "new_level_name": level_cfg["name"],
                "current_growth": rel.growth_value,
                "next_threshold": level_cfg["next_threshold"],
            }

        # 计算本次实际可增加的分值（不超过上限）
        actual_points = min(points, daily_limit - current_daily)

        # 更新 Redis 今日累计（同时写新旧两个 key 保证兼容）
        ttl = _seconds_until_midnight()
        await redis.incrby(old_redis_key, actual_points)
        await redis.expire(old_redis_key, ttl)
        await redis.incrby(new_redis_key, actual_points)
        await redis.expire(new_redis_key, ttl)

        # 更新 MySQL
        rel = await self._get_or_create_relationship(user_id)
        old_level = rel.level
        rel.growth_value += actual_points
        rel.last_interaction_at = datetime.utcnow()

        # 检查是否升级
        new_level = _calc_level(rel.growth_value)
        leveled_up = new_level > old_level
        if leveled_up:
            rel.level = new_level
            logger.info(
                "用户 %d 升级: %d -> %d, 成长值=%d",
                user_id, old_level, new_level, rel.growth_value,
            )
            # 写入等级升级历史
            history_record = RelationshipLevelHistory(
                user_id=user_id,
                from_level=old_level,
                to_level=new_level,
                achieved_at=datetime.utcnow(),
            )
            self.db.add(history_record)

        await self.db.flush()

        # 写入成长值获取日志（异步写入，不阻塞主流程）
        growth_log = RelationshipGrowthLog(
            user_id=user_id,
            action_type=action_type,
            points=actual_points,
            created_at=datetime.utcnow(),
        )
        self.db.add(growth_log)
        await self.db.flush()

        level_cfg = LEVEL_CONFIG[rel.level]
        return {
            "leveled_up": leveled_up,
            "new_level": rel.level,
            "new_level_name": level_cfg["name"],
            "current_growth": rel.growth_value,
            "next_threshold": level_cfg["next_threshold"],
        }

    async def get_relationship_info(self, user_id: int) -> dict:
        """
        获取用户关系状态信息。

        Returns:
            包含等级、成长值、进度、沉默天数、AI 情绪的字典
        """
        rel = await self._get_or_create_relationship(user_id)
        level_cfg = LEVEL_CONFIG[rel.level]

        # 计算升级进度百分比
        if level_cfg["next_threshold"] is None:
            progress_percent = 100
        else:
            current_threshold = level_cfg["threshold"]
            next_threshold = level_cfg["next_threshold"]
            accumulated = rel.growth_value - current_threshold
            total_needed = next_threshold - current_threshold
            progress_percent = int(accumulated / total_needed * 100) if total_needed > 0 else 100

        silence_days = await self.get_silence_days(user_id)

        # 从 Redis 读取 AI 当前情绪（存储格式为 JSON）
        redis = await get_redis()
        ai_emotion_raw = await redis.get(f"ai_emotion:{user_id}")
        ai_emotion = "平静"
        if ai_emotion_raw:
            try:
                ai_data = json.loads(ai_emotion_raw)
                if isinstance(ai_data, dict):
                    ai_emotion = ai_data.get("label", "平静")
                else:
                    ai_emotion = str(ai_data)
            except (json.JSONDecodeError, TypeError):
                ai_emotion = ai_emotion_raw

        return {
            "level": rel.level,
            "level_name": level_cfg["name"],
            "growth_value": rel.growth_value,
            "current_growth": rel.growth_value,
            "next_threshold": level_cfg["next_threshold"],
            "progress_percent": progress_percent,
            "silence_days": silence_days,
            "ai_current_emotion": ai_emotion,
        }

    async def get_relationship_detail(self, user_id: int) -> dict:
        """
        获取关系状态页完整数据。

        Returns:
            包含 level_info, growth_info, milestones, level_history,
            today_growth, ai_current_emotion 的字典
        """
        rel = await self._get_or_create_relationship(user_id)
        level = rel.level
        level_cfg = LEVEL_CONFIG[level]

        # === 1. 等级信息 ===
        next_level_name = LEVEL_CONFIG[level + 1]["name"] if level < 3 else None
        level_info = {
            "level": level,
            "name": level_cfg["name"],
            "description": level_cfg["description"],
            "ai_behavior": level_cfg["ai_behavior"],
            "perks": level_cfg["perks"],
            "next_level_name": next_level_name,
            "next_perks": level_cfg["next_perks"],
        }

        # === 2. 成长进度 ===
        current_threshold = level_cfg["threshold"]
        next_threshold = level_cfg["next_threshold"]
        is_max_level = level == 3

        if not is_max_level:
            points_in_level = rel.growth_value - current_threshold
            points_needed = next_threshold - current_threshold
            progress_percent = round(points_in_level / points_needed * 100) if points_needed > 0 else 100
            points_to_next = next_threshold - rel.growth_value
        else:
            points_in_level = 0
            points_needed = 0
            progress_percent = 100
            points_to_next = 0

        growth_info = {
            "current_growth": rel.growth_value,
            "next_threshold": next_threshold,
            "points_in_level": points_in_level,
            "points_needed": points_needed,
            "progress_percent": progress_percent,
            "points_to_next": points_to_next,
            "is_max_level": is_max_level,
        }

        # === 3. 互动里程碑 ===
        # 用户注册时间
        user_stmt = select(User.created_at).where(User.id == user_id)
        user_result = await self.db.execute(user_stmt)
        user_created_at = user_result.scalar_one_or_none()
        known_days = (datetime.utcnow() - user_created_at).days if user_created_at else 0

        # 总对话轮次（role='user' 的记录数）
        rounds_stmt = (
            select(func.count())
            .select_from(ConversationLog)
            .where(ConversationLog.user_id == user_id, ConversationLog.role == "user")
        )
        rounds_result = await self.db.execute(rounds_stmt)
        total_conversation_rounds = rounds_result.scalar() or 0

        # 第一条对话时间
        first_conv_stmt = (
            select(func.min(ConversationLog.created_at))
            .where(ConversationLog.user_id == user_id)
        )
        first_conv_result = await self.db.execute(first_conv_stmt)
        first_conversation_at = first_conv_result.scalar()

        # 沉默天数
        if rel.last_interaction_at:
            silence_days = (datetime.utcnow() - rel.last_interaction_at).days
        else:
            silence_days = known_days

        milestones = {
            "known_days": known_days,
            "total_conversation_rounds": total_conversation_rounds,
            "first_conversation_at": first_conversation_at.isoformat() if first_conversation_at else None,
            "silence_days": silence_days,
            "consecutive_login_days": rel.consecutive_login_days or 0,
        }

        # === 4. 等级升级历史（最近5条，倒序） ===
        history_stmt = (
            select(RelationshipLevelHistory)
            .where(RelationshipLevelHistory.user_id == user_id)
            .order_by(RelationshipLevelHistory.achieved_at.desc())
            .limit(5)
        )
        history_result = await self.db.execute(history_stmt)
        history_records = history_result.scalars().all()
        level_history = [
            {
                "from_level": h.from_level,
                "to_level": h.to_level,
                "level_name": LEVEL_CONFIG.get(h.to_level, {}).get("name", "未知"),
                "achieved_at": h.achieved_at.isoformat() if h.achieved_at else None,
            }
            for h in history_records
        ]

        # === 5. 今日成长值明细（从 Redis 读取） ===
        redis = await get_redis()
        today_str = date.today().strftime("%Y%m%d")

        today_dialog = await redis.get(f"growth_dialog:{user_id}:{today_str}")
        today_login = await redis.get(f"growth_login:{user_id}:{today_str}")
        today_session = await redis.get(f"growth_session:{user_id}:{today_str}")
        today_reply = await redis.get(f"growth_reply:{user_id}:{today_str}")

        today_dialog_points = int(today_dialog) if today_dialog else 0
        today_login_points = int(today_login) if today_login else 0
        today_session_points = int(today_session) if today_session else 0
        today_reply_points = int(today_reply) if today_reply else 0
        today_total_points = today_dialog_points + today_login_points + today_session_points + today_reply_points

        today_growth = {
            "today_total_points": today_total_points,
            "today_dialog_points": today_dialog_points,
            "today_login_points": today_login_points,
            "today_session_points": today_session_points,
            "today_reply_points": today_reply_points,
            "today_dialog_limit_reached": today_dialog_points >= 50,
            "today_remaining_dialog": max(0, 50 - today_dialog_points),
        }

        # === 6. AI 当前情绪 ===
        ai_emotion_raw = await redis.get(f"ai_emotion:{user_id}")
        ai_emotion = "平静"
        if ai_emotion_raw:
            try:
                ai_data = json.loads(ai_emotion_raw)
                if isinstance(ai_data, dict):
                    ai_emotion = ai_data.get("label", "平静")
                else:
                    ai_emotion = str(ai_data)
            except (json.JSONDecodeError, TypeError):
                ai_emotion = ai_emotion_raw

        return {
            "level_info": level_info,
            "growth_info": growth_info,
            "milestones": milestones,
            "level_history": level_history,
            "today_growth": today_growth,
            "ai_current_emotion": ai_emotion,
        }

    async def get_growth_log_paginated(self, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        """
        分页获取成长值获取记录。

        Returns:
            包含 list, total, page, page_size 的字典
        """
        # 总数
        count_stmt = (
            select(func.count())
            .select_from(RelationshipGrowthLog)
            .where(RelationshipGrowthLog.user_id == user_id)
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        list_stmt = (
            select(RelationshipGrowthLog)
            .where(RelationshipGrowthLog.user_id == user_id)
            .order_by(RelationshipGrowthLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        list_result = await self.db.execute(list_stmt)
        records = list_result.scalars().all()

        items = [
            {
                "id": r.id,
                "action_type": r.action_type,
                "action_label": ACTION_LABELS.get(r.action_type, r.action_type),
                "points": r.points,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

        return {
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_silence_days(self, user_id: int) -> int:
        """
        计算距离上次互动的天数。

        用于 Prompt 中沉默语气修正：
        - 0-7天：正常语气
        - 8-14天：语气带担心和想念
        - 15天以上：久别重逢的温柔感
        """
        stmt = select(Relationship).where(Relationship.user_id == user_id)
        result = await self.db.execute(stmt)
        relationship = result.scalar_one_or_none()

        if not relationship or not relationship.last_interaction_at:
            return 999

        now = datetime.utcnow()
        delta = now - relationship.last_interaction_at
        return delta.days

    async def update_consecutive_login(self, user_id: int) -> None:
        """
        更新连续登录天数，每日首次登录时调用。

        规则：
        - 上次登录是昨天 → consecutive_login_days + 1
        - 上次登录是今天 → 不变（同一天多次登录不重复计数）
        - 上次登录超过昨天 → 重置为 1
        """
        rel = await self._get_or_create_relationship(user_id)
        today = date.today()

        if rel.last_interaction_at is None:
            rel.consecutive_login_days = 1
            rel.last_interaction_at = datetime.utcnow()
            await self.db.flush()
            return

        last_date = rel.last_interaction_at.date()

        if last_date == today:
            return

        if last_date == today - timedelta(days=1):
            rel.consecutive_login_days += 1
        else:
            rel.consecutive_login_days = 1

        await self.db.flush()

    async def get_growth_history(self, user_id: int) -> list[dict]:
        """
        获取关系成长历史（通过 Redis 读取今日各行为已获成长值）。

        返回今日各行为的成长值记录。
        """
        redis = await get_redis()
        today_str = date.today().strftime("%Y%m%d")
        history = []

        for action_type, cfg in GROWTH_ACTIONS.items():
            redis_key = f"growth:{user_id}:{today_str}:{action_type}"
            earned = await redis.get(redis_key)
            earned = int(earned) if earned else 0
            history.append({
                "action_type": action_type,
                "earned_today": earned,
                "daily_limit": cfg["daily_limit"],
                "points_per_action": cfg["points"],
            })

        return history

    # ── STEP-015：Step6 标量写回 + 历史 + Future 槽 ──

    # Step6 输出字段（驼峰）→ relationship 表列名（蛇形）的映射
    _STEP6_FIELD_MAP: dict[str, str] = {
        "UserRealName": "user_real_name",
        "UserHobbyName": "user_hobby_name",
        "UserDescription": "user_description",
        "CharacterPurpose": "character_purpose",
        "CharacterAttitude": "character_attitude",
        "RelationDescription": "relation_description",
    }

    async def update_relationship_from_step6(
        self,
        relationship: Relationship,
        step6_output,
        round_id: Optional[str] = None,
        *,
        future_time_natural: Optional[str] = None,
        future_action: Optional[str] = None,
    ) -> dict:
        """
        将 Step6 记忆 LLM 的 6 个标量字段写回 relationship 表，并处理 Future 槽。

        规则（R-MEM-05）：
        - 值非「无」→ UPDATE 覆盖该列 + 写入变更历史（含 old_value）
        - 值为「无」→ 跳过赋值，保留库内上一轮值
        - 历史记录 trigger_source='step6'，携带 round_id

        Future 槽（§2.8.4）：
        - future.time_natural 调用 parse_future_time 解析
        - 解析成功 → 写入 future_timestamp + future_action
        - action 为「无」→ 清空 future 字段
        - 解析失败 → 清空 future 字段 + 保留 proactive_times + 写日志

        Args:
            relationship: 当前用户的 Relationship 实例（已从 DB 加载）
            step6_output: Step6MemoryOutput 实例（含 6 个标量字段）
            round_id: 本轮对话 round_id
            future_time_natural: Step5 输出的 future.time_natural
            future_action: Step5 输出的 future.action

        Returns:
            {"updated_fields": [...], "history_count": N, "future_status": "..."}
        """
        history_svc = RelationshipHistoryService(self.db)
        updated_fields: list[str] = []
        history_count = 0

        # ── 1. 6 个标量字段写回 ──
        for step6_key, db_column in self._STEP6_FIELD_MAP.items():
            new_value = getattr(step6_output, step6_key, "无")
            if not isinstance(new_value, str):
                new_value = str(new_value)

            if new_value.strip() == "无":
                continue

            old_value = getattr(relationship, db_column, None)

            setattr(relationship, db_column, new_value)
            updated_fields.append(db_column)

            await history_svc.append_history(
                relationship_id=relationship.id,
                user_id=relationship.user_id,
                field_name=db_column,
                old_value=old_value,
                new_value=new_value,
                trigger_source="step6",
                round_id=round_id,
            )
            history_count += 1

        # ── 2. Future 槽处理 ──
        future_status = "no_future"

        if future_action is not None and future_action.strip() == "无":
            # action 为「无」→ 清空 future 字段
            old_ts = str(relationship.future_timestamp) if relationship.future_timestamp is not None else None
            old_act = relationship.future_action

            relationship.future_timestamp = None
            relationship.future_action = None
            future_status = "cleared_by_action_none"

            # 记录清空历史
            if old_ts is not None:
                await history_svc.append_history(
                    relationship_id=relationship.id,
                    user_id=relationship.user_id,
                    field_name="future_timestamp",
                    old_value=old_ts,
                    new_value=None,
                    trigger_source="step6",
                    round_id=round_id,
                )
                history_count += 1
            if old_act is not None:
                await history_svc.append_history(
                    relationship_id=relationship.id,
                    user_id=relationship.user_id,
                    field_name="future_action",
                    old_value=old_act,
                    new_value=None,
                    trigger_source="step6",
                    round_id=round_id,
                )
                history_count += 1

        elif future_time_natural is not None and future_time_natural.strip() != "无":
            # 有 time_natural 需要解析
            parsed_ts = parse_future_time(future_time_natural)

            if parsed_ts is not None:
                # 解析成功 → 写入 future_timestamp + future_action
                old_ts = str(relationship.future_timestamp) if relationship.future_timestamp is not None else None
                old_act = relationship.future_action

                relationship.future_timestamp = parsed_ts
                relationship.future_action = future_action
                future_status = "written"

                await history_svc.append_history(
                    relationship_id=relationship.id,
                    user_id=relationship.user_id,
                    field_name="future_timestamp",
                    old_value=old_ts,
                    new_value=str(parsed_ts),
                    trigger_source="step6",
                    round_id=round_id,
                )
                history_count += 1
                await history_svc.append_history(
                    relationship_id=relationship.id,
                    user_id=relationship.user_id,
                    field_name="future_action",
                    old_value=old_act,
                    new_value=future_action,
                    trigger_source="step6",
                    round_id=round_id,
                )
                history_count += 1
            else:
                # 解析失败 → 清空 future 字段，保留 proactive_times
                old_ts = str(relationship.future_timestamp) if relationship.future_timestamp is not None else None
                old_act = relationship.future_action

                relationship.future_timestamp = None
                relationship.future_action = None
                future_status = "cleared_parse_failed"

                logger.warning(
                    "Step6 Future 槽解析失败, user_id=%d, time_natural=%s, "
                    "proactive_times 保留=%d",
                    relationship.user_id,
                    future_time_natural,
                    relationship.proactive_times,
                )

                if old_ts is not None:
                    await history_svc.append_history(
                        relationship_id=relationship.id,
                        user_id=relationship.user_id,
                        field_name="future_timestamp",
                        old_value=old_ts,
                        new_value=None,
                        trigger_source="step6",
                        round_id=round_id,
                    )
                    history_count += 1
                if old_act is not None:
                    await history_svc.append_history(
                        relationship_id=relationship.id,
                        user_id=relationship.user_id,
                        field_name="future_action",
                        old_value=old_act,
                        new_value=None,
                        trigger_source="step6",
                        round_id=round_id,
                    )
                    history_count += 1

        await self.db.flush()

        logger.info(
            "Step6 关系标量写回完成: user_id=%d, updated=%s, history=%d, future=%s",
            relationship.user_id, updated_fields, history_count, future_status,
        )

        return {
            "updated_fields": updated_fields,
            "history_count": history_count,
            "future_status": future_status,
        }
