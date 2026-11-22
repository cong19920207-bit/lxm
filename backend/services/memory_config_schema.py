"""Validated memory configuration (M2 parameter dictionary, independent of providers)."""
from copy import deepcopy
import json
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROUTES = ("cg", "cp", "ck", "user")
ROUTE_DEFAULT = {"dense_top_k": 20, "bm25_top_k": 20, "final_top_k": 8, "rerank_min_score": 0.1}
PROMPT_TOTAL_MAX = 49152
RECENT_CHAT_MAX = 24576
PROMPT_DEFAULTS = {"max_total": PROMPT_TOTAL_MAX, "system": 2048, "persona": 3072,
                   "character_knowledge": 3072, "relationship": 1024, "memory": 4096,
                   "emotion": 512, "time_activity": 256, "recent_chat": RECENT_CHAT_MAX,
                   "user_nickname": 50, "user_input": 8192}
PROMPT_KEYS = tuple(key for key in PROMPT_DEFAULTS if key != "user_nickname")
ROUTER_KEY = "memory_query_router_config"
FLASH_MODEL = "deepseek-flash"
DEFAULT_ROUTER_PROMPT = (
    "判断回答本轮用户消息是否需要查询已提供上下文之外的记忆。"
    "问候、普通交流或当前上下文已足够时无需查询。"
    "如果用户只要改写、缩短或翻译一句话，且在当前消息或最近对话中找得到原文，"
    "已有材料就足够，判 false。只有还需要找回未提供的原文或其他专属事实时才查询。"
    "依赖未提供的个人事实、过去事件、角色知识、专属约定，或无法可靠判断时需要查询。"
)


ROUTER_PROMPT_MAX_CHARS = 20000
ROUTER_CONFIG_MAX_BYTES = 65535
ROUTER_SIZE_MESSAGE = "完整配置序列化后最多 65535 个 UTF-8 字节，须同时能保存关闭状态，请缩短提示词"


