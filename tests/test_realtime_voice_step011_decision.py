import pytest


def test_ready_and_target_are_both_required_and_deadline_is_technical_failure():
    from backend.services.realtime_voice_decision_service import RingGate
    gate=RingGate(target_seconds=6)
    assert gate.result(elapsed=3,ready=True)=='ringing'
    assert gate.result(elapsed=6,ready=False)=='ringing'
    assert gate.result(elapsed=6,ready=True)=='connected'
    assert gate.result(elapsed=12,ready=False)=='failed'
    assert gate.result(elapsed=5,ready=True,cancelled=True)=='cancelled'


@pytest.mark.asyncio
@pytest.mark.parametrize('result',['not json','{"answer":"yes","delay_seconds":6,"opening_text":"hi"}'])
async def test_invalid_model_output_falls_back_without_shared_stats(result):
    from backend.services.realtime_voice_decision_service import decide_call
    calls=[];metrics=[]
    async def model(prompt):calls.append(prompt);return result
    decision=await decide_call(inputs={'is_first_call':True,'missed_last_5_minutes':0},settings={'prompt_template':'决定是否接听'},
                               model=model,metric=lambda key,value:metrics.append(key))
    assert decision.answer and 4<=decision.delay_seconds<=8 and decision.fallback
    assert len(calls)==1 and all(key.startswith('voice.call01.') for key in metrics)


@pytest.mark.asyncio
async def test_first_and_subsequent_use_same_model_and_five_misses_only_override_decision():
    from backend.services.realtime_voice_decision_service import decide_call
    prompts=[]
    async def model(prompt):prompts.append(prompt);return '{"answer":false,"delay_seconds":0,"opening_text":""}'
    results=[]
    for first,missed in ((True,0),(False,0),(False,5)):
        results.append(await decide_call(inputs={'is_first_call':first,'missed_last_5_minutes':missed},settings={'prompt_template':'同一模板'},model=model))
    assert [r.answer for r in results]==[False,False,True]
    assert len(prompts)==3 and all(p.startswith('同一模板') for p in prompts)


@pytest.mark.asyncio
@pytest.mark.parametrize('settings,expected',[
    ({'min_ring_seconds':5,'max_wait_seconds':7},7),
    ({'min_ring_seconds':1,'max_wait_seconds':99},12)])
async def test_frozen_ring_settings_preserve_hard_bounds(settings,expected):
    from backend.services.realtime_voice_decision_service import decide_call
    async def model(prompt):return '{"answer":true,"delay_seconds":12,"opening_text":"喂"}'
    decision=await decide_call(inputs={},settings={'prompt_template':'决定',**settings},model=model)
    assert decision.delay_seconds==expected


@pytest.mark.asyncio
async def test_fallback_uses_frozen_neutral_interval():
    from backend.services.realtime_voice_decision_service import decide_call
    decision=await decide_call(inputs={},settings={'prompt_template':'','fallback_delay_min_seconds':6,'fallback_delay_max_seconds':6})
    assert decision.fallback and decision.delay_seconds==6 and decision.opening_text=='喂，我在。'

@pytest.mark.asyncio
async def test_model_timeout_has_neutral_fallback_and_exact_scoped_metrics():
    from backend.services.realtime_voice_decision_service import decide_call
    metrics=[]
    async def model(prompt):raise TimeoutError('sentinel-provider-body')
    result=await decide_call(inputs={},settings={'prompt_template':'shared'},model=model,metric=lambda key,value:metrics.append((key,value)))
    assert result.answer and result.fallback and result.failure_category=='timeout'
    assert 4<=result.delay_seconds<=8 and result.opening_text=='喂，我在。'
    assert metrics==[('voice.call01.fallback.timeout',1),('voice.call01.decision.answer',1)]
