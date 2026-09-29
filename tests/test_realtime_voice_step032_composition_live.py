"""Synthetic full adapter smoke: actual DeepSeek and isolated MySQL/Redis."""
import json
import os
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import select,func
from backend.models.realtime_voice import VoiceCall,VoiceFollowupJob
from backend.models.agent_message import AgentMessage
from tests.test_realtime_voice_step032_dispatch_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step032_dispatch import dispatch_env

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1' or
    os.getenv('RUN_VOICE_DEEPSEEK_SMOKE')!='1',reason='isolated stores and synthetic provider opt-in')


@pytest.mark.asyncio
@pytest.mark.parametrize('name,later,expected',[
    ('continued','京都行程已经定为下周一，不用再问日期。','cancelled'),
    ('unrelated','今天早餐吃了面包，味道不错。','sent'),
])
async def test_actual_model_composed_dispatch(dispatch_env,runtime,monkeypatch,name,later,expected):
    import backend.database as database
    import backend.redis_client as redis_module
    from backend.config import get_deepseek_api_key
    from backend.constants.realtime_voice_summary import DEFAULT_VOICE_SUMMARY_MODEL
    from backend.services.realtime_voice_followup_runtime import build_voice_followup_service
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from tests.test_realtime_voice_step028_jobs import add_turn
    if not get_deepseek_api_key():pytest.skip('configured DeepSeek credential unavailable')
    factory,source_id,job_id,clock=dispatch_env;_,_,cache=runtime
    await add_turn(factory,source_id,user_text_final='想去京都旅行，日期还没决定。',
        effective_text_expires_at=clock[0]+timedelta(days=1))
    newer=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        source=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==source_id))
        source.status='ended';source.connected_at=source.ended_at-timedelta(seconds=60)
        source.duration_seconds=60;source.summary_status='ready';source.unfinished_topics=['京都行程日期']
        source.config_snapshot={'resolved_config':{'summary':{'model':DEFAULT_VOICE_SUMMARY_MODEL}}}
        later_call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==newer))
        later_call.connected_at=clock[0]-timedelta(minutes=1)
        job=await db.get(VoiceFollowupJob,job_id)
        job.content_type='topic_continuation';job.content='京都行程的日期定下来了吗？'
        await db.commit()
    await add_turn(factory,newer,user_text_final=later,effective_text_expires_at=clock[0]+timedelta(days=1))
    async def redis_provider():return cache
    async def quota(**kw):return True  # Explicit synthetic eligibility; no production policy.
    monkeypatch.setattr(database,'async_session_maker',factory)
    monkeypatch.setattr(redis_module,'get_redis',redis_provider)
    service=await build_voice_followup_service(quota_available=quota,lease_seconds=60,
        retry_seconds=5,clock=lambda:clock[0])
    outcome=await service.poll()
    replay=await service.poll()
    async with factory() as db:
        job=await db.get(VoiceFollowupJob,job_id)
        message_count=await db.scalar(select(func.count()).select_from(AgentMessage))
        evidence=dict(synthetic=True,model=DEFAULT_VOICE_SUMMARY_MODEL,case=name,later_user_text=later,
            expected=expected,outcome=outcome,replay=replay,status=job.status,
            cancel_reason=job.cancel_reason,fail_reason=job.fail_reason,message_count=message_count)
    evidence['agent_count']=await cache.get(f'agent:count:1:{clock[0]:%Y-%m-%d}')
    Path(f'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step032-composition-live-{name}.json').write_text(
        json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    assert outcome==[expected] and replay==[]
    assert message_count==(1 if expected=='sent' else 0)
    assert evidence['agent_count']==('1' if expected=='sent' else None)
    assert evidence['fail_reason'] is None
