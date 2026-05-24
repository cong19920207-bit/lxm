# -*- coding: utf-8 -*-
# STEP-027：角色知识库 CRUD（DashVector + Embedding 打桩）

import sys
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401

if "backend.tasks.scheduler" not in sys.modules:
    _mock_scheduler = type(sys)("backend.tasks.scheduler")
    _mock_scheduler.start_scheduler = lambda: None
    _mock_scheduler.shutdown_scheduler = lambda: None
    sys.modules["backend.tasks.scheduler"] = _mock_scheduler

from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.admin_user import AdminUser  # noqa: E402
from backend.constants import (  # noqa: E402
    ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
    MEMORY_TYPE_CHARACTER_GLOBAL,
)
from backend.utils.character_knowledge_validate import build_doc_id  # noqa: E402

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False,
)

_SUPER_ADMIN_USER = "superadmin"
_SUPER_ADMIN_PASS = "Super@Admin123!"
_OPS_ADMIN_USER = "opsadmin01"
_OPS_ADMIN_PASS = "Ops@Admin12345"

_FAKE_VECTOR = [0.1] * 8
_SAMPLE_KEY = "外貌-体态-细节"
_DOC_ID = build_doc_id(MEMORY_TYPE_CHARACTER_GLOBAL, _SAMPLE_KEY)
_STORE: dict[str, dict] = {}


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


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def _create_admin(username: str, password: str, role: str) -> None:
    from datetime import datetime, timezone

    async with async_session_test() as session:
        session.add(AdminUser(
            username=username,
            password_hash=_hash_password(password),
            role=role,
            is_active=True,
            is_locked=False,
            login_fail_count=0,
            last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        await session.commit()


async def _login_token(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/admin/auth/login",
        json={"username": username, "password": password},
    )
    data = resp.json()
    assert data["code"] == 0
    return data["data"]["token"]


async def _mock_get_embedding(text: str) -> list[float]:
    return _FAKE_VECTOR if text else []


async def _mock_upsert(doc_id: str, vector: list[float], fields: dict, memory_type: str) -> bool:
    _STORE[doc_id] = {
        "id": doc_id,
        "content": fields.get("content", ""),
        "fields": {**fields, "type": memory_type},
    }
    return True


async def _mock_fetch_by_ids(doc_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in doc_ids:
        if i in _STORE:
            item = _STORE[i]
            out[i] = {
                "id": i,
                "content": item["content"],
                "fields": item["fields"],
            }
    return out


async def _mock_delete(doc_ids: list[str]) -> bool:
    for i in doc_ids:
        _STORE.pop(i, None)
    return True


async def _mock_list_by_filter(filter_str: str, top_k: int = 100) -> list[dict]:
    results = []
    for doc_id, item in _STORE.items():
        mt = item["fields"].get("type", "")
        if f"type = '{mt}'" != filter_str:
            continue
        results.append({
            "id": doc_id,
            "content": item["content"],
            "fields": item["fields"],
        })
    return results[:top_k]


@pytest.fixture(autouse=True)
def _bind_test_db_override():
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if prev is not None:
        app.dependency_overrides[get_db] = prev
    else:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _reset_store():
    _STORE.clear()
    yield
    _STORE.clear()


@pytest.fixture(autouse=True)
def _patch_dashvector_and_embedding(monkeypatch):
    monkeypatch.setattr(
        "backend.services.embedding_service.embedding_service.get_embedding",
        _mock_get_embedding,
    )
    monkeypatch.setattr(
        "backend.utils.dashvector_client.dashvector_client.upsert",
        _mock_upsert,
    )
    monkeypatch.setattr(
        "backend.utils.dashvector_client.dashvector_client.fetch_by_ids",
        _mock_fetch_by_ids,
    )
    monkeypatch.setattr(
        "backend.utils.dashvector_client.dashvector_client.delete",
        _mock_delete,
    )
    monkeypatch.setattr(
        "backend.utils.dashvector_client.dashvector_client.list_by_filter",
        _mock_list_by_filter,
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
async def test_create_character_global_upserts_dashvector(client: AsyncClient):
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    resp = await client.post(
        "/api/admin/character-knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": MEMORY_TYPE_CHARACTER_GLOBAL,
            "key": _SAMPLE_KEY,
            "value": "长发，气质温柔",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["doc_id"] == _DOC_ID
    assert body["data"]["key"] == _SAMPLE_KEY
    assert _DOC_ID in _STORE
    assert _STORE[_DOC_ID]["fields"]["stable_key"] == _SAMPLE_KEY
    assert f"{_SAMPLE_KEY}：长发，气质温柔" == _STORE[_DOC_ID]["content"]


@pytest.mark.asyncio
async def test_two_layer_key_rejected(client: AsyncClient):
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    resp = await client.post(
        "/api/admin/character-knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": MEMORY_TYPE_CHARACTER_GLOBAL,
            "key": "外貌-体态",
            "value": "合法内容",
        },
    )
    data = resp.json()
    assert data["code"] == ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID
    assert not _STORE


@pytest.mark.asyncio
async def test_update_value_reembeds_and_overwrites(client: AsyncClient):
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    await client.post(
        "/api/admin/character-knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": MEMORY_TYPE_CHARACTER_GLOBAL,
            "key": _SAMPLE_KEY,
            "value": "旧描述",
        },
    )

    with patch(
        "backend.services.embedding_service.embedding_service.get_embedding",
        new_callable=AsyncMock,
    ) as mock_emb:
        mock_emb.return_value = _FAKE_VECTOR
        resp = await client.put(
            f"/api/admin/character-knowledge/{_DOC_ID}",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "新描述内容"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        mock_emb.assert_awaited_once_with("新描述内容")

    assert _STORE[_DOC_ID]["content"] == f"{_SAMPLE_KEY}：新描述内容"
    assert _STORE[_DOC_ID]["fields"]["stable_key"] == _SAMPLE_KEY


@pytest.mark.asyncio
async def test_key_over_20_cjk_rejected(client: AsyncClient):
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    long_key = "测-" + "试-" + "段" * 19
    resp = await client.post(
        "/api/admin/character-knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": MEMORY_TYPE_CHARACTER_GLOBAL,
            "key": long_key,
            "value": "合法内容",
        },
    )
    data = resp.json()
    assert data["code"] == ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG
    assert not _STORE


@pytest.mark.asyncio
async def test_delete_then_not_found(client: AsyncClient):
    await _create_admin(_SUPER_ADMIN_USER, _SUPER_ADMIN_PASS, "super_admin")
    token = await _login_token(client, _SUPER_ADMIN_USER, _SUPER_ADMIN_PASS)

    await client.post(
        "/api/admin/character-knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": MEMORY_TYPE_CHARACTER_GLOBAL,
            "key": _SAMPLE_KEY,
            "value": "待删除",
        },
    )
    del_resp = await client.delete(
        f"/api/admin/character-knowledge/{_DOC_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.json()["code"] == 0
    assert _DOC_ID not in _STORE

    from backend.services.character_knowledge_service import character_knowledge_service

    exists = await character_knowledge_service.doc_exists(_DOC_ID)
    assert exists is False


@pytest.mark.asyncio
async def test_ops_admin_forbidden(client: AsyncClient):
    await _create_admin(_OPS_ADMIN_USER, _OPS_ADMIN_PASS, "ops_admin")
    token = await _login_token(client, _OPS_ADMIN_USER, _OPS_ADMIN_PASS)

    resp = await client.get(
        "/api/admin/character-knowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
