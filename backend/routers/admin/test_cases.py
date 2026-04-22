# -*- coding: utf-8 -*-
# 测试用例管理接口：查看、添加、删除测试用例

import json
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_TEST_CASE_MIN_RETAIN, ADMIN_ERR_TEST_CASE_NOT_FOUND
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")

_MIN_CASES_COUNT = 5


# ──────────────────── 请求模型 ────────────────────

class TestCaseCreateRequest(BaseModel):
    input: str = Field(..., min_length=1)
    expected_pass_criteria: str = Field(..., min_length=1)
    emotion_label: str = Field("平静")
    relationship_level: int = Field(1, ge=0, le=3)


# ──────────────────── 辅助函数 ────────────────────

def _make_config_key(config_key: str) -> str:
    """将目标 config_key 转为测试用例的存储 key"""
    return f"test_cases:{config_key}"


# ──────────────────── 接口 ────────────────────

@router.get(
    "/test-cases/{config_key}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_test_cases(
    config_key: str,
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取指定 config_key 的测试用例列表"""
    store_key = _make_config_key(config_key)
    data = await admin_config_service.get_active_config(store_key)

    if data is None:
        cases = []
    elif isinstance(data, list):
        cases = data
    elif isinstance(data, str):
        try:
            cases = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            cases = []
    else:
        cases = []

    return ApiResponse.ok(data=cases)


@router.post(
    "/test-cases/{config_key}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def create_test_case(
    config_key: str,
    body: TestCaseCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """添加测试用例"""
    store_key = _make_config_key(config_key)

    # 读取现有用例
    existing = await admin_config_service.get_active_config(store_key)
    if isinstance(existing, list):
        cases = existing
    elif isinstance(existing, str):
        try:
            cases = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            cases = []
    else:
        cases = []

    # 生成新 id（max_id + 1）
    max_id = 0
    for c in cases:
        cid = c.get("id", 0)
        if isinstance(cid, int) and cid > max_id:
            max_id = cid

    new_case = {
        "id": max_id + 1,
        "input": body.input,
        "expected_pass_criteria": body.expected_pass_criteria,
        "emotion_label": body.emotion_label,
        "relationship_level": body.relationship_level,
    }
    cases.append(new_case)

    # 保存更新后的用例列表
    config_value = json.dumps(cases, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key=store_key,
        config_value=config_value,
        admin_user=admin_user,
        request=request,
        target_description=f"添加测试用例 #{new_case['id']}（{store_key}）",
    )

    return ApiResponse.ok(data={
        "case": new_case,
        "total_count": len(cases),
        **result,
    })


@router.delete(
    "/test-cases/{config_key}/{case_id}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def delete_test_case(
    config_key: str,
    case_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """删除测试用例（至少保留 5 条）"""
    store_key = _make_config_key(config_key)

    # 读取现有用例
    existing = await admin_config_service.get_active_config(store_key)
    if isinstance(existing, list):
        cases = existing
    elif isinstance(existing, str):
        try:
            cases = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            cases = []
    else:
        cases = []

    # 最少保留 5 条
    if len(cases) <= _MIN_CASES_COUNT:
        return ApiResponse.fail(
            ADMIN_ERR_TEST_CASE_MIN_RETAIN,
            message=f"至少需要保留{_MIN_CASES_COUNT}条测试用例",
        )

    # 查找并删除
    new_cases = [c for c in cases if c.get("id") != case_id]
    if len(new_cases) == len(cases):
        return ApiResponse.fail(
            ADMIN_ERR_TEST_CASE_NOT_FOUND,
            message=f"未找到 ID 为 {case_id} 的测试用例",
        )

    # 保存
    config_value = json.dumps(new_cases, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key=store_key,
        config_value=config_value,
        admin_user=admin_user,
        request=request,
        target_description=f"删除测试用例 #{case_id}（{store_key}）",
    )

    return ApiResponse.ok(data={
        "deleted_id": case_id,
        "total_count": len(new_cases),
        **result,
    })
