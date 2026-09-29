"""AC76: a published daily quota change must affect the next call today."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

pytest_plugins = ["tests.test_realtime_voice_step006_capability_control"]

from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY, VOICE_CALL_MASTER_SWITCH_KEY
from backend.routers import realtime_voice as voice_router
from backend.models.realtime_voice import VoiceCall, VoiceQuotaAccount, VoiceUsageLedger
from backend.models.user import User
from backend.models.admin_config import AdminConfig
from backend.services.realtime_voice_config_service import realtime_voice_config_service
from backend.services.realtime_voice_create_service import VoiceCreateService, VoicePreflightError
from backend.services.realtime_voice_quota_service import ConnectedMeter, VoiceQuotaService
from backend.services.realtime_voice_runtime_config_service import RealtimeVoiceRuntimeConfigService
from backend.services.realtime_voice_ticket_service import VoiceTicketCodec
from tests import test_realtime_voice_step006_capability_control as control


class Cache:
    async def get(self, _key):
        return None


class Metrics:
    async def emit_many(self, _events):
        return None


class Leases:
    async def check_new_dial(self, _user_id):
        return False

    async def acquire(self, **_kwargs):
        return True, "acquired"

    async def release(self, **_kwargs):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("used,previous_remaining,expected_remaining", [
    (0, 300, 600),
    (100, 200, 500),
    (300, 0, 300),
])
async def test_published_daily_increase_applies_to_next_call_with_same_day_account(
    database, monkeypatch, used, previous_remaining, expected_remaining,
):
    now = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
    config = control._default_config()
    config["global"]["enabled"] = True
    config["global"]["rollout"] = {"mode": "allowlist", "user_ids": [1]}
    await control._insert_voice_config(config)
    async with control.session_factory() as db:
        db.add(User(id=1, username="quota-publish-acceptance", password_hash="not-a-login"))
        db.add(AdminConfig(config_key="crisis_keywords", config_value='["fixture-only-keyword"]',
                           version=1, is_active=True, is_draft=False))
        db.add(AdminConfig(config_key=VOICE_CALL_MASTER_SWITCH_KEY,
                           config_value='{"enabled":true}', version=1,
                           is_active=True, is_draft=False))
        db.add(VoiceQuotaAccount(
            user_id=1,
            free_quota_date=now.astimezone(ZoneInfo("Asia/Shanghai")).date(),
            free_remaining_seconds=previous_remaining,
            extra_remaining_seconds=0,
            version=1,
        ))
        if used:
            old_call_id = str(uuid4())
            db.add(VoiceCall(
                call_id=old_call_id,
                user_id=1,
                initiated_by="user",
                status="ended",
                summary_status="not_applicable",
                config_snapshot={},
                capability_snapshot={},
                transcript_retention_days=180,
                generated_retention_days=30,
            ))
            db.add(VoiceUsageLedger(
                call_id=old_call_id,
                segment_seq=1,
                quota_date=now.astimezone(ZoneInfo("Asia/Shanghai")).date(),
                usage_type="connected",
                duration_seconds=used,
                free_seconds_used=used,
                extra_seconds_used=0,
            ))
        await db.commit()

    async def redis_provider():
        return control.fake_redis

    loader = RealtimeVoiceRuntimeConfigService(
        redis_provider=redis_provider,
        session_factory=control.session_factory,
    )
    old_snapshot = (await loader.load_bundle(user_id=1)).build_snapshot(user_id=1, now=now)
    assert old_snapshot.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"] == 300
    async with control.session_factory() as db:
        original = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
        assert original.free_remaining_seconds == previous_remaining

    quota = deepcopy(config["quota"])
    quota["daily_free_seconds"] = 600
    async with control.session_factory() as db:
        saved = await realtime_voice_config_service.save_draft_section(
            db,
            config_key=VOICE_CALL_CONFIG_KEY,
            section="quota",
            base_version=1,
            draft_revision=None,
            content=quota,
            admin_user=await control._admin(db, "tech_ops"),
        )
        await db.commit()
    assert saved["draft_revision"] == 1
    async with control.session_factory() as db:
        published = await realtime_voice_config_service.publish(
            db,
            config_key=VOICE_CALL_CONFIG_KEY,
            confirm_text="CONFIRM",
            change_note="隔离验收：日配额300升至600",
            admin_user=await control._admin(db, "tech_ops"),
        )
        await db.commit()
    assert published["version"] == 2
    new_snapshot = (await loader.load_bundle(user_id=1)).build_snapshot(user_id=1, now=now)
    assert new_snapshot.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"] == 600
    assert old_snapshot.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"] == 300
    monkeypatch.setattr(voice_router, "realtime_voice_runtime_config_service", loader)
    monkeypatch.setattr(voice_router, "datetime", SimpleNamespace(now=lambda _tz: now))
    async with control.session_factory() as db:
        balance = await VoiceQuotaService().balance(
            db, 1, daily_seconds=600, now=now, published_config=True,
        )
        assert balance.free == expected_remaining
        assert (await voice_router.quota(user_id=1, db=db))["data"]["remaining_seconds"] == expected_remaining
        account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
        assert account.free_remaining_seconds == previous_remaining  # Read remains read-only.

    async def healthy(_config):
        return True

    service = VoiceCreateService(
        loader=loader,
        cache=Cache(),
        leases=Leases(),
        ticket_codec=VoiceTicketCodec(b"step038-isolated-ticket-key-material"),
        provider_preflight=healthy,
        metrics=Metrics(),
        metric=lambda *_args: None,
    )
    async with control.session_factory() as db:
        created = await service.create(
            db,
            user_id=1,
            idempotency_key=str(uuid4()),
            payload={
                "source": "home",
                "device_id": str(uuid4()),
                "browser_supported": True,
                "microphone_granted": True,
            },
            now=now,
        )
    assert created["call_id"]
    async with control.session_factory() as db:
        account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
        assert account.free_remaining_seconds == expected_remaining
        created_call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == created["call_id"]))
        assert created_call.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"] == 600
        created_call.status = "connected"
        meter = ConnectedMeter(created["call_id"], 1, 600, 30)
        quota_service = VoiceQuotaService(metric=lambda *_args: None)
        await quota_service.observe(db, meter, connected=True, monotonic=0, now=now)
        await quota_service.observe(db, meter, connected=False, monotonic=20, now=now + timedelta(seconds=20))
        await quota_service.settle(db, meter)
        created_call.status = "ended"
        await db.commit()
        assert account.free_remaining_seconds == expected_remaining - 20

    async with control.session_factory() as db:
        rolled_back = await realtime_voice_config_service.rollback(
            db,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=1,
            confirm_text="CONFIRM",
            change_note="隔离验收：日配额回滚至300",
            admin_user=await control._admin(db, "tech_ops"),
        )
        await db.commit()
    assert rolled_back["version"] == 3
    rolled_back_snapshot = (await loader.load_bundle(user_id=1)).build_snapshot(user_id=1, now=now)
    assert rolled_back_snapshot.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"] == 300
    assert new_snapshot.config_snapshot["resolved_config"]["quota"]["daily_free_seconds"] == 600
    expected_after_rollback = max(0, 300 - used - 20)
    async with control.session_factory() as db:
        balance = await VoiceQuotaService().balance(db, 1, daily_seconds=300, now=now,
                                                    published_config=True)
        assert balance.free == expected_after_rollback
        previous = (await db.scalar(select(VoiceQuotaAccount).where(
            VoiceQuotaAccount.user_id == 1))).free_remaining_seconds
        assert previous == expected_remaining - 20
    async with control.session_factory() as db:
        if expected_after_rollback:
            next_call = await service.create(
                db, user_id=1, idempotency_key=str(uuid4()),
                payload={"source": "home", "device_id": str(uuid4()),
                         "browser_supported": True, "microphone_granted": True}, now=now,
            )
            assert next_call["call_id"]
            account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
            assert account.free_remaining_seconds == expected_after_rollback
        else:
            with pytest.raises(VoicePreflightError, match="quota_empty"):
                await service.create(
                    db, user_id=1, idempotency_key=str(uuid4()),
                    payload={"source": "home", "device_id": str(uuid4()),
                             "browser_supported": True, "microphone_granted": True}, now=now,
                )
            account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
            assert account.free_remaining_seconds == previous


@pytest.mark.asyncio
async def test_published_daily_decrease_preserves_extra_and_never_overcredits(database):
    now = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
    day = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    old_call_id = str(uuid4())
    async with control.session_factory() as db:
        db.add(User(id=1, username="quota-decrease-acceptance", password_hash="not-a-login"))
        db.add(VoiceQuotaAccount(user_id=1, free_quota_date=day,
                                 free_remaining_seconds=200, extra_remaining_seconds=40, version=1))
        db.add(VoiceCall(call_id=old_call_id, user_id=1, initiated_by="user", status="ended",
                         summary_status="not_applicable", config_snapshot={}, capability_snapshot={},
                         transcript_retention_days=180, generated_retention_days=30))
        db.add(VoiceUsageLedger(call_id=old_call_id, segment_seq=1, quota_date=day,
                                usage_type="connected", duration_seconds=100,
                                free_seconds_used=100, extra_seconds_used=0))
        await db.commit()
    async with control.session_factory() as db:
        quota = VoiceQuotaService()
        balance = await quota.balance(db, 1, daily_seconds=50, now=now, lock=True,
                                      published_config=True)
        assert (balance.free, balance.extra) == (0, 40)
        account = await db.scalar(select(VoiceQuotaAccount).where(VoiceQuotaAccount.user_id == 1))
        assert account.free_remaining_seconds == 200
        await quota.apply_published_balance(db, 1, now=now, free_remaining=balance.free)
        await db.commit()
        assert (account.free_remaining_seconds, account.extra_remaining_seconds) == (0, 40)
        raised = await quota.balance(db, 1, daily_seconds=300, now=now, published_config=True)
        assert (raised.free, raised.extra) == (200, 40)
