# -*- coding: utf-8 -*-
# STEP-024 单元测试：Step8 子链路（Future 槽到期触发主动消息）

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.conversation_log import ConversationLog
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


def _mock_step5_output(
    *,
    future_time_natural: str = "无",
    future_action: str = "无",
):
    """构建 Step5Output mock"""
    mock = MagicMock()
    mock.inner_monologue = "测试内心独白"
    msg1 = MagicMock()
    msg1.content = "嘿，上次说好的事情还记得吗"
    msg1.type = "text"
    msg1.model_dump.return_value = {"type": "text", "content": msg1.content}
    msg2 = MagicMock()
    msg2.content = "想跟你聊聊呢"
    msg2.type = "text"
    msg2.model_dump.return_value = {"type": "text", "content": msg2.content}
    mock.messages = [msg1, msg2]
    mock.emotion = MagicMock()
    mock.emotion.label = "开心"
    mock.emotion.confidence = 0.85
    mock.relation_change = MagicMock()
    mock.relation_change.delta = 1
    mock.future = MagicMock()
    mock.future.time_natural = future_time_natural
    mock.future.action = future_action
    mock.knowledge_expand = "否"
    mock.model_dump.return_value = {
        "inner_monologue": mock.inner_monologue,
        "messages": [m.model_dump() for m in mock.messages],
        "emotion": {"label": "开心", "confidence": 0.85},
        "relation_change": {"delta": 1},
        "future": {"time_natural": future_time_natural, "action": future_action},
        "knowledge_expand": "否",
    }
    return mock


def _mock_retrieval_result():
    """构建 MultiVectorRetrievalResult mock"""
    mock = MagicMock()
    mock.user_memory_results = [{"content": "用户喜欢看电影", "score": 0.85}]
    mock.format_for_prompt.return_value = {
        "character_global": [],
        "character_private": [],
        "character_knowledge": [],
        "user": [{"content": "用户喜欢看电影", "score": 0.85}],
    }
    return mock


def _mock_query_rewrite_result():
    """构建 QueryRewriteResult mock"""
    mock = MagicMock()
    mock.success = True
    mock.output = MagicMock()
    mock.output.CharacterGlobalQueryQuestion = "角色设定查询"
    mock.output.CharacterKnowledgeQueryQuestion = "知识查询"
    mock.output.UserProfileQueryQuestion = "用户查询"
    mock.fallback_embedding = []
    return mock


# 通用 mock 补丁列表
COMMON_PATCHES = {
    "async_session_maker": "backend.services.step8_subchain.async_session_maker",
    "get_redis": "backend.services.step8_subchain.get_redis",
    "execute_query_rewrite": "backend.services.step8_subchain.execute_query_rewrite",
    "execute_multi_vector_retrieval": "backend.services.step8_subchain.execute_multi_vector_retrieval",
    "chat_with_step5_parse": "backend.services.step8_subchain.llm_service.chat_with_step5_parse",
    "execute_step5_5": "backend.services.step8_subchain.execute_step5_5",
    "execute_step6": "backend.services.step8_subchain.execute_step6",
    "check_content": "backend.services.step8_subchain.check_content",
    "allocate_sort_seq": "backend.services.step8_subchain.allocate_sort_seq",
    "get_activity_description": "backend.services.step8_subchain.get_activity_description",
    "read_for_prompt": "backend.services.step8_subchain.user_short_term_emotion_service.read_for_prompt",
}


class TestStep8SubchainComplete:
    """测试场景1：Future 到期 → 子链路完整执行，agent_message 写入"""

    @pytest.mark.asyncio
    async def test_full_subchain_success(self, db_session):
        """完整子链路执行成功，agent_message 写入正确"""
        await _create_user(db_session, user_id=1)
        await _create_relationship(
            db_session, user_id=1, proactive_times=0,
            future_timestamp=int(time.time()) - 60,
            future_action="提醒用户看电影",
        )
        await db_session.commit()

        step5_output = _mock_step5_output()
        retrieval_result = _mock_retrieval_result()
        query_rewrite_result = _mock_query_rewrite_result()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(COMMON_PATCHES["async_session_maker"], return_value=async_session_test()), \
             patch(COMMON_PATCHES["get_redis"], return_value=mock_redis), \
             patch(COMMON_PATCHES["execute_query_rewrite"], return_value=query_rewrite_result), \
             patch(COMMON_PATCHES["execute_multi_vector_retrieval"], return_value=retrieval_result), \
             patch(COMMON_PATCHES["chat_with_step5_parse"], return_value=step5_output), \
             patch(COMMON_PATCHES["execute_step5_5"], return_value=None), \
             patch(COMMON_PATCHES["execute_step6"], return_value=None), \
             patch(COMMON_PATCHES["check_content"], return_value={"is_safe": True, "reason": ""}), \
             patch(COMMON_PATCHES["allocate_sort_seq"], return_value=[100001]), \
             patch(COMMON_PATCHES["get_activity_description"], return_value=""), \
             patch(COMMON_PATCHES["read_for_prompt"], return_value=None), \
             patch("backend.services.step8_subchain.agent_service") as mock_agent_svc:

            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)

            from backend.services.step8_subchain import execute_step8_subchain
            result = await execute_step8_subchain(user_id=1, future_action="提醒用户看电影")

        assert result is True

        # 验证 agent_message 已写入
        async with async_session_test() as check_db:
            stmt = select(AgentMessage).where(AgentMessage.user_id == 1)
            res = await check_db.execute(stmt)
            agent_msgs = list(res.scalars().all())
            assert len(agent_msgs) == 1
            assert agent_msgs[0].trigger_type == TriggerType.FUTURE
            assert "嘿" in agent_msgs[0].content or "想" in agent_msgs[0].content


