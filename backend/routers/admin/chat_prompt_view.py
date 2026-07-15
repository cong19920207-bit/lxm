# -*- coding: utf-8 -*-
# 对话流 Prompt 只读 API：Step1.5 / Step3 / Step8 / Agent P0～P4（无草稿、无发布）

from fastapi import APIRouter, Depends

from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services.chat_prompt_view_service import (
    get_agent_prompt_view,
    get_step3_prompt_view,
    get_step8_prompt_view,
    get_step15_prompt_view,
)
from backend.utils.admin_auth import get_current_admin, require_role

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")


@router.get(
    "/chat-prompt-view/step15",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def view_step15_prompt(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """只读：Step1.5 查询重写 Prompt 模板。"""
    return ApiResponse.ok(data=get_step15_prompt_view())


@router.get(
    "/chat-prompt-view/step3",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def view_step3_prompt(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """只读：Step3 Prompt 拼装规则与硬编码文案。"""
    return ApiResponse.ok(data=get_step3_prompt_view())


@router.get(
    "/chat-prompt-view/step8",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def view_step8_prompt(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """只读：Step8 Future【主动发起】模板。"""
    return ApiResponse.ok(data=get_step8_prompt_view())


@router.get(
    "/chat-prompt-view/agent",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def view_agent_prompt(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """只读：Agent P0～P4 任务指令。"""
    return ApiResponse.ok(data=get_agent_prompt_view())
