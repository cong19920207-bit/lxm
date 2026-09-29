"""Repository Nginx config against an isolated ASGI transport probe, no business app."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import httpx
import pytest
import websockets

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_NGINX_RUNTIME') != '1', reason='isolated Nginx opt-in')
DOCKER = '/Applications/Docker.app/Contents/Resources/bin/docker'
PROBE = '''from fastapi import FastAPI, WebSocket, Request
app=FastAPI()
@app.websocket('/api/voice/calls/{call_id}/{operation}')
async def stream(socket: WebSocket, call_id: str, operation: str):
    await socket.accept(subprotocol='voice.v1')
    await socket.send_json({'call_id':call_id,'operation':operation,
        'origin':socket.headers.get('origin'),'proto':socket.headers.get('x-forwarded-proto')})
    await socket.send_text(await socket.receive_text())
    await socket.close(code=1000)
@app.get('/{path:path}')
async def read(request: Request,path: str):
    return {'path':path,'connection':request.headers.get('connection'), 'upgrade':request.headers.get('upgrade')}
'''


CLIENT = """import asyncio,json,httpx,websockets
async def check():
    async with httpx.AsyncClient(base_url="http://proxy",trust_env=False) as client:
        for attempt in range(60):
            try:
                r=await client.get('/api/voice/probe')
                if r.status_code==200:break
            except httpx.HTTPError:pass
            await asyncio.sleep(.1)
        else:raise AssertionError('isolated probe did not start')
        for path in ['/api/voice/probe','/api/chat/probe','/admin/probe']:
            r=await client.get(path)
            assert r.status_code==200 and r.json()['path']==path[1:]
            assert r.json()['upgrade'] is None
            assert r.json()['connection'] != 'upgrade'
    for operation in ['stream','reconnect-stream']:
        async with websockets.connect(f'ws://proxy/api/voice/calls/test-call/{operation}',
                subprotocols=['voice.v1'],origin='https://app.example',open_timeout=5) as socket:
            assert socket.subprotocol=='voice.v1'
            assert json.loads(await socket.recv())=={'call_id':'test-call','operation':operation,
                'origin':'https://app.example','proto':'http'}
            await socket.send('controlled-frame')
            assert await socket.recv()=='controlled-frame'
            await socket.wait_closed()
            assert socket.close_code==1000
asyncio.run(check())
"""

def docker(*args):
    result = subprocess.run([DOCKER,*args],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


@pytest.mark.asyncio
async def test_nginx_initial_and_reconnect_upgrade_preserve_http(tmp_path):
    suffix=uuid4().hex[:10]
    network='codex-voice-ws-'+suffix
    names=[]
    docker('network','create','--internal',network)
    (tmp_path/'probe.py').write_text(PROBE)
    try:
        backend='codex-voice-probe-'+suffix
        docker('run','-d','--pull=never','--name',backend,'--network',network,'--network-alias','backend',
               '-v',str(tmp_path/'probe.py')+':/probe/probe.py:ro','-w','/probe','--entrypoint','python',
               'lxm_for-backend:latest','-m','uvicorn','probe:app','--host','0.0.0.0','--port','8000')
        names.append(backend)
        proxy='codex-voice-nginx-'+suffix
        docker('run','-d','--pull=never','--name',proxy,'--network',network,'--network-alias','proxy',
               '-v',str(Path('nginx/nginx.conf').resolve())+':/etc/nginx/nginx.conf:ro','nginx:alpine')
        names.append(proxy)
        docker('exec',backend,'python','-c',CLIENT)
        assert docker('exec',proxy,'nginx','-t') == ''
    except BaseException:
        for name in names:
            print(docker('logs',name))
        raise
    finally:
        for name in reversed(names):docker('rm','-f',name)
        docker('network','rm',network)
