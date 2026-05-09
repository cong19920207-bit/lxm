# -*- coding: utf-8 -*-
# STEP-025：向量召回与 Prompt Token 配置接口（SQLite + 打桩 admin_config 会话与 Redis）

import sys
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401 — 注册 ORM 表

if "backend.tasks.scheduler" not in sys.modules:
    _mock_scheduler = type(sys)("backend.tasks.scheduler")
    _mock_scheduler.start_scheduler = lambda: None
    _mock_scheduler.shutdown_scheduler = lambda: None
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler

from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.admin_user import AdminUser  # noqa: E402
from backend.constants import ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID  # noqa: E402

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False,
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

_SUPER_ADMIN_USER = "superadmin"
_SUPER_ADMIN_PASS = "Super@Admin123!"
_OPS_ADMIN_USER = "opsadmin01"
_OPS_ADMIN_PASS = "Ops@Admin12345"


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def _create_admin(username: str, password: str, role: str) -> None:
    from datetime import datetime, timezone

    async with async_session_test() as session:
        admin = AdminUser(
            username=username,
            password_hash=_hash_password(password),
            role=role,
            is_active=True,
            is_locked=False,
            login_fail_count=0,
            last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(admin)
        await session.commit()


async def _login_token(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/admin/auth/login",
        json={"username": username, "password": password},
    )
    data = resp.json()
    assert data["code"] == 0
    return data["data"]["token"]


_redis_mock_holder: dict[str, AsyncMock] = {}


@pytest.fixture(autouse=True)
def _patch_admin_config_engine_and_redis(monkeypatch):
    """使 admin_config_service 走测试库，并捕获 Redis setex"""
    monkeypatch.setattr(
        "backend.services.admin_config_service.async_session_maker",
        async_session_test,
    )
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock(return_value=True)
    _redis_mock_holder["redis"] = r

    async def _fake_get_redis():
        return r

    monkeypatch.setattr(
        "backend.services.admin_config_service.get_redis",
        _fake_get_redis,
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


@pytest.mark.asyncio
async def test_put_vector_partial_merges_and_updates_redis(client: AsyncClient):
    """PATCH 仅 top_k：与默认值合并后发布，Redis 写入 active_config"""
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    resp = await client.put(
        "/api/admin/configs/vector_retrieval_config",
        headers={"Authorization": f"Bearer {token}"},
        json={"top_k": 7},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0

    r = _redis_mock_holder["redis"]
    assert r.setex.called
    active_calls = [
        c for c in r.setex.call_args_list
        if c[0] and c[0][0] == "active_config:vector_retrieval_config"
    ]
    assert len(active_calls) == 1
    stored = active_calls[0][0][2]
    assert '"top_k": 7' in stored or '"top_k":7' in stored
    assert "threshold" in stored

    from backend.models.admin_config import AdminConfig

    async with async_session_test() as session:
        stmt = select(AdminConfig).where(
            AdminConfig.config_key == "vector_retrieval_config",
            AdminConfig.is_active == True,  # noqa: E712
            AdminConfig.is_draft == False,   # noqa: E712
        )
        row = (await session.execute(stmt)).scalars().first()
        assert row is not None
        assert '"top_k": 7' in row.config_value


@pytest.mark.asyncio
async def test_no_db_config_runtime_vector_defaults(client: AsyncClient):
    """无 admin_config 行时，Step2 加载逻辑回退默认 TopK/阈值"""
    from backend.services.multi_vector_retrieval_service import _load_retrieval_config

    tk, th = await _load_retrieval_config()
    assert tk == 3
    assert abs(th - 0.7) < 1e-9


@pytest.mark.asyncio
async def test_ops_admin_put_forbidden(client: AsyncClient):
    """非 super_admin / ai_trainer → 403"""
    await _create_admin(_OPS_ADMIN_USER, _OPS_ADMIN_PASS, "ops_admin")
    token = await _login_token(client, _OPS_ADMIN_USER, _OPS_ADMIN_PASS)

    resp = await client.put(
        "/api/admin/configs/vector_retrieval_config",
        headers={"Authorization": f"Bearer {token}"},
        json={"top_k": 5},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_put_empty_patch_rejected(client: AsyncClient):
    """PATCH 体无任何有效字段 → 20046"""
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    resp = await client.put(
        "/api/admin/configs/vector_retrieval_config",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID


@pytest.mark.asyncio
async def test_invalid_json_returns_422(client: AsyncClient):
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    resp = await client.put(
        "/api/admin/configs/prompt_token_config",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        content=b"{not-json",
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_prompt_patch_out_of_range_pydantic_422(client: AsyncClient):
    """合法 JSON 但字段越出 Pydantic 约束 → 422"""
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    resp = await client.put(
        "/api/admin/configs/prompt_token_config",
        headers={"Authorization": f"Bearer {token}"},
        json={"system": 0},
    )
    assert resp.status_code == 422
