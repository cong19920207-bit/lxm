"""Real Docker DNS/IP changes, TLS, Redis and browser; never starts business jobs."""
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest
from tests.test_realtime_voice_nginx_runtime import docker

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_NGINX_RUNTIME') != '1', reason='isolated Docker opt-in')
NODE = '/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
MODULE = '/Users/umark/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'

PROBE = '''from types import SimpleNamespace
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from backend.services.proxy_discovery import ProxyDiscovery, DiscoveredProxyHeadersMiddleware
from backend.routers.admin import voice_transport
from backend.services.realtime_voice_gateway_service import socket_credentials
from backend.services.realtime_voice_ticket_service import TicketError
from backend.utils.admin_auth import get_current_admin
app = FastAPI()
app.state.proxy_discovery = ProxyDiscovery()
app.add_middleware(DiscoveredProxyHeadersMiddleware, discovery=app.state.proxy_discovery)
async def admin(request: Request):
    role = request.headers.get('x-role', 'tech_ops')
    if request.headers.get('authorization') != 'Bearer isolated-test': raise HTTPException(401)
    return SimpleNamespace(id=1,role=role)
app.dependency_overrides[get_current_admin] = admin
app.include_router(voice_transport.router,prefix='/api/admin/voice')
app.include_router(voice_transport.socket_router,prefix='/api/voice')
app.mount('/admin',StaticFiles(directory='/app/admin',html=True))
@app.get('/api/admin/voice/master-switch')
async def switch(): return {'code':0,'data':{'enabled':False,'version':1,'updated_at':'2026-10-16','updated_by':'isolated'}}
@app.get('/api/ready')
async def ready(request: Request): return {'ready':True,'scheme':request.url.scheme,'path':str(request.url)}
@app.websocket('/api/voice/calls/{call_id}/{operation}')
async def stream(socket: WebSocket, call_id: str, operation: str):
    try: socket_credentials(socket,set())
    except TicketError:
        await socket.close(code=4403)
        return
    await socket.accept(subprotocol='voice.v1')
    await socket.send_json({'scheme':socket.url.scheme,'operation':operation})
    await socket.close()
'''

CLIENT = '''import asyncio,json,ssl,httpx,websockets
from websockets.exceptions import InvalidStatus
async def check():
    tls=ssl.create_default_context(cafile='/probe/cert.pem')
    async with httpx.AsyncClient(verify=tls,trust_env=False) as client:
        for attempt in range(120):
            try:
                r=await client.get('https://nginx:8443/api/ready?keep=1')
                if r.status_code==200 and r.json()['scheme']=='https':
                    assert r.json()['path'].endswith('/api/ready?keep=1')
                    break
            except httpx.HTTPError: pass
            await asyncio.sleep(.25)
        else: raise AssertionError('proxy not recovered')
        headers={'Authorization':'Bearer isolated-test'}
        status=(await client.get('https://nginx:8443/api/admin/voice/master-switch/diagnostics',headers=headers)).json()['data']
        assert status['proxy']['status']=='ready',status
        print(json.dumps(status['proxy']))
    path='/api/voice/calls/11111111-1111-4111-8111-111111111111/'
    for operation in ['stream','reconnect-stream']:
        async with websockets.connect('wss://nginx:8443'+path+operation,ssl=tls,
                origin='https://nginx:8443',subprotocols=['voice.v1','ticket.synthetic','device.synthetic'],
                additional_headers={'X-Forwarded-Proto':'http'}) as ws:
            assert json.loads(await ws.recv())=={'scheme':'wss','operation':operation}
    for address,origin in [('ws://backend:8000','https://backend:8000'),('wss://nginx:8443','https://evil.test')]:
        try:
            async with websockets.connect(address+path+'stream',ssl=tls if address.startswith('wss') else None,
                    origin=origin,subprotocols=['voice.v1','ticket.synthetic','device.synthetic'],
                    additional_headers={'X-Forwarded-Proto':'https','X-Forwarded-For':'127.0.0.1'}):
                raise AssertionError('forged forwarding or wrong origin accepted')
        except InvalidStatus as exc: assert exc.response.status_code==403
asyncio.run(check())
'''