class TestStep8Step15Fallback:
    """测试场景2：Step1.5 失败 → 降级用 future.action Embedding（T9）"""

    @pytest.mark.asyncio
    async def test_step15_failure_fallback(self, db_session):
        """Step1.5 失败时降级用 future.action Embedding，子链路仍成功"""
        await _create_user(db_session, user_id=2)
        await _create_relationship(
            db_session, user_id=2, proactive_times=0,
            future_timestamp=int(time.time()) - 60,
            future_action="约好一起听歌",
        )
        await db_session.commit()

        # Step1.5 返回降级结果
        fallback_qr = MagicMock()
        fallback_qr.success = False
        fallback_qr.output = None
        fallback_qr.fallback_embedding = [0.1] * 1024

        step5_output = _mock_step5_output()
        retrieval_result = _mock_retrieval_result()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(COMMON_PATCHES["async_session_maker"], return_value=async_session_test()), \
             patch(COMMON_PATCHES["get_redis"], return_value=mock_redis), \
             patch(COMMON_PATCHES["execute_query_rewrite"], return_value=fallback_qr) as mock_qr, \
             patch(COMMON_PATCHES["execute_multi_vector_retrieval"], return_value=retrieval_result), \
             patch(COMMON_PATCHES["chat_with_step5_parse"], return_value=step5_output), \
             patch(COMMON_PATCHES["execute_step5_5"], return_value=None), \
             patch(COMMON_PATCHES["execute_step6"], return_value=None), \
             patch(COMMON_PATCHES["check_content"], return_value={"is_safe": True, "reason": ""}), \
             patch(COMMON_PATCHES["allocate_sort_seq"], return_value=[100002]), \
             patch(COMMON_PATCHES["get_activity_description"], return_value=""), \
             patch(COMMON_PATCHES["read_for_prompt"], return_value=None), \
             patch("backend.services.step8_subchain.agent_service") as mock_agent_svc:

            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)

            from backend.services.step8_subchain import execute_step8_subchain
            result = await execute_step8_subchain(user_id=2, future_action="约好一起听歌")

        assert result is True

        # 验证 execute_query_rewrite 使用 future_action 作为 last_user_text
        call_kwargs = mock_qr.call_args
        assert call_kwargs.kwargs["last_user_text"] == "约好一起听歌"
        assert call_kwargs.kwargs["source"] == "step8"


