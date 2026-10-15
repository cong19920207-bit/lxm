# -*- coding: utf-8 -*-
# 用户向量记忆服务：type=user / character_private 的 DashVector CRUD 与列表辅助。
# 行为与 Step6 upsert（memory_llm_service.upsert_step6_vectors）一致；不扩展 character_knowledge_service（C-06）。

import logging
from typing import Optional

from backend.constants import (
    ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
)
from backend.services.admin_memory_write_service import source_write, active_rows, frozen_writer
from backend.services.memory_mutation_service import MutationError
from backend.utils.character_knowledge_validate import (
    USER_MANAGEABLE_TYPES,
    build_content,
    build_doc_id,
    is_user_manageable_doc_id,
    parse_doc_id,
    parse_key_from_content,
    parse_value_from_content,
    validate_key,
    validate_value,
)
from backend.utils.dashvector_client import build_filter, dashvector_client

logger = logging.getLogger(__name__)

# P9：单用户列表三处（H5 list / Admin user-memories / global 带 user_id）统一上限
USER_LIST_TOPK = 500
# R-01/P4：全局无 user_id 时上限（供 STEP-005 复用）
GLOBAL_LIST_TOPK_NO_USER = 300


def _build_user_fields(key: str, content: str, user_id: int, *, last_write_source: str = "admin") -> dict:
    """
    组装写入 DashVector 的 fields（用户级须额外写 user_id），
    与 upsert_step6_vectors 写入字段保持一致；last_write_source 只用于最后写入溯源。

    key 已由 validate_key 保证为三层 XXX-XXX-XXX，segments 必有 ≥3 段。
    """
    segments = key.split("-")
    return {
        "content": content,
        "stable_key": key,
        "key_l1": segments[0],
        "key_l2": segments[0] + "-" + segments[1],
        "user_id": user_id,
        "last_write_source": last_write_source,
    }


def _validation_error_code(message: str) -> int:
    if "key 汉字不能超过" in message:
        return ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG
    if "value 汉字不能超过" in message:
        return ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG
    return ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID


def _resolve_stable_key(fields: dict, content: str) -> str:
    """优先 fields.stable_key，否则从 content 解析。"""
    sk = (fields or {}).get("stable_key")
    if isinstance(sk, str) and sk.strip():
        return sk.strip()
    return parse_key_from_content(content)


def _entry_from_doc(doc_id: str, content: str, fields: dict) -> dict:
    """解析单条 DashVector 文档为 UserVectorEntry：{doc_id, key, value, content, user_id?}。"""
    parsed = parse_doc_id(doc_id)
    key = _resolve_stable_key(fields, content)
    value = parse_value_from_content(content, key)
    entry: dict = {
        "doc_id": doc_id,
        "key": key,
        "value": value,
        "content": content,
    }
    # user_id 优先取 fields，其次由 doc_id 的 user_suffix 解析
    user_id_val = (fields or {}).get("user_id")
    if user_id_val is None and parsed:
        suffix = parsed[1]
        if suffix.isdigit():
            user_id_val = int(suffix)
    if user_id_val is not None:
        entry["user_id"] = user_id_val
    return entry


