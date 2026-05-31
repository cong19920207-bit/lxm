# -*- coding: utf-8 -*-
# 记忆系统管理：记忆规则配置、向量数据库配置、全局记忆搜索与批量删除

import json
import logging
import random
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import (
    get_dashvector_api_key,
    get_dashvector_collection,
    get_dashvector_endpoint,
)
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED,
    MEMORY_TYPE_USER,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.memory_llm_service import (
    STEP6_PROMPT_CONFIG_KEY,
    STEP6_PROMPT_DEFAULT,
    _ALL_FIELD_NAMES,
)
from backend.services.user_vector_memory_service import (
    GLOBAL_LIST_TOPK_NO_USER,
    USER_LIST_TOPK,
)
from backend.utils.admin_auth import get_current_admin, log_operation, require_role
from backend.utils.character_knowledge_validate import (
    parse_doc_id,
    parse_key_from_content,
    parse_value_from_content,
)
from backend.utils.dashvector_client import build_filter, dashvector_client

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")


# ──────────────────── 请求模型 ────────────────────

class Step6MemoryPromptRequest(BaseModel):
    """Step6 记忆 Prompt 6 块结构（C-02/C-10，保存即发布，Pydantic 必填校验）。"""
    system_instruction: str = Field(..., min_length=1)
    output_format_rules: str = Field(..., min_length=1)
    kv_field_rules: str = Field(..., min_length=1)
    task_fields: dict[str, str]
    merge_rules: str = Field(..., min_length=1)
    few_shot_example: str = Field(..., min_length=1)

    @field_validator(
        "system_instruction",
        "output_format_rules",
        "kv_field_rules",
        "merge_rules",
        "few_shot_example",
    )
    @classmethod
    def _block_non_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("文本块不能为空")
        return v

    @field_validator("task_fields")
    @classmethod
    def _validate_task_fields(cls, v: dict) -> dict:
        # 必须恰好包含全部 11 个字段（集合与 _ALL_FIELD_NAMES 一致，P6）
        if set(v.keys()) != set(_ALL_FIELD_NAMES) or len(v) != len(_ALL_FIELD_NAMES):
            raise ValueError("task_fields 必须包含且仅包含 11 个字段")
        for name, text in v.items():
            if not text or not str(text).strip():
                raise ValueError(f"task_fields.{name} 不能为空")
        return v


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
    # P8：按 DashVector doc_id 批量删除（仅删向量，不再走 MySQL）
    doc_ids: list[str] = Field(..., min_length=1, max_length=100)


# ──────────────────── 1. Step6 记忆 Prompt（C-02/C-10）────────────────────
# 旧 GET/PUT /memory-rules 已删除（C-08：memory_rules 后台不展示、不提供 API）。

@router.get(
    "/step6-memory-prompt",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_step6_memory_prompt(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的 Step6 记忆 Prompt（无配置时返回 DEFAULT）。"""
    config = await admin_config_service.get_active_config(STEP6_PROMPT_CONFIG_KEY)
    if not isinstance(config, dict):
        config = STEP6_PROMPT_DEFAULT
    return ApiResponse.ok(data=config)


@router.put(
    "/step6-memory-prompt",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_step6_memory_prompt(
    body: Step6MemoryPromptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新 Step6 记忆 Prompt（保存即发布，更新 MySQL+Redis，不需重启）。"""
    current = await admin_config_service.get_active_config(STEP6_PROMPT_CONFIG_KEY)
    before_value = json.dumps(current, ensure_ascii=False) if current else None

    config_value = json.dumps(body.model_dump(), ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key=STEP6_PROMPT_CONFIG_KEY,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布 Step6 记忆 Prompt",
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

def _global_entry_from_row(row: dict) -> Optional[dict]:
    """将一条 DashVector user 向量解析为全局列表项 {doc_id, user_id, key, value, content}。"""
    doc_id = row.get("id", "")
    parsed = parse_doc_id(doc_id)
    if not parsed:
        return None
    fields = row.get("fields", {}) or {}
    content = row.get("content", "") or fields.get("content", "")
    key = (fields.get("stable_key") or parse_key_from_content(content)).strip()
    value = parse_value_from_content(content, key)
    # user_id 优先取 fields，其次由 doc_id 的 user_suffix 解析
    user_id_val = fields.get("user_id")
    if user_id_val is None:
        suffix = parsed[1]
        user_id_val = int(suffix) if suffix.isdigit() else None
    return {
        "doc_id": doc_id,
        "user_id": user_id_val,
        "key": key,
        "value": value,
        "content": content,
    }


@router.get(
    "/memories/global",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def search_memories_global(
    keyword: str = Query("", description="关键词搜索"),
    user_id: Optional[int] = Query(None, description="用户ID（可选）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """
    全局用户记忆搜索（Step6 user 向量）。

    - 有 user_id：build_filter("user", user_id, []) top_k=500（P4）
    - 无 user_id：build_filter("user", None, []) top_k=300（R-01/P4），命中上限附 truncated=true
    - keyword 先取候选再内存子串过滤（key/value/content）后分页
    - 仅 type=user，不含 character_private（§6.4.1）；不过滤 mem_*（P1）
    """
    top_k = USER_LIST_TOPK if user_id is not None else GLOBAL_LIST_TOPK_NO_USER
    filter_str = build_filter(MEMORY_TYPE_USER, user_id=user_id, candidate_keys=[])
    rows = await dashvector_client.list_by_filter(filter_str, top_k=top_k)

    # 未传 user_id 且候选数命中上限 → 结果可能不完整
    truncated = user_id is None and len(rows) >= GLOBAL_LIST_TOPK_NO_USER

    entries: list[dict] = []
    seen_ids: set[str] = set()
    for row in rows:
        entry = _global_entry_from_row(row)
        if not entry:
            continue
        if entry["doc_id"] in seen_ids:
            continue
        seen_ids.add(entry["doc_id"])
        entries.append(entry)

    entries.sort(key=lambda x: x["doc_id"])

    kw = (keyword or "").strip()
    if kw:
        entries = [
            e for e in entries
            if kw in e.get("key", "")
            or kw in e.get("value", "")
            or kw in e.get("content", "")
        ]

    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    page_list = entries[start:end]

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": page_list,
    }
    if truncated:
        data["truncated"] = True
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
    """
    按 doc_id 批量删除用户记忆（P8，仅删 DashVector）。

    逐条校验「以 user_ 开头 且 parse_doc_id 合法」，非法计入 failed_doc_ids 不中断；
    合法项删除并累加 deleted_count；「涉及用户」从 user_suffix 解析去重聚合。
    """
    deleted_count = 0
    failed_doc_ids: list[str] = []
    affected_user_ids: set[str] = set()

    for doc_id in body.doc_ids:
        parsed = parse_doc_id(doc_id)
        # 仅允许 user_ 前缀的用户记忆（global 不含 character_private）
        if not doc_id.startswith(f"{MEMORY_TYPE_USER}_") or not parsed:
            failed_doc_ids.append(doc_id)
            continue

        ok = await dashvector_client.delete([doc_id])
        if not ok:
            failed_doc_ids.append(doc_id)
            continue

        deleted_count += 1
        affected_user_ids.add(parsed[1])

    # 写入操作日志（module 仍用 memory）
    await log_operation(
        db=db,
        admin_user=admin_user,
        module="memory",
        action="batch_delete",
        target_description=f"批量删除用户记忆 {deleted_count} 条，涉及用户: {sorted(affected_user_ids)}",
        request=request,
    )

    return ApiResponse.ok(data={
        "deleted_count": deleted_count,
        "failed_doc_ids": failed_doc_ids,
    })
