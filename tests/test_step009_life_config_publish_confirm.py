# -*- coding: utf-8 -*-
"""STEP-009: life-config 发布必须由后端严格校验 CONFIRM。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.constants import ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID
from backend.database import Base, get_db
from backend.models.admin_user import AdminUser
from backend.routers.admin import life_config_mgmt
from backend.utils.admin_auth import create_admin_token


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app = FastAPI()
app.include_router(life_config_mgmt.router, prefix="/api/admin")
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as value:
        yield value


async def _token_for(role: str) -> str:
    async with maker() as session:
        admin = AdminUser(
            username=f"{role}01",
            password_hash=bcrypt.hashpw(b"Test@Password123", bcrypt.gensalt()).decode(),
            role=role,
            is_active=True,
            is_locked=False,
            login_fail_count=0,
            token_version=0,
            last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return create_admin_token(admin.id, admin.role, admin.token_version)


def _body(confirm_text=...):
    body = {
        "config_key": next(iter(life_config_mgmt._WHITELIST)),
        "config_value": {"enabled": True},
    }
    if confirm_text is not ...:
        body["confirm_text"] = confirm_text
    return body


@pytest.mark.asyncio
@pytest.mark.parametrize("confirm_text", [..., None, "", "   ", "confirm"])
async def test_invalid_confirm_returns_20021_without_publish(
    client, monkeypatch, confirm_text
):
    token = await _token_for("super_admin")
    get_active = AsyncMock(return_value={"old": True})
    publish = AsyncMock(return_value={"version": 2})
    monkeypatch.setattr(life_config_mgmt.admin_config_service, "get_active_config", get_active)
    monkeypatch.setattr(life_config_mgmt.admin_config_service, "publish_config", publish)

    response = await client.post(
        "/api/admin/life-config/publish",
        json=_body(confirm_text),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
        "data": None,
        "message": "请输入 CONFIRM 以确认操作",
    }
    get_active.assert_not_awaited()
    publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_exact_confirm_enters_original_publish_flow(client, monkeypatch):
    token = await _token_for("ai_trainer")
    get_active = AsyncMock(return_value={"old": True})
    publish = AsyncMock(return_value={"version": 2})
    monkeypatch.setattr(life_config_mgmt.admin_config_service, "get_active_config", get_active)
    monkeypatch.setattr(life_config_mgmt.admin_config_service, "publish_config", publish)

    response = await client.post(
        "/api/admin/life-config/publish",
        json=_body("CONFIRM"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == 0
    get_active.assert_awaited_once()
    publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_does_not_replace_role_authorization(client, monkeypatch):
    token = await _token_for("tech_ops")
    publish = AsyncMock(return_value={"version": 2})
    monkeypatch.setattr(life_config_mgmt.admin_config_service, "publish_config", publish)

    response = await client.post(
        "/api/admin/life-config/publish",
        json=_body("CONFIRM"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    publish.assert_not_awaited()
