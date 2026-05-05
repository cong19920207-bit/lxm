# -*- coding: utf-8 -*-
# STEP-012：内容安全兼容新结构化输出 单元测试

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with async_session_test() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def mock_auth_redis():
    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)
    with patch("backend.utils.auth_middleware.get_redis", return_value=mock_r):
        yield


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    with patch("backend.routers.chat.async_session_maker", async_session_test):
        yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _make_step5_output(messages_content: list[str], inner_monologue: str = "正常独白"):
    """构造 Step5Output 用于测试。"""
    from backend.services.llm_service import parse_step5_output

    raw = json.dumps(
        {
            "inner_monologue": inner_monologue,
            "messages": [{"type": "text", "content": c} for c in messages_content],
            "relation_change": {"delta": 0},
            "future": {"time_natural": "无", "action": "无"},
            "emotion": {"label": "平静", "confidence": 1.0},
            "knowledge_expand": "否",
        },
        ensure_ascii=False,
    )
    return parse_step5_output(raw)


def _mock_redis_factory():
    """构造可运行的 mock Redis 实例。"""
    mock_redis = AsyncMock()
    store: dict = {}

    async def redis_get(k):
        return store.get(k)

    async def redis_set(k, v, ex=None, px=None):
        store[k] = v
        return True

    mock_redis.get = AsyncMock(side_effect=redis_get)
    mock_redis.set = AsyncMock(side_effect=redis_set)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)
    return mock_redis


async def _insert_user_row(user_id: int = 1, content: str = "测试输入"):
    """插入一条 pending_llm 状态的 user 行。"""
    from backend.constants import DELIVERY_STATUS_PENDING_LLM
    from backend.models.conversation_log import ConversationLog
    from backend.services.timeline_seq_service import allocate_sort_seq

    async with async_session_test() as db:
        seqs = await allocate_sort_seq(user_id, 1, db=db)
        urow = ConversationLog(
            user_id=user_id,
            role="user",
            content=content,
            sort_seq=seqs[0],
            delivery_status=DELIVERY_STATUS_PENDING_LLM,
            skipped_in_prompt=False,
            persona_risk_flag=False,
        )
        db.add(urow)
        await db.commit()
        await db.refresh(urow)
        return urow


# ============ 测试场景 1：3 条 messages 全通过 → 正常流程 ============


class TestStep012AllPass:
    """3 条 messages 全部通过内容安全检测，流程正常闭环。"""

    @pytest.mark.asyncio
    async def test_all_messages_pass_normal_flow(self):
        from backend.constants import DELIVERY_STATUS_DELIVERED
        from backend.models.conversation_log import ConversationLog
        from backend.routers import chat as chat_mod

        gen_fixed = "aaaa-bbbb-cccc-dddd-eeee00000001"
        urow = await _insert_user_row()
        mock_redis = _mock_redis_factory()

        step5_out = _make_step5_output(["你好呀", "今天开心吗", "我一直都在"])

        with (
            patch("backend.routers.chat.redis_get_generation", new_callable=AsyncMock, return_value=gen_fixed),
            patch("backend.routers.chat.embedding_service.get_embedding", new_callable=AsyncMock, return_value=[0.1] * 8),
            patch("backend.routers.chat.dashvector_client.search", new_callable=AsyncMock, return_value=[]),
            patch("backend.routers.chat.llm_service.chat_with_step5_parse", new_callable=AsyncMock, return_value=step5_out),
            patch("backend.routers.chat.check_content", new_callable=AsyncMock, return_value={"is_safe": True, "reason": ""}),
            patch("backend.routers.chat.memory_service.extract_and_save", new_callable=AsyncMock),
            patch("backend.routers.chat._post_bundle_success_tasks", new_callable=AsyncMock),
            patch("backend.routers.chat.execute_step5_5", new_callable=AsyncMock, return_value=None),
            patch("backend.routers.chat.get_redis", return_value=mock_redis),
            patch("backend.services.prompt_builder.get_redis", return_value=mock_redis),
            patch("backend.services.chat_queue_service.get_redis", return_value=mock_redis),
        ):
            await chat_mod._execute_llm_bundle(1)

        async with async_session_test() as db:
            assistants = (
                await db.execute(
                    select(ConversationLog).where(
                        ConversationLog.user_id == 1, ConversationLog.role == "assistant"
                    )
                )
            ).scalars().all()
            assert len(assistants) == 3

            u = await db.get(ConversationLog, urow.id)
            assert u.delivery_status == DELIVERY_STATUS_DELIVERED