def router_storage_size(value):
    return len(json.dumps({**value, "enabled": False}, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8"))


class MemoryQueryRouterConfig(BaseModel):
    """A complete atomic publication. The editable prompt is literal text."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    enabled: bool
    timeout_ms: int = Field(ge=1000, le=10000)
    prompt: str = Field(min_length=1)
    model_profile_id: Literal["inherit_reply", "deepseek-flash"]
    thinking_enabled: bool = False
    behavior_profile_id: Literal["router_boolean_v1"]
    max_retries: int = Field(ge=0, le=0)

    @field_validator("prompt")
    @classmethod
    def valid_instruction(cls, value):
        if len(value) > ROUTER_PROMPT_MAX_CHARS:
            raise ValueError("路由提示词最多 20000 个字符，请缩短后保存")
        if not value.strip() or any(ord(c) < 32 and c not in "\r\n\t" for c in value):
            raise ValueError("Router 任务说明须为有效文本")
        return value

    @model_validator(mode="after")
    def fit_storage(self):
        # JSON false needs one more byte than true. Every accepted version must
        # be closable without changing its prompt, even at the TEXT boundary.
        if router_storage_size(self.model_dump(exclude_unset=True)) > ROUTER_CONFIG_MAX_BYTES:
            raise ValueError(ROUTER_SIZE_MESSAGE)
        return self

    def effective_model(self, reply_model: str) -> str:
        return FLASH_MODEL if self.model_profile_id == FLASH_MODEL else reply_model

    @property
    def provider_name(self) -> str:
        return "deepseek" if self.model_profile_id == FLASH_MODEL else "volcengine"


DEFAULT_ROUTER = MemoryQueryRouterConfig(
    enabled=False, timeout_ms=5000, prompt=DEFAULT_ROUTER_PROMPT,
    model_profile_id="inherit_reply", thinking_enabled=False, behavior_profile_id="router_boolean_v1", max_retries=0,
)


class StrictPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def no_explicit_null(cls, value):
        if isinstance(value, dict) and any(v is None for v in value.values()):
            raise ValueError("显式 null 不合法；保留原值请省略字段")
        return value


Count = Annotated[int, Field(ge=1, le=50)]
Budget = Annotated[int, Field(ge=1, le=8192)]


class RoutePatch(StrictPatch):
    dense_top_k: Count | None = None
    bm25_top_k: Count | None = None
    final_top_k: Count | None = None
    rerank_min_score: Annotated[float, Field(ge=0, le=1)] | None = None

    @model_validator(mode="before")
    @classmethod
    def numeric_score(cls, value):
        if isinstance(value, dict) and "rerank_min_score" in value and isinstance(value["rerank_min_score"], bool):
            raise ValueError("门槛须为有限数值")
        return value


class RoutesPatch(StrictPatch):
    cg: RoutePatch | None = None
    cp: RoutePatch | None = None
    ck: RoutePatch | None = None
    user: RoutePatch | None = None


class VectorRetrievalPatch(StrictPatch):
    routes: RoutesPatch | None = None


class PromptTokenPatch(StrictPatch):
    max_total: Annotated[int, Field(ge=1024, le=PROMPT_TOTAL_MAX)] | None = None
    system: Budget | None = None
    persona: Budget | None = None
    character_knowledge: Budget | None = None
    relationship: Budget | None = None
    memory: Budget | None = None
    emotion: Budget | None = None
    time_activity: Budget | None = None
    recent_chat: Annotated[int, Field(ge=1, le=RECENT_CHAT_MAX)] | None = None
    user_input: Budget | None = None


def vector_effective(raw: Any) -> dict:
    if raw is None:
        return {"routes": {route: dict(ROUTE_DEFAULT) for route in ROUTES}}
    if not isinstance(raw, dict) or not isinstance(raw.get("routes"), dict) or set(raw["routes"]) != set(ROUTES):
        raise ValueError("已发布混合召回配置不完整")
    result = {"routes": {}}
    for route in ROUTES:
        item = raw["routes"][route]
        if not isinstance(item, dict) or set(item) != set(ROUTE_DEFAULT):
            raise ValueError("已发布召回参数不完整")
        parsed = RoutePatch.model_validate(item).model_dump()
        if parsed["final_top_k"] > parsed["dense_top_k"] + parsed["bm25_top_k"]:
            raise ValueError("最终数量不能大于该路两种候选数量之和")
        result["routes"][route] = parsed
    # Historical settings are audit-only and never enter routes.
    if "legacy" in raw:
        result["legacy"] = deepcopy(raw["legacy"])
    return result


def merge_vector(current: Any, patch: dict) -> dict:
    parsed = VectorRetrievalPatch.model_validate(patch).model_dump(exclude_unset=True)
    if not parsed.get("routes") or not any(parsed["routes"].values()):
        raise ValueError("须至少提交一个召回参数")
    merged = vector_effective(current)
    for route, fields in parsed["routes"].items():
        merged["routes"][route].update(fields)
    return vector_effective(merged)


def prompt_effective(raw: Any) -> dict:
    if raw is None:
        return dict(PROMPT_DEFAULTS)
    if not isinstance(raw, dict) or not set(PROMPT_KEYS).issubset(raw):
        raise ValueError("已发布 Token 配置不完整")
    if raw.get("user_nickname", 50) != 50 or isinstance(raw.get("user_nickname"), bool):
        raise ValueError("昵称固定预算须为50")
    parsed = PromptTokenPatch.model_validate({k: raw[k] for k in PROMPT_KEYS}).model_dump()
    if any(v > parsed["max_total"] for k, v in parsed.items() if k != "max_total"):
        raise ValueError("模块预算不能超过总预算")
    return {**parsed, "user_nickname": 50}


def merge_prompt(current: Any, patch: dict) -> dict:
    parsed = PromptTokenPatch.model_validate(patch).model_dump(exclude_unset=True)
    if not parsed:
        raise ValueError("须至少提交一个可编辑预算")
    return prompt_effective({**prompt_effective(current), **parsed})
