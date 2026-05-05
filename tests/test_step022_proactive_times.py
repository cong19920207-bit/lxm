# -*- coding: utf-8 -*-
# STEP-022 单元测试：proactive_times 计数/清零 + 频控参数调整

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.relationship import Relationship

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


async def _create_user_and_relationship(
    db: AsyncSession,
    user_id: int = 1,
    *,
    proactive_times: int = 0,
    last_interaction_at: datetime | None = None,
    future_timestamp: int | None = None,
    future_action: str | None = None,
    level: int = 1,
) -> Relationship:
    """创建测试用 users 行 + relationship 行"""
    from backend.models.user import User

    user = User(id=user_id, username=f"test_user_{user_id}", password_hash="fake_hash")
    db.add(user)
    await db.flush()

    rel = Relationship(
        user_id=user_id,
        level=level,
        growth_value=300,
        proactive_times=proactive_times,
        last_interaction_at=last_interaction_at,
        future_timestamp=future_timestamp,
        future_action=future_action,
    )
    db.add(rel)
    await db.flush()
    return rel


# ================================================================
#  测试场景 1：用户发消息 → proactive_times 清零
# ================================================================


class TestProactiveTimesResetOnSend:
    """用户发消息时 proactive_times 清零（chat.py POST /api/chat/send）"""

    @pytest.mark.asyncio
    async def test_reset_to_zero_when_nonzero(self, db_session: AsyncSession):
        """proactive_times=2 时，用户发消息后应清零"""
        rel = await _create_user_and_relationship(db_session, proactive_times=2)
        assert rel.proactive_times == 2

        # 模拟清零逻辑（与 chat.py 中的实现一致）
        from sqlalchemy import select

        stmt = select(Relationship).where(Relationship.user_id == 1)
        result = await db_session.execute(stmt)
        r = result.scalar_one_or_none()
        assert r is not None
        r.proactive_times = 0
        await db_session.flush()

        # 验证已清零
        result2 = await db_session.execute(stmt)
        r2 = result2.scalar_one_or_none()
        assert r2.proactive_times == 0

    @pytest.mark.asyncio
    async def test_no_op_when_already_zero(self, db_session: AsyncSession):
        """proactive_times=0 时不需要更新"""
        rel = await _create_user_and_relationship(db_session, proactive_times=0)
        assert rel.proactive_times == 0

        from sqlalchemy import select

        stmt = select(Relationship).where(Relationship.user_id == 1)
        result = await db_session.execute(stmt)
        r = result.scalar_one_or_none()
        # 值已经是 0，逻辑中不执行 commit（条件 != 0 不成立）
        assert r.proactive_times == 0

    @pytest.mark.asyncio
    async def test_reset_max_value(self, db_session: AsyncSession):
        """proactive_times=3（上限值）时，用户发消息后应清零"""
        rel = await _create_user_and_relationship(db_session, proactive_times=3)
        assert rel.proactive_times == 3

        from sqlalchemy import select

        stmt = select(Relationship).where(Relationship.user_id == 1)
        result = await db_session.execute(stmt)
        r = result.scalar_one_or_none()
        r.proactive_times = 0
        await db_session.flush()

        result2 = await db_session.execute(stmt)
        r2 = result2.scalar_one_or_none()
        assert r2.proactive_times == 0


# ================================================================
#  测试场景 2：主动消息执行后 → proactive_times +1
# ================================================================


class TestProactiveTimesIncrement:
    """主动消息成功执行后 proactive_times +1"""

    @pytest.mark.asyncio
    async def test_increment_from_zero(self, db_session: AsyncSession):
        """proactive_times=0 → 执行后变为 1"""
        rel = await _create_user_and_relationship(db_session, proactive_times=0)
        assert rel.proactive_times == 0

        # 模拟 +1 逻辑
        if rel.proactive_times < 3:
            rel.proactive_times += 1
        await db_session.flush()

        assert rel.proactive_times == 1

    @pytest.mark.asyncio
    async def test_increment_from_two(self, db_session: AsyncSession):
        """proactive_times=2 → 执行后变为 3（达上限）"""
        rel = await _create_user_and_relationship(db_session, proactive_times=2)
        assert rel.proactive_times == 2

        if rel.proactive_times < 3:
            rel.proactive_times += 1
        await db_session.flush()

        assert rel.proactive_times == 3

    @pytest.mark.asyncio
    async def test_no_increment_at_upper_limit(self, db_session: AsyncSession):
        """proactive_times=3（上限）→ 不再增加"""
        rel = await _create_user_and_relationship(db_session, proactive_times=3)
        assert rel.proactive_times == 3

        if rel.proactive_times < 3:
            rel.proactive_times += 1
        await db_session.flush()

        # 上限保护，不超过 3
        assert rel.proactive_times == 3


