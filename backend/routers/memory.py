# -*- coding: utf-8 -*-
# 记忆相关 API：列表查询、编辑、删除、手动添加

import logging

from fastapi import APIRouter, Depends, Query

from backend.constants import ERR_MEMORY_NOT_FOUND, ERR_PARAM_INVALID
from backend.schemas.common import ApiResponse
from backend.schemas.memory import MemoryAddRequest, MemoryUpdateRequest
from backend.services.memory_service import memory_service
from backend.utils.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["记忆"])


@router.get("/list")
async def get_memory_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
):
    """获取我的记忆列表"""
    data = await memory_service.get_user_memories(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(data=data)


@router.put("/{memory_id}")
async def update_memory(
    memory_id: int,
    req: MemoryUpdateRequest,
    user_id: int = Depends(get_current_user),
):
    """编辑单条记忆"""
    if not req.content.strip():
        return ApiResponse.fail(code=ERR_PARAM_INVALID, message="记忆内容不能为空")

    success = await memory_service.update_memory(
        memory_id=memory_id,
        user_id=user_id,
        new_content=req.content.strip(),
    )
    if not success:
        return ApiResponse.fail(code=ERR_MEMORY_NOT_FOUND)
    return ApiResponse.ok()


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    user_id: int = Depends(get_current_user),
):
    """删除单条记忆"""
    success = await memory_service.delete_memory(
        memory_id=memory_id,
        user_id=user_id,
    )
    if not success:
        return ApiResponse.fail(code=ERR_MEMORY_NOT_FOUND)
    return ApiResponse.ok()


@router.post("/add")
async def add_memory(
    req: MemoryAddRequest,
    user_id: int = Depends(get_current_user),
):
    """手动添加记忆（来源标记为 manual）"""
    if not req.content.strip():
        return ApiResponse.fail(code=ERR_PARAM_INVALID, message="记忆内容不能为空")

    data = await memory_service.add_memory_manual(
        user_id=user_id,
        content=req.content.strip(),
    )
    return ApiResponse.ok(data=data)
