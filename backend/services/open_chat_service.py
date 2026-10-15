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


async def open_send(user_id, db, content, run_bundle, request_id=None):
    from backend.services.chat_lifecycle import AdmissionError
    try:
        admission=await chat_service.submit(user_id,db,'send',request_id,run_bundle,content=content,channel='open')
    except AdmissionError as exc:return ApiResponse.fail(exc.code,data=exc.status)
    return await _admission_response(admission,user_id)


async def open_resend(user_id,db,run_bundle,request_id=None):
    from backend.services.chat_lifecycle import AdmissionError
    try:admission=await chat_service.submit(user_id,db,'resend',request_id,run_bundle,channel='open')
    except AdmissionError as exc:return ApiResponse.fail(exc.code,data=exc.status)
    return await _admission_response(admission,user_id)


async def _payload_to_api_response(generation_id: str,user_id:int|None=None) -> ApiResponse:
    payload = await chat_service.await_bundle_payload(generation_id,user_id)
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


async def _admission_response(admission,user_id):
    response=await _payload_to_api_response(admission.generation_id,user_id)
    if response.code==10110:
        from backend.database import async_session_maker
        from backend.services.chat_lifecycle import read_status
        async with async_session_maker() as db:
            response.data=await read_status(db,user_id,admission.operation,admission.request_id)
    return response
