# -*- coding: utf-8 -*-
"""STEP-022：observer 用户、统计与脱敏操作日志读取边界。"""

from datetime import datetime
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.models.user import User


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


ROLE_PASSWORDS = {
    "super_admin": "Super@Step022!",
    "ops_admin": "Ops@Step022!!",
    "ai_trainer": "Trainer@Step022!",
    "tech_ops": "Tech@Step022!!",
    "observer": "Observer@Step022!",
}


class _FakeRedis:
    async def get(self, _key):
        return None

    async def set(self, *_args, **_kwargs):
        return True

    async def hgetall(self, _key):
        return {}


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    from backend.services.stats_service import stats_service

    monkeypatch.setattr(
        stats_service,
        "get_dashboard_data",
        AsyncMock(return_value={"dashboard": "readable"}),
    )
    monkeypatch.setattr(
        stats_service,
        "get_trend_data",
        AsyncMock(return_value={"metric": "new_users", "list": []}),
    )
    monkeypatch.setattr(
        stats_service,
        "get_report_data",
        AsyncMock(return_value={"total": 0, "page": 1, "page_size": 20, "list": []}),
    )

    async def _fake_redis():
        return _FakeRedis()

    monkeypatch.setattr("backend.redis_client.get_redis", _fake_redis)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role, password in ROLE_PASSWORDS.items():
            session.add(
                AdminUser(
                    username=f"step022-{role}",
                    password_hash=bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8"),
                    role=role,
                    token_version=0,
                    last_password_change_at=datetime.utcnow(),
                )
            )
        user = User(
            username="step022-user",
            password_hash=bcrypt.hashpw(
                b"User@Step022!", bcrypt.gensalt()
            ).decode("utf-8"),
        )
        session.add(user)
        await session.flush()
        session.add(
            AdminOperationLog(
                admin_user_id=None,
                admin_username="historical-admin",
                module="STEP-022",
                action="view",
                target_description="api_key=step022-plain-secret",
                before_value='{"password":"step022-before"}',
                after_value="Authorization: Bearer step022-after-token",
            )
        )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://step022"
    ) as http_client:
        yield http_client


async def _login(client: AsyncClient, role: str) -> str:
    response = await client.post(
        "/api/admin/auth/login",
        json={
            "username": f"step022-{role}",
            "password": ROLE_PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    return response.json()["data"]["token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _business_user_id() -> int:
    async with session_factory() as session:
        return (
            await session.execute(
                select(User.id).where(User.username == "step022-user")
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_observer_reads_approved_user_stats_and_redacted_logs(client):
    token = await _login(client, "observer")
    headers = _headers(token)
    user_id = await _business_user_id()

    approved_user_paths = (
        "/api/admin/users",
        f"/api/admin/users/{user_id}",
        f"/api/admin/users/{user_id}/conversations",
        f"/api/admin/users/{user_id}/emotion-rounds",
        f"/api/admin/users/{user_id}/diaries",
    )
    for path in approved_user_paths:
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert response.json()["code"] == 0, (path, response.text)

    approved_stats_paths = (
        "/api/admin/stats/dashboard",
        "/api/admin/stats/trend?metric=new_users&days=7",
        "/api/admin/stats/report?report_type=user",
        "/api/admin/stats/liblib?days=7",
    )
    for path in approved_stats_paths:
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert response.json()["code"] == 0, (path, response.text)

    log_list = await client.get(
        "/api/admin/operation-logs?module=STEP-022", headers=headers
    )
    assert log_list.status_code == 200
    log_item = log_list.json()["data"]["list"][0]
    assert "step022-plain-secret" not in str(log_item)
    assert "[REDACTED]" in log_item["target_description"]

    log_detail = await client.get(
        f"/api/admin/operation-logs/{log_item['id']}", headers=headers
    )
    assert log_detail.status_code == 200
    serialized_detail = str(log_detail.json()["data"])
    assert "step022-before" not in serialized_detail
    assert "step022-after-token" not in serialized_detail
    assert "[REDACTED]" in serialized_detail


@pytest.mark.asyncio
async def test_observer_excluded_reads_and_all_writes_remain_forbidden(client):
    token = await _login(client, "observer")
    headers = _headers(token)
    user_id = await _business_user_id()

    for path in (
        "/api/admin/accounts",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 403, (path, response.text)

    async with session_factory() as session:
        before_user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        before_hash = before_user.password_hash
        before_banned = before_user.is_banned

    write_calls = (
        ("PUT", f"/api/admin/users/{user_id}/status", {"action": "ban"}),
        ("POST", f"/api/admin/users/{user_id}/reset-password", None),
        ("POST", f"/api/admin/users/{user_id}/open-api-key", None),
        (
            "POST",
            f"/api/admin/users/{user_id}/user-memories",
            {"key": "a/b/c", "value": "must-not-write"},
        ),
        ("POST", "/api/admin/stats/report/export?report_type=user", None),
        ("POST", "/api/admin/operation-logs/export", None),
    )
    for method, path, body in write_calls:
        response = await client.request(method, path, headers=headers, json=body)
        assert response.status_code == 403, (method, path, response.text)
        assert "content-disposition" not in response.headers

    async with session_factory() as session:
        after_user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        assert after_user.password_hash == before_hash
        assert after_user.is_banned == before_banned


@pytest.mark.asyncio
async def test_original_four_role_read_matrix_is_preserved(client):
    tokens = {
        role: await _login(client, role)
        for role in ROLE_PASSWORDS
        if role != "observer"
    }

    cases = (
        ("/api/admin/users", {"super_admin", "ops_admin"}),
        (
            "/api/admin/stats/trend?metric=new_users&days=7",
            {"super_admin", "ops_admin"},
        ),
        (
            "/api/admin/stats/report?report_type=user",
            {"super_admin", "ops_admin"},
        ),
        (
            "/api/admin/stats/liblib?days=7",
            {"super_admin", "ai_trainer", "tech_ops"},
        ),
        (
            "/api/admin/operation-logs",
            {"super_admin", "ops_admin", "tech_ops"},
        ),
    )
    for path, allowed_roles in cases:
        for role, token in tokens.items():
            response = await client.get(path, headers=_headers(token))
            expected = 200 if role in allowed_roles else 403
            assert response.status_code == expected, (path, role, response.text)
