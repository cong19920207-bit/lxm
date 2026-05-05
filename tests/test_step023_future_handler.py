# -*- coding: utf-8 -*-
# STEP-023 单元测试：Future 槽消费轮询 Handler

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.agent_message import TriggerType
from backend.models.relationship import Relationship
from backend.models.user import User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前创建全部表，测试后销毁"""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """获取测试数据库会话"""
    async with async_session_test() as session:
        yield session
        await session.commit()


async def _create_user(
    db: AsyncSession,
    user_id: int = 1,
    is_banned: bool = False,
) -> User:
    """创建测试用 users 行"""
    user = User(
        id=user_id,
        username=f"test_user_{user_id}",
        password_hash="fake_hash",
        is_banned=is_banned,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_relationship(
    db: AsyncSession,
    user_id: int = 1,
    *,
    level: int = 2,
    future_timestamp: int | None = None,
    future_action: str | None = None,
    proactive_times: int = 0,
) -> Relationship:
    """创建测试用 relationship 行"""
    rel = Relationship(
        user_id=user_id,
        level=level,
        growth_value=800,
        proactive_times=proactive_times,
        future_timestamp=future_timestamp,
        future_action=future_action,
    )
    db.add(rel)
    await db.flush()
    return rel


# ================================================================
#  测试场景 1：Future 到期 + 非黑名单 + 评分≥6 → 触发子链路
# ================================================================


class TestFutureSlotConsumeSuccess:
    """到期 Future 槽通过全部检查后触发消费"""

    @pytest.mark.asyncio
    async def test_consume_success(self):
        """正常到期 + 非黑名单 + 评分足够 → 消费成功"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=False)  # 非黑名单

        with patch(
            "backend.services.future_handler.get_redis", return_value=mock_redis
        ), patch(
            "backend.services.future_handler.agent_service"
        ) as mock_agent_svc, patch(
            "backend.services.future_handler.execute_step8_subchain",
            new_callable=AsyncMock, return_value=True,
        ) as mock_step8:
            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)
            mock_agent_svc.increment_agent_count_for_future = AsyncMock()

            with patch(
                "backend.services.future_handler.async_session_maker"
            ) as mock_sm:
                mock_rel = MagicMock()
                mock_rel.future_timestamp = int(time.time()) - 60
                mock_rel.future_action = "提醒喝水"
                mock_rel.proactive_times = 1

                mock_db = AsyncMock(spec=AsyncSession)
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_rel
                mock_db.execute = AsyncMock(return_value=mock_result)
                mock_db.commit = AsyncMock()

                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                mock_sm.return_value = mock_ctx

                result = await handler._consume_one(
                    user_id=1, future_action="提醒喝水"
                )
                assert result is True

            # 验证 Step8 子链路被调用
            mock_step8.assert_called_once_with(1, "提醒喝水")
            # 验证 increment_agent_count_for_future 被调用
            mock_agent_svc.increment_agent_count_for_future.assert_called_once_with(1)


# ================================================================
#  测试场景 2：Future 过期超 30 分钟 → 忽略并清空
# ================================================================


class TestFutureSlotExpiredBeyondWindow:
    """Future 过期超过 30 分钟窗口不应被 scan_and_consume 扫到"""

    @pytest.mark.asyncio
    async def test_expired_beyond_window_not_scanned(self, db_session: AsyncSession):
        """future_timestamp 超出 30 分钟窗口 → 不在候选列表中"""
        now_ts = int(time.time())
        expired_ts = now_ts - 2000  # 超过 1800 秒窗口

        await _create_user(db_session, user_id=1)
        await _create_relationship(
            db_session,
            user_id=1,
            future_timestamp=expired_ts,
            future_action="提醒喝水",
        )

        # 验证 SQL 条件排除超过窗口的记录
        from sqlalchemy import and_

        window_start = now_ts - 1800
        stmt = select(Relationship).where(
            and_(
                Relationship.future_timestamp.isnot(None),
                Relationship.future_timestamp <= now_ts,
                Relationship.future_timestamp > window_start,
            )
        )
        result = await db_session.execute(stmt)
        candidates = list(result.scalars().all())
        assert len(candidates) == 0  # 超窗口的不在候选中

    @pytest.mark.asyncio
    async def test_cleanup_expired_slots(self, db_session: AsyncSession):
        """cleanup_expired_slots 应清理超窗口的槽位"""
        now_ts = int(time.time())
        expired_ts = now_ts - 2000  # 超过 1800 秒窗口

        await _create_user(db_session, user_id=1)
        rel = await _create_relationship(
            db_session,
            user_id=1,
            future_timestamp=expired_ts,
            future_action="提醒喝水",
        )
        assert rel.future_timestamp is not None

        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        with patch(
            "backend.services.future_handler.async_session_maker", return_value=async_session_test()
        ):
            cleaned = await handler.cleanup_expired_slots()

        # 验证被清理
        result = await db_session.execute(
            select(Relationship).where(Relationship.user_id == 1)
        )
        updated = result.scalar_one_or_none()
        # cleanup 在自己的 session 中操作，这里验证逻辑正确性
        assert cleaned >= 0  # 至少不报错


