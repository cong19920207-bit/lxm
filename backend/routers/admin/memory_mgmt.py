# -*- coding: utf-8 -*-
# 记忆系统管理：记忆规则配置、向量数据库配置、全局记忆搜索与批量删除

import json
import logging
import random
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import (
    get_dashvector_api_key,
    get_dashvector_collection,
    get_dashvector_endpoint,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.models.memory import Memory
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID,
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID,
    ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.vector_service import vector_service
from backend.utils.admin_auth import get_current_admin, log_operation, require_role
from backend.utils.dashvector_client import dashvector_client

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")


# ──────────────────── 请求模型 ────────────────────

class ImportanceRule(BaseModel):
    type: str
    score: int


class MemoryRulesRequest(BaseModel):
    extract_prompt: str
    importance_rules: list[ImportanceRule] = Field(..., min_length=4, max_length=4)
    store_threshold: int
    search_threshold: float
    merge_threshold: float


class VectorDbConfigRequest(BaseModel):
    api_key: Optional[str] = None
    endpoint: str
    collection_name: str
    top_k: int = 5
    need_test_first: bool = False


class VectorDbTestRequest(BaseModel):
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    collection_name: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    memory_ids: list[int] = Field(..., min_length=1, max_length=100)


# ──────────────────── 1. 记忆规则 ────────────────────

@router.get(
    "/memory-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_memory_rules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的记忆规则配置"""
    config = await admin_config_service.get_active_config("memory_rules")
    return ApiResponse.ok(data=config)


@router.put(
    "/memory-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_memory_rules(
    body: MemoryRulesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新记忆规则配置（直接发布）"""
    # 校验 search_threshold
    if not (0.5 <= body.search_threshold <= 0.85):
        return ApiResponse.fail(ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID, message="检索阈值必须在0.5到0.85之间")

    # 校验 merge_threshold
    if not (0.85 <= body.merge_threshold <= 0.98):
        return ApiResponse.fail(ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID, message="合并阈值必须在0.85到0.98之间")

    # merge_threshold 必须严格大于 search_threshold
    if body.merge_threshold <= body.search_threshold:
        return ApiResponse.fail(
            ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID,
            message=f"合并阈值({body.merge_threshold})必须大于检索阈值({body.search_threshold})，"
                    f"否则会出现记忆既被检索到又被合并删除的逻辑冲突",
        )

    # 校验 store_threshold
    if not (1 <= body.store_threshold <= 4):
        return ApiResponse.fail(ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID, message="存储阈值必须是1到4之间的整数")

    # 获取当前配置作为 before_value
    current = await admin_config_service.get_active_config("memory_rules")
    before_value = json.dumps(current, ensure_ascii=False) if current else None

    config_value = json.dumps(body.model_dump(), ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key="memory_rules",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布记忆规则配置",
    )
    return ApiResponse.ok(data=result)


# ──────────────────── 2. 向量数据库配置 ────────────────────

def _mask_api_key(api_key: str) -> str:
    """API Key脱敏：前4位+****+后4位"""
    if not api_key or len(api_key) < 8:
        return "****"
    return api_key[:4] + "****" + api_key[-4:]


@router.get(
    "/vector-db-config",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_vector_db_config(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取向量数据库配置（API Key脱敏）"""
    config = await admin_config_service.get_active_config("vector_db_config")

    if config is None:
        # 从环境变量读取默认值
        config = {
            "endpoint": get_dashvector_endpoint(),
            "collection_name": get_dashvector_collection(),
            "top_k": 5,
            "api_key_masked": _mask_api_key(get_dashvector_api_key()),
        }
    else:
        raw_key = config.get("api_key", "")
        config["api_key_masked"] = _mask_api_key(raw_key)
        config.pop("api_key", None)

    return ApiResponse.ok(data=config)


@router.put(
    "/vector-db-config",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_vector_db_config(
    body: VectorDbConfigRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新向量数据库配置（直接发布）"""
    # 如果 need_test_first，先进行连接测试
    if body.need_test_first:
        test_result = await _do_test_connection(
            api_key=body.api_key,
            endpoint=body.endpoint,
            collection_name=body.collection_name,
        )
        if not test_result["connected"]:
            return ApiResponse.fail(
                ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED,
                message=f"连接测试失败：{test_result.get('error', '未知错误')}，请检查配置后重试",
            )

    # 构建配置值
    current = await admin_config_service.get_active_config("vector_db_config")
    config_data = {
        "endpoint": body.endpoint,
        "collection_name": body.collection_name,
        "top_k": body.top_k,
    }

    # api_key 不传则保留原值
    if body.api_key:
        config_data["api_key"] = body.api_key
    elif current and current.get("api_key"):
        config_data["api_key"] = current["api_key"]

    before_value = json.dumps(current, ensure_ascii=False) if current else None

    # 日志中 API Key 脱敏
    log_data = config_data.copy()
    if "api_key" in log_data:
        log_data["api_key"] = _mask_api_key(log_data["api_key"])

    config_value = json.dumps(config_data, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key="vector_db_config",
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"发布向量数据库配置 {json.dumps(log_data, ensure_ascii=False)[:200]}",
    )
    return ApiResponse.ok(data=result)


# ──────────────────── 3. 连接测试 ────────────────────

async def _do_test_connection(
    api_key: str = None,
    endpoint: str = None,
    collection_name: str = None,
) -> dict:
    """执行 DashVector 连接测试"""
    import httpx

    test_endpoint = endpoint or get_dashvector_endpoint()
    test_collection = collection_name or get_dashvector_collection()
    test_api_key = api_key or get_dashvector_api_key()

    if not test_endpoint or not test_api_key:
        return {"connected": False, "latency_ms": 0, "error": "缺少 endpoint 或 api_key"}

    # 构建随机向量（维度1536，text-embedding-v3 默认维度）
    random_vector = [random.uniform(-1, 1) for _ in range(1536)]

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{test_endpoint}/v1/collections/{test_collection}/query",
                headers={
                    "Content-Type": "application/json",
                    "dashvector-auth-token": test_api_key,
                },
                json={
                    "vector": random_vector,
                    "topk": 1,
                    "include_vector": False,
                },
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                return {"connected": True, "latency_ms": elapsed_ms, "error": ""}
            else:
                return {
                    "connected": False,
                    "latency_ms": elapsed_ms,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {"connected": False, "latency_ms": elapsed_ms, "error": str(e)}


@router.post(
    "/vector-db-config/test-connection",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def test_vector_db_connection(
    body: VectorDbTestRequest = None,
    admin_user: AdminUser = Depends(get_current_admin),
):
    """测试 DashVector 连接"""
    api_key = None
    endpoint = None
    collection_name = None

    if body:
        api_key = body.api_key
        endpoint = body.endpoint
        collection_name = body.collection_name

    # 如果未传参数，尝试从已有配置中读取
    if not endpoint or not api_key:
        current = await admin_config_service.get_active_config("vector_db_config")
        if current:
            if not endpoint:
                endpoint = current.get("endpoint")
            if not api_key:
                api_key = current.get("api_key")
            if not collection_name:
                collection_name = current.get("collection_name")

    result = await _do_test_connection(api_key, endpoint, collection_name)
    return ApiResponse.ok(data=result)


# ──────────────────── 4. 全局记忆搜索 ────────────────────

@router.get(
    "/memories/global",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def search_memories_global(
    keyword: str = Query("", description="关键词搜索"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    source: Optional[str] = Query(None, description="来源 auto/manual/admin"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """全局记忆搜索"""
    filters = [Memory.is_deleted == False]  # noqa: E712

    if keyword:
        filters.append(Memory.content.like(f"%{keyword}%"))
    if user_id is not None:
        filters.append(Memory.user_id == user_id)
    if source:
        filters.append(Memory.source == source)
    if start_date:
        try:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            filters.append(Memory.created_at >= dt)
        except ValueError:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID, message="start_date 格式错误，应为 YYYY-MM-DD")
    if end_date:
        try:
            dt = datetime.strptime(end_date, "%Y-%m-%d")
            # 包含当天，所以加1天
            from datetime import timedelta
            filters.append(Memory.created_at < dt + timedelta(days=1))
        except ValueError:
            return ApiResponse.fail(ADMIN_ERR_QUERY_DATE_FORMAT_INVALID, message="end_date 格式错误，应为 YYYY-MM-DD")

    where_clause = and_(*filters)

    # 总数
    count_stmt = select(func.count()).select_from(Memory).where(where_clause)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    list_stmt = (
        select(Memory)
        .where(where_clause)
        .order_by(Memory.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(list_stmt)).scalars().all()

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "content": m.content,
                "importance_score": m.importance_score,
                "source": m.source,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ],
    }
    return ApiResponse.ok(data=data)


# ──────────────────── 5. 批量删除记忆 ────────────────────

@router.delete(
    "/memories/batch-delete",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def batch_delete_memories(
    body: BatchDeleteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """批量删除记忆（MySQL软删除 + DashVector删除）"""
    deleted_count = 0
    failed_ids = []
    affected_user_ids = set()

    for mid in body.memory_ids:
        stmt = select(Memory).where(
            and_(Memory.id == mid, Memory.is_deleted == False)  # noqa: E712
        )
        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()

        if not memory:
            failed_ids.append(mid)
            continue

        try:
            memory.is_deleted = True
            memory.updated_at = datetime.utcnow()
            affected_user_ids.add(memory.user_id)

            # DashVector 删除
            if memory.dashvector_id:
                try:
                    await vector_service.delete(memory.dashvector_id)
                except Exception as e:
                    logger.warning("DashVector 删除失败 memory_id=%d: %s", mid, str(e))

            deleted_count += 1
        except Exception as e:
            logger.error("删除记忆失败 memory_id=%d: %s", mid, str(e))
            failed_ids.append(mid)

    # 写入操作日志
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="memory",
        action="batch_delete",
        target_description=f"批量删除记忆 {deleted_count} 条，涉及用户: {list(affected_user_ids)}",
        request=request,
    )

    return ApiResponse.ok(data={
        "deleted_count": deleted_count,
        "failed_ids": failed_ids,
    })
