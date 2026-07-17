# -*- coding: utf-8 -*-
"""STEP-023：AI 配置、Prompt、测试用例与安全规则读写角色拆分。"""

import ast
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
AI_ROUTE_FILES = (
    ROOT / "backend/routers/admin/persona.py",
    ROOT / "backend/routers/admin/prompt_mgmt.py",
    ROOT / "backend/routers/admin/chat_prompt_view.py",
    ROOT / "backend/routers/admin/test_cases.py",
    ROOT / "backend/routers/admin/safety_rules.py",
)

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
    "super_admin": "Super@Step023!",
    "ai_trainer": "Trainer@Step023!",
    "observer": "Observer@Step023!",
}


@pytest_asyncio.fixture(autouse=True)
async def database(monkeypatch):
    from backend.services.admin_config_service import admin_config_service

    monkeypatch.setattr(
        admin_config_service, "get_active_config", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        admin_config_service, "get_active_config_detail", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        admin_config_service, "get_draft", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        admin_config_service,
        "get_version_history",
        AsyncMock(return_value={"total": 0, "list": []}),
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        for role, password in ROLE_PASSWORDS.items():
            session.add(
                AdminUser(
                    username=f"step023-{role}",
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
        transport=ASGITransport(app=app), base_url="http://step023"
    ) as http_client:
        yield http_client


async def _login(client: AsyncClient, role: str) -> str:
    response = await client.post(
        "/api/admin/auth/login",
        json={
            "username": f"step023-{role}",
            "password": ROLE_PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _decorator_role_collection(decorator: ast.Call) -> str | None:
    for keyword in decorator.keywords:
        if keyword.arg != "dependencies" or not isinstance(keyword.value, ast.List):
            continue
        for dependency in keyword.value.elts:
            if not isinstance(dependency, ast.Call):
                continue
            if not isinstance(dependency.func, ast.Name):
                continue
            if dependency.func.id != "require_role" or not dependency.args:
                continue
            first_arg = dependency.args[0]
            if isinstance(first_arg, ast.Starred) and isinstance(
                first_arg.value, ast.Name
            ):
                return first_arg.value.id
    return None


def test_all_ai_routes_use_explicit_read_or_write_role_collection():
    for path in AI_ROUTE_FILES:
        source = path.read_text(encoding="utf-8")
        assert '_READ_ROLES = ("super_admin", "ai_trainer", "observer")' in source
        assert '_WRITE_ROLES = ("super_admin", "ai_trainer")' in source

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr.lower()
                if method not in {"get", "head", "post", "put", "patch", "delete"}:
                    continue
                expected = "_READ_ROLES" if method in {"get", "head"} else "_WRITE_ROLES"
                assert _decorator_role_collection(decorator) == expected, (
                    path.name,
                    node.name,
                    method,
                )


@pytest.mark.asyncio
async def test_observer_can_read_representative_ai_views(client):
    token = await _login(client, "observer")
    headers = _headers(token)

    for path in (
        "/api/admin/persona/current",
        "/api/admin/persona/draft",
        "/api/admin/persona/history",
        "/api/admin/prompt/step5",
        "/api/admin/prompt/step5/draft",
        "/api/admin/prompt/step5/history",
        "/api/admin/prompt/step5-5/fragments",
        "/api/admin/chat-prompt-view/step15",
        "/api/admin/chat-prompt-view/agent",
        "/api/admin/test-cases/persona",
        "/api/admin/safety-rules",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)


@pytest.mark.asyncio
async def test_observer_ai_writes_are_forbidden_before_business_logic(client):
    token = await _login(client, "observer")
    headers = _headers(token)

    calls = (
        ("PUT", "/api/admin/persona/draft", {}),
        ("DELETE", "/api/admin/persona/draft", None),
        ("POST", "/api/admin/persona/test", {}),
        ("POST", "/api/admin/persona/publish", {}),
        ("POST", "/api/admin/persona/rollback", {}),
        ("PUT", "/api/admin/prompt/step5/draft", {}),
        ("POST", "/api/admin/prompt/step5/publish", {}),
        ("POST", "/api/admin/prompt/step5/rollback", {}),
        ("POST", "/api/admin/prompt/test", {}),
        ("POST", "/api/admin/test-cases/persona", {}),
        ("DELETE", "/api/admin/test-cases/persona/1", None),
        ("PUT", "/api/admin/safety-rules/banned-keywords", {}),
        ("POST", "/api/admin/safety-rules/banned-keywords/import", None),
    )
    for method, path, body in calls:
        response = await client.request(method, path, headers=headers, json=body)
        assert response.status_code == 403, (method, path, response.text)


@pytest.mark.asyncio
async def test_existing_ai_role_matrix_is_preserved(client):
    tokens = {
        role: await _login(client, role)
        for role in ("super_admin", "ai_trainer")
    }
    for role, token in tokens.items():
        response = await client.get(
            "/api/admin/chat-prompt-view/step3", headers=_headers(token)
        )
        assert response.status_code == 200, role
