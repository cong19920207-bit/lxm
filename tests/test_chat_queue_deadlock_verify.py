# -*- coding: utf-8 -*-
# 验证：未闭环队列满（5 条 pending 无叹号）、generation 作废后 DB 仍 pending、failed_blocked 无叹号

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


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "qverify%s" % uuid.uuid4().hex[:8],
            "password": "pass1234",
            "confirm_password": "pass1234",
        },
    )
    return resp.json()["data"]["token"]


def _step5_output():
    from backend.services.llm_service import parse_step5_output

    raw = json.dumps(
        {
            "inner_monologue": "测",
            "messages": [{"type": "text", "content": "回复"}],
            "relation_change": {"delta": 0},
            "future": {"time_natural": "1分钟后", "action": "关心用户"},
            "emotion": {"label": "平静", "confidence": 1.0},
            "knowledge_expand": "否",
        },
        ensure_ascii=False,
    )
    return parse_step5_output(raw)


async def _seed_open_window(user_id: int, user_count: int, *, delivery: str, with_assistant: bool = True):
    """在最后一条 assistant 之后插入 user_count 条 user 行。"""
    from backend.constants import DELIVERY_STATUS_DELIVERED, DELIVERY_STATUS_PENDING_LLM
    from backend.models.conversation_log import ConversationLog
    from backend.services.timeline_seq_service import allocate_sort_seq

    async with async_session_test() as db:
        seq = 0
        if with_assistant:
            seqs = await allocate_sort_seq(user_id, 1, db=db)
            db.add(
                ConversationLog(
                    user_id=user_id,
                    role="assistant",
                    content="此前已回复",
                    sort_seq=seqs[0],
                    delivery_status=None,
                )
            )
            seq = seqs[0]
        for i in range(user_count):
            seqs = await allocate_sort_seq(user_id, 1, db=db)
            assert seqs[0] > seq
            db.add(
                ConversationLog(
                    user_id=user_id,
                    role="user",
                    content="用户消息%d" % (i + 1),
                    sort_seq=seqs[0],
                    delivery_status=delivery,
                    skipped_in_prompt=False,
                    persona_risk_flag=False,
                )
            )
            seq = seqs[0]
        await db.commit()


class TestQueueFullDeadlockVerify:
    """复现用户场景：≥5 条 pending_llm、无 failed_* → 10104 / 无法 resend。"""

    @pytest.mark.asyncio
    async def test_five_pending_no_bang_blocks_quota(self):
        from backend.constants import DELIVERY_STATUS_PENDING_LLM
        from backend.services import chat_service

        await _seed_open_window(1, 5, delivery=DELIVERY_STATUS_PENDING_LLM)

        async with async_session_test() as db:
            open_rows = await chat_service.fetch_open_window_user_rows(db, 1)
            assert len(open_rows) == 5
            assert chat_service.open_window_has_bang(open_rows) is False
            assert chat_service._should_block_new_send(open_rows) is True
            assert await chat_service.check_send_quota(1, db) is True

    @pytest.mark.asyncio
    async def test_api_send_returns_10104_when_queue_full(self, client: AsyncClient, auth_token: str):
        from backend.constants import DELIVERY_STATUS_PENDING_LLM, ERR_CHAT_QUEUE_FULL

        await _seed_open_window(1, 5, delivery=DELIVERY_STATUS_PENDING_LLM)

        resp = await client.post(
            "/api/chat/send",
            json={"content": "第6条应被拒绝"},
            headers={"Authorization": "Bearer " + auth_token},
        )
        body = resp.json()
        assert body["code"] == ERR_CHAT_QUEUE_FULL

    @pytest.mark.asyncio
    async def test_resend_10107_when_only_pending_no_bang(self, client: AsyncClient, auth_token: str):
        from backend.constants import DELIVERY_STATUS_PENDING_LLM, ERR_CHAT_NOTHING_TO_RESEND

        await _seed_open_window(1, 5, delivery=DELIVERY_STATUS_PENDING_LLM)

        resp = await client.post(
            "/api/chat/resend",
            json={},
            headers={"Authorization": "Bearer " + auth_token},
        )
        body = resp.json()
        assert body["code"] == ERR_CHAT_NOTHING_TO_RESEND


