# -*- coding: utf-8 -*-

from datetime import datetime

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


from backend.main import app  # noqa: E402
from backend.models.admin_user import AdminUser  # noqa: E402

app.dependency_overrides[get_db] = override_get_db

ROLE_PASSWORDS = {
    "super_admin": "Super@Role016!",
    "ops_admin": "Ops@Role016!!",
    "ai_trainer": "Trainer@Role016!",
    "tech_ops": "Tech@Role016!!",
}


@pytest_asyncio.fixture(autouse=True)
async def database(tmp_path, monkeypatch):
    from backend.routers.admin import system_monitor

    monkeypatch.setattr(system_monitor, "_LOG_DIR", str(tmp_path))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role, password in ROLE_PASSWORDS.items():
            session.add(
                AdminUser(
                    username=f"step016-{role}",
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
        transport=ASGITransport(app=app), base_url="http://step016"
    ) as http_client:
        yield http_client


async def _tokens(client: AsyncClient) -> dict[str, str]:
    tokens = {}
    for role, password in ROLE_PASSWORDS.items():
        response = await client.post(
            "/api/admin/auth/login",
            json={"username": f"step016-{role}", "password": password},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        assert payload["data"]["role"] == role
        tokens[role] = payload["data"]["token"]
    return tokens


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_four_role_login_read_write_publish_accounts_and_exports(client):
    tokens = await _tokens(client)

    for role, token in tokens.items():
        read_response = await client.get(
            "/api/admin/life-config?keys=step016_invalid_key",
            headers=_headers(token),
        )
        assert read_response.status_code == 200, role
        assert read_response.json()["code"] != 0, role

        draft_response = await client.put(
            "/api/admin/life-config/draft",
            json={"config_key": "step016_invalid_key", "config_value": "value"},
            headers=_headers(token),
        )
        publish_response = await client.post(
            "/api/admin/life-config/publish",
            json={
                "config_key": "step016_invalid_key",
                "config_value": "value",
                "confirm_text": "CONFIRM",
            },
            headers=_headers(token),
        )
        expected_write_status = 200 if role in {"super_admin", "ai_trainer"} else 403
        assert draft_response.status_code == expected_write_status, role
        assert publish_response.status_code == expected_write_status, role

        accounts_response = await client.get(
            "/api/admin/accounts", headers=_headers(token)
        )
        expected_accounts_status = 200 if role == "super_admin" else 403
        assert accounts_response.status_code == expected_accounts_status, role

        operation_export = await client.post(
            "/api/admin/operation-logs/export", headers=_headers(token)
        )
        expected_operation_export = (
            200 if role in {"super_admin", "ops_admin", "tech_ops"} else 403
        )
        assert operation_export.status_code == expected_operation_export, role

        system_export = await client.post(
            "/api/admin/system/logs/export", headers=_headers(token)
        )
        expected_system_export = 200 if role in {"super_admin", "tech_ops"} else 403
        assert system_export.status_code == expected_system_export, role
