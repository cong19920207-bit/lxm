# -*- coding: utf-8 -*-
# 管理端用户历史对话 / 情绪日志日期筛选 API 测试

import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401

from backend.database import Base, get_db

import backend.tasks.scheduler as _sched_mod

_sched_mod.start_scheduler = lambda *a, **k: None
_sched_mod.shutdown_scheduler = lambda *a, **k: None

if "backend.tasks.scheduler" in sys.modules and sys.modules["backend.tasks.scheduler"] is not _sched_mod:
    sys.modules["backend.tasks.scheduler"] = _sched_mod

from backend.main import app  # noqa: E402
from backend.models.admin_user import AdminUser  # noqa: E402
from backend.models.agent_message import AgentMessage  # noqa: E402
from backend.models.conversation_log import ConversationLog  # noqa: E402
from backend.models.emotion_log import EmotionLog  # noqa: E402
from backend.constants import (  # noqa: E402
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
    ADMIN_ERR_USER_NOT_FOUND,
)

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
def _patch_redis(monkeypatch):
    monkeypatch.setattr("backend.main.create_all_tables", AsyncMock())

    async def _fake_get_redis():
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        return r

    monkeypatch.setattr("backend.utils.auth_middleware.get_redis", _fake_get_redis)
    monkeypatch.setattr("backend.services.admin_config_service.get_redis", _fake_get_redis)
    monkeypatch.setattr(
        "backend.services.admin_config_service.admin_config_service.get_active_config",
        AsyncMock(return_value=None),
    )


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _hash_admin_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def _create_admin_user(username: str, password: str, role: str) -> None:
    async with async_session_test() as session:
        session.add(
            AdminUser(
                username=username,
                password_hash=_hash_admin_password(password),
                role=role,
                is_active=True,
                is_locked=False,
                login_fail_count=0,
                last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        await session.commit()


async def _admin_token(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post(
        "/api/admin/auth/login",
        json={"username": username, "password": password},
    )
    data = r.json()
    assert data["code"] == 0, data
    return data["data"]["token"]


async def _register_user(client: AsyncClient, username: str) -> int:
    body = {
        "username": username,
        "password": "pass1234",
        "confirm_password": "pass1234",
    }
    r = await client.post("/api/auth/register", json=body)
    d = r.json()
    assert d["code"] == 0, d
    return d["data"]["user_id"]


class TestAdminUserConversationsApi:
    """GET /api/admin/users/{user_id}/conversations 日期筛选与合并"""

    @pytest.mark.asyncio
    async def test_end_date_includes_late_records_on_end_day(self, client: AsyncClient):
        await _create_admin_user("suconv", "Super@Cnv123!!", "super_admin")
        uid = await _register_user(client, "convuser01")
        day1 = datetime(2026, 6, 4, 10, 0, 0)
        day2_late = datetime(2026, 6, 5, 2, 22, 0)
        async with async_session_test() as session:
            session.add(
                ConversationLog(
                    user_id=uid,
                    role="user",
                    content="六月四日",
                    sort_seq=100,
                    created_at=day1,
                    delivery_status="delivered",
                )
            )
            session.add(
                ConversationLog(
                    user_id=uid,
                    role="user",
                    content="六月五日深夜",
                    sort_seq=101,
                    created_at=day2_late,
                    delivery_status="delivered",
                )
            )
            await session.commit()

        token = await _admin_token(client, "suconv", "Super@Cnv123!!")
        r = await client.get(
            f"/api/admin/users/{uid}/conversations"
            "?start_date=2026-06-04&end_date=2026-06-05&page=1&page_size=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        d = r.json()
        assert d["code"] == 0
        assert d["data"]["total"] == 2
        contents = [row["content"] for row in d["data"]["list"]]
        assert "六月四日" in contents
        assert "六月五日深夜" in contents

    @pytest.mark.asyncio
    async def test_merges_agent_message_in_date_range(self, client: AsyncClient):
        await _create_admin_user("suconv2", "Super@Cnv223!!", "super_admin")
        uid = await _register_user(client, "convuser02")
        ts = datetime(2026, 6, 5, 12, 0, 0)
        async with async_session_test() as session:
            session.add(
                AgentMessage(
                    user_id=uid,
                    content="主动问候",
                    trigger_type="P2",
                    action_score=6.0,
                    sort_seq=200,
                    created_at=ts,
                    is_read=False,
                )
            )
            await session.commit()

        token = await _admin_token(client, "suconv2", "Super@Cnv223!!")
        r = await client.get(
            f"/api/admin/users/{uid}/conversations"
            "?start_date=2026-06-05&end_date=2026-06-05&page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        d = r.json()
        assert d["code"] == 0
        assert d["data"]["total"] == 1
        row = d["data"]["list"][0]
        assert row["message_source"] == "agent"
        assert row["content"] == "主动问候"
        assert row["trigger_type"] == "P2"

    @pytest.mark.asyncio
    async def test_start_after_end_fails(self, client: AsyncClient):
        await _create_admin_user("suconv3", "Super@Cnv323!!", "super_admin")
        uid = await _register_user(client, "convuser03")
        token = await _admin_token(client, "suconv3", "Super@Cnv323!!")
        r = await client.get(
            f"/api/admin/users/{uid}/conversations"
            "?start_date=2026-06-05&end_date=2026-06-04&page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == ADMIN_ERR_QUERY_DATE_FORMAT_INVALID

    @pytest.mark.asyncio
    async def test_user_not_found(self, client: AsyncClient):
        await _create_admin_user("suconv4", "Super@Cnv423!!", "super_admin")
        token = await _admin_token(client, "suconv4", "Super@Cnv423!!")
        r = await client.get(
            "/api/admin/users/999999/conversations?page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == ADMIN_ERR_USER_NOT_FOUND


class TestAdminUserEmotionRoundsDateFilter:
    """emotion-rounds 与 conversations 共用 admin_date_filter"""

    @pytest.mark.asyncio
    async def test_end_date_includes_late_emotion_on_end_day(self, client: AsyncClient):
        await _create_admin_user("suemo3", "Super@Emo323!!", "super_admin")
        uid = await _register_user(client, "emouser01")
        rid = "22222222-2222-4222-8222-222222222222"
        late = datetime(2026, 6, 5, 3, 0, 0)
        async with async_session_test() as session:
            u1 = ConversationLog(
                user_id=uid,
                role="user",
                content="晚",
                sort_seq=1,
                delivery_status="delivered",
                round_id=rid,
            )
            session.add(u1)
            await session.flush()
            session.add(
                EmotionLog(
                    user_id=uid,
                    emotion_label="平静",
                    confidence=0.5,
                    conversation_id=u1.id,
                    round_id=rid,
                    created_at=late,
                )
            )
            await session.commit()

        token = await _admin_token(client, "suemo3", "Super@Emo323!!")
        r = await client.get(
            f"/api/admin/users/{uid}/emotion-rounds"
            "?start_date=2026-06-05&end_date=2026-06-05&page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        d = r.json()
        assert d["code"] == 0
        assert d["data"]["total"] == 1
