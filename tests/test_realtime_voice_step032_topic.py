"""Topic recheck protocol and input isolation; provider smoke is separate."""
import json
import pytest


def inputs(**changes):
    return dict(user_id=1,source_call_id='source',content_type='topic_continuation',
        followup_content='京都行程的日期定下来了吗？',unfinished_topics=['京都行程日期'],
        later_user_texts=['京都行程已定为下周一，不用再问日期。'],
        config_snapshot={'resolved_config':{'summary':{'model':'deepseek-v4-pro'}},'credential_ref':'MUST_NOT_ENTER_PROMPT'},**changes)


@pytest.mark.asyncio
@pytest.mark.parametrize('verdict',[True,False])
async def test_topic_strict_boolean_and_safe_projection(verdict):
    from backend.services.realtime_voice_followup_topic_service import VoiceFollowupTopicCheck
    seen=[]
    def factory(snapshot):
        assert snapshot['credential_ref']=='MUST_NOT_ENTER_PROMPT'
        async def model(prompt):seen.append(prompt);return json.dumps({'continued':verdict})
        return model
    check=VoiceFollowupTopicCheck(model_factory=factory)
    assert await check(**inputs()) is verdict
    assert len(seen)==1 and 'MUST_NOT_ENTER_PROMPT' not in seen[0]
    data=json.loads(seen[0].split('INPUT_JSON:\n')[1])
    assert set(data)=={'content_type','followup_content','unfinished_topics','later_user_texts'}
    assert data['later_user_texts']==inputs()['later_user_texts']


@pytest.mark.asyncio
@pytest.mark.parametrize('raw',['{}','{"continued":null}','{"continued":"false"}',
    '{"continued":0}','{"continued":false,"reasoning":"secret"}',
    '{"continued":true,"continued":false}','```json\n{"continued":false}\n```'])
async def test_unknown_or_invalid_topic_result_is_not_permission_to_send(raw):
    from backend.services.realtime_voice_followup_topic_service import VoiceFollowupTopicCheck
    def factory(snapshot):
        async def model(prompt):return raw
        return model
    with pytest.raises(RuntimeError):await VoiceFollowupTopicCheck(model_factory=factory)(**inputs())


@pytest.mark.asyncio
async def test_same_recheck_reuses_verdict_but_changed_transcript_rechecks():
    from backend.services.realtime_voice_followup_topic_service import VoiceFollowupTopicCheck
    calls=[]
    def factory(snapshot):
        async def model(prompt):calls.append(prompt);return '{"continued":false}'
        return model
    check=VoiceFollowupTopicCheck(model_factory=factory)
    await check(**inputs());await check(**inputs())
    changed=inputs();changed['later_user_texts']=['我不想再谈行程日期。']
    await check(**changed)
    assert len(calls)==2
    # The bounded cache retains only a digest/verdict, no transcript.
    assert '京都' not in repr(check._last)


@pytest.mark.asyncio
async def test_provider_error_is_not_cached_as_false():
    from backend.services.realtime_voice_followup_topic_service import VoiceFollowupTopicCheck
    tries=[]
    def factory(snapshot):
        async def model(prompt):
            tries.append(1)
            if len(tries)==1:raise RuntimeError('provider unavailable')
            return '{"continued":true}'
        return model
    check=VoiceFollowupTopicCheck(model_factory=factory)
    with pytest.raises(RuntimeError):await check(**inputs())
    assert await check(**inputs()) is True