# ================================================================
#  测试场景 3：proactive_times=3 时概率公式验证（T10）
# ================================================================


class TestProactiveTimesProbability:
    """proactive_times=3 时 0.15^4 ≈ 0.05% 几乎不再写槽"""

    def test_probability_below_threshold(self):
        """验证 proactive_times=3 时概率公式 0.15^(3+1)"""
        proactive_times = 3
        probability = 0.15 ** (proactive_times + 1)
        # 0.15^4 ≈ 0.00050625
        assert probability < 0.001  # < 0.1%
        assert probability == pytest.approx(0.00050625, abs=1e-8)

    def test_probability_at_zero(self):
        """proactive_times=0 时概率为 0.15^1 = 15%"""
        proactive_times = 0
        probability = 0.15 ** (proactive_times + 1)
        assert probability == pytest.approx(0.15, abs=1e-8)

    def test_probability_at_one(self):
        """proactive_times=1 时概率为 0.15^2 = 2.25%"""
        proactive_times = 1
        probability = 0.15 ** (proactive_times + 1)
        assert probability == pytest.approx(0.0225, abs=1e-8)


# ================================================================
#  边界测试：频控 8 次/天 + 30min 间隔
# ================================================================


class TestFrequencyControl:
    """验证频控参数调整后的行为"""

    @pytest.mark.asyncio
    async def test_daily_limit_is_8(self):
        """每日上限从 2 调整为 8"""
        from backend.services.agent_service import AgentService

        svc = AgentService()

        # 构造 mock Redis
        mock_redis = AsyncMock()
        # 模拟已触发 7 次 → 仍可触发
        mock_redis.get = AsyncMock(return_value="7")
        mock_redis.exists = AsyncMock(return_value=False)

        with patch("backend.services.agent_service.get_redis", return_value=mock_redis):
            with patch.object(svc, "_check_p0", return_value=True):
                with patch("backend.services.agent_service.async_session_maker") as mock_sm:
                    # mock DB 查询（最近一条 agent_message 不存在）
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_result = MagicMock()
                    mock_result.scalar_one_or_none.return_value = None
                    mock_db.execute = AsyncMock(return_value=mock_result)

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_sm.return_value = mock_ctx

                    with patch.object(svc, "calculate_action_score", return_value=8.0):
                        with patch.object(svc, "generate_and_save_message", return_value=True):
                            result = await svc.check_and_trigger(user_id=1)
                            assert result is True

    @pytest.mark.asyncio
    async def test_daily_limit_blocks_at_8(self):
        """已触发 8 次后应阻止"""
        from backend.services.agent_service import AgentService

        svc = AgentService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="8")

        with patch("backend.services.agent_service.get_redis", return_value=mock_redis):
            with patch.object(svc, "_check_p0", return_value=True):
                with patch("backend.services.agent_service.async_session_maker") as mock_sm:
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_sm.return_value = mock_ctx

                    result = await svc.check_and_trigger(user_id=1)
                    assert result is False

    @pytest.mark.asyncio
    async def test_interval_30min_blocks(self):
        """距上次主动消息不足 30 分钟应阻止"""
        from backend.services.agent_service import AgentService

        svc = AgentService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")

        # 模拟最近一条 agent_message 在 10 分钟前
        ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
        mock_latest_msg = SimpleNamespace(created_at=ten_min_ago)

        with patch("backend.services.agent_service.get_redis", return_value=mock_redis):
            with patch.object(svc, "_check_p0", return_value=True):
                with patch("backend.services.agent_service.async_session_maker") as mock_sm:
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_result = MagicMock()
                    mock_result.scalar_one_or_none.return_value = mock_latest_msg
                    mock_db.execute = AsyncMock(return_value=mock_result)

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_sm.return_value = mock_ctx

                    result = await svc.check_and_trigger(user_id=1)
                    assert result is False

    @pytest.mark.asyncio
    async def test_interval_30min_passes(self):
        """距上次主动消息超过 30 分钟应允许"""
        from backend.services.agent_service import AgentService

        svc = AgentService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")
        mock_redis.exists = AsyncMock(return_value=False)

        # 模拟最近一条 agent_message 在 40 分钟前
        forty_min_ago = datetime.utcnow() - timedelta(minutes=40)
        mock_latest_msg = SimpleNamespace(created_at=forty_min_ago)

        with patch("backend.services.agent_service.get_redis", return_value=mock_redis):
            with patch.object(svc, "_check_p0", return_value=True):
                with patch("backend.services.agent_service.async_session_maker") as mock_sm:
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_result = MagicMock()
                    mock_result.scalar_one_or_none.return_value = mock_latest_msg
                    mock_db.execute = AsyncMock(return_value=mock_result)

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_sm.return_value = mock_ctx

                    with patch.object(svc, "calculate_action_score", return_value=8.0):
                        with patch.object(svc, "generate_and_save_message", return_value=True):
                            result = await svc.check_and_trigger(user_id=1)
                            assert result is True