class TestStep8DecayGating:
    """测试场景3：proactive_times=3 → 写下一轮概率 ≈ 0.05%（T10）"""

    @pytest.mark.asyncio
    async def test_decay_probability_at_pt3(self, db_session):
        """proactive_times=3 时衰减门控概率为 0.15^4 ≈ 0.00050625"""
        await _create_user(db_session, user_id=3)
        await _create_relationship(
            db_session, user_id=3, proactive_times=3,
            future_timestamp=int(time.time()) - 60,
            future_action="提醒复习",
        )
        await db_session.commit()

        from backend.services.step8_subchain import DECAY_BASE
        # pt=3，+1 后 pt 仍=3（上限），概率 = 0.15^(3+1) = 0.15^4
        prob = DECAY_BASE ** (3 + 1)
        assert abs(prob - 0.00050625) < 1e-8

    @pytest.mark.asyncio
    async def test_decay_gate_writes_future_when_hit(self, db_session):
        """衰减门控命中时正确写入 Future 槽"""
        await _create_user(db_session, user_id=4)
        await _create_relationship(
            db_session, user_id=4, proactive_times=0,
            future_timestamp=int(time.time()) - 60,
            future_action="提醒喝水",
        )
        await db_session.commit()

        # 构造 step5_result 带 future 输出
        step5_output = _mock_step5_output(
            future_time_natural="3小时后",
            future_action="提醒休息一下",
        )
        retrieval_result = _mock_retrieval_result()
        query_rewrite_result = _mock_query_rewrite_result()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        future_ts = int(time.time()) + 3 * 3600

        with patch(COMMON_PATCHES["async_session_maker"], return_value=async_session_test()), \
             patch(COMMON_PATCHES["get_redis"], return_value=mock_redis), \
             patch(COMMON_PATCHES["execute_query_rewrite"], return_value=query_rewrite_result), \
             patch(COMMON_PATCHES["execute_multi_vector_retrieval"], return_value=retrieval_result), \
             patch(COMMON_PATCHES["chat_with_step5_parse"], return_value=step5_output), \
             patch(COMMON_PATCHES["execute_step5_5"], return_value=None), \
             patch(COMMON_PATCHES["execute_step6"], return_value=None), \
             patch(COMMON_PATCHES["check_content"], return_value={"is_safe": True, "reason": ""}), \
             patch(COMMON_PATCHES["allocate_sort_seq"], return_value=[100004]), \
             patch(COMMON_PATCHES["get_activity_description"], return_value=""), \
             patch(COMMON_PATCHES["read_for_prompt"], return_value=None), \
             patch("backend.services.step8_subchain.agent_service") as mock_agent_svc, \
             patch("backend.services.step8_subchain.random.random", return_value=0.0001), \
             patch("backend.services.step8_subchain.parse_future_time", return_value=future_ts):

            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)

            from backend.services.step8_subchain import execute_step8_subchain
            result = await execute_step8_subchain(user_id=4, future_action="提醒喝水")

        assert result is True

        # 验证 proactive_times +1 且 Future 槽已写入
        async with async_session_test() as check_db:
            stmt = select(Relationship).where(Relationship.user_id == 4)
            res = await check_db.execute(stmt)
            rel = res.scalar_one()
            assert rel.proactive_times == 1
            assert rel.future_timestamp == future_ts
            assert rel.future_action == "提醒休息一下"

    @pytest.mark.asyncio
    async def test_decay_gate_no_write_when_miss(self, db_session):
        """衰减门控未命中时不写入 Future 槽"""
        await _create_user(db_session, user_id=5)
        await _create_relationship(
            db_session, user_id=5, proactive_times=1,
            future_timestamp=int(time.time()) - 60,
            future_action="提醒运动",
        )
        await db_session.commit()

        step5_output = _mock_step5_output(
            future_time_natural="2小时后",
            future_action="提醒跑步",
        )
        retrieval_result = _mock_retrieval_result()
        query_rewrite_result = _mock_query_rewrite_result()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(COMMON_PATCHES["async_session_maker"], return_value=async_session_test()), \
             patch(COMMON_PATCHES["get_redis"], return_value=mock_redis), \
             patch(COMMON_PATCHES["execute_query_rewrite"], return_value=query_rewrite_result), \
             patch(COMMON_PATCHES["execute_multi_vector_retrieval"], return_value=retrieval_result), \
             patch(COMMON_PATCHES["chat_with_step5_parse"], return_value=step5_output), \
             patch(COMMON_PATCHES["execute_step5_5"], return_value=None), \
             patch(COMMON_PATCHES["execute_step6"], return_value=None), \
             patch(COMMON_PATCHES["check_content"], return_value={"is_safe": True, "reason": ""}), \
             patch(COMMON_PATCHES["allocate_sort_seq"], return_value=[100005]), \
             patch(COMMON_PATCHES["get_activity_description"], return_value=""), \
             patch(COMMON_PATCHES["read_for_prompt"], return_value=None), \
             patch("backend.services.step8_subchain.agent_service") as mock_agent_svc, \
             patch("backend.services.step8_subchain.random.random", return_value=0.999):

            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)

            from backend.services.step8_subchain import execute_step8_subchain
            result = await execute_step8_subchain(user_id=5, future_action="提醒运动")

        assert result is True

        # 验证 proactive_times +1 但 Future 槽未写入新值
        async with async_session_test() as check_db:
            stmt = select(Relationship).where(Relationship.user_id == 5)
            res = await check_db.execute(stmt)
            rel = res.scalar_one()
            assert rel.proactive_times == 2
            # Future 槽保持旧值（_decay_gate_and_update 不会主动清除旧值，
            # 清除由 future_handler._on_consume_success 负责）