class UserVectorMemoryService:
    """用户向量记忆（user / character_private）DashVector 读写。"""

    @staticmethod
    def _validate_memory_type(memory_type: str) -> Optional[str]:
        if memory_type not in USER_MANAGEABLE_TYPES:
            return "type 须为 user 或 character_private"
        return None

    async def list_entries(
        self,
        memory_type: str,
        user_id: int,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        列出某用户在指定类型下的向量记忆（cap=USER_LIST_TOPK），keyword 内存子串过滤后分页。

        total = 过滤后条数（cap 内，P9 口径），非库内真实总数。
        """
        type_err = self._validate_memory_type(memory_type)
        if type_err:
            return {"error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID, "message": type_err}

        filter_str = build_filter(memory_type, user_id=user_id, candidate_keys=[])
        try:
            rows = await active_rows(memory_type, user_id, USER_LIST_TOPK)
        except MutationError as exc:
            return {"error_code": exc.code, "message": exc.reason}

        merged: list[dict] = []
        seen_ids: set[str] = set()
        for row in rows:
            doc_id = row.get("id", "")
            if not doc_id or doc_id in seen_ids:
                continue
            # P3 双匹配：仅保留 type 与 user_suffix 同时匹配的条目（跨类型隔离）
            if not row.get("legacy_read_only") and not is_user_manageable_doc_id(doc_id, user_id=user_id, expected_type=memory_type):
                continue
            seen_ids.add(doc_id)
            fields = row.get("fields", {}) or {}
            entry = _entry_from_doc(doc_id, row.get("content", ""), fields)
            entry.update(generation=row.get("generation"), index_state=row.get("index_state"), legacy_read_only=row.get("legacy_read_only", False))
            entry['index_maintenance'] = row.get('index_maintenance')
            if entry["legacy_read_only"]:entry.update(key="", value=row["content"])
            merged.append(entry)

        merged.sort(key=lambda x: x["doc_id"])

        kw = (keyword or "").strip()
        if kw:
            merged = [
                e for e in merged
                if kw in e.get("key", "")
                or kw in e.get("value", "")
                or kw in e.get("content", "")
            ]

        total = len(merged)
        start = (page - 1) * page_size
        end = start + page_size
        page_list = merged[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "list": page_list,
        }

    async def doc_exists(self, doc_id: str) -> bool:
        writer = await frozen_writer()
        fetched = await writer.mutations.remote.fetch(writer.partition, doc_id)
        if fetched.status == 'unknown':
            raise MutationError(20129, 'memory_source_unreadable')
        return fetched.status == 'found' and not fetched.document['fields'].get('mr_deleted')

    async def create_entry(self, memory_type: str, user_id: int, key: str, value: str, *, actor_id=None, client_request_id=None) -> dict:
        type_err = self._validate_memory_type(memory_type)
        if type_err:
            return {"error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID, "message": type_err}
        key_err = validate_key(key)
        if key_err:
            return {"error_code": _validation_error_code(key_err), "message": key_err}
        value_err = validate_value(value)
        if value_err:
            return {"error_code": _validation_error_code(value_err), "message": value_err}

        return await self._write(kind="create", memory_type=memory_type, user_id=user_id, key=key, value=value, actor_id=actor_id, client_request_id=client_request_id)

    async def update_entry(self, memory_type: str, user_id: int, doc_id: str, value: str, *, actor_id=None, client_request_id=None) -> dict:
        # C-03：仅改 value；先做 P3 双匹配校验
        if not is_user_manageable_doc_id(doc_id, user_id=user_id, expected_type=memory_type):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
                "message": "doc_id 非法或不允许操作该类型/用户",
            }

        value_err = validate_value(value)
        if value_err:
            return {"error_code": _validation_error_code(value_err), "message": value_err}

        return await self._write(kind="update", memory_type=memory_type, user_id=user_id, doc_id=doc_id, value=value, actor_id=actor_id, client_request_id=client_request_id)

    async def delete_entry(self, memory_type: str, user_id: int, doc_id: str, *, actor_id=None, client_request_id=None) -> dict:
        if not is_user_manageable_doc_id(doc_id, user_id=user_id, expected_type=memory_type):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
                "message": "doc_id 非法或不允许操作该类型/用户",
            }

        return await self._write(kind="delete", memory_type=memory_type, user_id=user_id, doc_id=doc_id, actor_id=actor_id, client_request_id=client_request_id)

    async def _write(self, **kwargs):
        try:
            return await source_write(**kwargs)
        except MutationError as exc:
            code = ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY if exc.reason == 'memory_already_exists' else exc.code
            return {'error_code': code, 'message': exc.reason}



user_vector_memory_service = UserVectorMemoryService()