def test_recreated_nginx_and_backend_recover_without_env_edits(tmp_path):
    suffix = uuid4().hex[:10]
    network = 'codex-voice-auto-' + suffix
    app, proxy, cache, client = [network + '-' + value for value in ('app','proxy','redis','client')]
    names = []
    root = Path.cwd()
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                    '-subj','/CN=nginx','-addext','subjectAltName=DNS:nginx,DNS:localhost,IP:127.0.0.1',
                    '-keyout',str(tmp_path/'key.pem'),'-out',str(tmp_path/'cert.pem')],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (tmp_path/'probe.py').write_text(PROBE)
    # The exact local nginx config, with TLS listener/cert added for this fixture.
    config = (root/'nginx/nginx.conf').read_text().replace('listen 80;',
        'listen 8443 ssl;\n ssl_certificate /probe/cert.pem;\n ssl_certificate_key /probe/key.pem;')
    (tmp_path/'nginx.conf').write_text(config)
    # Loopback-only published port lets the host Chrome test reach this isolated stack.
    docker('network','create',network)
    def start_app():
        docker('run','-d','--pull=never','--name',app,'--network',network,'--network-alias','backend',
            '-v',str(root/'backend')+':/app/backend:ro','-v',str(root/'admin')+':/app/admin:ro',
            '-v',str(tmp_path)+':/probe:ro','-e','PYTHONPATH=/app:/probe','-e','REDIS_HOST=redis',
            '-e','FORWARDED_ALLOW_IPS=*','--entrypoint','python','lxm_for-backend:latest',
            '-m','uvicorn','probe:app','--host','0.0.0.0','--port','8000','--no-proxy-headers','--no-access-log')
    def start_proxy():
        docker('run','-d','--pull=never','--name',proxy,'--network',network,'--network-alias','nginx',
            '-p','127.0.0.1::8443','-v',str(tmp_path)+':/probe:ro',
            '-v',str(tmp_path/'nginx.conf')+':/etc/nginx/nginx.conf:ro','nginx:alpine')
    def ip(name):
        return docker('inspect','-f','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',name)
    def check():
        return json.loads(docker('exec',client,'python','-c',CLIENT).splitlines()[-1])
    def occupy(old_ip, label):
        name = network + '-' + label
        docker('run','-d','--pull=never','--name',name,'--network',network,'--ip',old_ip,
               '--entrypoint','python','lxm_for-backend:latest','-c','import time;time.sleep(300)')
        names.append(name)
    try:
        docker('run','-d','--pull=never','--name',cache,'--network',network,'--network-alias','redis','redis:7-alpine')
        names.append(cache)
        start_app(); names.append(app)
        start_proxy(); names.append(proxy)
        docker('run','-d','--pull=never','--name',client,'--network',network,'-v',str(tmp_path)+':/probe:ro',
               '--entrypoint','python','lxm_for-backend:latest','-c','import time;time.sleep(300)')
        names.append(client)
        first = check()
        old_proxy = ip(proxy)
        docker('rm','-f',proxy)
        occupy(old_proxy,'old-proxy')
        start_proxy()
        second = check()
        assert old_proxy not in second['trusted_addresses']
        assert second['instance'] == first['instance'] and second['generation'] > first['generation']
        old_backend = ip(app)
        docker('rm','-f',app)
        occupy(old_backend,'old-backend')
        start_app()
        third = check()
        assert ip(app) != old_backend and third['instance'] != second['instance']
        # Resolver caches are per worker. A successful request proves one worker
        # recovered; allow the declared 5-second TTL to expire on the others.
        time.sleep(5.1)
        port = json.loads(docker('inspect',proxy))[0]['NetworkSettings']['Ports']['8443/tcp'][0]['HostPort']
        result = subprocess.run([NODE,'tests/test_voice_transport_browser.cjs','https://127.0.0.1:'+port,
                                 str(tmp_path/'voice-diagnostics.png')],
                                env={**os.environ,'VOICE_PLAYWRIGHT_PATH':MODULE},capture_output=True,text=True,timeout=90)
        if result.returncode:
            from tests.test_realtime_voice_nginx_runtime import DOCKER
            logs = subprocess.run([DOCKER,'logs',app],capture_output=True,text=True)
            print(logs.stdout + logs.stderr)
            print(docker('exec',cache,'redis-cli','GET','voice:transport-diagnostic:last'))
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout)
        print('runtime evidence: nginx IP and backend IP changed; TLS guards and browser roundtrip passed')
    finally:
        for name in reversed(names):
            docker('rm','-f',name)
        docker('network','rm',network)
