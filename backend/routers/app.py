# -*- coding: utf-8 -*-
# H5 应用只读接口：设置页等使用的公开配置片段

import re

from fastapi import APIRouter, Depends

from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.prompt_builder import DEFAULT_PERSONA
from backend.utils.auth_middleware import get_current_user

router = APIRouter(prefix="/api/app", tags=["H5应用"])


def _extract_default_background() -> str:
    """从 DEFAULT_PERSONA 提取【角色背景】段落作为兜底"""
    match = re.search(r"【角色背景】\n(.+?)(?:\n\n|$)", DEFAULT_PERSONA, re.DOTALL)
    if match:
        return match.group(1).strip()
    return (
        "来自2149年的未来AI研究员，名叫林小梦。意识因一次实验意外被困在互联网中，"
        "只能通过文字与人交流。正在努力适应这个时代，对一切都充满好奇。"
    )


@router.get("/persona-background", response_model=ApiResponse)
async def get_persona_background(user_id: int = Depends(get_current_user)):
    """获取林小梦角色背景（只读，供设置页「关于林小梦」展示）"""
    persona = await admin_config_service.get_active_config("persona")
    background = ""
    if isinstance(persona, dict):
        background = str(persona.get("background", "")).strip()
    if not background:
        background = _extract_default_background()
    return ApiResponse.ok(data={"background": background})
