# -*- coding: utf-8 -*-
"""STEP-001: ADMIN_JWT_SECRET 配置读取与 lifespan 双守卫。"""

from unittest.mock import AsyncMock
import importlib

import pytest

import backend.config as config
import backend.main as main


INVALID_SECRETS = [None, "", "   ", "admin_secret_change_me", "your_admin_jwt_secret_here"]


def _set_admin_secret(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("ADMIN_JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("ADMIN_JWT_SECRET", value)


@pytest.mark.parametrize("value", INVALID_SECRETS)
def test_config_reader_rejects_missing_blank_and_placeholders(monkeypatch, value):
    _set_admin_secret(monkeypatch, value)

    with pytest.raises(ValueError, match="ADMIN_JWT_SECRET"):
        config.get_admin_jwt_secret()


def test_config_reader_accepts_custom_secret_without_extra_policy(monkeypatch):
    _set_admin_secret(monkeypatch, "custom-secret")

    assert config.get_admin_jwt_secret() == "custom-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize("value", INVALID_SECRETS)
async def test_lifespan_rejects_same_invalid_values_before_startup(monkeypatch, value):
    _set_admin_secret(monkeypatch, value)
    create_tables = AsyncMock()
    monkeypatch.setattr(main, "create_all_tables", create_tables)

    with pytest.raises(ValueError, match="ADMIN_JWT_SECRET"):
        async with main.lifespan(main.app):
            pass

    create_tables.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_accepts_custom_secret_and_reuses_config_validator(monkeypatch):
    _set_admin_secret(monkeypatch, "custom-secret")
    calls: list[str] = []
    real_validator = config.validate_admin_jwt_secret

    def tracking_validator(value=None):
        calls.append("validate")
        return real_validator(value)

    monkeypatch.setattr(config, "validate_admin_jwt_secret", tracking_validator)
    monkeypatch.setattr(config, "validate_open_api_pepper_on_startup", lambda: None)
    monkeypatch.setattr(config, "warn_deepseek_config_on_startup", lambda: None)
    monkeypatch.setattr(main, "create_all_tables", AsyncMock())

    diary_rules_loader = importlib.import_module("backend.services.diary_rules_loader")
    scheduler = importlib.import_module("backend.tasks.scheduler")

    monkeypatch.setattr(
        diary_rules_loader,
        "get_scheduled_diary_cron_times",
        AsyncMock(return_value=(2, 0)),
    )
    monkeypatch.setattr(scheduler, "start_scheduler", lambda **_kwargs: None)
    monkeypatch.setattr(scheduler, "shutdown_scheduler", lambda: None)

    async with main.lifespan(main.app):
        pass

    assert calls == ["validate"]
