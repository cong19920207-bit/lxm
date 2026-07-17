# -*- coding: utf-8 -*-
"""STEP-026：生活流六模块 observer 只读边界。"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.admin_user import AdminUser


ROOT = Path(__file__).resolve().parents[1]
ROUTE_FILES = tuple(
    ROOT / f"backend/routers/admin/{name}.py"
    for name in (
        "life_config_mgmt",
        "life_plan_mgmt",
        "feed_mgmt",
        "feed_comment_mgmt",
        "agent_aware_mgmt",
        "worldview_mgmt",
    )
)
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with session_factory() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    from backend.services.admin_config_service import admin_config_service

    monkeypatch.setattr(
        admin_config_service, "get_active_config", AsyncMock(return_value=None)
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role, password in (
            ("ops_admin", "Ops@Step026!!"),
            ("observer", "Observer@Step026!"),
        ):
            session.add(
                AdminUser(
                    username=f"step026-{role}",
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
        transport=ASGITransport(app=app), base_url="http://step026"
    ) as http_client:
        yield http_client


async def _login(client: AsyncClient, role: str) -> str:
    password = "Ops@Step026!!" if role == "ops_admin" else "Observer@Step026!"
    response = await client.post(
        "/api/admin/auth/login",
        json={"username": f"step026-{role}", "password": password},
    )
    return response.json()["data"]["token"]


def test_life_stream_role_collections_do_not_add_observer_to_writes():
    for path in ROUTE_FILES:
        source = path.read_text(encoding="utf-8")
        read_line = next(
            line for line in source.splitlines() if line.startswith("_READ_ROLES =")
        )
        assert '"observer"' in read_line, path.name
        allowed_line = next(
            line for line in source.splitlines() if line.startswith("_ALLOWED_ROLES =")
        )
        assert '"observer"' not in allowed_line, path.name

    feed_source = (ROOT / "backend/routers/admin/feed_mgmt.py").read_text("utf-8")
    assert '@router.get("/feed/config/auto-publish", dependencies=[require_role(*_READ_ROLES)])' in feed_source


@pytest.mark.asyncio
async def test_observer_and_existing_ops_read_life_stream_without_write_access(client):
    read_paths = (
        "/api/admin/life-config?keys=step026_invalid_key",
        "/api/admin/life-plan/outline",
        "/api/admin/life-plan/settings",
        "/api/admin/life-plan/daily",
        "/api/admin/feed/posts",
        "/api/admin/feed/comments",
        "/api/admin/agent-aware",
        "/api/admin/worldview/snapshots",
        "/api/admin/worldview/events",
        "/api/admin/feed/config/auto-publish",
    )
    for role in ("observer", "ops_admin"):
        token = await _login(client, role)
        headers = {"Authorization": f"Bearer {token}"}
        for path in read_paths:
            response = await client.get(path, headers=headers)
            assert response.status_code == 200, (role, path, response.text)

    observer = await _login(client, "observer")
    headers = {"Authorization": f"Bearer {observer}"}
    for method, path in (
        ("PUT", "/api/admin/life-config/draft"),
        ("POST", "/api/admin/life-config/publish"),
        ("POST", "/api/admin/life-plan/outline/generate"),
        ("POST", "/api/admin/feed/posts"),
        ("PUT", "/api/admin/feed/comments/1"),
        ("POST", "/api/admin/agent-aware/1/retry"),
        ("POST", "/api/admin/users/1/aware/reset"),
        ("POST", "/api/admin/worldview/events"),
    ):
        response = await client.request(method, path, headers=headers, json={})
        assert response.status_code == 403, (method, path, response.text)