class TestStep8FutureActionEmpty:
    """边界测试：future.action 为空 → 整轮主动消息失败"""

    @pytest.mark.asyncio
    async def test_empty_future_action(self, db_session):
        """future_action 为空时返回 False"""
        from backend.services.step8_subchain import execute_step8_subchain
        result = await execute_step8_subchain(user_id=99, future_action="")
        assert result is False

    @pytest.mark.asyncio
    async def test_none_future_action(self, db_session):
        """future_action 为 None 时返回 False"""
        from backend.services.step8_subchain import execute_step8_subchain
        result = await execute_step8_subchain(user_id=99, future_action=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_whitespace_future_action(self, db_session):
        """future_action 为纯空白时返回 False"""
        from backend.services.step8_subchain import execute_step8_subchain
        result = await execute_step8_subchain(user_id=99, future_action="   ")
        assert result is False


class TestStep8Step5Failure:
    """Step5 LLM 调用失败时子链路正确终止"""

    @pytest.mark.asyncio
    async def test_step5_failure_returns_false(self, db_session):
        """Step5 失败时返回 False，不写 agent_message"""
        await _create_user(db_session, user_id=6)
        await _create_relationship(
            db_session, user_id=6, proactive_times=0,
            future_timestamp=int(time.time()) - 60,
            future_action="测试失败",
        )
        await db_session.commit()

        from backend.services.llm_service import Step5ParseError

        query_rewrite_result = _mock_query_rewrite_result()
        retrieval_result = _mock_retrieval_result()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(COMMON_PATCHES["async_session_maker"], return_value=async_session_test()), \
             patch(COMMON_PATCHES["get_redis"], return_value=mock_redis), \
             patch(COMMON_PATCHES["execute_query_rewrite"], return_value=query_rewrite_result), \
             patch(COMMON_PATCHES["execute_multi_vector_retrieval"], return_value=retrieval_result), \
             patch(COMMON_PATCHES["chat_with_step5_parse"], side_effect=Step5ParseError("解析失败")), \
             patch(COMMON_PATCHES["get_activity_description"], return_value=""), \
             patch(COMMON_PATCHES["read_for_prompt"], return_value=None):

            from backend.services.step8_subchain import execute_step8_subchain
            result = await execute_step8_subchain(user_id=6, future_action="测试失败")

        assert result is False

        # 验证没有写入 agent_message
        async with async_session_test() as check_db:
            stmt = select(AgentMessage).where(AgentMessage.user_id == 6)
            res = await check_db.execute(stmt)
            agent_msgs = list(res.scalars().all())
            assert len(agent_msgs) == 0


class TestStep8ProactiveTimesLimit:
    """proactive_times 到达上限 3 时不再增加"""

    @pytest.mark.asyncio
    async def test_proactive_times_cap_at_3(self, db_session):
        """proactive_times 已经是 3 时不再递增"""
        await _create_user(db_session, user_id=7)
        await _create_relationship(
            db_session, user_id=7, proactive_times=3,
            future_timestamp=int(time.time()) - 60,
            future_action="上限测试",
        )
        await db_session.commit()

        step5_output = _mock_step5_output()
        retrieval_result = _mock_retrieval_result()
        query_rewrite_result = _mock_query_rewrite_result()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(COMMON_PATCHES["async_session_maker"], return_value=async_session_test()), \
             patch(COMMON_PATCHES["get_redis"], return_value=mock_redis), \
             patch(COMMON_PATCHES["execute_query_rewrite"], return_value=query_rewrite_result), \
             patch(COMMON_PATCHES["execute_multi_vector_retrieval"], return_value=retrieval_result), \
             patch(COMMON_PATCHES["chat_with_step5_parse"], return_value=step5_output), \
             patch(COMMON_PATCHES["execute_step5_5"], return_value=None), \
             patch(COMMON_PATCHES["execute_step6"], return_value=None), \
             patch(COMMON_PATCHES["check_content"], return_value={"is_safe": True, "reason": ""}), \
             patch(COMMON_PATCHES["allocate_sort_seq"], return_value=[100007]), \
             patch(COMMON_PATCHES["get_activity_description"], return_value=""), \
             patch(COMMON_PATCHES["read_for_prompt"], return_value=None), \
             patch("backend.services.step8_subchain.agent_service") as mock_agent_svc:

            mock_agent_svc.calculate_action_score = AsyncMock(return_value=8.0)

            from backend.services.step8_subchain import execute_step8_subchain
            result = await execute_step8_subchain(user_id=7, future_action="上限测试")

        assert result is True

        async with async_session_test() as check_db:
            stmt = select(Relationship).where(Relationship.user_id == 7)
            res = await check_db.execute(stmt)
            rel = res.scalar_one()
            assert rel.proactive_times == 3  # 不超过上限
