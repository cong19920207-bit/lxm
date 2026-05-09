# -*- coding: utf-8 -*-
# STEP-026：Step5 / Step5.5 模板校验、热加载与总开关行为（无网络/Tiktoken 依赖）

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.prompt_builder import PromptBuilder, SYSTEM_PROMPT_TEXT
from backend.services.step5_5_prompt_fragments import (
    get_default_step5_5_fragments,
    validate_step5_5_fragments_dict,
    validate_step5_system_content,
)
from backend.services.step5_5_service import (
    STEP5_5_SWITCH_CONFIG_KEY,
    should_trigger_step5_5,
)


def test_validate_step5_system_ok():
    assert validate_step5_system_content(SYSTEM_PROMPT_TEXT) is None


def test_validate_step5_system_missing_field():
    err = validate_step5_system_content("hello")
    assert err is not None


def test_validate_step5_5_fragments_ok():
    d = get_default_step5_5_fragments()
    assert validate_step5_5_fragments_dict(d) is None


def test_validate_step5_5_fragments_missing_placeholder():
    d = get_default_step5_5_fragments()
    d = dict(d)
    d["ctx_readonly"] = d["ctx_readonly"].replace("{{INNER_MONOLOGUE}}", "")
    assert validate_step5_5_fragments_dict(d) is not None


@pytest.mark.asyncio
async def test_step5_system_hot_load_from_admin_config():
    """发布后运行时读取 admin_config step5_system_prompt → System 模块正文变化"""
    custom_system = SYSTEM_PROMPT_TEXT + "\n标记STEP026TEST"

    builder = PromptBuilder(db=AsyncMock())
    with patch(
        "backend.services.prompt_builder.admin_config_service.get_active_config",
        new_callable=AsyncMock,
        return_value={"content": custom_system},
    ):
        raw = await builder._load_step5_system_template_raw()
    assert "STEP026TEST" in raw


@pytest.mark.asyncio
async def test_switch_off_skips_step5_5_trigger():
    """总开关关闭 → should_trigger_step5_5 为 False"""
    with patch(
        "backend.services.step5_5_service.admin_config_service.get_active_config",
        new_callable=AsyncMock,
        return_value=False,
    ):
        assert await should_trigger_step5_5("是", _rand_a=0.0, _rand_b=0.0) is False


@pytest.mark.asyncio
async def test_switch_key_constant():
    assert STEP5_5_SWITCH_CONFIG_KEY == "step5_5_enabled"