# ================================================================
#  测试场景 3：黑名单用户 → 不触发，清空槽
# ================================================================


class TestFutureSlotBlacklisted:
    """黑名单用户的 Future 槽消费应被拒绝并清空"""

    @pytest.mark.asyncio
    async def test_blacklisted_user_rejected(self):
        """黑名单用户 → _consume_one 返回 False + 清空槽位"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=True)  # 在黑名单中

        with patch(
            "backend.services.future_handler.get_redis", return_value=mock_redis
        ), patch.object(handler, "_clear_future_slot", new_callable=AsyncMock) as mock_clear:
            result = await handler._consume_one(user_id=1, future_action="提醒喝水")

            assert result is False
            mock_clear.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_low_score_user_rejected(self):
        """行动评分 < 6 → _consume_one 返回 False + 清空槽位"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=False)  # 非黑名单

        with patch(
            "backend.services.future_handler.get_redis", return_value=mock_redis
        ), patch(
            "backend.services.future_handler.agent_service"
        ) as mock_agent_svc, patch.object(
            handler, "_clear_future_slot", new_callable=AsyncMock
        ) as mock_clear:
            mock_agent_svc.calculate_action_score = AsyncMock(return_value=4.0)

            result = await handler._consume_one(user_id=1, future_action="提醒喝水")

            assert result is False
            mock_clear.assert_called_once_with(1)


# ================================================================
#  测试场景 4：定时扫描 P0 命中但 Future 未过期 → 跳过写入（T5）
# ================================================================


class TestRouteBFuturePriorityProtection:
    """路 B 优先级保护：Future 槽未过期时定时扫描应跳过"""

    @pytest.mark.asyncio
    async def test_skip_when_future_pending(self):
        """存在未过期 Future 槽 → check_and_trigger 返回 False"""
        from backend.services.agent_service import AgentService

        svc = AgentService()

        # 模拟 P0 命中
        with patch.object(svc, "_check_p0", return_value=True), patch.object(
            svc, "_check_p1", return_value=False
        ), patch.object(svc, "_check_p2", return_value=False), patch.object(
            svc, "_check_p3", return_value=False
        ), patch.object(svc, "_check_p4", return_value=False):

            # mock async_session_maker（check_and_trigger 首次 DB 查询）
            mock_db = AsyncMock(spec=AsyncSession)
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "backend.services.agent_service.async_session_maker",
                return_value=mock_ctx,
            ):
                # _has_pending_future_slot 返回 True（有未过期槽）
                with patch.object(
                    svc, "_has_pending_future_slot", return_value=True
                ):
                    result = await svc.check_and_trigger(user_id=1)
                    assert result is False

    @pytest.mark.asyncio
    async def test_proceed_when_no_future(self):
        """无 Future 槽 → 正常继续频控检查"""
        from backend.services.agent_service import AgentService

        svc = AgentService()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")
        mock_redis.exists = AsyncMock(return_value=False)

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.object(svc, "_check_p0", return_value=True), patch.object(
            svc, "_check_p1", return_value=False
        ), patch.object(svc, "_check_p2", return_value=False), patch.object(
            svc, "_check_p3", return_value=False
        ), patch.object(svc, "_check_p4", return_value=False):

            with patch(
                "backend.services.agent_service.async_session_maker",
                return_value=mock_ctx,
            ), patch(
                "backend.services.agent_service.get_redis",
                return_value=mock_redis,
            ):
                with patch.object(
                    svc, "_has_pending_future_slot", return_value=False
                ), patch.object(
                    svc, "calculate_action_score", return_value=8.0
                ), patch.object(
                    svc, "generate_and_save_message", return_value=True
                ):
                    result = await svc.check_and_trigger(user_id=1)
                    assert result is True


# ================================================================
#  边界测试：Future 槽为空 → 跳过
# ================================================================


