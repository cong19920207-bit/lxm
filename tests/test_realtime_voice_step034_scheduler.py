from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest


def test_retention_registration(monkeypatch):
    from backend.tasks import scheduler as module
    registrations=[]
    class Scheduler:
        running=False
        def add_job(self,callback,**kw):registrations.append((callback,kw))
        def start(self):pass
        def get_jobs(self):return []
    monkeypatch.setattr(module,'scheduler',Scheduler());module.start_scheduler()
    found=[(fn,kw) for fn,kw in registrations if kw['id']=='voice_retention_task']
    assert len(found)==1 and found[0][0] is module._run_voice_retention
    assert found[0][1]['trigger'].interval.total_seconds()==60
    assert found[0][1]['coalesce'] and found[0][1]['max_instances']==1


@pytest.mark.asyncio
async def test_retention_cursor_failure_and_wrap(monkeypatch,caplog):
    from backend.tasks import scheduler as module
    from backend.services import realtime_voice_retention_service as runtime
    content=AsyncMock(side_effect=[RuntimeError('PRIVATE'),{'next_cursor':7},{'next_cursor':None}])
    replay=AsyncMock(return_value={'next_cursor':None})
    async def builder():return SimpleNamespace(purge_contents=content,purge_replays=replay)
    monkeypatch.setattr(runtime,'build_voice_retention_service',builder)
    monkeypatch.setattr(module,'_voice_retention_cursors',{'contents':3,'replays':9})
    await module._run_voice_retention()
    assert module._voice_retention_cursors=={'contents':3,'replays':0}
    await module._run_voice_retention();assert module._voice_retention_cursors['contents']==7
    await module._run_voice_retention();assert module._voice_retention_cursors['contents']==0
    assert [call.kwargs['after_id'] for call in content.call_args_list]==[3,3,7]
    assert content.call_args_list[0].kwargs['now']==replay.call_args_list[0].kwargs['now']
    assert 'PRIVATE' not in caplog.text
