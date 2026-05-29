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
async def test_persona_background_requires_auth(client):
    resp = await client.get("/api/app/persona-background")
    assert resp.status_code == 401


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