# ============ 测试场景 2：第 2 条违规 → 整轮失败，叹号路径 ============


class TestStep012MessageBlocked:
    """messages 中第 2 条违规 → 整轮 Step5 失败，user 行标 failed_blocked。"""

    @pytest.mark.asyncio
    async def test_second_message_blocked_whole_round_fails(self):
        from backend.constants import DELIVERY_STATUS_FAILED_BLOCKED
        from backend.models.conversation_log import ConversationLog
        from backend.routers import chat as chat_mod

        gen_fixed = "aaaa-bbbb-cccc-dddd-eeee00000002"
        urow = await _insert_user_row()
        mock_redis = _mock_redis_factory()

        step5_out = _make_step5_output(["正常内容", "包含暴力违规内容", "另一条正常"])

        call_count = [0]

        async def mock_check_content(text: str):
            call_count[0] += 1
            # inner_monologue 检测（第 1 次调用）放行
            if call_count[0] == 1:
                return {"is_safe": True, "reason": ""}
            # messages[0] 放行
            if "正常内容" in text and "暴力" not in text:
                return {"is_safe": True, "reason": ""}
            # messages[1] 命中
            if "暴力" in text:
                return {"is_safe": False, "reason": "命中违规词: 暴力"}
            return {"is_safe": True, "reason": ""}

        with (
            patch("backend.routers.chat.redis_get_generation", new_callable=AsyncMock, return_value=gen_fixed),
            patch("backend.routers.chat.embedding_service.get_embedding", new_callable=AsyncMock, return_value=[0.1] * 8),
            patch("backend.routers.chat.dashvector_client.search", new_callable=AsyncMock, return_value=[]),
            patch("backend.routers.chat.llm_service.chat_with_step5_parse", new_callable=AsyncMock, return_value=step5_out),
            patch("backend.routers.chat.check_content", side_effect=mock_check_content),
            patch("backend.routers.chat.memory_service.extract_and_save", new_callable=AsyncMock),
            patch("backend.routers.chat._post_bundle_success_tasks", new_callable=AsyncMock),
            patch("backend.routers.chat.execute_step5_5", new_callable=AsyncMock, return_value=None) as mock_step5_5,
            patch("backend.routers.chat.get_redis", return_value=mock_redis),
            patch("backend.services.prompt_builder.get_redis", return_value=mock_redis),
            patch("backend.services.chat_queue_service.get_redis", return_value=mock_redis),
        ):
            await chat_mod._execute_llm_bundle(1)

        # 验证：user 行标为 failed_blocked
        async with async_session_test() as db:
            u = await db.get(ConversationLog, urow.id)
            assert u.delivery_status == DELIVERY_STATUS_FAILED_BLOCKED

            # 无 assistant 行写入
            assistants = (
                await db.execute(
                    select(ConversationLog).where(
                        ConversationLog.user_id == 1, ConversationLog.role == "assistant"
                    )
                )
            ).scalars().all()
            assert len(assistants) == 0

        # Step5.5 不应被调用（不进 5.5）
        mock_step5_5.assert_not_called()


# ============ 测试场景 3：inner_monologue 违规 → 不拦截整轮，替换为空串 ============


