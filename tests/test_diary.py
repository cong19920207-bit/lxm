# -*- coding: utf-8 -*-
# AI 日记：diary_rules_loader 单元测试 + H5/管理端 API 测试（SQLite 内存库 + 启动期打桩）

import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models  # noqa: F401 — 注册 ORM 表到 Base.metadata

from backend.database import Base, get_db

# 与 main.lifespan 中 start_scheduler(diary_hour=..., diary_minute=...) 兼容
import backend.tasks.scheduler as _sched_mod

_sched_mod.start_scheduler = lambda *a, **k: None
_sched_mod.shutdown_scheduler = lambda *a, **k: None

if "backend.tasks.scheduler" in sys.modules and sys.modules["backend.tasks.scheduler"] is not _sched_mod:
    sys.modules["backend.tasks.scheduler"] = _sched_mod

from backend.main import app  # noqa: E402
from backend.models.admin_user import AdminUser  # noqa: E402
from backend.models.ai_diary import AiDiary  # noqa: E402
from backend.models.conversation_log import ConversationLog  # noqa: E402
from backend.models.emotion_log import EmotionLog  # noqa: E402
from backend.constants import (  # noqa: E402
    ADMIN_ERR_DIARY_RULE_PARAM_INVALID,
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
    ADMIN_ERR_USER_NOT_FOUND,
    ERR_DIARY_NOT_FOUND,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine_test = create_async_engine(TEST_DB_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
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


@pytest.fixture(autouse=True)
def _patch_lifespan_for_diary(monkeypatch):
    """避免 lifespan 连真实 MySQL/Redis；并打桩用户 JWT 所需的 Redis、管理端配置读。"""
    monkeypatch.setattr("backend.main.create_all_tables", AsyncMock())

    async def _fake_schedule(*, use_cache=True):
        return (0, 15)

    monkeypatch.setattr(
        "backend.services.diary_rules_loader.get_scheduled_diary_cron_times",
        _fake_schedule,
    )

    # get_current_user 会 await get_redis().get("user_banned:…")；无 Redis 时 CI 失败
    async def _fake_get_redis():
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.set = AsyncMock(return_value=True)
        r.setex = AsyncMock(return_value=True)
        return r

    monkeypatch.setattr("backend.utils.auth_middleware.get_redis", _fake_get_redis)
    monkeypatch.setattr("backend.services.admin_config_service.get_redis", _fake_get_redis)

    # get_active_config(use_cache=True) 在缓存未命中时会走全局 async_session_maker（生产库），此处默认打桩
    monkeypatch.setattr(
        "backend.services.admin_config_service.admin_config_service.get_active_config",
        AsyncMock(return_value=None),
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


def _hash_admin_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def _create_admin_user(
    username: str,
    password: str,
    role: str,
) -> None:
    async with async_session_test() as session:
        admin = AdminUser(
            username=username,
            password_hash=_hash_admin_password(password),
            role=role,
            is_active=True,
            is_locked=False,
            login_fail_count=0,
            last_password_change_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(admin)
        await session.commit()


async def _admin_token(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post(
        "/api/admin/auth/login",
        json={"username": username, "password": password},
    )
    data = r.json()
    assert data["code"] == 0, data
    return data["data"]["token"]


async def _register_and_token(client: AsyncClient) -> tuple[int, str]:
    body = {
        "username": "diaryuser01",
        "password": "pass1234",
        "confirm_password": "pass1234",
    }
    r = await client.post("/api/auth/register", json=body)
    d = r.json()
    assert d["code"] == 0, d
    return d["data"]["user_id"], d["data"]["token"]


# ──────────────────── L1：diary_rules_loader ────────────────────


class TestDiaryRulesLoader:
    """不启动 HTTP，仅校验解析与回退。"""

    def test_legacy_generation_prompt_fills_both_templates(self):
        from backend.services.diary_rules_loader import resolve_diary_rules_dict

        raw = {
            "generation_prompt": "同一模板",
            "max_length": 150,
            "generation_hour": 2,
            "generation_minute": 15,
        }
        r = resolve_diary_rules_dict(raw)
        assert r.prompt_with_interaction == "同一模板"
        assert r.prompt_without_interaction == "同一模板"
        assert r.max_length == 150
        assert r.generation_hour == 2
        assert r.generation_minute == 15

    def test_invalid_hour_falls_back_shanghai_0_15(self):
        from backend.services.diary_rules_loader import resolve_diary_rules_dict

        raw = {
            "prompt_with_interaction": "a",
            "prompt_without_interaction": "b",
            "max_length": 100,
            "generation_hour": 99,
            "generation_minute": 0,
        }
        r = resolve_diary_rules_dict(raw)
        assert r.generation_hour == 0
        assert r.generation_minute == 15

    def test_valid_hour_22_schedule(self):
        from backend.services.diary_rules_loader import resolve_diary_rules_dict

        raw = {
            "prompt_with_interaction": "a",
            "prompt_without_interaction": "b",
            "max_length": 100,
            "generation_hour": 22,
            "generation_minute": 5,
        }
        r = resolve_diary_rules_dict(raw)
        assert r.generation_hour == 22
        assert r.generation_minute == 5


class TestShanghaiDiaryWindow:
    def test_compute_shanghai_diary_batch_window_midnight_region(self):
        """锚点 D=上海日历日，覆盖日 D-1，对话窗 naive UTC 与 [D-1 00:00, D 00:00) 上海一致。"""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from backend.services.diary_service import compute_shanghai_diary_batch_window

        fixed = datetime(2026, 5, 17, 0, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
        anchor_d, covers_d, s_utc, e_utc = compute_shanghai_diary_batch_window(fixed)
        assert anchor_d.isoformat() == "2026-05-17"
        assert covers_d.isoformat() == "2026-05-16"
        assert s_utc == datetime(2026, 5, 15, 16, 0, 0)
        assert e_utc == datetime(2026, 5, 16, 16, 0, 0)


class TestDiaryH5Api:
    """GET /api/diary/list、POST /api/diary/{id}/read"""

    @pytest.mark.asyncio
    async def test_list_empty_has_items_not_diaries(self, client: AsyncClient):
        _, token = await _register_and_token(client)
        r = await client.get(
            "/api/diary/list?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert data["code"] == 0
        assert "items" in data["data"]
        assert data["data"]["items"] == []
        assert "diaries" not in data["data"]
        assert data["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_rows_and_mark_read(self, client: AsyncClient):
        uid, token = await _register_and_token(client)
        async with async_session_test() as session:
            d1 = AiDiary(
                user_id=uid,
                content="第一条日记",
                relationship_level_at_creation=1,
                is_read=False,
            )
            session.add(d1)
            await session.commit()
            await session.refresh(d1)
            diary_id = d1.id

        r = await client.get(
            "/api/diary/list?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert data["code"] == 0
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["content"] == "第一条日记"
        assert data["data"]["items"][0]["is_read"] is False
        assert "covers_beijing_date" in data["data"]["items"][0]

        r2 = await client.post(
            f"/api/diary/{diary_id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.json()["code"] == 0

        async with async_session_test() as session:
            row = await session.get(AiDiary, diary_id)
            assert row.is_read is True

    @pytest.mark.asyncio
    async def test_mark_read_not_found(self, client: AsyncClient):
        _, token = await _register_and_token(client)
        r = await client.post(
            "/api/diary/999999/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert data["code"] == ERR_DIARY_NOT_FOUND


# ──────────────────── L2：管理端 diary-history / diary-rules ────────────────────


class TestAdminDiaryHistoryApi:
    @pytest.mark.asyncio
    async def test_super_admin_can_list(self, client: AsyncClient):
        await _create_admin_user("sudiary", "Super@Diary123!", "super_admin")
        # 用户 + 日记
        uid, _ = await _register_and_token(client)
        async with async_session_test() as session:
            session.add(
                AiDiary(
                    user_id=uid,
                    content="后台可见",
                    relationship_level_at_creation=2,
                    is_read=True,
                )
            )
            await session.commit()

        token = await _admin_token(client, "sudiary", "Super@Diary123!")
        r = await client.get(
            "/api/admin/diary-history?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert data["code"] == 0
        assert "list" in data["data"]
        assert data["data"]["total"] >= 1
        hit = [x for x in data["data"]["list"] if x.get("content") == "后台可见"]
        assert hit, "应至少有一条测试日记"
        assert hit[0].get("username") == "diaryuser01"
        assert hit[0].get("user_id") == uid
        assert "covers_beijing_date" in hit[0]

    @pytest.mark.asyncio
    async def test_ops_admin_can_list(self, client: AsyncClient):
        await _create_admin_user("opsdiary", "Ops@Diary12345!", "ops_admin")
        token = await _admin_token(client, "opsdiary", "Ops@Diary12345!")
        r = await client.get(
            "/api/admin/diary-history?page=1&page_size=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_ai_trainer_forbidden(self, client: AsyncClient):
        await _create_admin_user("aidiary", "Ai@Diary1234!", "ai_trainer")
        token = await _admin_token(client, "aidiary", "Ai@Diary1234!")
        r = await client.get(
            "/api/admin/diary-history?page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


class TestAdminUserDiariesApi:
    """GET /api/admin/users/{user_id}/diaries 与 diary-history 共用查询逻辑"""

    @pytest.mark.asyncio
    async def test_list_user_diaries_matches_diary_history(self, client: AsyncClient):
        await _create_admin_user("sudud", "Super@Dud123!!", "super_admin")
        uid, _ = await _register_and_token(client)
        async with async_session_test() as session:
            session.add(
                AiDiary(
                    user_id=uid,
                    content="详情Tab可见",
                    relationship_level_at_creation=1,
                    is_read=False,
                )
            )
            await session.commit()

        token = await _admin_token(client, "sudud", "Super@Dud123!!")
        r1 = await client.get(
            f"/api/admin/users/{uid}/diaries?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        r2 = await client.get(
            f"/api/admin/diary-history?user_id={uid}&page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        d1 = r1.json()
        d2 = r2.json()
        assert d1["code"] == 0 and d2["code"] == 0
        assert d1["data"]["total"] == d2["data"]["total"]
        assert len(d1["data"]["list"]) == len(d2["data"]["list"])
        if d1["data"]["list"]:
            a = d1["data"]["list"][0]
            b = d2["data"]["list"][0]
            assert a["id"] == b["id"]
            assert a["content"] == b["content"]
            assert a["username"] == b["username"] == "diaryuser01"

    @pytest.mark.asyncio
    async def test_user_not_found(self, client: AsyncClient):
        await _create_admin_user("sudud2", "Super@Dud223!!", "super_admin")
        token = await _admin_token(client, "sudud2", "Super@Dud223!!")
        r = await client.get(
            "/api/admin/users/999999/diaries?page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == ADMIN_ERR_USER_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bad_start_date(self, client: AsyncClient):
        await _create_admin_user("sudud3", "Super@Dud323!!", "super_admin")
        uid, _ = await _register_and_token(client)
        token = await _admin_token(client, "sudud3", "Super@Dud323!!")
        r = await client.get(
            f"/api/admin/users/{uid}/diaries?page=1&start_date=not-a-date",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == ADMIN_ERR_QUERY_DATE_FORMAT_INVALID

    @pytest.mark.asyncio
    async def test_start_after_end_fails(self, client: AsyncClient):
        await _create_admin_user("sudud4", "Super@Dud423!!", "super_admin")
        uid, _ = await _register_and_token(client)
        token = await _admin_token(client, "sudud4", "Super@Dud423!!")
        r = await client.get(
            f"/api/admin/users/{uid}/diaries?page=1&start_date=2026-06-05&end_date=2026-06-04",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == ADMIN_ERR_QUERY_DATE_FORMAT_INVALID

    @pytest.mark.asyncio
    async def test_ai_trainer_forbidden(self, client: AsyncClient):
        await _create_admin_user("aidud", "Ai@Dud1234!!", "ai_trainer")
        uid, _ = await _register_and_token(client)
        token = await _admin_token(client, "aidud", "Ai@Dud1234!!")
        r = await client.get(
            f"/api/admin/users/{uid}/diaries?page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


class TestAdminDiaryRulesApi:
    @pytest.mark.asyncio
    async def test_put_missing_prompts_fails(self, client: AsyncClient):
        await _create_admin_user("ruleadm", "Rule@Admin123!", "super_admin")
        token = await _admin_token(client, "ruleadm", "Rule@Admin123!")
        body = {
            "max_length": 150,
            "frequency": "daily",
            "generation_hour": 0,
            "generation_minute": 30,
        }
        r = await client.put(
            "/api/admin/diary-rules",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        data = r.json()
        assert data["code"] == ADMIN_ERR_DIARY_RULE_PARAM_INVALID

    @pytest.mark.asyncio
    async def test_put_success_persists_to_test_db(self, client: AsyncClient):
        """依赖 autouse 的 get_redis / get_active_config 打桩；写入经 Depends(get_db) 落在 SQLite。"""
        await _create_admin_user("ruleadm2", "Rule@Admin223!", "super_admin")
        token = await _admin_token(client, "ruleadm2", "Rule@Admin223!")
        body = {
            "prompt_with_interaction": "有互动 {{max_length}}",
            "prompt_without_interaction": "无互动 {{max_length}}",
            "max_length": 150,
            "frequency": "daily",
            "generation_hour": 1,
            "generation_minute": 0,
        }
        r = await client.put(
            "/api/admin/diary-rules",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        data = r.json()
        assert data["code"] == 0, data
        assert "version" in data["data"]

        # 写入应落在测试库 admin_config
        from backend.models.admin_config import AdminConfig

        async with async_session_test() as session:
            stmt = select(AdminConfig).where(
                AdminConfig.config_key == "diary_rules",
                AdminConfig.is_active == True,  # noqa: E712
            )
            row = (await session.execute(stmt)).scalars().first()
            assert row is not None
            assert "有互动" in (row.config_value or "")

    @pytest.mark.asyncio
    async def test_get_rules_with_stub_config(self, client: AsyncClient, monkeypatch):
        """避免 get_active_config 走真实 Redis/MySQL 连接。"""
        stub = {
            "prompt_with_interaction": "A",
            "prompt_without_interaction": "B",
            "max_length": 120,
            "generation_hour": 3,
            "generation_minute": 30,
        }
        monkeypatch.setattr(
            "backend.services.admin_config_service.admin_config_service.get_active_config",
            AsyncMock(return_value=stub),
        )
        await _create_admin_user("ruleget", "Rule@Get123!!", "ai_trainer")
        token = await _admin_token(client, "ruleget", "Rule@Get123!!")
        r = await client.get(
            "/api/admin/diary-rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["prompt_with_interaction"] == "A"
        assert data["data"]["prompt_without_interaction"] == "B"


class TestAdminUserEmotionRoundsApi:
    """GET /api/admin/users/{user_id}/emotion-rounds（V2-C，只读、按 round_id 聚合）"""

    @pytest.mark.asyncio
    async def test_super_admin_lists_round_with_conv(self, client: AsyncClient):
        await _create_admin_user("suemo", "Super@Emo123!!", "super_admin")
        uid, _ = await _register_and_token(client)
        rid = "11111111-1111-4111-8111-111111111111"
        async with async_session_test() as session:
            u1 = ConversationLog(
                user_id=uid,
                role="user",
                content="用户一句",
                sort_seq=10,
                delivery_status="delivered",
                skipped_in_prompt=False,
                round_id=rid,
            )
            session.add(u1)
            await session.flush()
            a1 = ConversationLog(
                user_id=uid,
                role="assistant",
                content="助手一句",
                sort_seq=11,
                delivery_status=None,
                skipped_in_prompt=False,
                round_id=rid,
            )
            session.add(a1)
            el = EmotionLog(
                user_id=uid,
                emotion_label="开心",
                confidence=0.88,
                conversation_id=u1.id,
                round_id=rid,
            )
            session.add(el)
            await session.commit()

        token = await _admin_token(client, "suemo", "Super@Emo123!!")
        r = await client.get(
            f"/api/admin/users/{uid}/emotion-rounds?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        d = r.json()
        assert d["code"] == 0
        assert d["data"]["total"] == 1
        row = d["data"]["list"][0]
        assert row["round_id"] == rid
        assert row["emotion_label"] == "开心"
        assert "用户一句" in row["user_text"]
        assert row["assistant_text"] == "助手一句"

    @pytest.mark.asyncio
    async def test_user_not_found(self, client: AsyncClient):
        await _create_admin_user("suemo2", "Super@Emo223!!", "super_admin")
        token = await _admin_token(client, "suemo2", "Super@Emo223!!")
        r = await client.get(
            "/api/admin/users/999999/emotion-rounds?page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == ADMIN_ERR_USER_NOT_FOUND

    @pytest.mark.asyncio
    async def test_ai_trainer_forbidden(self, client: AsyncClient):
        await _create_admin_user("aiemo", "Ai@Emo1234!!", "ai_trainer")
        uid, _ = await _register_and_token(client)
        token = await _admin_token(client, "aiemo", "Ai@Emo1234!!")
        r = await client.get(
            f"/api/admin/users/{uid}/emotion-rounds?page=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
