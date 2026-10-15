# -*- coding: utf-8 -*-
# 记忆系统管理：记忆规则配置、向量数据库配置、全局记忆搜索与批量删除

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.memory_effective_config import (
    EffectiveConfigError, load_environment, provider_record, provider_public_state,
    publish_provider, resolve_provider, server_time,
)
from backend.services.memory_provider_service import probe_provider
from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED,
    MEMORY_TYPE_USER,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_memory_write_service import validate_write_header
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
from backend.utils.dashvector_client import build_filter
from backend.services.admin_memory_write_service import active_rows, batch_delete
from backend.services.memory_mutation_service import MutationError

logger = logging.getLogger(__name__)

router = APIRouter()

_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")


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
    model_config = ConfigDict(extra="forbid", strict=True)
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    collection_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def validate_without_echoing_secrets(cls, value):
        if not isinstance(value, dict) or set(value) - {"api_key", "endpoint", "collection_name"} or any(item is not None and not isinstance(item, str) for item in value.values()):
            # Default Pydantic errors include the rejected input; credentials
            # must never be reflected by even the malformed-body path.
            raise HTTPException(status_code=422, detail="配置字段须为字符串或省略，且不能包含未知字段")
        return value


class VectorDbTestRequest(VectorDbConfigRequest):
    pass


class BatchDeleteRequest(BaseModel):
    # P8：按 DashVector doc_id 批量删除（仅删向量，不再走 MySQL）
    doc_ids: list[str] = Field(..., min_length=1, max_length=100)


# ──────────────────── 1. Step6 记忆 Prompt（C-02/C-10）────────────────────
# 旧 GET/PUT /memory-rules 已删除（C-08：memory_rules 后台不展示、不提供 API）。

@router.get(
    "/step6-memory-prompt",
    dependencies=[require_role(*_READ_ROLES)],
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
    dependencies=[require_role(*_WRITE_ROLES)],
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

@router.get("/vector-db-config", dependencies=[require_role(*_READ_ROLES)])
async def get_vector_db_config(
    admin_user: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Current canonical target, including explicit pre-activation mismatch."""
    try:
        record = await provider_record(db, "dashvector")
        data = provider_public_state("dashvector", record, load_environment())
        raw = record.get("raw") or {}
        data["legacy"] = {"top_k": raw.get("top_k", (raw.get("legacy") or {}).get("top_k"))}
        data["server_time"] = server_time()
        if admin_user.role != "observer":
            data["api_key_masked"] = "[REDACTED]" if data["credential_configured"] else ""
        return ApiResponse.ok(data=data)
    except EffectiveConfigError as exc:
        return ApiResponse.fail(exc.code, message="配置读取不可用", data={"reason": exc.reason, "server_time": server_time()})


@router.put("/vector-db-config", dependencies=[require_role(*_WRITE_ROLES)])
async def update_vector_db_config(
    body: VectorDbConfigRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    from backend.services.memory_config_publication import PublicationError, get_or_create_publish_id
    try:
        publish_id = get_or_create_publish_id(request.headers.get("Idempotency-Key"))
    except (ValueError, PublicationError):
        raise HTTPException(status_code=422, detail="Idempotency-Key 必须为规范 UUIDv7") from None
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return ApiResponse.fail(20120, message="须提交修改字段")
    try:
        receipt = await publish_provider(db, "dashvector", patch, admin_user.id, publish_id, request.url.path)
    except (EffectiveConfigError, PublicationError) as exc:
        return ApiResponse.fail(exc.code, message="配置发布未完成", data={"publish_id": publish_id, "reason": exc.reason, "server_time": server_time()})
    data = {**receipt, "version": receipt.get("committed_version"), "server_time": server_time()}
    state = receipt["commit_state"]
    if state == "committed":
        return ApiResponse.ok(data=data)
    code = 20123 if state == "expired" else 20127 if receipt.get("reason") == "publication_revision_conflict" else ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED if state == "rejected" else 20122
    return ApiResponse.fail(code, message="配置未发布或结果待核实", data=data)


@router.post("/vector-db-config/test-connection", dependencies=[require_role(*_WRITE_ROLES)])
async def test_vector_db_connection(
    body: VectorDbTestRequest = None,
    admin_user: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        # Null form fields retain the already resolved group; never consult a
        # different fallback source inside the HTTP adapter.
        patch = body.model_dump(exclude_unset=True, exclude_none=True) if body else None
        config = await resolve_provider(db, "dashvector", patch)
        result = await probe_provider(config)
        return ApiResponse.ok(data={**result, "server_time": server_time()})
    except EffectiveConfigError as exc:
        return ApiResponse.fail(exc.code, message="配置无法核验", data={"connected": False, "reason": exc.reason, "error": "配置无效或来源不可读", "latency_ms": 0, "server_time": server_time()})


# ──────────────────── 4. 全局记忆搜索 ────────────────────

def _global_entry_from_row(row: dict) -> Optional[dict]:
    """将一条 DashVector user 向量解析为全局列表项 {doc_id, user_id, key, value, content}。"""
    doc_id = row.get("id", "")
    parsed = parse_doc_id(doc_id)
    if not parsed and not row.get("legacy_read_only"):
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
        "key": "" if row.get("legacy_read_only") else key,
        "value": content if row.get("legacy_read_only") else value,
        "legacy_read_only": row.get("legacy_read_only", False),
        "content": content,
        "generation": row.get("generation"), "index_state": row.get("index_state"),
        "index_maintenance": row.get("index_maintenance"),
    }


@router.get(
    "/memories/global",
    dependencies=[require_role(*_READ_ROLES)],
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
    try:
        rows = await active_rows(MEMORY_TYPE_USER, user_id or 0, top_k)
    except MutationError as exc:
        return ApiResponse.fail(exc.code, message=exc.reason)

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
    return ApiResponse.ok(data={**data, "server_time": server_time()})


# ──────────────────── 5. 批量删除记忆 ────────────────────

@router.delete(
    "/memories/batch-delete",
    dependencies=[require_role(*_WRITE_ROLES), Depends(validate_write_header)],
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
    try:
        result = await batch_delete(body.doc_ids, admin_user.id, request.headers.get('Idempotency-Key'))
    except MutationError as exc:
        return ApiResponse.fail(exc.code, message=exc.reason)
    data = result['data']
    await log_operation(db=db, admin_user=admin_user, module='memory', action='batch_delete',
        target_description=f"批量删除用户记忆 {data.get('deleted_count', 0)} 条", request=request)
    if result['error_code']:
        return ApiResponse.fail(result['error_code'], message='部分结果待核实', data=data)
    return ApiResponse.ok(data=data)
