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
from backend.services.embedding_service import embedding_service
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
from backend.utils.dashvector_client import dashvector_client

logger = logging.getLogger(__name__)

LIST_TOPK = 500


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

        merged: list[dict] = []
        seen_ids: set[str] = set()
        for mt in types_to_query:
            filter_str = f"type = '{mt}'"
            rows = await dashvector_client.list_by_filter(filter_str, top_k=LIST_TOPK)
            for row in rows:
                doc_id = row.get("id", "")
                if not doc_id or doc_id in seen_ids:
                    continue
                if not is_admin_manageable_doc_id(doc_id):
                    continue
                seen_ids.add(doc_id)
                fields = row.get("fields", {}) or {}
                merged.append(_entry_from_doc(
                    doc_id,
                    row.get("content", ""),
                    fields,
                ))

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
        found = await dashvector_client.fetch_by_ids([doc_id])
        return doc_id in found

    async def _fetch_entry_key(self, doc_id: str) -> Optional[str]:
        """从 DashVector 读取已有条目的 stable_key。"""
        found = await dashvector_client.fetch_by_ids([doc_id])
        item = found.get(doc_id)
        if not item:
            return None
        fields = item.get("fields", {}) or {}
        return _resolve_stable_key(fields, item.get("content", ""))

    async def create_entry(self, memory_type: str, key: str, value: str) -> dict:
        type_err = validate_type(memory_type)
        if type_err:
            return {"error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID, "message": type_err}
        key_err = validate_key(key)
        if key_err:
            return {"error_code": _validation_error_code(key_err), "message": key_err}
        value_err = validate_value(value)
        if value_err:
            return {"error_code": _validation_error_code(value_err), "message": value_err}

        key = key.strip()
        value = value.strip()
        doc_id = build_doc_id(memory_type, key)

        if await self.doc_exists(doc_id):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY,
                "message": "该类型下 key 已存在，请直接编辑",
            }

        vector = await embedding_service.get_embedding(value)
        if not vector:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
                "message": "Embedding 生成失败",
            }

        content = build_content(key, value)
        ok = await dashvector_client.upsert(
            doc_id=doc_id,
            vector=vector,
            fields={"content": content, "stable_key": key},
            memory_type=memory_type,
        )
        if not ok:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
                "message": "DashVector 写入失败",
            }

        return {"data": _entry_from_doc(doc_id, content, {"type": memory_type, "stable_key": key})}

    async def update_entry(self, doc_id: str, value: str) -> dict:
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

        value = value.strip()
        if not await self.doc_exists(doc_id):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,
                "message": "条目不存在",
            }

        key = await self._fetch_entry_key(doc_id)
        if not key:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,
                "message": "条目不存在或 key 无法解析",
            }

        vector = await embedding_service.get_embedding(value)
        if not vector:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
                "message": "Embedding 生成失败",
            }

        content = build_content(key, value)
        ok = await dashvector_client.upsert(
            doc_id=doc_id,
            vector=vector,
            fields={"content": content, "stable_key": key},
            memory_type=memory_type,
        )
        if not ok:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
                "message": "DashVector 更新失败",
            }

        return {"data": _entry_from_doc(doc_id, content, {"type": memory_type, "stable_key": key})}

    async def delete_entry(self, doc_id: str) -> dict:
        if not is_admin_manageable_doc_id(doc_id):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID,
                "message": "doc_id 非法或不允许操作该类型",
            }

        if not await self.doc_exists(doc_id):
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,
                "message": "条目不存在",
            }

        ok = await dashvector_client.delete([doc_id])
        if not ok:
            return {
                "error_code": ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,
                "message": "DashVector 删除失败",
            }

        return {"data": {"doc_id": doc_id}}


character_knowledge_service = CharacterKnowledgeService()
