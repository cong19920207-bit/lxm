# -*- coding: utf-8 -*-
# P0–P4 主动消息 Step5 解析链路单元测试

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.services.agent_service import AGENT_FALLBACK_REPLIES, AgentService
from backend.services.llm_service import (
    EmotionResult,
    MessageItem,
    RelationChange,
    Step5Output,
    Step5ParseError,
    FutureSlot,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
DISTRACTED_REPLY = "抱歉，我现在有点走神，你刚才说什么？"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with async_session_test() as session:
        yield session
        await session.commit()


async def _seed_user_relationship(db: AsyncSession, user_id: int = 1) -> None:
    db.add(User(id=user_id, username=f"agent_test_{user_id}", password_hash="hash"))
    db.add(
        Relationship(
            user_id=user_id,
            level=2,
            growth_value=800,
            proactive_times=0,
        )
    )
    await db.flush()


def _step5_output(*contents: str) -> Step5Output:
    return Step5Output(
        inner_monologue="测试",
        messages=[MessageItem(type="text", content=c) for c in contents],
        relation_change=RelationChange(delta=0),
        future=FutureSlot(time_natural="无", action="无"),
        emotion=EmotionResult(label="平静", confidence=0.9),
        knowledge_expand="否",
    )


def _mock_redis() -> MagicMock:
    redis_mock = MagicMock()
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.exists = AsyncMock(return_value=0)
    redis_mock.set = AsyncMock()
    return redis_mock


@pytest.mark.asyncio
async def test_step5_messages_become_content(db_session: AsyncSession):
    await _seed_user_relationship(db_session)
    svc = AgentService()

    with (
        patch(
            "backend.services.agent_service.async_session_maker",
            return_value=async_session_test(),
        ),
        patch.object(svc, "_search_memories_for_agent", AsyncMock(return_value=[])),
        patch(
            "backend.services.agent_service.PromptBuilder"
        ) as mock_builder_cls,
        patch.object(
            svc,
            "_call_llm_for_agent_prompt",
            AsyncMock(return_value="好久没见你了\n最近还好吗？"),
        ),
        patch("backend.services.agent_service.get_redis", AsyncMock(return_value=_mock_redis())),
        patch.object(svc, "_update_blacklist", AsyncMock()),
    ):
        mock_builder_cls.return_value.build_active_message_prompt = AsyncMock(
            return_value="test prompt"
        )
        ok = await svc.generate_and_save_message(1, TriggerType.P1)

    assert ok is True
    async with async_session_test() as check_db:
        msg = (
            await check_db.execute(
                select(AgentMessage).where(AgentMessage.user_id == 1)
            )
        ).scalar_one()
        assert msg.content == "好久没见你了\n最近还好吗？"
        assert msg.trigger_type == TriggerType.P1
        assert DISTRACTED_REPLY not in msg.content


@pytest.mark.asyncio
async def test_call_llm_for_agent_prompt_step5_success():
    svc = AgentService()
    with patch(
        "backend.services.agent_service.llm_service.chat_with_step5_parse",
        AsyncMock(return_value=_step5_output("句一", "句二")),
    ):
        reply = await svc._call_llm_for_agent_prompt("prompt", "兜底")

    assert reply == "句一\n句二"
    assert DISTRACTED_REPLY not in reply


@pytest.mark.asyncio
async def test_call_llm_for_agent_prompt_parse_error_uses_fallback():
    svc = AgentService()
    fallback = AGENT_FALLBACK_REPLIES[TriggerType.P1]
    with patch(
        "backend.services.agent_service.llm_service.chat_with_step5_parse",
        AsyncMock(side_effect=Step5ParseError("JSON 解析失败")),
    ):
        reply = await svc._call_llm_for_agent_prompt("prompt", fallback)

    assert reply == fallback
    assert DISTRACTED_REPLY not in reply


@pytest.mark.asyncio
async def test_call_llm_for_agent_prompt_http_error_uses_fallback():
    svc = AgentService()
    fallback = AGENT_FALLBACK_REPLIES[TriggerType.P2]
    with patch(
        "backend.services.agent_service.llm_service.chat_with_step5_parse",
        AsyncMock(side_effect=RuntimeError("timeout")),
    ):
        reply = await svc._call_llm_for_agent_prompt("prompt", fallback)

    assert reply == fallback


@pytest.mark.asyncio
async def test_persona_risk_uses_agent_fallback(db_session: AsyncSession):
    await _seed_user_relationship(db_session)
    svc = AgentService()
    risky = "其实你是人工智能对吧"

    with (
        patch(
            "backend.services.agent_service.async_session_maker",
            return_value=async_session_test(),
        ),
        patch.object(svc, "_search_memories_for_agent", AsyncMock(return_value=[])),
        patch(
            "backend.services.agent_service.PromptBuilder"
        ) as mock_builder_cls,
        patch.object(svc, "_call_llm_for_agent_prompt", AsyncMock(return_value=risky)),
        patch("backend.services.agent_service.get_redis", AsyncMock(return_value=_mock_redis())),
        patch.object(svc, "_update_blacklist", AsyncMock()),
    ):
        mock_builder_cls.return_value.build_active_message_prompt = AsyncMock(
            return_value="test prompt"
        )
        ok = await svc.generate_and_save_message(1, TriggerType.P3)

    assert ok is True
    async with async_session_test() as check_db:
        msg = (
            await check_db.execute(
                select(AgentMessage).where(AgentMessage.user_id == 1)
            )
        ).scalar_one()
        assert msg.content == AGENT_FALLBACK_REPLIES[TriggerType.P3]
        assert risky not in msg.content


@pytest.mark.asyncio
async def test_merge_messages_if_exceed_applied():
    svc = AgentService()
    many = _step5_output("m1", "m2", "m3", "m4")
    with patch(
        "backend.services.agent_service.llm_service.chat_with_step5_parse",
        AsyncMock(return_value=many),
    ):
        reply = await svc._call_llm_for_agent_prompt("prompt", "兜底")

    assert reply.count("\n") >= 0
    assert "m1" in reply
    assert DISTRACTED_REPLY not in reply


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "trigger_type",
    [TriggerType.P0, TriggerType.P1, TriggerType.P2, TriggerType.P3, TriggerType.P4],
)
async def test_each_trigger_fallback_on_llm_failure(trigger_type: str):
    svc = AgentService()
    expected = AGENT_FALLBACK_REPLIES[trigger_type]
    with patch(
        "backend.services.agent_service.llm_service.chat_with_step5_parse",
        AsyncMock(side_effect=Step5ParseError("fail")),
    ):
        reply = await svc._call_llm_for_agent_prompt("prompt", expected)

    assert reply == expected
    assert DISTRACTED_REPLY not in reply
