# -*- coding: utf-8 -*-
"""STEP-027：observer 凭据读取只返回配置状态。"""

import json
from datetime import datetime
from pathlib import Path

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.models.user import User
from backend.models.user_api_key import UserApiKey


ROOT = Path(__file__).resolve().parents[1]
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

THIRD_PARTY_SECRET = "sk-step027-third-party-secret-TAIL"
USER_KEY_PREFIX = "sk-lxm-HEAD…TAIL"
USER_KEY_HASH = "a" * 64


async def override_get_db():
    async with session_factory() as session:
        yield session
        await session.commit()


class _FakeRedis:
    async def get(self, _key):
        return None

    async def set(self, *_args, **_kwargs):
        return True

    async def hget(self, *_args, **_kwargs):
        return None

    async def lrange(self, *_args, **_kwargs):
        return []


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    from backend.routers.admin import system_monitor

    async def _fake_redis():
        return _FakeRedis()

    monkeypatch.setattr(system_monitor, "get_redis", _fake_redis)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role, password in (
            ("ops_admin", "Ops@Step027!!"),
            ("observer", "Observer@Step027!"),
        ):
            session.add(
                AdminUser(
                    username=f"step027-{role}",
                    password_hash=bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8"),
                    role=role,
                    token_version=0,
                    last_password_change_at=datetime.utcnow(),
                )
            )
        user = User(username="step027-user", password_hash="unused")
        session.add(user)
        await session.flush()
        session.add(
            UserApiKey(
                user_id=user.id,
                key_hash=USER_KEY_HASH,
                key_prefix=USER_KEY_PREFIX,
            )
        )
        session.add(
            AdminConfig(
                config_key="third_party:doubao",
                config_value=json.dumps(
                    {
                        "endpoint": "https://step027.example",
                        "api_key": THIRD_PARTY_SECRET,
                    }
                ),
                version=1,
                is_draft=False,
                is_active=True,
                updated_by="step027",
            )
        )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://step027"
    ) as http_client:
        yield http_client


async def _login(client: AsyncClient, role: str) -> str:
    password = "Ops@Step027!!" if role == "ops_admin" else "Observer@Step027!"
    response = await client.post(
        "/api/admin/auth/login",
        json={"username": f"step027-{role}", "password": password},
    )
    return response.json()["data"]["token"]


async def _user_id() -> int:
    from sqlalchemy import select

    async with session_factory() as session:
        return (
            await session.execute(
                select(User.id).where(User.username == "step027-user")
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_observer_only_receives_third_party_and_open_key_status(client):
    token = await _login(client, "observer")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id()

    third_party = await client.get("/api/admin/third-party/status", headers=headers)
    open_key = await client.get(
        f"/api/admin/users/{user_id}/open-api-key", headers=headers
    )
    assert third_party.status_code == 200
    assert open_key.status_code == 200
    assert open_key.json()["data"] == {"enabled": True}

    services = third_party.json()["data"]["services"]
    by_name = {item["name"]: item for item in services}
    assert by_name["LLM（豆包）"]["credential_configured"] is True
    assert by_name["Embedding（阿里云）"]["credential_configured"] is False

    serialized = json.dumps(
        {"third_party": third_party.json(), "open_key": open_key.json()},
        ensure_ascii=False,
    )
    forbidden = (
        THIRD_PARTY_SECRET,
        "sk-step027",
        "secret-TAIL",
        "sk-***AIL",
        USER_KEY_PREFIX,
        "HEAD",
        "TAIL",
        USER_KEY_HASH,
    )
    for fragment in forbidden:
        assert fragment not in serialized


@pytest.mark.asyncio
async def test_unconfigured_status_and_writes_remain_forbidden(client):
    async with session_factory() as session:
        await session.execute(__import__("sqlalchemy").delete(UserApiKey))
        await session.execute(__import__("sqlalchemy").delete(AdminConfig))
        await session.commit()

    token = await _login(client, "observer")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id()
    open_key = await client.get(
        f"/api/admin/users/{user_id}/open-api-key", headers=headers
    )
    third_party = await client.get("/api/admin/third-party/status", headers=headers)
    assert open_key.json()["data"] == {"enabled": False}
    assert all(
        item.get("credential_configured") is False
        for item in third_party.json()["data"]["services"]
        if item["name"] != "内容安全"
    )

    assert (
        await client.post(
            f"/api/admin/users/{user_id}/open-api-key", headers=headers
        )
    ).status_code == 403
    assert (
        await client.put(
            "/api/admin/third-party/doubao/config", headers=headers, json={}
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_existing_ops_open_key_metadata_is_preserved(client):
    token = await _login(client, "ops_admin")
    user_id = await _user_id()
    response = await client.get(
        f"/api/admin/users/{user_id}/open-api-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["key_prefix"] == USER_KEY_PREFIX


def test_frontend_uses_status_only_for_observer():
    third_party = (ROOT / "admin/pages/third-party.html").read_text("utf-8")
    user_detail = (ROOT / "admin/pages/user-detail.html").read_text("utf-8")
    assert "credential_configured" in third_party
    assert "getAdminRole() === 'observer'" in third_party
    assert "getAdminRole() === 'observer'" in user_detail
    assert "观察者仅显示配置状态" in user_detail
