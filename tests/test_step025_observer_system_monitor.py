# -*- coding: utf-8 -*-
"""STEP-025：系统状态、第三方状态与脱敏系统日志只读。"""

from datetime import datetime
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.admin_user import AdminUser


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with session_factory() as session:
        yield session
        await session.commit()


class _FakeRedis:
    async def get(self, _key):
        return None

    async def set(self, *_args, **_kwargs):
        return True

    async def setex(self, *_args, **_kwargs):
        return True

    async def hget(self, *_args, **_kwargs):
        return None

    async def lrange(self, *_args, **_kwargs):
        return []

    async def info(self, section=None):
        return {}


@pytest_asyncio.fixture(autouse=True)
async def database(tmp_path, monkeypatch):
    from backend.routers.admin import system_monitor

    monkeypatch.setattr(system_monitor, "_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        system_monitor, "_do_test_connection", AsyncMock(return_value={"connected": True})
    )

    async def _fake_redis():
        return _FakeRedis()

    monkeypatch.setattr(system_monitor, "get_redis", _fake_redis)
    (tmp_path / "system.log").write_text(
        "2026-07-16 12:00:00 | INFO | step025 | api_key=step025-secret\n",
        encoding="utf-8",
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role in ("super_admin", "tech_ops", "observer"):
            password = f"{role.title().replace('_', '')}@Step025!"
            session.add(
                AdminUser(
                    username=f"step025-{role}",
                    password_hash=bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8"),
                    role=role,
                    token_version=0,
                    last_password_change_at=datetime.utcnow(),
                )
            )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://step025"
    ) as http_client:
        yield http_client


async def _login(client: AsyncClient, role: str) -> str:
    password = f"{role.title().replace('_', '')}@Step025!"
    response = await client.post(
        "/api/admin/auth/login",
        json={"username": f"step025-{role}", "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]["token"]


@pytest.mark.asyncio
async def test_observer_reads_system_third_party_and_redacted_logs(client):
    token = await _login(client, "observer")
    headers = {"Authorization": f"Bearer {token}"}
    for path in (
        "/api/admin/system/status",
        "/api/admin/third-party/status",
        "/api/admin/system/logs",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert response.json()["code"] == 0

    logs = await client.get("/api/admin/system/logs", headers=headers)
    serialized = str(logs.json())
    assert "step025-secret" not in serialized
    assert "[REDACTED]" in serialized


@pytest.mark.asyncio
async def test_observer_system_writes_tests_and_export_are_forbidden(client):
    from backend.routers.admin import system_monitor

    token = await _login(client, "observer")
    headers = {"Authorization": f"Bearer {token}"}
    for method, path in (
        ("PUT", "/api/admin/third-party/doubao/config"),
        ("POST", "/api/admin/third-party/doubao/test-connection"),
        ("POST", "/api/admin/system/logs/export"),
    ):
        response = await client.request(method, path, headers=headers, json={})
        assert response.status_code == 403, (method, path, response.text)
        assert "content-disposition" not in response.headers
    system_monitor._do_test_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_super_and_tech_system_access_is_preserved(client):
    for role in ("super_admin", "tech_ops"):
        token = await _login(client, role)
        headers = {"Authorization": f"Bearer {token}"}
        assert (
            await client.get("/api/admin/system/status", headers=headers)
        ).status_code == 200
        assert (
            await client.post("/api/admin/system/logs/export", headers=headers)
        ).status_code == 200