class TestGenerationStaleDiscardVerify:
    """验证：LLM 完成后 generation 已变 → 静默 return，user 行仍为 pending_llm。"""

    @pytest.mark.asyncio
    async def test_gen_mismatch_after_llm_keeps_pending_no_assistant(self):
        from backend.constants import DELIVERY_STATUS_PENDING_LLM
        from backend.models.conversation_log import ConversationLog
        from backend.routers import chat as chat_mod

        gen_before = "00000000-0000-4000-8000-000000000001"
        gen_after = "00000000-0000-4000-8000-000000000002"

        await _seed_open_window(1, 3, delivery=DELIVERY_STATUS_PENDING_LLM)

        call_count = {"n": 0}

        async def redis_get_side_effect(_user_id):
            call_count["n"] += 1
            # 打包前两次、LLM 后第三次：第三次返回新代
            if call_count["n"] <= 2:
                return gen_before
            return gen_after

        mock_redis = AsyncMock()
        store: dict = {}

        async def redis_set(k, v, ex=None, px=None):
            store[k] = v
            return True

        mock_redis.get = AsyncMock(side_effect=lambda k: store.get(k))
        mock_redis.set = AsyncMock(side_effect=redis_set)

        with (
            patch(
                "backend.routers.chat.redis_get_generation",
                new_callable=AsyncMock,
                side_effect=redis_get_side_effect,
            ),
            patch(
                "backend.routers.chat.execute_query_rewrite",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.routers.chat.execute_multi_vector_retrieval",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.routers.chat.llm_service.chat_with_step5_parse",
                new_callable=AsyncMock,
                return_value=_step5_output(),
            ),
            patch("backend.routers.chat._post_bundle_success_tasks", new_callable=AsyncMock),
            patch("backend.routers.chat.execute_step5_5", new_callable=AsyncMock, return_value=None),
            patch("backend.routers.chat.execute_step6", new_callable=AsyncMock),
            patch("backend.routers.chat.get_redis", return_value=mock_redis),
            patch("backend.services.prompt_builder.get_redis", return_value=mock_redis),
            patch("backend.services.chat_queue_service.get_redis", return_value=mock_redis),
        ):
            await chat_mod._execute_llm_bundle(1)

        async with async_session_test() as db:
            rows = (
                (await db.execute(select(ConversationLog).where(ConversationLog.user_id == 1)))
                .scalars()
                .all()
            )
            users = [r for r in rows if r.role == "user"]
            assistants = [r for r in rows if r.role == "assistant"]
            assert len(assistants) == 1  # 仅 seed 时的历史 assistant
            assert len(users) == 3
            assert all(r.delivery_status == DELIVERY_STATUS_PENDING_LLM for r in users)


class TestSseTimeoutVsDbVerify:
    """验证：Future 等待超时只返回 error payload，不自动写 failed 到 DB。"""

    @pytest.mark.asyncio
    async def test_await_bundle_timeout_returns_error_without_db_side_effect(self):
        import asyncio

        from backend.constants import DELIVERY_STATUS_PENDING_LLM, ERR_LLM_FAILED
        from backend.models.conversation_log import ConversationLog
        from backend.services import chat_service

        await _seed_open_window(1, 1, delivery=DELIVERY_STATUS_PENDING_LLM)

        gen = "timeout-gen-%s" % uuid.uuid4().hex
        # 注册永不完成的 Future
        await chat_service._get_or_create_bundle_future(gen)

        with patch.object(chat_service, "BUNDLE_WAIT_TIMEOUT_SEC", 0.05):
            payload = await chat_service.await_bundle_payload(gen)

        assert payload.get("error") is True
        assert payload.get("message") == "等待回复超时"

        async with async_session_test() as db:
            u = (
                await db.execute(
                    select(ConversationLog).where(
                        ConversationLog.user_id == 1,
                        ConversationLog.role == "user",
                    )
                )
            ).scalar_one()
            assert u.delivery_status == DELIVERY_STATUS_PENDING_LLM


class TestFailedBlockedNoBangVerify:
    """TD-030：failed_blocked 不计入叹号，但仍占未闭环名额。"""

    @pytest.mark.asyncio
    async def test_failed_blocked_counts_pending_but_no_bang(self):
        from backend.constants import DELIVERY_STATUS_FAILED_BLOCKED
        from backend.services import chat_service

        await _seed_open_window(1, 5, delivery=DELIVERY_STATUS_FAILED_BLOCKED)

        async with async_session_test() as db:
            open_rows = await chat_service.fetch_open_window_user_rows(db, 1)
            assert len(open_rows) == 5
            assert chat_service.open_window_has_bang(open_rows) is False
            assert chat_service._should_block_new_send(open_rows) is True
