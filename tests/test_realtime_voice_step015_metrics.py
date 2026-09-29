import pytest
from backend.services.realtime_voice_turn_service import VoiceTurnService,EffectiveText
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step015_turns import turn_env,storage,Gate,event
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
async def test_turn_observations_after_state_advance_and_lock_release(turn_env):
    factory,call_id=turn_env;sink=CounterCache()
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate())
    class CheckedMetrics:
        async def emit_many(self,events):
            assert not service._lock.locked()
            assert service._sequence>=1 or events[0][1]['kind']=='out_of_order'
            await VoiceMetrics(sink).emit_many(events)
    service.metrics=CheckedMetrics()
    await service.consume(event(call_id,2,'asr_final','private-final'))
    await service.consume(event(call_id,1,'asr_interim','private-interim'))
    await service.consume(event(call_id,2,'asr_final','private-replay'))
    with pytest.raises(ValueError):await service.consume(event('other-call',3,'asr_final','private-orphan'))
    events=[e for b in sink.batches for e in b]
    assert events==[('voice.turn.event',{'kind':kind},1) for kind in ('out_of_order','interim','final','duplicate','orphan')]
    assert 'private-' not in str(events) and call_id not in str(events)


@pytest.mark.asyncio
@pytest.mark.parametrize('rollback',[False,True])
async def test_finalizer_incomplete_metric_follows_owner_commit(turn_env,rollback):
    factory,call_id=turn_env;sink=CounterCache();metrics=VoiceMetrics(sink)
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate(),metrics=metrics)
    await service.consume(event(call_id,1,'asr_final','private-final'));await service.freeze()
    before=list(sink.batches)
    async with factory() as db:
        await service.final_flush(db)
        assert sink.batches==before
        if rollback:await db.rollback()
        else:await db.commit()
        await flush_voice_metrics(db,metrics)
    extra=[e for b in sink.batches[len(before):] for e in b]
    assert extra==([] if rollback else [('voice.turn.event',{'kind':'incomplete'},1)])


@pytest.mark.asyncio
async def test_turn_close_duration_and_duplicate_effective(turn_env,monkeypatch):
    from types import SimpleNamespace
    import backend.services.realtime_voice_turn_service as module
    factory,call_id=turn_env;sink=CounterCache()
    service=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=Gate(),metrics=VoiceMetrics(sink))
    await service.consume(event(call_id,1,'asr_final','private-final'))
    await service.consume(event(call_id,2,'chat_text','private-answer',reply='r1'))
    await service.consume(event(call_id,3,'tts_finished',{},reply='r1'))
    service._drafts['q1'].started_clock=10
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:12))
    result=EffectiveText('private-answer','full',completed=True)
    assert await service.apply_effective('r1',result)
    assert not await service.apply_effective('r1',result)
    events=[e for b in sink.batches for e in b]
    assert events.count(('voice.turn.close_duration_ms',{},2000))==1
    assert events.count(('voice.turn.closed',{},1))==1
    assert events[-1]==('voice.turn.event',{'kind':'duplicate'},1)


@pytest.mark.asyncio
@pytest.mark.parametrize('outer_rollback',[False,True])
async def test_savepoint_discards_only_its_own_observations(turn_env,outer_rollback):
    from backend.services.realtime_voice_metric_service import stage_voice_metrics
    factory,_=turn_env;sink=CounterCache()
    async with factory() as db:
        async with db.begin():
            stage_voice_metrics(db,[('voice.turn.event',{'kind':'incomplete'},1)])
            try:
                async with db.begin_nested():
                    stage_voice_metrics(db,[('voice.turn.event',{'kind':'duplicate'},1)])
                    async with db.begin_nested():
                        stage_voice_metrics(db,[('voice.turn.event',{'kind':'late'},1)])
                    raise ValueError('rollback savepoint')
            except ValueError:pass
            async with db.begin_nested():
                stage_voice_metrics(db,[('voice.turn.event',{'kind':'isolation_failed'},1)])
            if outer_rollback:await db.rollback()
        await flush_voice_metrics(db,VoiceMetrics(sink))
    assert [e for batch in sink.batches for e in batch]==([] if outer_rollback else [
        ('voice.turn.event',{'kind':'incomplete'},1),('voice.turn.event',{'kind':'isolation_failed'},1)])


@pytest.mark.asyncio
async def test_flush_integrity_failure_preserves_outer_metrics(turn_env):
    from backend.models.realtime_voice import VoiceCallTurn
    from backend.services.realtime_voice_metric_service import stage_voice_metrics
    from sqlalchemy.exc import IntegrityError
    factory,call_id=turn_env;sink=CounterCache()
    async with factory() as db:
        async with db.begin():
            stage_voice_metrics(db,[('voice.turn.event',{'kind':'incomplete'},1)])
            with pytest.raises(IntegrityError):
                async with db.begin_nested():
                    stage_voice_metrics(db,[('voice.turn.event',{'kind':'late'},1)])
                    db.add(VoiceCallTurn(call_id=call_id))  # required columns deliberately missing
                    await db.flush()
        await flush_voice_metrics(db,VoiceMetrics(sink))
    assert sink.batches==[[('voice.turn.event',{'kind':'incomplete'},1)]]
