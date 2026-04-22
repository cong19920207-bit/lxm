# -*- coding: utf-8 -*-
# AI 配置管理核心服务：所有配置模块的共用基础服务

import json
import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models.admin_config import AdminConfig
from backend.redis_client import get_redis
from backend.services.llm_service import llm_service
from backend.utils.admin_auth import log_operation

logger = logging.getLogger(__name__)

_CONFIG_CACHE_TTL = 3600
_MAX_HISTORY_VERSIONS = 20


class AdminConfigService:
    """配置管理核心服务，供人格、情绪、世界观等模块共用"""

    # ──────────────────── 读取 ────────────────────

    async def get_active_config(self, config_key: str, *, use_cache: bool = True) -> Any:
        """
        获取当前生效配置值。
        use_cache=True：优先 Redis → MySQL → 回写缓存（默认，供运行时读）。
        use_cache=False：仅查 MySQL，不读不写 Redis（供管理端需权威库读的场景）。
        config_value 可 JSON 解析则返回 dict/list 等，否则返回原始字符串。
        """
        if use_cache:
            redis = await get_redis()
            cache_key = f"active_config:{config_key}"

            cached = await redis.get(cache_key)
            if cached is not None:
                try:
                    return json.loads(cached)
                except (json.JSONDecodeError, TypeError):
                    return cached

        async with async_session_maker() as db:
            stmt = select(AdminConfig).where(
                AdminConfig.config_key == config_key,
                AdminConfig.is_active == True,   # noqa: E712
                AdminConfig.is_draft == False,    # noqa: E712
            )
            result = await db.execute(stmt)
            config = result.scalars().first()

        if config is None:
            return None

        if use_cache:
            redis = await get_redis()
            cache_key = f"active_config:{config_key}"
            await redis.setex(cache_key, _CONFIG_CACHE_TTL, config.config_value or "")

        try:
            return json.loads(config.config_value)
        except (json.JSONDecodeError, TypeError):
            return config.config_value

    async def get_active_config_detail(self, config_key: str) -> dict | None:
        """获取当前生效配置的完整信息（含版本号、操作人等元数据）"""
        async with async_session_maker() as db:
            stmt = select(AdminConfig).where(
                AdminConfig.config_key == config_key,
                AdminConfig.is_active == True,   # noqa: E712
                AdminConfig.is_draft == False,    # noqa: E712
            )
            result = await db.execute(stmt)
            config = result.scalars().first()

        if config is None:
            return None

        try:
            value = json.loads(config.config_value)
        except (json.JSONDecodeError, TypeError):
            value = config.config_value

        return {
            "version": config.version,
            "updated_by": config.updated_by,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            "content": value,
        }

    async def get_draft(self, config_key: str) -> dict | None:
        """
        获取草稿记录。
        无草稿返回 None；有草稿返回 {id, config_key, config_value, updated_by, updated_at}。
        """
        async with async_session_maker() as db:
            stmt = select(AdminConfig).where(
                AdminConfig.config_key == config_key,
                AdminConfig.is_draft == True,    # noqa: E712
            )
            result = await db.execute(stmt)
            draft = result.scalars().first()

        if draft is None:
            return None

        try:
            value = json.loads(draft.config_value)
        except (json.JSONDecodeError, TypeError):
            value = draft.config_value

        return {
            "id": draft.id,
            "config_key": draft.config_key,
            "config_value": value,
            "updated_by": draft.updated_by,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }

    # ──────────────────── 草稿 ────────────────────

    async def save_draft(
        self, db: AsyncSession, config_key: str,
        config_value: str, updated_by: str,
    ) -> dict:
        """
        保存草稿（不发布，不更新 Redis 缓存）。
        已有草稿则 UPDATE，无草稿则 INSERT。
        """
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == True,    # noqa: E712
        )
        result = await db.execute(stmt)
        draft = result.scalars().first()

        now = datetime.utcnow()
        if draft:
            draft.config_value = config_value
            draft.updated_by = updated_by
            draft.updated_at = now
        else:
            draft = AdminConfig(
                config_key=config_key,
                config_value=config_value,
                version=0,
                is_draft=True,
                is_active=False,
                updated_by=updated_by,
                updated_at=now,
            )
            db.add(draft)

        await db.flush()

        return {
            "id": draft.id,
            "config_key": draft.config_key,
            "updated_by": draft.updated_by,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }

    async def discard_draft(self, db: AsyncSession, config_key: str) -> bool:
        """删除草稿，返回是否成功删除"""
        stmt = delete(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == True,    # noqa: E712
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount > 0

    # ──────────────────── 发布 ────────────────────

    async def publish_config(
        self, db: AsyncSession, config_key: str,
        config_value: str, admin_user,
        before_value: str = None,
        request=None,
        target_description: str = None,
    ) -> dict:
        """
        发布配置标准流程（原子性执行）：
        旧版本置为非活跃 → 插入新活跃版本 → 删除草稿 →
        更新 Redis → 清理超限历史 → 写操作日志 → 设监控标记。
        """
        # a. 获取当前生效版本的 version 号
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_active == True,   # noqa: E712
            AdminConfig.is_draft == False,    # noqa: E712
        )
        result = await db.execute(stmt)
        current_active = result.scalars().first()
        current_version = current_active.version if current_active else 0

        # b. 当前生效版本设为非活跃
        if current_active:
            current_active.is_active = False

        # c. 插入新的活跃记录
        new_version = current_version + 1
        now = datetime.utcnow()
        new_config = AdminConfig(
            config_key=config_key,
            config_value=config_value,
            version=new_version,
            is_draft=False,
            is_active=True,
            updated_by=admin_user.username,
            updated_at=now,
        )
        db.add(new_config)

        # d. 删除草稿记录（若存在）
        draft_stmt = delete(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == True,    # noqa: E712
        )
        await db.execute(draft_stmt)

        await db.flush()

        # e. 更新 Redis 缓存
        redis = await get_redis()
        cache_key = f"active_config:{config_key}"
        await redis.setex(cache_key, _CONFIG_CACHE_TTL, config_value)

        # f. 保留最近 20 个版本，超出则删除最早的历史版本
        count_stmt = select(func.count(AdminConfig.id)).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == False,   # noqa: E712
        )
        count_result = await db.execute(count_stmt)
        total_versions = count_result.scalar() or 0

        if total_versions > _MAX_HISTORY_VERSIONS:
            excess = total_versions - _MAX_HISTORY_VERSIONS
            oldest_stmt = (
                select(AdminConfig.id)
                .where(
                    AdminConfig.config_key == config_key,
                    AdminConfig.is_draft == False,   # noqa: E712
                    AdminConfig.is_active == False,  # noqa: E712
                )
                .order_by(AdminConfig.version.asc())
                .limit(excess)
            )
            oldest_result = await db.execute(oldest_stmt)
            oldest_ids = [row[0] for row in oldest_result.fetchall()]
            if oldest_ids:
                del_stmt = delete(AdminConfig).where(AdminConfig.id.in_(oldest_ids))
                await db.execute(del_stmt)
                await db.flush()

        # g. 写入操作日志
        desc = target_description or f"发布配置 {config_key} V{new_version}"
        await log_operation(
            db=db,
            admin_user=admin_user,
            module="ai_config",
            action="publish",
            target_description=desc,
            before_value=before_value,
            after_value=config_value[:500] if config_value else None,
            request=request,
        )

        # h. 设置发布监控标记（5 分钟过期）
        monitor_key = f"publish_monitor:{config_key}"
        await redis.setex(monitor_key, 300, str(int(time.time())))

        return {
            "version": new_version,
            "published_at": now.isoformat(),
        }

    # ──────────────────── 版本历史与回滚 ────────────────────

    async def get_version_history(
        self, db: AsyncSession, config_key: str,
        page: int = 1, page_size: int = 20,
    ) -> dict:
        """查询历史版本列表，config_value 仅返回前 100 字符摘要"""
        count_stmt = select(func.count(AdminConfig.id)).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_draft == False,   # noqa: E712
        )
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query_stmt = (
            select(AdminConfig)
            .where(
                AdminConfig.config_key == config_key,
                AdminConfig.is_draft == False,   # noqa: E712
            )
            .order_by(AdminConfig.version.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(query_stmt)
        configs = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "list": [
                {
                    "version": c.version,
                    "is_active": c.is_active,
                    "updated_by": c.updated_by,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "summary": (
                        (c.config_value[:100] + "...")
                        if c.config_value and len(c.config_value) > 100
                        else c.config_value
                    ),
                }
                for c in configs
            ],
        }

    async def rollback_config(
        self, db: AsyncSession, config_key: str,
        version: int, admin_user, request=None,
    ) -> dict:
        """回滚到指定版本：读取目标版本内容后调用 publish_config 发布"""
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.version == version,
            AdminConfig.is_draft == False,   # noqa: E712
        )
        result = await db.execute(stmt)
        target = result.scalars().first()

        if target is None:
            raise ValueError(f"版本 V{version} 不存在")

        # 获取当前生效版本内容作为 before_value
        active = await self._get_active_record(db, config_key)
        before_value = active.config_value if active else None

        return await self.publish_config(
            db=db,
            config_key=config_key,
            config_value=target.config_value,
            admin_user=admin_user,
            before_value=before_value,
            request=request,
            target_description=f"回滚自版本V{version} 配置 {config_key}",
        )

    # ──────────────────── 发布前测试 ────────────────────

    async def run_standard_tests(
        self, db: AsyncSession, config_key: str,
        draft_content: str,
    ) -> dict:
        """
        发布前强制测试（三道卡点之一）。
        从 admin_config 读取测试用例，逐条调用 LLM 并进行三维评分。
        """
        test_cases_key = f"test_cases:{config_key}"
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == test_cases_key,
            AdminConfig.is_active == True,   # noqa: E712
            AdminConfig.is_draft == False,    # noqa: E712
        )
        result = await db.execute(stmt)
        test_config = result.scalars().first()

        if not test_config or not test_config.config_value:
            return {
                "total": 0, "passed": 0, "failed": 0,
                "pass_rate": 100, "can_publish": True,
                "details": [],
                "message": "无测试用例，跳过测试",
            }

        try:
            test_cases = json.loads(test_config.config_value)
        except (json.JSONDecodeError, TypeError):
            return {
                "total": 0, "passed": 0, "failed": 0,
                "pass_rate": 100, "can_publish": True,
                "details": [],
                "message": "测试用例格式错误",
            }

        if not isinstance(test_cases, list) or len(test_cases) == 0:
            return {
                "total": 0, "passed": 0, "failed": 0,
                "pass_rate": 100, "can_publish": True,
                "details": [],
                "message": "无测试用例",
            }

        # 从 Redis 读取违规关键词
        redis = await get_redis()
        style_keywords = await self._get_keywords(redis, "style_violation_keywords")
        boundary_keywords = await self._get_keywords(redis, "persona_boundary_keywords")

        details = []
        passed_count = 0
        can_publish = True

        for idx, case in enumerate(test_cases):
            case_id = case.get("id", idx + 1)
            user_input = case.get("input", "")
            emotion_label = case.get("emotion_label", "平静")
            relationship_level = case.get("relationship_level", 1)

            prompt = self._build_test_prompt(
                draft_content, user_input, emotion_label, relationship_level,
            )

            try:
                llm_result = await llm_service.chat_with_parse(prompt)
                ai_reply = llm_result.get("reply", "")
            except Exception as e:
                logger.error("测试用例 %d LLM 调用失败: %s", case_id, str(e))
                ai_reply = ""

            style_score, style_violations = self._score_style(ai_reply, style_keywords)
            boundary_score, boundary_violations = self._score_boundary(ai_reply, boundary_keywords)
            emotion_score = self._score_emotion(ai_reply, emotion_label)

            total_score = round(style_score * 0.4 + boundary_score * 0.4 + emotion_score * 0.2)

            if total_score >= 80:
                level = "高"
            elif total_score >= 60:
                level = "中"
            else:
                level = "低"

            all_violations = style_violations + boundary_violations
            case_passed = total_score >= 60 and len(boundary_violations) == 0
            if case_passed:
                passed_count += 1
            else:
                can_publish = False

            details.append({
                "case_id": case_id,
                "input": user_input,
                "ai_reply": ai_reply,
                "total_score": total_score,
                "level": level,
                "style_score": style_score,
                "boundary_score": boundary_score,
                "emotion_score": emotion_score,
                "violations": all_violations,
                "passed": case_passed,
            })

        total = len(details)
        failed = total - passed_count
        pass_rate = round(passed_count / total * 100) if total > 0 else 100

        return {
            "total": total,
            "passed": passed_count,
            "failed": failed,
            "pass_rate": pass_rate,
            "can_publish": can_publish,
            "details": details,
        }

    # ──────────────────── 内部辅助方法 ────────────────────

    async def _get_active_record(
        self, db: AsyncSession, config_key: str,
    ) -> AdminConfig | None:
        """获取当前活跃记录"""
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == config_key,
            AdminConfig.is_active == True,   # noqa: E712
            AdminConfig.is_draft == False,    # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def _get_keywords(self, redis, keywords_key: str) -> list:
        """从 Redis（或回退 MySQL）读取关键词列表"""
        cache_key = f"active_config:{keywords_key}"
        raw = await redis.get(cache_key)
        if raw:
            try:
                keywords = json.loads(raw)
                if isinstance(keywords, list):
                    return keywords
            except (json.JSONDecodeError, TypeError):
                pass

        async with async_session_maker() as db:
            stmt = select(AdminConfig).where(
                AdminConfig.config_key == keywords_key,
                AdminConfig.is_active == True,   # noqa: E712
                AdminConfig.is_draft == False,    # noqa: E712
            )
            result = await db.execute(stmt)
            config = result.scalars().first()

        if config and config.config_value:
            try:
                keywords = json.loads(config.config_value)
                if isinstance(keywords, list):
                    await redis.setex(cache_key, _CONFIG_CACHE_TTL, config.config_value)
                    return keywords
            except (json.JSONDecodeError, TypeError):
                pass

        return []

    def _build_test_prompt(
        self, persona_content: str, user_input: str,
        emotion_label: str, relationship_level: int,
    ) -> str:
        """构建测试用临时 Prompt"""
        level_names = {0: "陌生", 1: "朋友", 2: "亲密", 3: "知己"}
        level_name = level_names.get(relationship_level, "朋友")

        return (
            "【系统指令】\n"
            "你是林小梦。请严格按照以下人格设定回复用户。\n"
            "回复要求：1-3个短句，禁止列表和Markdown格式，语气温暖自然。\n"
            "永远不承认自己是AI/程序/模型。\n"
            '请用JSON格式输出：{"emotion":{"label":"情绪标签","confidence":0.9},"reply":"回复内容"}\n\n'
            "【人格设定】\n"
            f"{persona_content}\n\n"
            "【情绪状态】\n"
            f"用户当前情绪：{emotion_label}\n\n"
            "【关系状态】\n"
            f"当前关系等级：{relationship_level}级（{level_name}）\n\n"
            "【用户输入】\n"
            f"{user_input}"
        )

    def _score_style(self, reply: str, keywords: list) -> tuple[int, list]:
        """语言风格符合度评分：命中0个=100，1个=80，2个及以上=50"""
        violations = [kw for kw in keywords if kw in reply]
        hit_count = len(violations)
        if hit_count == 0:
            score = 100
        elif hit_count == 1:
            score = 80
        else:
            score = 50
        return score, [f"风格违规词：{v}" for v in violations]

    def _score_boundary(self, reply: str, keywords: list) -> tuple[int, list]:
        """角色边界符合度评分：命中0个=100，1个=50，2个及以上=0"""
        violations = [kw for kw in keywords if kw in reply]
        hit_count = len(violations)
        if hit_count == 0:
            score = 100
        elif hit_count == 1:
            score = 50
        else:
            score = 0
        return score, [f"边界违规词：{v}" for v in violations]

    def _score_emotion(self, reply: str, emotion_label: str) -> int:
        """情绪指令匹配度评分：匹配=100，不匹配=0，平静默认通过"""
        emotion_words = {
            "开心": ["快乐", "开心", "高兴", "嘻嘻", "哈哈"],
            "悲伤": ["难过", "心疼", "担心", "抱抱", "不哭"],
            "焦虑": ["担心", "没事", "放心", "别怕", "会好"],
            "愤怒": ["担心", "理解", "委屈", "心疼"],
            "孤独": ["陪", "在", "一起", "想你", "身边"],
            "疲惫": ["担心", "休息", "辛苦", "心疼", "累"],
            "平静": [],
        }

        target_words = emotion_words.get(emotion_label, [])
        if not target_words:
            return 100

        for word in target_words:
            if word in reply:
                return 100
        return 0


# 全局单例
admin_config_service = AdminConfigService()
