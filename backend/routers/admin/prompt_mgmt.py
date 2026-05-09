# -*- coding: utf-8 -*-
# Prompt 管理：Step5 System、Step5.5 六段模板、Step5.5 总开关；在线测试对接主链 build_chat_prompt

import json
import logging
from datetime import datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
    ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD,
    ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED,
    ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND,
    ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING,
    ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.llm_service import llm_service
from backend.services.prompt_builder import (
    PromptBuilder,
    SYSTEM_PROMPT_TEXT,
    get_activity_description,
    _generate_time_description,
)
from backend.routers.chat import _build_round_context
from backend.services.step5_5_prompt_fragments import (
    STEP5_5_FRAGMENT_KEYS,
    get_default_step5_5_fragments,
    merge_step5_5_fragments,
    validate_step5_5_fragments_dict,
    validate_step5_system_content,
)
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")

_CONFIG_STEP5 = "step5_system_prompt"
_CONFIG_STEP5_5 = "step5_5_prompt_fragments"
_CONFIG_SWITCH = "step5_5_enabled"


# ──────────────────── 请求模型 ────────────────────


class Step5DraftBody(BaseModel):
    content: str = Field(..., min_length=1)


class Step55FragmentDraftBody(BaseModel):
    content: str = Field(..., min_length=1)


class Step55SwitchDraftBody(BaseModel):
    enabled: bool


class PromptPublishRequest(BaseModel):
    confirm_text: str
    test_passed: bool


class PromptRollbackRequest(BaseModel):
    version: int
    confirm_text: str


class PromptTestRequest(BaseModel):
    test_input: str = Field(..., min_length=1)
    relationship_level: int = Field(1, ge=0, le=3)
    emotion_label: str = Field("平静")
    mock_memories: list[str] = Field(default_factory=list)
    use_draft: bool = False


# ──────────────────── 解析辅助 ────────────────────


def _step5_extract_content(raw: object) -> str:
    """从 admin_config 解析出的 dict/str 中取 Step5 System 正文。"""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        c = raw.get("content")
        return str(c) if c is not None else ""
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return ""
        try:
            j = json.loads(s)
            if isinstance(j, dict) and "content" in j:
                return str(j.get("content") or "")
        except (json.JSONDecodeError, TypeError):
            pass
        return raw
    return ""


def _step5_wrap_publish_payload(content: str) -> str:
    return json.dumps({"content": content}, ensure_ascii=False)


def _normalize_switch_enabled(raw: object) -> bool:
    """与 step5_5_service._is_switch_on 语义对齐（简化版，供管理端展示）。"""
    from backend.services.step5_5_service import _is_switch_on

    return _is_switch_on(raw)


def _empty_retrieval_for_test(mem_rows: list[dict]) -> dict:
    return {
        "character_global": [],
        "character_private": [],
        "character_knowledge": [],
        "user": mem_rows,
    }


# ═══════════════════ Step5 System ═══════════════════


@router.get("/prompt/step5", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_step5_prompt(admin_user: AdminUser = Depends(get_current_admin)):
    """Step5 System 模板：生效正文 + 草稿状态。"""
    detail = await admin_config_service.get_active_config_detail(_CONFIG_STEP5)
    draft = await admin_config_service.get_draft(_CONFIG_STEP5)

    version = 0
    content = SYSTEM_PROMPT_TEXT
    if detail and detail.get("content") is not None:
        parsed = detail["content"]
        extracted = _step5_extract_content(parsed)
        if extracted.strip():
            content = extracted
        version = int(detail.get("version") or 0)

    return ApiResponse.ok(data={
        "version": version,
        "has_draft": draft is not None,
        "content": content,
        "baseline_is_builtin": version == 0 and not (detail and _step5_extract_content(detail.get("content"))),
    })


@router.get("/prompt/step5/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_step5_draft(admin_user: AdminUser = Depends(get_current_admin)):
    return ApiResponse.ok(data=await admin_config_service.get_draft(_CONFIG_STEP5))


@router.put("/prompt/step5/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def put_step5_draft(
    body: Step5DraftBody,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    payload = _step5_wrap_publish_payload(body.content)
    result = await admin_config_service.save_draft(
        db, _CONFIG_STEP5, payload, admin_user.username,
    )
    return ApiResponse.ok(data=result)


@router.delete("/prompt/step5/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_step5_draft(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    ok = await admin_config_service.discard_draft(db, _CONFIG_STEP5)
    if not ok:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD)
    return ApiResponse.ok(message="草稿已丢弃")


@router.post("/prompt/step5/publish", dependencies=[require_role(*_ALLOWED_ROLES)])
async def publish_step5(
    body: PromptPublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认发布")
    if not body.test_passed:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED, message="请先测试通过后再发布")

    draft = await admin_config_service.get_draft(_CONFIG_STEP5)
    if not draft:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH)

    draft_val = draft.get("config_value")
    inner = _step5_extract_content(draft_val)
    err = validate_step5_system_content(inner)
    if err:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING, message=err)

    config_value = draft_val if isinstance(draft_val, str) else json.dumps(draft_val, ensure_ascii=False)

    stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_STEP5,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(stmt)
    active_config = active_result.scalars().first()
    before_value = active_config.config_value if active_config else None

    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_STEP5,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布 Step5 System 模板（step5_system_prompt）",
    )
    return ApiResponse.ok(data=result)


