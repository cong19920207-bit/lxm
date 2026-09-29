import asyncio
import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, func

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceCallTurn, VoiceMemoryJob, VoiceMemoryTrace
from backend.models.relationship import Relationship
from tests.test_realtime_voice_step009_ops import storage, add_call, StateCache
from tests.test_realtime_voice_step015_turns import Gate


@pytest_asyncio.fixture
async def memory_env(storage):
    async with storage.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[m.__table__ for m in
            (VoiceCallTurn, VoiceMemoryJob, VoiceMemoryTrace, Relationship)])
    call = await add_call(storage, 'connected', StateCache())
    async with storage() as db:
        row = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call))
        row.config_snapshot = {**row.config_snapshot, 'resolved_script':{'memory':{
            'prompt_template':'提取长期事实', 'max_items_per_turn':5}}}
        await db.commit()
    return storage, call


async def add_turn(factory, call, index=1, **changes):
    async with factory() as db:
        row=VoiceCallTurn(call_id=call, turn_index=index, question_id=f'q{index}',
            reply_id=f'r{index}', turn_status='finalized', user_text_final='下月去日本',
            assistant_text_effective='去看看京都', effective_text_evidence='full',
            memory_status='pending', user_content_safety_status='passed',
            assistant_content_safety_status='passed', user_crisis_status='passed',
            assistant_crisis_status='passed', started_at=datetime.utcnow(), finalized_at=datetime.utcnow(),
            effective_text_expires_at=datetime.utcnow()+timedelta(days=180))
        for key,value in changes.items(): setattr(row,key,value)
        db.add(row); await db.commit()
        return row.id


class Writer:
    def __init__(self): self.docs={}; self.calls=[]
    async def __call__(self, **kw):
        from backend.utils.character_knowledge_validate import build_doc_id
        doc=build_doc_id(kw['memory_type'],kw['key'],kw['user_id'])
        self.docs[doc]=kw['value']; self.calls.append(doc)
        return doc


@pytest.mark.asyncio
async def test_unique_jobs_ordered_two_routes_and_trace(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env
    turns=[await add_turn(factory,call,i) for i in (1,2)]
    writer=Writer()
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"},{"memory_type":"character_private","stable_key":"后续话题-日本-行程","content":"以后问行程"}]}'
    service=VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=writer)
    for turn in turns:
        await service.enqueue(call_id=call, turn_id=turn)
        await service.enqueue(call_id=call, turn_id=turn)
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceMemoryJob)) == 2
    assert await service.process_next(call_id=call) == 'success'
    assert await service.process_next(call_id=call) == 'success'
    assert await service.process_next(call_id=call) == 'idle'
    assert len(writer.docs)==2 and len(writer.calls)==4
    async with factory() as db:
        traces=(await db.scalars(select(VoiceMemoryTrace).order_by(VoiceMemoryTrace.turn_index))).all()
        assert [t.turn_index for t in traces]==[1,1,2,2]
        assert {t.memory_type for t in traces}=={'user','character_private'}
        assert all(t.pipeline_version=='voice_memory_v1' for t in traces)


@pytest.mark.asyncio
async def test_model_wait_does_not_hold_call_lock_or_start_duplicate(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env; turn=await add_turn(factory,call)
    entered,release=asyncio.Event(),asyncio.Event()
    async def model(prompt):
        entered.set(); await release.wait(); return '{"memory_items":[]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer())
    await service.enqueue(call_id=call,turn_id=turn)
    task=asyncio.create_task(service.process_next(call_id=call))
    try:
        await asyncio.wait_for(entered.wait(),1)
        next_turn=await asyncio.wait_for(add_turn(factory,call,2),1)
        await asyncio.wait_for(service.enqueue(call_id=call,turn_id=next_turn),1)
        assert await service.process_next(call_id=call)=='busy'
    finally:
        release.set(); await task


@pytest.mark.asyncio
async def test_claim_lease_covers_extended_extraction_and_five_writes(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory, call = memory_env
    turn = await add_turn(factory, call)
    writer = Writer()

    async def model(prompt):
        async with factory() as db:
            job = await db.scalar(select(VoiceMemoryJob))
            remaining = (job.lease_expires_at - datetime.utcnow()).total_seconds()
            assert remaining > 200
        return json.dumps({'memory_items': [
            {'memory_type': 'user', 'stable_key': f'旅行-计划-{index}', 'content': f'计划{index}'}
            for index in range(5)]}, ensure_ascii=False)

    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=writer)
    await service.enqueue(call_id=call, turn_id=turn)

    assert await service.process_next(call_id=call) == 'success'
    assert len(writer.calls) == 5
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceMemoryTrace)) == 5


