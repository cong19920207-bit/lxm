# -*- coding: utf-8 -*-
"""STEP-024：记忆、向量、知识、Agent、关系、情绪与世界状态只读。"""

import ast
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.models.admin_user import AdminUser
from backend.models.user import User


ROOT = Path(__file__).resolve().parents[1]
ROUTE_FILES = tuple(
    ROOT / f"backend/routers/admin/{name}.py"
    for name in (
        "memory_mgmt",
        "vector_config",
        "knowledge_mgmt",
        "agent_mgmt",
        "relationship_mgmt",
        "emotion_config",
        "world_state_mgmt",
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
    from backend.services.character_knowledge_service import character_knowledge_service
    from backend.services.user_vector_memory_service import user_vector_memory_service

    monkeypatch.setattr(
        admin_config_service, "get_active_config", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        character_knowledge_service,
        "list_entries",
        AsyncMock(return_value={"total": 0, "page": 1, "page_size": 20, "list": []}),
    )
    monkeypatch.setattr(
        user_vector_memory_service,
        "list_entries",
        AsyncMock(return_value={"total": 0, "page": 1, "page_size": 20, "list": []}),
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        session.add(
            AdminUser(
                username="step024-observer",
                password_hash=bcrypt.hashpw(
                    b"Observer@Step024!", bcrypt.gensalt()
                ).decode("utf-8"),
                role="observer",
                token_version=0,
                last_password_change_at=datetime.utcnow(),
            )
        )
        session.add(User(username="step024-user", password_hash="unused"))
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://step024"
    ) as http_client:
        yield http_client


def _role_collection(decorator: ast.Call) -> str | None:
    for keyword in decorator.keywords:
        if keyword.arg == "dependencies" and isinstance(keyword.value, ast.List):
            for item in keyword.value.elts:
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
                    if item.func.id == "require_role" and item.args:
                        arg = item.args[0]
                        if isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
                            return arg.value.id
    return None


def test_all_domain_routes_use_read_or_write_role_collection():
    for path in ROUTE_FILES:
        source = path.read_text(encoding="utf-8")
        assert '_READ_ROLES = ("super_admin", "ai_trainer", "observer")' in source
        assert '_WRITE_ROLES = ("super_admin", "ai_trainer")' in source
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(
                    decorator.func, ast.Attribute
                ):
                    continue
                method = decorator.func.attr.lower()
                if method not in {"get", "head", "post", "put", "patch", "delete"}:
                    continue
                collection = _role_collection(decorator)
                expected_suffix = "_READ_ROLES" if method in {"get", "head"} else "_WRITE_ROLES"
                assert collection is not None and collection.endswith(expected_suffix), (
                    path.name,
                    node.name,
                    method,
                )

    users_source = (ROOT / "backend/routers/admin/users.py").read_text("utf-8")
    assert "_USER_MEMORY_READ_ROLES = (" in users_source
    assert '    "observer",\n)' in users_source
    assert '_USER_MEMORY_WRITE_ROLES = ("super_admin", "ops_admin", "ai_trainer")' in users_source


@pytest.mark.asyncio
async def test_observer_reads_representative_domain_endpoints(client):
    login = await client.post(
        "/api/admin/auth/login",
        json={"username": "step024-observer", "password": "Observer@Step024!"},
    )
    token = login.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    async with session_factory() as session:
        user_id = (
            await session.execute(
                select(User.id).where(User.username == "step024-user")
            )
        ).scalar_one()

    paths = (
        "/api/admin/step6-memory-prompt",
        "/api/admin/vector-db-config",
        "/api/admin/configs/vector_retrieval_config",
        "/api/admin/configs/prompt_token_config",
        "/api/admin/character-knowledge",
        "/api/admin/agent-rules",
        "/api/admin/agent-messages",
        "/api/admin/relationship-rules",
        "/api/admin/diary-history",
        "/api/admin/emotion-config",
        "/api/admin/world-state/config",
        "/api/admin/world-state/history",
        f"/api/admin/users/{user_id}/user-memories",
        f"/api/admin/users/{user_id}/private-settings",
    )
    for path in paths:
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)

    for method, path in (
        ("PUT", "/api/admin/step6-memory-prompt"),
        ("PUT", "/api/admin/configs/vector_retrieval_config"),
        ("POST", "/api/admin/character-knowledge"),
        ("PUT", "/api/admin/agent-rules"),
        ("PUT", "/api/admin/relationship-rules"),
        ("PUT", "/api/admin/emotion-config/happy"),
        ("PUT", "/api/admin/world-state/config"),
        ("POST", f"/api/admin/users/{user_id}/user-memories"),
    ):
        response = await client.request(method, path, headers=headers, json={})
        assert response.status_code == 403, (method, path, response.text)
