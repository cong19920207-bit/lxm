"""New scheduler registration and callback contract; existing jobs stay intact."""
from types import SimpleNamespace
import pytest


def test_followup_scheduler_is_registered_once(monkeypatch):
    from backend.tasks import scheduler as module
    registrations=[]
    class Scheduler:
        running=False
        def add_job(self,callback,**kw):registrations.append((callback,kw))
        def start(self):self.running=True
        def get_jobs(self):return []
    monkeypatch.setattr(module,'scheduler',Scheduler())
    module.start_scheduler()
    found=[(fn,kw) for fn,kw in registrations if kw['id']=='voice_followup_task']
    assert len(found)==1
    callback,options=found[0]
    assert callback is module._run_voice_followup
    assert options['trigger'].interval.total_seconds()==1
    assert options['max_instances']==1 and options['coalesce'] and options['replace_existing']
    assert any(kw['id']=='voice_summary_task' for _,kw in registrations)


@pytest.mark.asyncio
async def test_followup_scheduler_polls_composed_service(monkeypatch):
    from backend.tasks import scheduler as module
    from backend.services import realtime_voice_followup_runtime as runtime
    calls=[]
    async def poll():calls.append('poll')
    async def build():calls.append('build');return SimpleNamespace(poll=poll)
    monkeypatch.setattr(runtime,'build_voice_followup_service',build)
    await module._run_voice_followup()
    assert calls==['build','poll']


@pytest.mark.asyncio
async def test_scheduler_failure_log_contains_no_provider_content(monkeypatch,caplog):
    from backend.tasks import scheduler as module
    from backend.services import realtime_voice_followup_runtime as runtime
    async def build():raise RuntimeError('PRIVATE_PROVIDER_CONTENT')
    monkeypatch.setattr(runtime,'build_voice_followup_service',build)
    await module._run_voice_followup()
    assert 'voice.followup.poll_unavailable' in caplog.text
    assert 'PRIVATE_PROVIDER_CONTENT' not in caplog.text
