"""Original API + builtin producer + temporary SQL. Provider wire is controlled."""
import json
from copy import deepcopy
import pytest
from backend.services.realtime_voice_admin_capability_probe import BuiltinCapabilityProbe
from backend.services.realtime_voice_provider_service import ProviderAdminTestRunner,ProviderError
from tests import test_realtime_voice_step006_test_api as base
from tests.test_realtime_voice_step006_test_api import database,runner,client
from tests.test_realtime_voice_admin_capability_probe import PlaybackWire
from tests.test_realtime_voice_step007_provider import Wire,response

@pytest.mark.asyncio
@pytest.mark.parametrize('outcome',['passed','failed','authentication_failed','timeout'])
async def test_original_api_builtin_evidence_and_audit_leave_active_and_other_capabilities_unchanged(client,monkeypatch,outcome):
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    active,draft=await base._insert_voice_config()
    class NoAudio(Wire):
        async def send(self,raw):
            await super().send(raw)
            if int.from_bytes(raw[4:8],'big')==300:
                n=int.from_bytes(raw[8:12],'big');sid=raw[12:12+n].decode()
                fields={'question_id':'q','reply_id':'r','sentence_id':'s','text':'safe fixture'}
                for code in (350,351,359):await self.incoming.put(response(code,sid,fields))
    wire=NoAudio() if outcome=='failed' else PlaybackWire()
    async def transport(*a,**kw):
        if outcome in ('authentication_failed','timeout'):raise ProviderError(outcome)
        return wire
    real_runner=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    base.app.dependency_overrides[base._runner_dependency()]=lambda:real_runner
    before=await base._voice_rows_projection()
    result=await client.post('/api/admin/voice/config/test-capability',headers=base._headers('super_admin'),json={'capability_key':'supports_playback_text_mapping'})
    assert result.status_code==200
    data=result.json()['data'];assert data['status']==(outcome if outcome in ('passed','failed') else 'error'), data
    rows=await base._evidence_rows();assert len(rows)==1
    assert rows[0].evidence_report_id==data['evidence_report_id'] and rows[0].source_type=='admin_capability_test'
    after=await base._voice_rows_projection()
    assert after[0]==before[0]
    old=json.loads(before[1][1]);new=json.loads(after[1][1]);key='supports_playback_text_mapping'
    for other in old['capabilities']:
        if other!=key:assert old['capabilities'][other]==new['capabilities'][other]
    cap=new['capabilities'][key];assert cap['enabled'] is False and cap['effective_scope']=='off' and cap['forced_enabled'] is False
    assert after[1][3]==before[1][3]+1
    async with base.session_factory() as db:
        from sqlalchemy import select
        logs=(await db.scalars(select(base.AdminOperationLog))).all()
        audits=[json.loads(x.after_value) for x in logs if x.action=='test_capability']
        assert len(audits)==1 and audits[0]['evidence_report_id']==data['evidence_report_id']
        assert all('SENTINEL' not in (x.after_value or '') for x in logs)
    assert 'SENTINEL' not in result.text

@pytest.mark.asyncio
@pytest.mark.parametrize('category',['authentication_failed','timeout','upstream_unavailable'])
async def test_reconnect_infrastructure_failure_is_unverified_not_capability_failed(monkeypatch,category):
    from tests.test_realtime_voice_admin_capability_probe import ProbeWire
    from tests.test_realtime_voice_step007_provider import config
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    calls=0;wire=ProbeWire({})
    async def transport(*a,**kw):
        nonlocal calls
        calls+=1
        if calls==2:raise ProviderError(category)
        return wire
    task=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    try:result=await task.run_capability(capability_key='supports_session_reconnect',draft_snapshot=config(),secret='fixture')
    finally:await task.aclose()
    assert calls==2 and result['status']=='error' and result['failure_category']==category
    assert result['evidence_record']['evidence_payload']['capability_status']=='unverified'

@pytest.mark.asyncio
async def test_original_capability_stream_disconnect_closes_and_records_only_error(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    from starlette.requests import Request
    from backend.routers.admin.voice_playback import capability_stream
    from sqlalchemy import select
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','fixture-app')
    await base._insert_voice_config()
    ready=asyncio.Event();cache=AsyncMock();cache.set.return_value=True
    async def wait_ack(*a,**kw):
        ready.set();await asyncio.Event().wait()
    cache.blpop.side_effect=wait_ack
    wire=PlaybackWire()
    async def transport(*a,**kw):return wire
    task=ProviderAdminTestRunner(transport_factory=transport,capability_probe=BuiltinCapabilityProbe())
    response=await capability_stream(capability_key='supports_sentence_playback_ack',
        request=Request({'type':'http','method':'POST','path':'/','headers':[], 'query_string':b''}),
        admin=SimpleNamespace(id=base.role_ids['super_admin'],username='step006-test-api-super_admin'),
        cache=cache,runner=task,session_factory=base.session_factory)
    async def receive():
        await ready.wait();return {'type':'http.disconnect'}
    async def send(message):pass
    await response({'type':'http','asgi':{'spec_version':'2.0'}},receive,send)
    assert wire.closed and not await base._evidence_rows()
    async with base.session_factory() as db:
        logs=(await db.scalars(select(base.AdminOperationLog))).all()
        assert len(logs)==1
        data=json.loads(logs[0].after_value)
        assert data['failure_category']=='client_disconnected' and data['test_id']==task.test_target_id
    cache.eval.assert_awaited()