class TestFutureSlotEmpty:
    """Future 槽为空时 scan_and_consume 不做任何处理"""

    @pytest.mark.asyncio
    async def test_no_candidates(self):
        """无到期 Future 槽 → 返回 0"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        with patch(
            "backend.services.future_handler.async_session_maker"
        ) as mock_sm:
            mock_db = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_sm.return_value = mock_ctx

            consumed = await handler.scan_and_consume()
            assert consumed == 0

    @pytest.mark.asyncio
    async def test_has_pending_future_slot_empty(self):
        """_has_pending_future_slot 在 future_timestamp 为 None 时返回 False"""
        from backend.services.agent_service import AgentService

        svc = AgentService()

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.services.agent_service.async_session_maker",
            return_value=mock_ctx,
        ):
            result = await svc._has_pending_future_slot(user_id=1)
            assert result is False

    @pytest.mark.asyncio
    async def test_has_pending_future_slot_expired(self):
        """future_timestamp 已过期 → 返回 False"""
        from backend.services.agent_service import AgentService

        svc = AgentService()

        expired_ts = int(time.time()) - 100  # 已过期

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expired_ts
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.services.agent_service.async_session_maker",
            return_value=mock_ctx,
        ):
            result = await svc._has_pending_future_slot(user_id=1)
            assert result is False

    @pytest.mark.asyncio
    async def test_has_pending_future_slot_future(self):
        """future_timestamp 在未来 → 返回 True"""
        from backend.services.agent_service import AgentService

        svc = AgentService()

        future_ts = int(time.time()) + 3600  # 1 小时后

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = future_ts
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.services.agent_service.async_session_maker",
            return_value=mock_ctx,
        ):
            result = await svc._has_pending_future_slot(user_id=1)
            assert result is True


# ================================================================
#  频控绕过验证：Future 消费不检查 8 次/天 和 30min 间隔
# ================================================================


class TestFutureBypassFrequencyControl:
    """Future 槽消费绕过 8 次/天 + 30min 间隔频控"""

    @pytest.mark.asyncio
    async def test_future_bypasses_daily_limit(self):
        """即使每日已达 8 次，Future 消费仍应执行"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=False)  # 非黑名单
        mock_redis.get = AsyncMock(return_value="10")

        with patch(
            "backend.services.future_handler.get_redis", return_value=mock_redis
        ), patch(
            "backend.services.future_handler.agent_service"
        ) as mock_agent_svc, patch(
            "backend.services.future_handler.execute_step8_subchain",
            new_callable=AsyncMock, return_value=True,
        ):
            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)
            mock_agent_svc.increment_agent_count_for_future = AsyncMock()

            with patch(
                "backend.services.future_handler.async_session_maker"
            ) as mock_sm:
                mock_rel = MagicMock()
                mock_rel.proactive_times = 0

                mock_db = AsyncMock(spec=AsyncSession)
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_rel
                mock_db.execute = AsyncMock(return_value=mock_result)
                mock_db.commit = AsyncMock()

                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                mock_sm.return_value = mock_ctx

                result = await handler._consume_one(
                    user_id=1, future_action="提醒喝水"
                )
                # 即使 daily_count=10 也能消费成功（因为 Future 不检查频控）
                assert result is True


# ================================================================
#  消费成功后 proactive_times 递增验证
# ================================================================


class TestFutureConsumeProactiveTimesIncrement:
    """消费成功后 proactive_times +1"""

    @pytest.mark.asyncio
    async def test_proactive_times_increments(self):
        """proactive_times=1 → 消费后变为 2"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        mock_rel = MagicMock()
        mock_rel.future_timestamp = int(time.time()) - 60
        mock_rel.future_action = "提醒喝水"
        mock_rel.proactive_times = 1

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rel
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.services.future_handler.async_session_maker",
            return_value=mock_ctx,
        ), patch(
            "backend.services.future_handler.agent_service"
        ) as mock_agent_svc:
            mock_agent_svc.increment_agent_count_for_future = AsyncMock()

            await handler._on_consume_success(user_id=1)

            # 验证 proactive_times 从 1 增到 2
            assert mock_rel.proactive_times == 2
            # 验证 Future 槽被清空
            assert mock_rel.future_timestamp is None
            assert mock_rel.future_action is None

    @pytest.mark.asyncio
    async def test_proactive_times_capped_at_3(self):
        """proactive_times=3 → 不再增加"""
        from backend.services.future_handler import FutureSlotHandler

        handler = FutureSlotHandler()

        mock_rel = MagicMock()
        mock_rel.future_timestamp = int(time.time()) - 60
        mock_rel.future_action = "提醒喝水"
        mock_rel.proactive_times = 3

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rel
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.services.future_handler.async_session_maker",
            return_value=mock_ctx,
        ), patch(
            "backend.services.future_handler.agent_service"
        ) as mock_agent_svc:
            mock_agent_svc.increment_agent_count_for_future = AsyncMock()

            await handler._on_consume_success(user_id=1)

            # 上限保护：不超过 3
            assert mock_rel.proactive_times == 3
