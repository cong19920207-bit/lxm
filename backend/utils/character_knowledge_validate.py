# -*- coding: utf-8 -*-
# 角色知识库 / Step6 向量：doc_id 生成、key 校验、content 解析（全项目统一约定）

import hashlib
import re
from typing import Optional

from backend.constants import (
    MEMORY_TYPE_CHARACTER_GLOBAL,
    MEMORY_TYPE_CHARACTER_KNOWLEDGE,
    VALID_MEMORY_TYPES,
)

# 全角冒号，与 Step6 parse_kv_lines 一致
FULLWIDTH_COLON = "："

# CJK 统一表意文字（含扩展 A）
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# key 单段允许：汉字、数字、英文、连字符、下划线
_KEY_SEGMENT_PATTERN = re.compile(
    r"^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff0-9A-Za-z\-_]+$"
)

ADMIN_CHARACTER_KNOWLEDGE_TYPES = frozenset({
    MEMORY_TYPE_CHARACTER_GLOBAL,
    MEMORY_TYPE_CHARACTER_KNOWLEDGE,
})

MAX_KEY_CJK = 20
MAX_VALUE_CJK = 100
KEY_LAYER_COUNT = 3  # 强制 XXX-XXX-XXX 三层


def count_cjk(text: str) -> int:
    """统计文本中的 CJK 汉字数量。"""
    return len(_CJK_PATTERN.findall(text))


def hash_key(key: str) -> str:
    """稳定 key → doc_id 用 hash（sha256 前 12 位十六进制）。"""
    normalized = (key or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def build_doc_id(memory_type: str, key: str, user_id: int | None = None) -> str:
    """
    生成 DashVector 合法 doc_id。

    格式：{memory_type}_{key_hash12}_{user_suffix}
    - 角色级（无 user_id）：user_suffix = "0"
    - 用户级：user_suffix = str(user_id)
    """
    key_hash = hash_key(key)
    user_suffix = str(user_id) if user_id is not None else "0"
    return f"{memory_type}_{key_hash}_{user_suffix}"


def parse_doc_id(doc_id: str) -> Optional[tuple[str, str]]:
    """
    解析 doc_id → (memory_type, user_suffix)。

    user_suffix 为 "0" 表示角色级；否则为用户 ID 字符串。
    """
    if not doc_id:
        return None
    parts = doc_id.rsplit("_", 2)
    if len(parts) != 3:
        return None
    memory_type, _key_hash, user_suffix = parts
    if memory_type not in VALID_MEMORY_TYPES:
        return None
    if not _key_hash or len(_key_hash) != 12:
        return None
    if not re.fullmatch(r"[0-9a-f]{12}", _key_hash):
        return None
    if user_suffix != "0" and not user_suffix.isdigit():
        return None
    return memory_type, user_suffix


def is_admin_manageable_doc_id(doc_id: str) -> bool:
    """是否为本后台可管理的角色级条目（character_global / character_knowledge，user_suffix=0）。"""
    parsed = parse_doc_id(doc_id)
    if not parsed:
        return False
    memory_type, user_suffix = parsed
    return memory_type in ADMIN_CHARACTER_KNOWLEDGE_TYPES and user_suffix == "0"


def build_content(key: str, value: str) -> str:
    """拼装 fields.content（全角冒号）。"""
    return f"{key}{FULLWIDTH_COLON}{value}"


def parse_key_from_content(content: str) -> str:
    """从 content 按首处全角冒号解析 key。"""
    if not content:
        return ""
    idx = content.find(FULLWIDTH_COLON)
    if idx < 0:
        return content.strip()
    return content[:idx].strip()


def parse_value_from_content(content: str, key: str = "") -> str:
    """从 content 按首处全角冒号解析 value。"""
    if not content:
        return ""
    idx = content.find(FULLWIDTH_COLON)
    if idx < 0:
        return content.strip()
    return content[idx + 1:].strip()


def validate_type(memory_type: str) -> Optional[str]:
    if memory_type not in ADMIN_CHARACTER_KNOWLEDGE_TYPES:
        return f"type 须为 {MEMORY_TYPE_CHARACTER_GLOBAL} 或 {MEMORY_TYPE_CHARACTER_KNOWLEDGE}"
    return None


def validate_key(key: str) -> Optional[str]:
    """
    校验 key：须为三层 XXX-XXX-XXX（恰好 2 个半角连字符），每段非空。
    """
    key = (key or "").strip()
    if not key:
        return "key 不能为空"
    if FULLWIDTH_COLON in key:
        return "key 不能包含全角冒号"
    segments = key.split("-")
    if len(segments) != KEY_LAYER_COUNT:
        return f"key 须为 {KEY_LAYER_COUNT} 段，用半角 - 连接（如 外貌-体态-细节）"
    for seg in segments:
        if not seg.strip():
            return "key 每一段不能为空"
        if not _KEY_SEGMENT_PATTERN.match(seg):
            return "key 每段仅允许汉字、数字、英文字母、- 与 _"
    cjk_count = count_cjk(key)
    if cjk_count > MAX_KEY_CJK:
        return f"key 汉字不能超过 {MAX_KEY_CJK} 个（当前 {cjk_count} 个）"
    return None


def validate_value(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return "value 不能为空"
    cjk_count = count_cjk(value)
    if cjk_count > MAX_VALUE_CJK:
        return f"value 汉字不能超过 {MAX_VALUE_CJK} 个（当前 {cjk_count} 个）"
    return None
