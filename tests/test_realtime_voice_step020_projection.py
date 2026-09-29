from types import SimpleNamespace
from datetime import datetime
import pytest
from backend.constants.realtime_voice_config import get_default_voice_call_script
from backend.services.realtime_voice_presentation_service import call_presentation

@pytest.mark.parametrize('connected,reason,expected',[
    (False,'system_error','暂时无法接通'),(True,'system_error','通话暂时中断，请稍后再试'),
    (False,'provider_error','暂时无法接通'),(True,'provider_error','通话暂时中断，请稍后再试'),
    (True,'exit_intent','好，那我们先聊到这'),
    (True,'silence_timeout','好像暂时听不到你，我们下次再聊'),
    (True,'quota_exhausted','今天能聊的时间用完啦，我们下次再聊'),
    (True,'user_hangup','就先聊到这'),(True,'reconnect_timeout','网络没有恢复，我们下次再接着聊'),
    (True,'hard_limit','这次聊得有点久，我们先休息一下')])
def test_end_copy_uses_connection_anchor_and_published_snapshot(connected,reason,expected):
    row=SimpleNamespace(call_id='c1',status='ended' if connected else 'failed',end_reason=reason,
        connected_at=datetime.now() if connected else None,duration_seconds=42,
        config_snapshot={'resolved_script':get_default_voice_call_script()})
    value=call_presentation(row)
    assert value['end_message']==expected
    assert value['has_connected']==connected
    assert value['duration_seconds']==(42 if connected else 0)
    if connected:
        row.config_snapshot['resolved_script']['end_reason'][reason]='已发布的新文案'
        assert call_presentation(row)['end_message']=='已发布的新文案'


def test_cancel_never_renders_an_ended_page():
    row=SimpleNamespace(call_id='c1',status='cancelled',end_reason='user_cancel',connected_at=None,
        duration_seconds=0,config_snapshot={'resolved_script':get_default_voice_call_script()})
    assert call_presentation(row)['show_end_page'] is False


@pytest.mark.parametrize('script', [{}, get_default_voice_call_script(),
    {'followup': {'missed_explanation_template': '仅用于后续消息的已发布文案'}}])
def test_missed_result_does_not_use_or_mutate_followup_template(script):
    from copy import deepcopy
    row = SimpleNamespace(call_id='missed-test', status='missed', end_reason=None,
        connected_at=None, duration_seconds=0, config_snapshot={'resolved_script': deepcopy(script)})
    snapshot = deepcopy(row.config_snapshot)
    value = call_presentation(row)
    assert value['end_message'] == '她现在可能不方便'
    assert value['has_connected'] is False
    assert value['duration_seconds'] == 0
    assert value['show_end_page'] is True
    assert row.config_snapshot == snapshot
