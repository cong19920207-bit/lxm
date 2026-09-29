"""Same-instance MySQL/Redis, production HTTP routes, and production card component.

Authentication, unrelated badge/tip data, and expiry time setup are fixtures.
Covers the production card component and unmodified chat page; desktop Chrome
BFCache is asserted explicitly. This is not physical-device acceptance.
"""
import asyncio,json,os,socket
from pathlib import Path
from datetime import datetime,timedelta
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
import uvicorn
from backend.database import get_db
from backend.models.realtime_voice import VoiceCall,VoiceCrisisRecord
from backend.routers.realtime_voice import router as public_router
from backend.routers.admin.voice_records import router as admin_router
from backend.routers.chat import router as chat_router
from backend.utils.auth_middleware import get_current_user
from backend.utils.admin_auth import get_current_admin
from backend.services.realtime_voice_retention_service import VoiceRetentionService,build_voice_retention_service
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_m6_summary_delete_runtime import summary_env,base_summary_env
from tests.test_realtime_voice_step034_delete import ADMIN
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores/browser opt-in')


@pytest.mark.asyncio
@pytest.mark.parametrize('clear',['expiry','delete'])
@pytest.mark.parametrize('page_kind',['component','full_chat','full_chat_bfcache'])
async def test_actual_http_browser_resource_clear(summary_env,runtime,clear,page_kind):
    factory,call_id=summary_env
    sentinel='CRISIS-RAW-025-NEVER-PUBLIC'
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        call.config_snapshot={**call.config_snapshot,'resolved_script':{'crisis':{
            'in_call_banner':'请联系可信任的人，或拨打12356。','post_call_resource_card':'发布资源：110/120；12356。'}}}
        for direction in ('user','assistant'):
            db.add(VoiceCrisisRecord(call_id=call_id,turn_index=1,direction=direction,
                content_plaintext=sentinel,matched_keyword=sentinel,match_status='matched',
                is_persona_incident=direction=='assistant',expires_at=datetime.utcnow()+timedelta(days=30)))
        await db.commit()
    app=FastAPI();app.include_router(public_router);app.include_router(chat_router)
    app.include_router(admin_router,prefix='/api/admin/voice')
    async def session():
        async with factory() as db:yield db
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_user]=lambda:1
    app.dependency_overrides[get_current_admin]=lambda:ADMIN
    retention=VoiceRetentionService(session_factory=factory,cache=runtime[2])
    app.dependency_overrides[build_voice_retention_service]=lambda:retention
    app.mount('/static',StaticFiles(directory='frontend/static'),name='static')
    @app.get('/',response_class=HTMLResponse)
    async def harness():
        return '''<html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>STEP025 integration harness</title><link rel="stylesheet" href="/static/css/voice-call-cards.css"><main id="cards"></main><script src="/static/js/voice-call-cards.js"></script><script>
window.resourceReadsCompleted=0;window.timelineLoaded=false;
async function getResource(id){try{const r=await fetch('/api/voice/calls/'+id,{cache:'no-store'});if(!r.ok)return null;return (await r.json()).data.crisis;}finally{setTimeout(()=>{window.resourceReadsCompleted++;},0);}}
VoiceCallCards.configureResourceRefresh(getResource);
fetch('/api/chat/timeline?cursor=999999999',{cache:'no-store'}).then(r=>r.json()).then(r=>{r.data.items.filter(x=>x.source==='call').forEach(x=>document.querySelector('#cards').append(VoiceCallCards.render(x,Date.now())));window.timelineLoaded=true;});
</script></html>'''
    @app.get('/away',response_class=HTMLResponse)
    async def away_page():return '<html><title>Navigation target</title>测试导航目标</html>'
    @app.get('/chat.html')
    async def chat_page():return FileResponse('frontend/pages/chat.html')
    @app.get('/api/feed/badge')
    async def badge_fixture():return {'code':0,'data':{'unread_reply_count':0,'new_post_count':0}}
    @app.get('/api/agent/messages')
    async def agent_fixture():return {'code':0,'data':{'messages':[]}}
    @app.post('/__test__/expire')
    async def expire():
        async with factory() as db:
            for row in (await db.scalars(select(VoiceCrisisRecord))).all():row.expires_at=datetime.utcnow()-timedelta(seconds=1)
            await db.commit()
        await retention.purge_contents(now=datetime.utcnow())
        return {'ok':True}
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
    task=asyncio.create_task(server.serve(sockets=[sock]))
    proc=None
    try:
        for _ in range(100):
            if server.started:break
            if task.done():await task
            await asyncio.sleep(.02)
        assert server.started
        root=Path('/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node')
        env={**os.environ,'VOICE_PLAYWRIGHT_PATH':str(root/'node_modules/playwright')}
        proc=await asyncio.create_subprocess_exec(str(root/'bin/node'),'tests/test_realtime_voice_step025_e2e.cjs',
            f'http://127.0.0.1:{port}',call_id,clear,page_kind,env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await asyncio.wait_for(proc.communicate(),50)
        assert proc.returncode==0,(stdout+stderr).decode()
        assert 'PASS' in stdout.decode()
        async with factory() as db:
            assert all(row.content_plaintext is None for row in (await db.scalars(select(VoiceCrisisRecord))).all())
            call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
            assert (call.deleted_at is not None)==(clear=='delete')
    finally:
        if proc is not None and proc.returncode is None:
            proc.kill();await proc.wait()
        server.should_exit=True
        await asyncio.wait_for(task,10)
        sock.close()
