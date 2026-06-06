# -*- coding: utf-8 -*-
# Open API 对话 Facade（同步 JSON）

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    ERR_CHAT_GENERATION_OBSOLETE,
    ERR_CHAT_QUEUE_FULL,
    ERR_CONTENT_EMPTY,
    ERR_CONTENT_UNSAFE,
    ERR_LLM_FAILED,
)
from backend.schemas.common import ApiResponse
from backend.services import chat_service
from backend.services.timeline_read_service import get_timeline


async def open_send(
    user_id: int,
    db: AsyncSession,
    content: str,
    run_bundle: Callable[[int], Awaitable[None]],
) -> ApiResponse:
    safety = await chat_service.check_content_safety(content)
    if not safety.get("ok"):
        return ApiResponse.fail(safety["code"])

    if await chat_service.check_send_quota(user_id, db):
        await chat_service.trigger_recovery_if_queue_stuck(user_id, db, run_bundle)
        return ApiResponse.fail(ERR_CHAT_QUEUE_FULL)

    generation_id = await chat_service.enqueue_send(
        user_id,
        db,
        safety["content"],
        safety["persona_risk_flag"],
        safety["persona_risk_type"],
        run_bundle,
    )
    return await _payload_to_api_response(generation_id)


async def open_resend(
    user_id: int,
    db: AsyncSession,
    run_bundle: Callable[[int], Awaitable[None]],
) -> ApiResponse:
    generation_id, err_code = await chat_service.enqueue_resend(user_id, db, run_bundle)
    if err_code is not None:
        return ApiResponse.fail(err_code)
    return await _payload_to_api_response(generation_id)


async def _payload_to_api_response(generation_id: str) -> ApiResponse:
    payload = await chat_service.await_bundle_payload(generation_id)
    if payload.get("obsolete"):
        return ApiResponse.fail(ERR_CHAT_GENERATION_OBSOLETE)
    if payload.get("error"):
        code = payload.get("code", ERR_LLM_FAILED)
        return ApiResponse.fail(code)
    messages, emotion, round_id = chat_service.build_done_messages_from_payload(payload)
    if not round_id:
        return ApiResponse.fail(ERR_LLM_FAILED)
    return ApiResponse.ok(
        data={
            "messages": messages,
            "emotion": emotion,
            "round_id": round_id,
        }
    )


async def open_get_timeline(
    user_id: int,
    db: AsyncSession,
    cursor: int | None,
    limit: int,
) -> dict[str, Any]:
    return await get_timeline(user_id, db, cursor=cursor, limit=limit)
