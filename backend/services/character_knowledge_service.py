# -*- coding: utf-8 -*-
# 角色知识库管理服务：DashVector CRUD，与 Step6 向量写入约定一致

import logging
from typing import Optional

from backend.constants import (
    ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
    MEMORY_TYPE_CHARACTER_GLOBAL,
    MEMORY_TYPE_CHARACTER_KNOWLEDGE,
)
from backend.services.admin_memory_write_service import source_write, active_rows, frozen_writer
from backend.services.memory_mutation_service import MutationError
from backend.utils.character_knowledge_validate import (
    build_content,
    build_doc_id,
    is_admin_manageable_doc_id,
    parse_doc_id,
    parse_key_from_content,
    parse_value_from_content,
    validate_key,
    validate_type,
    validate_value,
)
from backend.utils.dashvector_client import build_filter, dashvector_client

logger = logging.getLogger(__name__)

LIST_TOPK = 500


def _build_knowledge_fields(key: str, content: str) -> dict:
    """
    组装写入 DashVector 的 fields，create_entry 与 update_entry 共用（C15），
    避免两条写入路径逻辑分叉；update 也必须补写 key_l1/key_l2（不赌 Upsert 字段保留行为）。

    key 已由 validate_key 保证为三层 XXX-XXX-XXX，segments 必有 ≥3 段。
    """
    segments = key.split("-")
    return {
        "content": content,
        "stable_key": key,
        "key_l1": segments[0],
        "key_l2": segments[0] + "-" + segments[1],
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
    parsed = parse_doc_id(doc_id)
    memory_type = parsed[0] if parsed else fields.get("type", "")
    key = _resolve_stable_key(fields, content)
    value = parse_value_from_content(content, key)
    return {
        "doc_id": doc_id,
        "type": memory_type,
        "key": key,
        "value": value,
        "content": content,
    }


class CharacterKnowledgeService:
    """角色知识库（character_global / character_knowledge）DashVector 读写。"""

    async def list_entries(
        self,
        memory_type: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        if memory_type:
            err = validate_type(memory_type)
            if err:
                return {"error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID, "message": err}

        types_to_query = (
            [memory_type]
            if memory_type
            else [MEMORY_TYPE_CHARACTER_GLOBAL, MEMORY_TYPE_CHARACTER_KNOWLEDGE]
        )

        try:
            writer = await frozen_writer()
        except MutationError as exc:
            return {"error_code": exc.code, "message": exc.reason}

        merged: list[dict] = []
        seen_ids: set[str] = set()
        for mt in types_to_query:
            # 统一用 build_filter（双引号，与检索侧一致 C33）；list 场景无 user_id / candidate_keys
            filter_str = build_filter(mt, user_id=None, candidate_keys=[])
            try:
                rows = await active_rows(mt, 0, LIST_TOPK, writer=writer)
            except MutationError as exc:
                return {"error_code": exc.code, "message": exc.reason}
            for row in rows:
                doc_id = row.get("id", "")
                if not doc_id or doc_id in seen_ids:
                    continue
                if not row.get("legacy_read_only") and not is_admin_manageable_doc_id(doc_id):
                    continue
                seen_ids.add(doc_id)
                fields = row.get("fields", {}) or {}
                entry = _entry_from_doc(
                    doc_id,
                    row.get("content", ""),
                    fields,
                )
                entry.update(generation=row.get("generation"), index_state=row.get("index_state"), legacy_read_only=row.get("legacy_read_only", False))
                if entry["legacy_read_only"]:entry.update(key="", value=row["content"])
                merged.append(entry)

        merged.sort(key=lambda x: x["doc_id"])

        kw = (keyword or "").strip()
        if kw:
            merged = [
                e for e in merged
                if kw in e.get("key", "") or kw in e.get("value", "")
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

    async def create_entry(self, memory_type: str, key: str, value: str, *, actor_id=None, client_request_id=None) -> dict:
        type_err = validate_type(memory_type)
        if type_err:
            return {"error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID, "message": type_err}
        key_err = validate_key(key)
        if key_err:
            return {"error_code": _validation_error_code(key_err), "message": key_err}
        value_err = validate_value(value)
        if value_err:
            return {"error_code": _validation_error_code(value_err), "message": value_err}

        return await self._write(kind="create", memory_type=memory_type, key=key, value=value, actor_id=actor_id, client_request_id=client_request_id)

    async def update_entry(self, doc_id: str, value: str, *, actor_id=None, client_request_id=None) -> dict:
        if not is_admin_manageable_doc_id(doc_id):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
                "message": "doc_id 非法或不允许操作该类型",
            }

        parsed = parse_doc_id(doc_id)
        if not parsed:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
                "message": "doc_id 非法或不允许操作该类型",
            }

        memory_type, _user_suffix = parsed
        value_err = validate_value(value)
        if value_err:
            return {"error_code": _validation_error_code(value_err), "message": value_err}

        return await self._write(kind="update", memory_type=parse_doc_id(doc_id)[0], doc_id=doc_id, value=value, actor_id=actor_id, client_request_id=client_request_id)

    async def delete_entry(self, doc_id: str, *, actor_id=None, client_request_id=None) -> dict:
        if not is_admin_manageable_doc_id(doc_id):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
                "message": "doc_id 非法或不允许操作该类型",
            }

        return await self._write(kind="delete", memory_type=parse_doc_id(doc_id)[0], doc_id=doc_id, actor_id=actor_id, client_request_id=client_request_id)

    async def _write(self, **kwargs):
        try:
            return await source_write(**kwargs)
        except MutationError as exc:
            code = ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY if exc.reason == 'memory_already_exists' else exc.code
            return {'error_code': code, 'message': exc.reason}



character_knowledge_service = CharacterKnowledgeService()