@router.get("/prompt/step5/history", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    result = await admin_config_service.get_version_history(db, _CONFIG_STEP5, page, page_size)
    return ApiResponse.ok(data=result)


@router.get("/prompt/step5/history/{version}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_history_detail(
    version: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_STEP5,
        AdminConfig.version == version,
        AdminConfig.is_draft == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND, message=f"版本 V{version} 不存在")
    try:
        content = json.loads(row.config_value) if row.config_value else {}
    except (json.JSONDecodeError, TypeError):
        content = row.config_value
    return ApiResponse.ok(data={
        "version": row.version,
        "is_active": row.is_active,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "content": content,
    })


@router.post("/prompt/step5/rollback", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_rollback(
    body: PromptRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认回滚")
    try:
        result = await admin_config_service.rollback_config(
            db=db,
            config_key=_CONFIG_STEP5,
            version=body.version,
            admin_user=admin_user,
            request=request,
        )
    except ValueError as e:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND, message=str(e))
    return ApiResponse.ok(data=result)


# ═══════════════════ Step5.5 六段 ═══════════════════


@router.get("/prompt/step5-5/fragments", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_step5_5_fragments(admin_user: AdminUser = Depends(get_current_admin)):
    detail = await admin_config_service.get_active_config_detail(_CONFIG_STEP5_5)
    draft = await admin_config_service.get_draft(_CONFIG_STEP5_5)

    defaults = get_default_step5_5_fragments()
    merged = dict(defaults)
    version = 0

    if detail and detail.get("content") is not None:
        raw = detail["content"]
        if isinstance(raw, dict):
            merged = merge_step5_5_fragments(raw)
        version = int(detail.get("version") or 0)

    return ApiResponse.ok(data={
        "version": version,
        "has_draft": draft is not None,
        "fragments": merged,
        "fragment_keys": list(STEP5_5_FRAGMENT_KEYS),
    })


@router.get("/prompt/step5-5/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_step5_5_draft(admin_user: AdminUser = Depends(get_current_admin)):
    return ApiResponse.ok(data=await admin_config_service.get_draft(_CONFIG_STEP5_5))


@router.put("/prompt/step5-5/draft/{fragment_key}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def put_step5_5_fragment_draft(
    fragment_key: str,
    body: Step55FragmentDraftBody,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if fragment_key not in STEP5_5_FRAGMENT_KEYS:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING, message=f"未知片段 key：{fragment_key}")

    draft = await admin_config_service.get_draft(_CONFIG_STEP5_5)
    if draft and draft.get("config_value"):
        current = draft["config_value"]
        if isinstance(current, str):
            try:
                current = json.loads(current)
            except (json.JSONDecodeError, TypeError):
                current = {}
        if not isinstance(current, dict):
            current = {}
    else:
        active = await admin_config_service.get_active_config(_CONFIG_STEP5_5)
        if isinstance(active, dict):
            current = dict(active)
        else:
            current = {}

    base = merge_step5_5_fragments(current)
    base[fragment_key] = body.content
    payload = json.dumps(base, ensure_ascii=False)

    result = await admin_config_service.save_draft(
        db, _CONFIG_STEP5_5, payload, admin_user.username,
    )
    return ApiResponse.ok(data=result)


@router.delete("/prompt/step5-5/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_step5_5_draft(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    ok = await admin_config_service.discard_draft(db, _CONFIG_STEP5_5)
    if not ok:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD)
    return ApiResponse.ok(message="草稿已丢弃")


@router.post("/prompt/step5-5/publish", dependencies=[require_role(*_ALLOWED_ROLES)])
async def publish_step5_5(
    body: PromptPublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认发布")
    if not body.test_passed:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED, message="请先测试通过后再发布")

    draft = await admin_config_service.get_draft(_CONFIG_STEP5_5)
    if not draft:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH)

    draft_val = draft.get("config_value")
    if not isinstance(draft_val, dict):
        return ApiResponse.fail(ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING, message="Step5.5 草稿格式无效")

    err = validate_step5_5_fragments_dict(draft_val)
    if err:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING, message=err)

    config_value = json.dumps(draft_val, ensure_ascii=False)

    stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_STEP5_5,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(stmt)
    active_config = active_result.scalars().first()
    before_value = active_config.config_value if active_config else None

    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_STEP5_5,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布 Step5.5 六段模板（step5_5_prompt_fragments）",
    )
    return ApiResponse.ok(data=result)


@router.get("/prompt/step5-5/history", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_5_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    result = await admin_config_service.get_version_history(db, _CONFIG_STEP5_5, page, page_size)
    return ApiResponse.ok(data=result)


@router.get("/prompt/step5-5/history/{version}", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_5_history_detail(
    version: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_STEP5_5,
        AdminConfig.version == version,
        AdminConfig.is_draft == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND, message=f"版本 V{version} 不存在")
    try:
        content = json.loads(row.config_value) if row.config_value else {}
    except (json.JSONDecodeError, TypeError):
        content = row.config_value
    return ApiResponse.ok(data={
        "version": row.version,
        "is_active": row.is_active,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "content": content,
    })


@router.post("/prompt/step5-5/rollback", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_5_rollback(
    body: PromptRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认回滚")
    try:
        result = await admin_config_service.rollback_config(
            db=db,
            config_key=_CONFIG_STEP5_5,
            version=body.version,
            admin_user=admin_user,
            request=request,
        )
    except ValueError as e:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND, message=str(e))
    return ApiResponse.ok(data=result)


# ═══════════════════ Step5.5 总开关 ═══════════════════


@router.get("/prompt/step5-5-switch", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_step5_5_switch(admin_user: AdminUser = Depends(get_current_admin)):
    detail = await admin_config_service.get_active_config_detail(_CONFIG_SWITCH)
    draft = await admin_config_service.get_draft(_CONFIG_SWITCH)

    enabled = False
    version = 0
    if detail and detail.get("content") is not None:
        enabled = _normalize_switch_enabled(detail["content"])
        version = int(detail.get("version") or 0)

    draft_enabled = None
    if draft and draft.get("config_value") is not None:
        draft_enabled = _normalize_switch_enabled(draft["config_value"])

    return ApiResponse.ok(data={
        "version": version,
        "has_draft": draft is not None,
        "enabled": enabled,
        "draft_enabled": draft_enabled,
    })


@router.get("/prompt/step5-5-switch/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def get_step5_5_switch_draft(admin_user: AdminUser = Depends(get_current_admin)):
    return ApiResponse.ok(data=await admin_config_service.get_draft(_CONFIG_SWITCH))


@router.put("/prompt/step5-5-switch/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def put_step5_5_switch_draft(
    body: Step55SwitchDraftBody,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    payload = json.dumps({"enabled": body.enabled}, ensure_ascii=False)
    result = await admin_config_service.save_draft(
        db, _CONFIG_SWITCH, payload, admin_user.username,
    )
    return ApiResponse.ok(data=result)


@router.delete("/prompt/step5-5-switch/draft", dependencies=[require_role(*_ALLOWED_ROLES)])
async def delete_step5_5_switch_draft(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    ok = await admin_config_service.discard_draft(db, _CONFIG_SWITCH)
    if not ok:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD)
    return ApiResponse.ok(message="草稿已丢弃")


@router.post("/prompt/step5-5-switch/publish", dependencies=[require_role(*_ALLOWED_ROLES)])
async def publish_step5_5_switch(
    body: PromptPublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认发布")
    # 布尔开关：不要求先跑主链 LLM 测试，以确认弹窗为准

    draft = await admin_config_service.get_draft(_CONFIG_SWITCH)
    if not draft:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH)

    draft_val = draft.get("config_value")
    config_value = (
        json.dumps(draft_val, ensure_ascii=False)
        if isinstance(draft_val, (dict, list))
        else (draft_val if isinstance(draft_val, str) else json.dumps(draft_val))
    )

    stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_SWITCH,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(stmt)
    active_config = active_result.scalars().first()
    before_value = active_config.config_value if active_config else None

    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_SWITCH,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="发布 Step5.5 总开关（step5_5_enabled）",
    )
    return ApiResponse.ok(data=result)


@router.get("/prompt/step5-5-switch/history", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_5_switch_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    result = await admin_config_service.get_version_history(db, _CONFIG_SWITCH, page, page_size)
    return ApiResponse.ok(data=result)


@router.post("/prompt/step5-5-switch/rollback", dependencies=[require_role(*_ALLOWED_ROLES)])
async def step5_5_switch_rollback(
    body: PromptRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认回滚")
    try:
        result = await admin_config_service.rollback_config(
            db=db,
            config_key=_CONFIG_SWITCH,
            version=body.version,
            admin_user=admin_user,
            request=request,
        )
    except ValueError as e:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND, message=str(e))
    return ApiResponse.ok(data=result)


# ═══════════════════ 在线测试：主链 Prompt ═══════════════════


@router.post("/prompt/test", dependencies=[require_role(*_ALLOWED_ROLES)])
async def test_prompt(
    body: PromptTestRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """
    使用 PromptBuilder.build_chat_prompt 拼装与线上一致的 Step5 主链 Prompt，
    再调用 LLM（Step5 JSON 解析）。
    """
    relationship_info = SimpleNamespace(
        level=body.relationship_level,
        growth_value=0,
        last_interaction_at=datetime.utcnow(),
        consecutive_login_days=1,
        relation_description=None,
        user_description=None,
        user_hobby_name=None,
        user_real_name=None,
        character_purpose=None,
        character_attitude=None,
    )

    memories = [{"content": m, "score": 0.9} for m in body.mock_memories]

    td = _generate_time_description()
    ad = await get_activity_description()
    round_ctx = _build_round_context(relationship_info, td, ad)

    system_prompt_override = None
    if body.use_draft:
        draft = await admin_config_service.get_draft(_CONFIG_STEP5)
        if draft and draft.get("config_value") is not None:
            system_prompt_override = _step5_extract_content(draft.get("config_value"))

    builder = PromptBuilder(db=db)
    full_prompt = await builder.build_chat_prompt(
        user_id=1,
        user_input=body.test_input,
        memories=memories,
        recent_conversations=[],
        relationship_info=relationship_info,
        emotion_context={"label": body.emotion_label, "confidence": 0.85},
        round_context=round_ctx,
        retrieval_results=_empty_retrieval_for_test(memories),
        system_prompt_override=system_prompt_override,
    )

    try:
        llm_result = await llm_service.chat_with_step5_parse(full_prompt, is_test=True)
        ai_reply = "\n".join(m.content for m in llm_result.messages)
    except Exception as e:
        logger.error("Prompt 测试 LLM 调用失败: %s", str(e))
        ai_reply = "LLM 调用失败，请稍后重试"

    redis = await get_redis()
    style_keywords = await admin_config_service._get_keywords(redis, "style_violation_keywords")
    boundary_keywords = await admin_config_service._get_keywords(redis, "persona_boundary_keywords")

    style_score, style_violations = admin_config_service._score_style(ai_reply, style_keywords)
    boundary_score, boundary_violations = admin_config_service._score_boundary(ai_reply, boundary_keywords)
    emotion_score = admin_config_service._score_emotion(ai_reply, body.emotion_label)

    total_score = round(style_score * 0.4 + boundary_score * 0.4 + emotion_score * 0.2)

    if total_score >= 80:
        level = "高"
    elif total_score >= 60:
        level = "中"
    else:
        level = "低"

    all_violations = style_violations + boundary_violations

    banned_keywords = await admin_config_service._get_keywords(redis, "banned_keywords")
    hit_banned = [kw for kw in banned_keywords if kw in ai_reply]
    is_safe = len(hit_banned) == 0
    safety_reason = f"命中违禁词：{'、'.join(hit_banned)}" if hit_banned else ""

    token_estimate = round(len(full_prompt) * 1.5)

    return ApiResponse.ok(data={
        "full_prompt": full_prompt,
        "ai_reply": ai_reply,
        "persona_match": {
            "total_score": total_score,
            "level": level,
            "style_score": style_score,
            "boundary_score": boundary_score,
            "emotion_score": emotion_score,
            "violations": all_violations,
        },
        "content_safety": {
            "is_safe": is_safe,
            "reason": safety_reason,
        },
        "token_estimate": token_estimate,
    })
