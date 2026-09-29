# -*- coding: utf-8 -*-
"""STEP-003 application-level 语音引用完整性校验。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.admin_user import AdminUser
from backend.models.agent_message import AgentMessage
from backend.models.realtime_voice import (
    VoiceCall,
    VoiceCallCreateIdempotency,
    VoiceCallTurn,
    VoiceCapabilityEvidence,
    VoiceCrisisRecord,
    VoiceFollowupJob,
    VoiceMemoryJob,
    VoiceMemoryTrace,
    VoicePostprocessJob,
    VoiceUsageLedger,
)


class VoiceReferenceValidationError(ValueError):
    """应用层弱引用不存在或跨对象不一致。"""


async def _call_for_id(db: AsyncSession, call_id: str) -> VoiceCall:
    result = await db.execute(select(VoiceCall).where(VoiceCall.call_id == call_id))
    call = result.scalar_one_or_none()
    if call is None:
        raise VoiceReferenceValidationError(f"voice_call 不存在: {call_id}")
    return call


async def _turn_for_call_index(
    db: AsyncSession,
    call_id: str,
    turn_index: int,
) -> VoiceCallTurn:
    result = await db.execute(
        select(VoiceCallTurn).where(
            VoiceCallTurn.call_id == call_id,
            VoiceCallTurn.turn_index == turn_index,
        )
    )
    turn = result.scalar_one_or_none()
    if turn is None:
        raise VoiceReferenceValidationError(
            f"voice_call_turn 不存在或不匹配: call_id={call_id}, turn_index={turn_index}"
        )
    return turn


async def validate_voice_application_references(
    db: AsyncSession,
    record: object,
) -> None:
    """在写入前校验 STEP-003 明确保留为 application-level 的引用。"""

    if isinstance(record, VoiceCallTurn):
        await _call_for_id(db, record.call_id)
        return

    if isinstance(record, VoiceCall):
        if record.deleted_by is None:
            return
        if await db.get(AdminUser, record.deleted_by) is None:
            raise VoiceReferenceValidationError(
                f"删除操作管理员不存在: {record.deleted_by}"
            )
        return

    if isinstance(record, VoiceCallCreateIdempotency):
        if record.call_id is None:
            return
        call = await _call_for_id(db, record.call_id)
        if call.user_id != record.user_id:
            raise VoiceReferenceValidationError("幂等记录 user_id 与 voice_call 不一致")
        return

    if isinstance(record, VoiceMemoryJob):
        turn = await db.get(VoiceCallTurn, record.turn_id)
        if turn is None:
            raise VoiceReferenceValidationError(f"voice_call_turn 不存在: {record.turn_id}")
        if turn.call_id != record.call_id or turn.turn_index != record.turn_index:
            raise VoiceReferenceValidationError("memory job 的 call_id/turn_index 与 turn_id 不一致")
        return

    if isinstance(record, VoiceFollowupJob):
        call = await _call_for_id(db, record.call_id)
        if call.user_id != record.user_id:
            raise VoiceReferenceValidationError("follow-up user_id 与 voice_call 不一致")
        if record.agent_message_id is not None:
            message = await db.get(AgentMessage, record.agent_message_id)
            if message is None:
                raise VoiceReferenceValidationError(
                    f"agent_message 不存在: {record.agent_message_id}"
                )
            if message.user_id != record.user_id:
                raise VoiceReferenceValidationError(
                    "follow-up user_id 与 agent_message 不一致"
                )
        return

    if isinstance(record, VoiceCapabilityEvidence):
        if record.operator_id is None:
            return
        if await db.get(AdminUser, record.operator_id) is None:
            raise VoiceReferenceValidationError(
                f"能力证据操作管理员不存在: {record.operator_id}"
            )
        return

    if isinstance(record, (VoiceMemoryTrace, VoiceCrisisRecord)):
        await _turn_for_call_index(db, record.call_id, record.turn_index)
        return

    if isinstance(record, (VoiceUsageLedger, VoicePostprocessJob)):
        await _call_for_id(db, record.call_id)
        return

    raise TypeError(f"不支持的语音引用校验对象: {type(record).__name__}")
