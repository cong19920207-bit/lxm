import json
from types import SimpleNamespace
from datetime import datetime
import pytest
from fastapi import FastAPI,HTTPException
from httpx import ASGITransport,AsyncClient
from sqlalchemy import select
from backend.database import get_db
from backend.models.realtime_voice import VoiceCall,VoicePostprocessJob
from backend.routers.admin.voice_records import router
from backend.utils.admin_auth import get_current_admin
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step028_jobs import add_turn
from tests.test_realtime_voice_step031_metrics import CounterCache


def application(factory,role,sink):
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice')
    app.state.voice_metrics=VoiceMetrics(sink)
    async def admin():
        if role=='unauthenticated':raise HTTPException(401,'private-auth-detail')
        return SimpleNamespace(id=1,username='private-user',role=role)
    async def session():
        async with factory() as db:yield db
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_admin]=admin
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','ops_admin','observer','tech_ops','ai_trainer','unauthenticated'])
@pytest.mark.parametrize('action',['view','export','debug','retry'])
async def test_admin_metric_role_results_and_audit(card_env,role,action):
    factory,call_id=card_env;sink=CounterCache();await add_turn(factory,call_id)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='ended';call.summary_status='failed';call.ended_at=datetime.utcnow()
        job=VoicePostprocessJob(call_id=call_id,job_type='call_summary',status='failed',fail_reason='model_unavailable')
        db.add(job);await db.commit();job_id=job.id
    app=application(factory,role,sink)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        if action=='export':response=await client.post('/api/admin/voice/calls/export',json={'call_ids':[call_id]})
        elif action=='retry':response=await client.post(f'/api/admin/voice/summary-jobs/{job_id}/retry')
        else:response=await client.get('/api/admin/voice/calls/'+call_id+('/debug' if action=='debug' else '/turns'))
    allowed=role in {'view':{'super_admin','ops_admin','observer'},'export':{'super_admin','ops_admin'},
        'debug':{'super_admin'},'retry':{'super_admin','tech_ops'}}[action]
    assert response.status_code==(200 if allowed else 401 if role=='unauthenticated' else 403)
    events=[e for batch in sink.batches for e in batch]
    assert ('voice.admin_record.authorization',{'action':action,'result':'authorized' if allowed else 'denied'},1) in events
    assert ('voice.admin_record.result',{'action':action,'result':'success' if allowed else 'rejected'},1) in events
    audit=[e for e in events if e[0]=='voice.admin_record.audit']
    assert audit==([('voice.admin_record.audit',{'action':action,'result':'success'},1)] if allowed else [])
    if allowed and action=='export':assert ('voice.admin_record.fixed_snapshot',{'result':'valid'},1) in events
    assert call_id not in json.dumps(events) and 'private' not in json.dumps(events)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['audit','projection'])
async def test_admin_metric_failure_does_not_return_partial_export(card_env,monkeypatch,failure):
    import backend.routers.admin.voice_records as module
    from backend.models.admin_operation_log import AdminOperationLog
    factory,call_id=card_env;sink=CounterCache();await add_turn(factory,call_id)
    if failure=='audit':
        async def broken(*args,**kwargs):raise RuntimeError('private-audit-body')
        monkeypatch.setattr(module,'log_operation',broken)
    else:
        original=module.export_turn
        monkeypatch.setattr(module,'export_turn',lambda item:{**original(item),'user_text_final':'wrong-projection'})
    app=application(factory,'super_admin',sink)
    async with AsyncClient(transport=ASGITransport(app=app,raise_app_exceptions=False),base_url='http://test') as client:
        response=await client.post('/api/admin/voice/calls/export',json={'call_ids':[call_id]})
    assert response.status_code==500 and '下月去日本' not in response.text
    events=[e for batch in sink.batches for e in batch]
    assert ('voice.admin_record.result',{'action':'export','result':'failure'},1) in events
    expected=('voice.admin_record.audit',{'action':'export','result':'failure'},1) if failure=='audit' else (
        'voice.admin_record.fixed_snapshot',{'result':'projection_mismatch'},1)
    assert expected in events and 'private' not in json.dumps(events)
    async with factory() as db:
        logs = (await db.scalars(select(AdminOperationLog))).all()
        summaries = [json.loads(row.after_value) for row in logs
                     if row.after_value and json.loads(row.after_value).get('kind') == 'request']
    assert len(summaries) == 1 and summaries[0]['http_status'] == 500
    assert summaries[0]['failure_category'] == ('audit_unavailable' if failure == 'audit' else 'projection_mismatch')
    assert summaries[0]['result'] == 'failure'
    assert 'private' not in json.dumps(summaries) and '下月去日本' not in json.dumps(summaries)