class TestStep012InnerMonologueBlocked:
    """inner_monologue 违规 → 仅日志 + 替换为空串，流程继续正常闭环。"""

    @pytest.mark.asyncio
    async def test_inner_monologue_blocked_replaced_with_empty(self):
        from backend.constants import DELIVERY_STATUS_DELIVERED
        from backend.models.conversation_log import ConversationLog
        from backend.routers import chat as chat_mod

        gen_fixed = "aaaa-bbbb-cccc-dddd-eeee00000003"
        urow = await _insert_user_row()
        mock_redis = _mock_redis_factory()

        step5_out = _make_step5_output(
            ["安全回复内容"],
            inner_monologue="这段独白包含暴力违规词",
        )

        async def mock_check_content(text: str):
            # inner_monologue 中的 "暴力" 命中
            if "暴力" in text:
                return {"is_safe": False, "reason": "命中违规词: 暴力"}
            return {"is_safe": True, "reason": ""}

        captured_step5_5_kwargs = {}

        async def capture_step5_5(**kwargs):
            captured_step5_5_kwargs.update(kwargs)
            return None

        with (
            patch("backend.routers.chat.redis_get_generation", new_callable=AsyncMock, return_value=gen_fixed),
            patch("backend.routers.chat.embedding_service.get_embedding", new_callable=AsyncMock, return_value=[0.1] * 8),
            patch("backend.routers.chat.dashvector_client.search", new_callable=AsyncMock, return_value=[]),
            patch("backend.routers.chat.llm_service.chat_with_step5_parse", new_callable=AsyncMock, return_value=step5_out),
            patch("backend.routers.chat.check_content", side_effect=mock_check_content),
            patch("backend.routers.chat.memory_service.extract_and_save", new_callable=AsyncMock),
            patch("backend.routers.chat._post_bundle_success_tasks", new_callable=AsyncMock),
            patch("backend.routers.chat.execute_step5_5", side_effect=capture_step5_5),
            patch("backend.routers.chat.get_redis", return_value=mock_redis),
            patch("backend.services.prompt_builder.get_redis", return_value=mock_redis),
            patch("backend.services.chat_queue_service.get_redis", return_value=mock_redis),
        ):
            await chat_mod._execute_llm_bundle(1)

        # 验证正常闭环：assistant 行写入
        async with async_session_test() as db:
            u = await db.get(ConversationLog, urow.id)
            assert u.delivery_status == DELIVERY_STATUS_DELIVERED

            assistants = (
                await db.execute(
                    select(ConversationLog).where(
                        ConversationLog.user_id == 1, ConversationLog.role == "assistant"
                    )
                )
            ).scalars().all()
            assert len(assistants) == 1

        # 验证 inner_monologue 被替换为空串（传给 Step5.5 时）
        assert captured_step5_5_kwargs.get("step5_inner_monologue") == ""


# ============ 边界测试：Step5.5 输出违规 → 回退 Step5 ============


class TestStep012Step55BlockedFallback:
    """Step5.5 输出违规 → 回退使用 Step5 原始 messages（已通过安全检测）。"""

    @pytest.mark.asyncio
    async def test_step5_5_blocked_fallback_to_step5(self):
        from backend.constants import DELIVERY_STATUS_DELIVERED
        from backend.models.conversation_log import ConversationLog
        from backend.routers import chat as chat_mod
        from backend.services.llm_service import MessageItem

        gen_fixed = "aaaa-bbbb-cccc-dddd-eeee00000004"
        urow = await _insert_user_row()
        mock_redis = _mock_redis_factory()

        # Step5 输出 2 条安全 messages
        step5_out = _make_step5_output(["Step5安全回复A", "Step5安全回复B"])

        # Step5.5 输出包含违规内容
        step5_5_messages = [
            MessageItem(type="text", content="润色后包含暴力违规词"),
            MessageItem(type="text", content="润色后正常内容"),
        ]

        check_call_count = [0]

        async def mock_check_content(text: str):
            check_call_count[0] += 1
            # inner_monologue 和 Step5 messages 全部放行
            if "Step5安全" in text or text == "正常独白":
                return {"is_safe": True, "reason": ""}
            # Step5.5 输出中 "暴力" 命中
            if "暴力" in text:
                return {"is_safe": False, "reason": "命中违规词: 暴力"}
            return {"is_safe": True, "reason": ""}

        with (
            patch("backend.routers.chat.redis_get_generation", new_callable=AsyncMock, return_value=gen_fixed),
            patch("backend.routers.chat.embedding_service.get_embedding", new_callable=AsyncMock, return_value=[0.1] * 8),
            patch("backend.routers.chat.dashvector_client.search", new_callable=AsyncMock, return_value=[]),
            patch("backend.routers.chat.llm_service.chat_with_step5_parse", new_callable=AsyncMock, return_value=step5_out),
            patch("backend.routers.chat.check_content", side_effect=mock_check_content),
            patch("backend.routers.chat.memory_service.extract_and_save", new_callable=AsyncMock),
            patch("backend.routers.chat._post_bundle_success_tasks", new_callable=AsyncMock),
            patch("backend.routers.chat.execute_step5_5", new_callable=AsyncMock, return_value=step5_5_messages),
            patch("backend.routers.chat.get_redis", return_value=mock_redis),
            patch("backend.services.prompt_builder.get_redis", return_value=mock_redis),
            patch("backend.services.chat_queue_service.get_redis", return_value=mock_redis),
        ):
            await chat_mod._execute_llm_bundle(1)

        # 验证正常闭环，使用 Step5 原始 messages
        async with async_session_test() as db:
            u = await db.get(ConversationLog, urow.id)
            assert u.delivery_status == DELIVERY_STATUS_DELIVERED

            assistants = (
                await db.execute(
                    select(ConversationLog)
                    .where(ConversationLog.user_id == 1, ConversationLog.role == "assistant")
                    .order_by(ConversationLog.sort_seq.asc())
                )
            ).scalars().all()
            # 回退使用 Step5 的 2 条 messages（合并后仍为 2 条，因 ≤5 不触发合并）
            assert len(assistants) == 2
            assert assistants[0].content == "Step5安全回复A"
            assert assistants[1].content == "Step5安全回复B"


