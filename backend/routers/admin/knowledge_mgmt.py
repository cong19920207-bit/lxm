# -*- coding: utf-8 -*-
# 角色知识库管理：character_global / character_knowledge DashVector CRUD（R-L1L3-20）

import logging
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERROR_MESSAGES
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services.character_knowledge_service import character_knowledge_service
from backend.utils.admin_auth import get_current_admin, log_operation, require_role

logger = logging.getLogger(__name__)

router = APIRouter()
_ALLOWED_ROLES = ("super_admin", "ai_trainer")


class CharacterKnowledgeCreateRequest(BaseModel):
    type: str = Field(..., description="character_global 或 character_knowledge")
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class CharacterKnowledgeUpdateRequest(BaseModel):
    value: str = Field(..., min_length=1)


def _fail_from_service(result: dict):
    code = result.get("error_code")
    message = result.get("message") or ADMIN_ERROR_MESSAGES.get(code, "操作失败")
    return ApiResponse.fail(code, message=message)


@router.get(
    "/character-knowledge",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def list_character_knowledge(
    type: Optional[str] = Query(None, alias="type", description="类型筛选"),
    keyword: Optional[str] = Query(None, description="key 或 value 子串"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """分页列出角色知识库条目（含 Step6 写入的同 type 数据）。"""
    result = await character_knowledge_service.list_entries(
        memory_type=type,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    if "error_code" in result:
        return _fail_from_service(result)
    return ApiResponse.ok(data=result)


@router.post(
    "/character-knowledge",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def create_character_knowledge(
    body: CharacterKnowledgeCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """新增条目：Embedding(value) 后 upsert DashVector。"""
    result = await character_knowledge_service.create_entry(
        memory_type=body.type.strip(),
        key=body.key.strip(),
        value=body.value.strip(),
    )
    if "error_code" in result:
        return _fail_from_service(result)

    entry = result["data"]
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="character_knowledge",
        action="create",
        target_description=f"新增 {entry['type']} key={entry['key']}",
        request=request,
    )
    return ApiResponse.ok(data=entry)


@router.put(
    "/character-knowledge/{doc_id:path}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_character_knowledge(
    doc_id: str,
    body: CharacterKnowledgeUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新 value（key 不可改），重新 Embedding 并覆盖。"""
    doc_id = unquote(doc_id)
    result = await character_knowledge_service.update_entry(
        doc_id=doc_id,
        value=body.value.strip(),
    )
    if "error_code" in result:
        return _fail_from_service(result)

    entry = result["data"]
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="character_knowledge",
        action="update",
        target_description=f"更新 {entry['type']} key={entry['key']}",
        request=request,
    )
    return ApiResponse.ok(data=entry)


@router.delete(
    "/character-knowledge/{doc_id:path}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def delete_character_knowledge(
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """从 DashVector 删除指定 doc_id。"""
    doc_id = unquote(doc_id)
    result = await character_knowledge_service.delete_entry(doc_id)
    if "error_code" in result:
        return _fail_from_service(result)

    await log_operation(
        db=db,
        admin_user=admin_user,
        module="character_knowledge",
        action="delete",
        target_description=f"删除 doc_id={doc_id}",
        request=request,
    )
    return ApiResponse.ok(data=result["data"])
