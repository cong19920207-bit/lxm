"""CALL-SUM output validation and closed-turn input isolation."""
import json
from types import SimpleNamespace
import pytest
from backend.services.realtime_voice_summary_service import parse_summary,build_summary_prompt,generate_summary


def output(**changes):
    result=dict(call_summary='聊了下个月去日本的计划',unfinished_topics=['日本行程准备'],user_emotion='期待',assistant_emotion='开心',should_send_followup=True,reasoning='旅行话题没有展开',followup_delay_minutes=90,followup_content='你的行程定到哪一步啦',content_type='topic_continuation')
    return {**result,**changes}


def turn(**changes):
    return SimpleNamespace(turn_index=1,user_text_final='下个月去日本',assistant_text_effective='可以看看京都',assistant_text_generated='未播放的完整调试文本',turn_status='finalized',effective_text_evidence='full',user_content_safety_status='passed',assistant_content_safety_status='passed',user_crisis_status='passed',assistant_crisis_status='passed',**changes)


def test_valid_summary_keeps_reasoning_separate_from_public_fields():
    value=parse_summary(json.dumps(output()))
    assert value.call_summary=='聊了下个月去日本的计划'
    assert value.reasoning=='旅行话题没有展开'
    assert value.followup['delay_minutes']==90
    assert 'reasoning' not in value.call_fields()
    assert set(value.call_fields())=={'call_summary','unfinished_topics','user_emotion','assistant_emotion'}


@pytest.mark.parametrize('changes',[
    {'call_summary':''},{'call_summary':'第一行\n第二行'},{'user_emotion':'a'*65},
    {'unfinished_topics':'话题'},{'unfinished_topics':[{}]},
    {'should_send_followup':'true'},{'followup_delay_minutes':True},
    {'followup_delay_minutes':-1},{'followup_content':''},{'content_type':'missed_explanation'},
    {'unknown_private_output':'secret'},
])
def test_invalid_output_never_becomes_ready(changes):
    with pytest.raises(ValueError):parse_summary(json.dumps(output(**changes)))


def test_no_followup_does_not_require_candidate_and_empty_reasoning_is_valid():
    value=parse_summary(json.dumps(output(should_send_followup=False,reasoning=None,followup_content=None,followup_delay_minutes=None,content_type=None)))
    assert value.followup is None and value.reasoning is None


def test_prompt_excludes_unplayed_unsafe_crisis_and_open_turns():
    rows=[turn()]
    for field,value in [('user_content_safety_status','matched'),('assistant_crisis_status','matched'),('turn_status','open'),('effective_text_evidence','none')]:
        row=turn();setattr(row,field,value);row.user_text_final='不能进入摘要的正文';rows.append(row)
    prompt=build_summary_prompt(duration_seconds=20,turns=rows)
    assert '下个月去日本' in prompt and '可以看看京都' in prompt
    assert '未播放的完整调试文本' not in prompt and '不能进入摘要的正文' not in prompt


@pytest.mark.asyncio
async def test_generated_output_must_pass_safety_before_return():
    assessed=[]
    async def model(prompt):return json.dumps(output())
    async def assess(text):assessed.append(text);return False
    with pytest.raises(ValueError,match='summary_output_rejected'):
        await generate_summary(duration_seconds=20,turns=[turn()],model=model,permits=assess)
    assert assessed

@pytest.mark.asyncio
@pytest.mark.parametrize('reasoning,mode',[({},'pass'),('内部说明','reject'),('内部说明','error')])
async def test_reasoning_failure_is_independent_of_valid_summary(reasoning,mode):
    async def model(prompt):return json.dumps(output(reasoning=reasoning))
    async def permits(value):
        if value=='内部说明':
            if mode=='error':raise RuntimeError('controlled reasoning check unavailable')
            return mode!='reject'
        return True
    result=await generate_summary(duration_seconds=20,turns=[turn()],model=model,permits=permits)
    assert result.reasoning is None and result.call_summary=='聊了下个月去日本的计划'
