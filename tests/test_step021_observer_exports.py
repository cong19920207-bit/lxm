# -*- coding: utf-8 -*-
"""STEP-021：三个内建导出端点显式拒绝 observer。"""

from datetime import datetime

import bcrypt
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.admin_user import AdminUser
from backend.utils.admin_auth import create_admin_token, deny_observer_export


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
    "super_admin": "Super@Step021!",
    "ops_admin": "Ops@Step021!!",
    "tech_ops": "Tech@Step021!",
    "observer": "Observer@Step021!",
}

EXPORT_PATHS = {
    "/api/admin/operation-logs/export",
    "/api/admin/stats/report/export",
    "/api/admin/system/logs/export",
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
                    username=f"step021-{role}",
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
        transport=ASGITransport(app=app), base_url="http://step021"
    ) as http_client:
        yield http_client


async def _login(client: AsyncClient, role: str) -> str:
    response = await client.post(
        "/api/admin/auth/login",
        json={
            "username": f"step021-{role}",
            "password": ROLE_PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    return response.json()["data"]["token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_observer_is_rejected_by_export_dependency_even_on_get():
    async with session_factory() as session:
        observer = next(
            admin
            for admin in (await session.execute(select(AdminUser))).scalars()
            if admin.role == "observer"
        )
        observer_token = create_admin_token(
            observer.id, observer.role, observer.token_version
        )

    probe_app = FastAPI()
    probe_app.dependency_overrides[get_db] = override_get_db

    @probe_app.get(
        "/api/admin/future-export",
        dependencies=[Depends(deny_observer_export)],
    )
    async def _future_export():
        return {"entered": True}

    async with AsyncClient(
        transport=ASGITransport(app=probe_app), base_url="http://step021-probe"
    ) as probe_client:
        response = await probe_client.get(
            "/api/admin/future-export",
            headers=_headers(observer_token),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "观察者禁止导出"


def test_all_admin_export_download_routes_have_explicit_observer_dependency():
    # 当前 FastAPI 对 include_router 使用惰性 _IncludedRouter 包装；审计时
    # 展开原始 APIRouter，兼容普通 APIRoute 与惰性包装两种结构。
    candidate_routes = []
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is None:
            candidate_routes.append((getattr(route, "path", ""), route))
        else:
            prefix = route.include_context.prefix
            candidate_routes.extend(
                (f"{prefix}{item.path}", item)
                for item in original_router.routes
            )

    marked_routes = {
        path: route
        for path, route in candidate_routes
        if path.startswith("/api/admin/")
        and any(
            marker in path.lower()
            for marker in ("export", "download")
        )
    }

    assert set(marked_routes) == EXPORT_PATHS
    for path, route in marked_routes.items():
        direct_dependencies = {item.call for item in route.dependant.dependencies}
        assert deny_observer_export in direct_dependencies, path


@pytest.mark.asyncio
async def test_three_exports_reject_observer_and_keep_legal_roles(client):
    tokens = {
        role: await _login(client, role)
        for role in ROLE_PASSWORDS
    }

    observer_headers = _headers(tokens["observer"])
    observer_responses = (
        await client.post(
            "/api/admin/operation-logs/export", headers=observer_headers
        ),
        await client.post(
            "/api/admin/stats/report/export?report_type=user",
            headers=observer_headers,
        ),
        await client.post(
            "/api/admin/system/logs/export", headers=observer_headers
        ),
    )
    for response in observer_responses:
        assert response.status_code == 403
        assert "content-disposition" not in response.headers

    legal_cases = (
        (
            "/api/admin/operation-logs/export",
            "tech_ops",
        ),
        (
            "/api/admin/stats/report/export?report_type=user",
            "ops_admin",
        ),
        (
            "/api/admin/system/logs/export",
            "tech_ops",
        ),
    )
    for path, role in legal_cases:
        response = await client.post(path, headers=_headers(tokens[role]))
        assert response.status_code == 200, (path, role, response.text)
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in response.headers["content-disposition"]