@pytest.mark.asyncio
async def test_risk_empty_low_confidence_and_fence_skip_all_writes(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env; writer=Writer()
    async def forbidden(prompt): pytest.fail('ineligible input reached model')
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=forbidden,writer=writer)
    for index,change in enumerate((dict(user_content_safety_status='matched'),
        dict(user_asr_confidence=.49),dict(assistant_text_effective=''),dict(user_text_final='嗯')),1):
        turn=await add_turn(factory,call,index,**change)
        assert await service.enqueue(call_id=call,turn_id=turn)=='skipped'
    turn=await add_turn(factory,call,5)
    await service.enqueue(call_id=call,turn_id=turn)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        row.deletion_fence_at=datetime.utcnow();await db.commit()
    assert await service.process_next(call_id=call)=='cancelled'
    assert not writer.docs


@pytest.mark.asyncio
async def test_real_turn_commit_creates_job_and_retains_supplied_confidence(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    from backend.services.realtime_voice_turn_service import VoiceTurnService, EffectiveText
    from backend.services.realtime_voice_provider_service import ProviderEvent
    from tests.test_realtime_voice_step015_turns import event
    factory,call=memory_env
    turns=VoiceTurnService(call_id=call,session_id='session1',session_factory=factory,gate=Gate(),
                           memory_job_writer=VoiceMemoryService.stage_job)
    await turns.consume(ProviderEvent('asr_final',call,'session1',1,'q1',None,'下月去日本',asr_confidence=.49))
    await turns.consume(event(call,2,'chat_text','去看看京都',reply='r1'))
    await turns.consume(event(call,3,'tts_finished',{},reply='r1'))
    await turns.apply_effective('r1',EffectiveText('去看看京都','full',completed=True))
    async with factory() as db:
        turn=await db.scalar(select(VoiceCallTurn).where(VoiceCallTurn.call_id==call))
        job=await db.scalar(select(VoiceMemoryJob).where(VoiceMemoryJob.call_id==call))
        assert turn.user_asr_confidence==.49 and turn.memory_status==job.status=='skipped'


@pytest.mark.asyncio
async def test_relationship_is_read_only_model_context(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env; turn=await add_turn(factory,call)
    async with factory() as db:
        db.add(Relationship(user_id=1,level=1,growth_value=12,relation_description='熟悉的朋友'))
        await db.commit()
    async def model(prompt):
        assert '熟悉的朋友' in prompt
        return '{"memory_items":[]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer())
    await service.enqueue(call_id=call,turn_id=turn)
    assert await service.process_next(call_id=call)=='skipped'
    async with factory() as db:
        relationship=await db.scalar(select(Relationship))
        assert (relationship.level,relationship.growth_value,relationship.relation_description)==(1,12,'熟悉的朋友')


@pytest.mark.asyncio
async def test_poll_consumes_persisted_jobs(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env; turn=await add_turn(factory,call)
    async def model(prompt): return '{"memory_items":[]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer())
    await service.enqueue(call_id=call,turn_id=turn)
    assert await service.poll()==['skipped']
    assert await service.poll()==[]


@pytest.mark.asyncio
async def test_scheduler_wrapper_drains_persisted_job(memory_env, monkeypatch):
    import backend.services.realtime_voice_memory_service as memory
    from backend.tasks.scheduler import _run_voice_memory
    factory,call=memory_env; turn=await add_turn(factory,call)
    async def model(prompt): return '{"memory_items":[]}'
    service=memory.VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer())
    await service.enqueue(call_id=call,turn_id=turn)
    async def build(): return service
    monkeypatch.setattr(memory,'build_voice_memory_service',build)
    await _run_voice_memory()
    async with factory() as db:
        assert (await db.scalar(select(VoiceMemoryJob))).status=='skipped'
