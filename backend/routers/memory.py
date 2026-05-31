# -*- coding: utf-8 -*-
# 记忆相关 API：只读列表查询（Step6 user 向量 KV）
# C-05：H5 写路由（PUT/DELETE/POST）已删除，memory.html 改为只读。

import logging

from fastapi import APIRouter, Depends, Query

from backend.constants import MEMORY_TYPE_USER
from backend.schemas.common import ApiResponse
from backend.services.user_vector_memory_service import user_vector_memory_service
from backend.utils.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["记忆"])


@router.get("/list")
async def get_memory_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
):
    """
    获取我的记忆列表（只读）。

    数据源改为 Step6 写入的 user 向量（cap=USER_LIST_TOPK=500），
    响应 `{total, page, page_size, list:[{doc_id, key, value, content}]}`，
    不再返回 importance_score / source / id；total 为 cap 内条数（P9）。
    不对 `mem_*` 做运行时过滤（P1，靠 M2 人工清理）。
    """
    data = await user_vector_memory_service.list_entries(
        memory_type=MEMORY_TYPE_USER,
        user_id=user_id,
        keyword=None,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(data=data)