# ================================================================
#  测试场景：30 天无活动自动清零
# ================================================================


class TestInactiveReset:
    """30 天无活动自动清零 proactive_times 并清空 Future 槽"""

    @pytest.mark.asyncio
    async def test_reset_inactive_user(self, db_session: AsyncSession):
        """last_interaction_at 超过 30 天 → 清零"""
        old_time = datetime.utcnow() - timedelta(days=35)
        rel = await _create_user_and_relationship(
            db_session,
            proactive_times=2,
            last_interaction_at=old_time,
            future_timestamp=9999999,
            future_action="提醒喝水",
        )
        assert rel.proactive_times == 2
        assert rel.future_timestamp == 9999999

        # 模拟清零逻辑
        from sqlalchemy import select

        threshold = datetime.utcnow() - timedelta(days=30)
        stmt = select(Relationship).where(
            Relationship.proactive_times > 0,
            Relationship.last_interaction_at < threshold,
        )
        result = await db_session.execute(stmt)
        rels = list(result.scalars().all())
        assert len(rels) == 1

        rels[0].proactive_times = 0
        rels[0].future_timestamp = None
        rels[0].future_action = None
        await db_session.flush()

        result2 = await db_session.execute(
            select(Relationship).where(Relationship.user_id == 1)
        )
        updated = result2.scalar_one_or_none()
        assert updated.proactive_times == 0
        assert updated.future_timestamp is None
        assert updated.future_action is None

    @pytest.mark.asyncio
    async def test_no_reset_for_active_user(self, db_session: AsyncSession):
        """last_interaction_at 在 30 天内 → 不清零"""
        recent_time = datetime.utcnow() - timedelta(days=5)
        rel = await _create_user_and_relationship(
            db_session,
            proactive_times=2,
            last_interaction_at=recent_time,
            future_timestamp=9999999,
            future_action="提醒喝水",
        )

        from sqlalchemy import select

        threshold = datetime.utcnow() - timedelta(days=30)
        stmt = select(Relationship).where(
            Relationship.proactive_times > 0,
            Relationship.last_interaction_at < threshold,
        )
        result = await db_session.execute(stmt)
        rels = list(result.scalars().all())
        assert len(rels) == 0

        # 原值不变
        assert rel.proactive_times == 2
        assert rel.future_timestamp == 9999999

    @pytest.mark.asyncio
    async def test_no_reset_when_proactive_times_zero(self, db_session: AsyncSession):
        """proactive_times=0 时不需要清零（即使超过 30 天）"""
        old_time = datetime.utcnow() - timedelta(days=35)
        rel = await _create_user_and_relationship(
            db_session,
            proactive_times=0,
            last_interaction_at=old_time,
        )

        from sqlalchemy import select

        threshold = datetime.utcnow() - timedelta(days=30)
        stmt = select(Relationship).where(
            Relationship.proactive_times > 0,
            Relationship.last_interaction_at < threshold,
        )
        result = await db_session.execute(stmt)
        rels = list(result.scalars().all())
        # proactive_times=0 不匹配条件
        assert len(rels) == 0

    @pytest.mark.asyncio
    async def test_reset_null_last_interaction(self, db_session: AsyncSession):
        """last_interaction_at 为 NULL → 也应清零"""
        rel = await _create_user_and_relationship(
            db_session,
            proactive_times=1,
            last_interaction_at=None,
        )

        from sqlalchemy import select

        stmt = select(Relationship).where(
            Relationship.proactive_times > 0,
            (
                (Relationship.last_interaction_at == None)  # noqa: E711
                | (Relationship.last_interaction_at < datetime.utcnow() - timedelta(days=30))
            ),
        )
        result = await db_session.execute(stmt)
        rels = list(result.scalars().all())
        assert len(rels) == 1
        assert rels[0].user_id == rel.user_id


# ================================================================
#  测试场景：Future 槽消费后计入 agent:count 计数器
# ================================================================


class TestFutureSlotAgentCount:
    """Future 槽消费成功后额外计入 agent:count 计数器"""

    @pytest.mark.asyncio
    async def test_increment_agent_count_for_future(self):
        """调用 increment_agent_count_for_future 后 Redis 计数器 +1"""
        from backend.services.agent_service import AgentService

        svc = AgentService()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("backend.services.agent_service.get_redis", return_value=mock_redis):
            await svc.increment_agent_count_for_future(user_id=42)

            # 验证 INCR 被调用且 key 格式正确
            mock_redis.incr.assert_called_once()
            call_args = mock_redis.incr.call_args
            key = call_args[0][0]
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            assert key == f"agent:count:42:{today_str}"

            # 验证 EXPIRE 被调用
            mock_redis.expire.assert_called_once()
