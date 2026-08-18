# -*- coding: utf-8 -*-
# H5 应用只读接口单元测试

import sys
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db

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


if "backend.tasks.scheduler" not in sys.modules:
    _mock_scheduler = type(sys)("backend.tasks.scheduler")
    _mock_scheduler.start_scheduler = lambda *a, **k: None
    _mock_scheduler.shutdown_scheduler = lambda: None
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler

from backend.main import app  # noqa: E402

app.dependency_overrides[get_db] = override_get_db

_DEFAULT_USER = "player0001"
_DEFAULT_PASS = "pass1234"


@pytest_asyncio.fixture(autouse=True)
def mock_infra(monkeypatch):
    monkeypatch.setattr("backend.main.create_all_tables", AsyncMock())

    async def _fake_get_redis():
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.set = AsyncMock(return_value=True)
        r.setex = AsyncMock(return_value=True)
        return r

    monkeypatch.setattr("backend.utils.auth_middleware.get_redis", _fake_get_redis)
    monkeypatch.setattr("backend.services.admin_config_service.get_redis", _fake_get_redis)


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


async def _register_and_login(client: AsyncClient) -> str:
    await client.post("/api/auth/register", json={
        "username": _DEFAULT_USER,
        "password": _DEFAULT_PASS,
        "confirm_password": _DEFAULT_PASS,
    })
    resp = await client.post("/api/auth/login", json={
        "username": _DEFAULT_USER,
        "password": _DEFAULT_PASS,
    })
    return resp.json()["data"]["token"]


@pytest.mark.asyncio
async def test_persona_background_allows_missing_authorization(client):
    """只有完全缺少 Authorization 时，persona-background 才进入匿名分支。"""
    with patch(
        "backend.routers.app.admin_config_service.get_active_config",
        new=AsyncMock(return_value={"background": "公开角色背景"}),
    ):
        resp = await client.get("/api/app/persona-background")

    assert resp.status_code == 200
    assert resp.json()["data"] == {"background": "公开角色背景"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authorization",
    [
        "",
        "Basic not-a-bearer-token",
        "Bearer",
        "Bearer invalid.token.here",
    ],
)
async def test_persona_background_rejects_present_but_invalid_authorization(
    client, authorization
):
    """出现认证头后不得静默降级为匿名访问。"""
    resp = await client.get(
        "/api/app/persona-background",
        headers={"Authorization": authorization},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_only_feed_public_gets_allow_missing_authorization(client):
    """Feed 匿名白名单精确到 list/header，写接口和 badge 继续强鉴权。"""
    with (
        patch(
            "backend.routers.feed.feed_service.list_feed",
            new=AsyncMock(return_value={"posts": [], "next_cursor": None}),
        ) as list_feed,
        patch(
            "backend.routers.feed.feed_service.get_header_config",
            new=AsyncMock(return_value={"display_nickname": "林小梦"}),
        ),
    ):
        list_resp = await client.get("/api/feed/list")
        header_resp = await client.get("/api/feed/config/header")

    assert list_resp.status_code == 200
    assert header_resp.status_code == 200
    assert list_feed.await_args.args[1] is None

    assert (await client.get("/api/feed/badge")).status_code == 401
    assert (await client.post("/api/feed/enter")).status_code == 401
    assert (await client.post("/api/feed/1/like")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/feed/list",
        "/api/feed/config/header",
        "/api/app/persona-background",
    ],
)
async def test_public_gets_reject_forged_bearer_token(client, path):
    resp = await client.get(
        path,
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_get_rejects_expired_bearer_token(client):
    from datetime import datetime, timedelta, timezone

    import jwt as pyjwt

    from backend.config import get_jwt_algorithm, get_jwt_secret

    expired_token = pyjwt.encode(
        {
            "user_id": 1,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        },
        get_jwt_secret(),
        algorithm=get_jwt_algorithm(),
    )
    resp = await client.get(
        "/api/app/persona-background",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_get_rejects_banned_user_token(client, monkeypatch):
    token = await _register_and_login(client)

    async def _banned_redis():
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="1")
        return redis

    monkeypatch.setattr("backend.utils.auth_middleware.get_redis", _banned_redis)
    resp = await client.get(
        "/api/app/persona-background",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_feed_list_keeps_authenticated_user_context(client):
    token = await _register_and_login(client)
    with patch(
        "backend.routers.feed.feed_service.list_feed",
        new=AsyncMock(return_value={"posts": [], "next_cursor": None}),
    ) as list_feed:
        resp = await client.get(
            "/api/feed/list",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert isinstance(list_feed.await_args.args[1], int)


@pytest.mark.asyncio
async def test_protected_page_module_gets_remain_strongly_authenticated(client):
    """开放 H5 页面不等于开放 Diary/Memory/Relationship 私有接口。"""
    paths = (
        "/api/diary/list?page=1",
        "/api/memory/list?page=1&page_size=50",
        "/api/relationship/detail",
    )

    responses = [await client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [401, 401, 401]


@pytest.mark.asyncio
async def test_persona_background_from_config(client):
    token = await _register_and_login(client)
    mock_persona = {
        "background": "测试角色背景文案",
        "personality": "x",
        "emotion_preference": "x",
        "language_style": "x",
        "behavior_pattern": "x",
    }
    with patch(
        "backend.routers.app.admin_config_service.get_active_config",
        new=AsyncMock(return_value=mock_persona),
    ):
        resp = await client.get(
            "/api/app/persona-background",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["background"] == "测试角色背景文案"


@pytest.mark.asyncio
async def test_persona_background_fallback_when_empty(client):
    token = await _register_and_login(client)
    with patch(
        "backend.routers.app.admin_config_service.get_active_config",
        new=AsyncMock(return_value=None),
    ):
        resp = await client.get(
            "/api/app/persona-background",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "2149" in body["data"]["background"]
    assert "林小梦" in body["data"]["background"]
