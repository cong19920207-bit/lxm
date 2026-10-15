"""Validated memory configuration (M2 parameter dictionary, independent of providers)."""
from copy import deepcopy
import math
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROUTES = ("cg", "cp", "ck", "user")
ROUTE_DEFAULT = {"dense_top_k": 20, "bm25_top_k": 20, "final_top_k": 8, "rerank_min_score": 0.1}
PROMPT_DEFAULTS = {"max_total": 7373, "system": 720, "persona": 1080,
                   "character_knowledge": 600, "relationship": 360, "memory": 900,
                   "emotion": 270, "time_activity": 80, "recent_chat": 1800,
                   "user_nickname": 50, "user_input": 900}
PROMPT_KEYS = tuple(key for key in PROMPT_DEFAULTS if key != "user_nickname")


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
    max_total: Annotated[int, Field(ge=1024, le=32768)] | None = None
    system: Budget | None = None
    persona: Budget | None = None
    character_knowledge: Budget | None = None
    relationship: Budget | None = None
    memory: Budget | None = None
    emotion: Budget | None = None
    time_activity: Budget | None = None
    recent_chat: Annotated[int, Field(ge=1, le=16384)] | None = None
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