# ============ 辅助函数单元测试 ============


class TestStep012HelperFunctions:
    """_check_messages_safety / _check_inner_monologue_safety 辅助函数独立测试。"""

    @pytest.mark.asyncio
    async def test_check_messages_safety_all_pass(self):
        from backend.routers.chat import _check_messages_safety
        from backend.services.llm_service import MessageItem

        messages = [
            MessageItem(type="text", content="你好"),
            MessageItem(type="text", content="今天不错"),
        ]

        with patch("backend.routers.chat.check_content", new_callable=AsyncMock, return_value={"is_safe": True, "reason": ""}):
            is_safe, reason = await _check_messages_safety(messages)

        assert is_safe is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_check_messages_safety_second_blocked(self):
        from backend.routers.chat import _check_messages_safety
        from backend.services.llm_service import MessageItem

        messages = [
            MessageItem(type="text", content="正常"),
            MessageItem(type="text", content="暴力内容"),
            MessageItem(type="text", content="也正常"),
        ]

        async def _check(text):
            if "暴力" in text:
                return {"is_safe": False, "reason": "命中违规词: 暴力"}
            return {"is_safe": True, "reason": ""}

        with patch("backend.routers.chat.check_content", side_effect=_check):
            is_safe, reason = await _check_messages_safety(messages)

        assert is_safe is False
        assert "messages[1]" in reason

    @pytest.mark.asyncio
    async def test_check_messages_safety_empty_content_skipped(self):
        from backend.routers.chat import _check_messages_safety
        from backend.services.llm_service import MessageItem

        messages = [
            MessageItem(type="text", content=""),
            MessageItem(type="text", content="正常内容"),
        ]

        with patch("backend.routers.chat.check_content", new_callable=AsyncMock, return_value={"is_safe": True, "reason": ""}) as mock_cc:
            is_safe, reason = await _check_messages_safety(messages)

        assert is_safe is True
        # 空 content 跳过检测，只调用 1 次
        assert mock_cc.call_count == 1

    @pytest.mark.asyncio
    async def test_check_inner_monologue_safe(self):
        from backend.routers.chat import _check_inner_monologue_safety

        with patch("backend.routers.chat.check_content", new_callable=AsyncMock, return_value={"is_safe": True, "reason": ""}):
            result = await _check_inner_monologue_safety("我在想事情", user_id=1)

        assert result == "我在想事情"

    @pytest.mark.asyncio
    async def test_check_inner_monologue_blocked_returns_empty(self):
        from backend.routers.chat import _check_inner_monologue_safety

        with patch("backend.routers.chat.check_content", new_callable=AsyncMock, return_value={"is_safe": False, "reason": "命中违规词: 暴力"}):
            result = await _check_inner_monologue_safety("这段有暴力内容", user_id=1)

        assert result == ""

    @pytest.mark.asyncio
    async def test_check_inner_monologue_empty_passthrough(self):
        from backend.routers.chat import _check_inner_monologue_safety

        with patch("backend.routers.chat.check_content", new_callable=AsyncMock) as mock_cc:
            result = await _check_inner_monologue_safety("", user_id=1)

        assert result == ""
        mock_cc.assert_not_called()
