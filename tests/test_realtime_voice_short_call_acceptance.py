"""AC39: a short call can retain meaningful memory without a summary."""
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall, VoiceCallTurn
from backend.services.realtime_voice_card_service import stage_call_card
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_step031_jobs import summary_env, card_env, memory_env, storage, service
from tests.test_realtime_voice_step028_jobs import Writer, Gate


@pytest.mark.asyncio
async def test_short_call_keeps_static_card_and_memory_without_summary_model(summary_env):
    factory, call_id = summary_env
    async with factory() as db:
        row = await db.scalar(select(VoiceCall))
        row.duration_seconds = 14
        row.summary_status = 'not_applicable'
        await stage_call_card(db,row)
        await db.commit()
        sequence = row.sort_seq
        turn = await db.scalar(select(VoiceCallTurn))
        turn_id = turn.id
    async def forbidden(prompt):
        pytest.fail('short call must not invoke summary model')
    summary = service(factory,model=forbidden)
    await summary.enqueue(call_id=call_id)
    assert await summary.process(call_id=call_id) == 'not_applicable'
    calls=[]
    async def memory_model(prompt):
        calls.append(prompt)
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    writer=Writer()
    memory=VoiceMemoryService(session_factory=factory,gate=Gate(),model=memory_model,writer=writer)
    await memory.enqueue(call_id=call_id,turn_id=turn_id)
    assert await memory.process_next(call_id=call_id) == 'success'
    assert len(calls)==1 and len(writer.docs)==1
    async with factory() as db:
        row=await db.scalar(select(VoiceCall))
        assert row.sort_seq==sequence and sequence is not None
        assert row.summary_status=='not_applicable' and row.call_summary is None
