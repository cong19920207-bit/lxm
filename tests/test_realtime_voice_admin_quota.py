"""Admin grants for the P1 voice extra-time pool."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.models  # noqa: F401 - register metadata
from backend.config import get_mysql_url
from backend.database import Base
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.realtime_voice import VoiceCall, VoiceQuotaAccount, VoiceUsageLedger
from backend.models.user import User
from backend.services.realtime_voice_quota_service import QuotaError, VoiceQuotaService
from backend.utils.admin_auth import get_current_admin
from backend.database import get_db


NOW = datetime(2026, 9, 27, 4, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, VoiceCall.__table__, VoiceQuotaAccount.__table__,
                    VoiceUsageLedger.__table__, AdminOperationLog.__table__],
        )
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id=1, username="voice-grant", password_hash="unused"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_grant_creates_extra_pool_without_consuming_daily_free_pool(db):
    result = await VoiceQuotaService().grant_extra(
        db, 1, seconds=300, expected_version=0, daily_seconds=300, now=NOW,
    )
    await db.commit()

    account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
    assert result == {"free_remaining_seconds": 300, "extra_remaining_seconds": 300,
                      "remaining_seconds": 600, "version": 1}
    assert account.free_quota_date == NOW.date()
    assert account.free_remaining_seconds == 300
    assert account.extra_remaining_seconds == 300


@pytest.mark.asyncio
async def test_grant_preserves_used_free_balance_and_replay_cannot_grant_twice(db):
    db.add(VoiceQuotaAccount(user_id=1, free_quota_date=NOW.date(),
                             free_remaining_seconds=0, extra_remaining_seconds=20, version=4))
    await db.commit()
    service = VoiceQuotaService()

    result = await service.grant_extra(db, 1, seconds=300, expected_version=4,
                                       daily_seconds=300, now=NOW)
    await db.commit()
    assert result["extra_remaining_seconds"] == 320
    assert result["free_remaining_seconds"] == 0
    with pytest.raises(QuotaError, match="quota_admin_version_conflict"):
        await service.grant_extra(db, 1, seconds=300, expected_version=4,
                                  daily_seconds=300, now=NOW)
    await db.rollback()
    account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
    assert account.extra_remaining_seconds == 320
    assert account.version == 5


@pytest.mark.asyncio
async def test_grant_extra_pool_survives_shanghai_midnight(db):
    await VoiceQuotaService().grant_extra(db, 1, seconds=300, expected_version=0,
                                          daily_seconds=300, now=NOW)
    await db.commit()

    next_day = NOW + timedelta(days=1)
    balance = await VoiceQuotaService().balance(db, 1, daily_seconds=300, now=next_day)
    assert (balance.free, balance.extra, balance.total) == (300, 300, 600)


@pytest.mark.asyncio
async def test_first_grant_waits_until_an_active_call_has_settled(db):
    db.add(VoiceCall(call_id=str(uuid4()), user_id=1, initiated_by="user", status="connected",
                     summary_status="pending", config_snapshot={}, capability_snapshot={},
                     transcript_retention_days=180, generated_retention_days=30))
    await db.commit()

    with pytest.raises(QuotaError, match="quota_admin_active_call"):
        await VoiceQuotaService().grant_extra(db, 1, seconds=300, expected_version=0,
                                               daily_seconds=300, now=NOW)
    await db.rollback()
    assert await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1)) is None


@pytest.mark.asyncio
async def test_first_grant_detects_call_created_after_mysql_snapshot():
    if not os.getenv("MYSQL_DATABASE", "").startswith("lxm_voice_quota_test_"):
        pytest.skip("requires an isolated lxm_voice_quota_test_ database")
    engine = create_async_engine(get_mysql_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[
                User.__table__, VoiceCall.__table__, VoiceQuotaAccount.__table__,
                VoiceUsageLedger.__table__,
            ])
        async with sessions() as seed:
            user = User(username="quota-" + uuid4().hex[:8], password_hash="unused")
            seed.add(user)
            await seed.commit()
            user_id = user.id

        async with sessions() as admin, sessions() as caller:
            # Authentication's ordinary SELECT fixes an old MySQL RR snapshot.
            assert await admin.scalar(select(User.id).where(User.id == user_id)) == user_id
            caller.add(VoiceCall(call_id=str(uuid4()), user_id=user_id, initiated_by="user",
                                 status="connected", summary_status="pending",
                                 config_snapshot={}, capability_snapshot={},
                                 transcript_retention_days=180, generated_retention_days=30))
            await caller.commit()
            with pytest.raises(QuotaError, match="quota_admin_active_call"):
                await VoiceQuotaService().grant_extra(
                    admin, user_id, seconds=300, expected_version=0, daily_seconds=300, now=NOW,
                )
            await admin.rollback()
            assert await admin.scalar(select(VoiceQuotaAccount).where(
                VoiceQuotaAccount.user_id == user_id)) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds", [0, -1, True, 86401])
async def test_grant_rejects_invalid_amount_without_creating_an_account(db, seconds):
    with pytest.raises(QuotaError, match="quota_admin_amount_invalid"):
        await VoiceQuotaService().grant_extra(db, 1, seconds=seconds, expected_version=0,
                                               daily_seconds=300, now=NOW)
    await db.rollback()
    assert await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1)) is None


@pytest.mark.asyncio
async def test_grant_rejects_balance_overflow_without_mutation(db):
    db.add(VoiceQuotaAccount(user_id=1, free_quota_date=NOW.date(),
                             free_remaining_seconds=0, extra_remaining_seconds=2_147_483_600,
                             version=1))
    await db.commit()

    with pytest.raises(QuotaError, match="quota_admin_balance_overflow"):
        await VoiceQuotaService().grant_extra(db, 1, seconds=100, expected_version=1,
                                               daily_seconds=300, now=NOW)
    await db.rollback()
    account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
    assert (account.extra_remaining_seconds, account.version) == (2_147_483_600, 1)


@pytest.mark.asyncio
async def test_admin_quota_route_grants_once_and_audits_in_same_transaction(db):
    from backend.routers.admin import voice_quota as routes

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/admin/voice")

    def admin_dep():
        return SimpleNamespace(id=7, username="operator", role="ops_admin")

    async def db_dep():
        yield db

    async def daily_dep(user_id: int):
        return 300

    app.dependency_overrides[get_current_admin] = admin_dep
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[routes.get_daily_seconds] = daily_dep
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/api/admin/voice/users/1/quota")
        assert initial.status_code == 200
        assert initial.json()["data"] == {
            "quota_date": "2026-09-27", "daily_free_seconds": 300,
            "free_remaining_seconds": 300, "extra_remaining_seconds": 0,
            "remaining_seconds": 300, "version": 0,
        }
        body = {"seconds": 300, "expected_version": 0}
        granted = await client.post("/api/admin/voice/users/1/quota/extra", json=body)
        repeated = await client.post("/api/admin/voice/users/1/quota/extra", json=body)

    assert granted.status_code == 200
    assert granted.json()["data"]["extra_remaining_seconds"] == 300
    assert repeated.status_code == 409
    account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
    logs = (await db.scalars(select(AdminOperationLog))).all()
    assert account.extra_remaining_seconds == 300
    assert len(logs) == 1
    assert logs[0].admin_username == "operator"
    assert "300" in logs[0].target_description


@pytest.mark.asyncio
async def test_admin_grant_rolls_back_when_audit_write_fails(db, monkeypatch):
    from backend.routers.admin import voice_quota as routes

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/admin/voice")

    def admin_dep():
        return SimpleNamespace(id=7, username="operator", role="ops_admin")

    async def db_dep():
        yield db

    async def daily_dep(user_id: int):
        return 300

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    app.dependency_overrides[get_current_admin] = admin_dep
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[routes.get_daily_seconds] = daily_dep
    monkeypatch.setattr(routes, "log_operation", fail_audit)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                           base_url="http://test") as client:
        response = await client.post("/api/admin/voice/users/1/quota/extra",
                                     json={"seconds": 300, "expected_version": 0})

    assert response.status_code == 500
    assert await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role,allowed", [("super_admin", True), ("ops_admin", True),
                                          ("observer", False), ("tech_ops", False),
                                          ("ai_trainer", False)])
async def test_admin_quota_write_roles(db, role, allowed):
    from backend.routers.admin import voice_quota as routes

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/admin/voice")

    def admin_dep():
        return SimpleNamespace(id=7, username=role, role=role)

    async def db_dep():
        yield db

    async def daily_dep(user_id: int):
        return 300

    app.dependency_overrides[get_current_admin] = admin_dep
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[routes.get_daily_seconds] = daily_dep
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/admin/voice/users/1/quota/extra",
                                     json={"seconds": 300, "expected_version": 0})
    assert response.status_code == (200 if allowed else 403)


def test_admin_quota_routes_are_registered_in_the_application():
    from backend.main import app

    paths = app.openapi()["paths"]
    assert "get" in paths["/api/admin/voice/users/{user_id}/quota"]
    assert "post" in paths["/api/admin/voice/users/{user_id}/quota/extra"]
