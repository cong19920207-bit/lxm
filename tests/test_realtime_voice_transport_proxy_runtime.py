"""TLS proxy + production voice guard, isolated from user data and providers."""
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest
from tests.test_realtime_voice_nginx_runtime import docker

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_NGINX_RUNTIME') != '1', reason='isolated TLS proxy test')

PROBE = '''from fastapi import FastAPI, WebSocket
from backend.services.realtime_voice_gateway_service import socket_credentials
from backend.services.realtime_voice_ticket_service import TicketError
app = FastAPI()
@app.get('/ready')
async def ready(): return {'ready':True}
@app.websocket('/api/voice/calls/{call_id}/{operation}')
async def stream(socket: WebSocket, call_id: str, operation: str):
    try:
        socket_credentials(socket, set())
    except TicketError:
        await socket.close(code=4403)
        return
    await socket.accept(subprotocol='voice.v1')
    await socket.send_json({'scheme':socket.url.scheme, 'host':socket.headers['host'], 'operation':operation})
    await socket.close()
'''

CLIENT = '''import asyncio,json,ssl,httpx,websockets
from websockets.exceptions import InvalidStatus
async def check():
    tls = ssl.create_default_context(cafile='/probe/cert.pem')
    protocols = ['voice.v1','ticket.transport-only','device.transport-only']
    path = '/api/voice/calls/11111111-1111-4111-8111-111111111111/'
    async with httpx.AsyncClient(verify=tls,trust_env=False) as client:
        for attempt in range(60):
            try:
                response = await client.get('https://proxy:8443/')
                ready = await client.get('http://backend:8000/ready')
                if response.status_code == 404 and ready.status_code == 200: break
            except httpx.HTTPError: pass
            await asyncio.sleep(.1)
        else: raise AssertionError('TLS proxy not ready')
    for host in ['proxy:8443','next-site.test:8443']:
        for operation in ['stream','reconnect-stream']:
            async with websockets.connect('wss://'+host+path+operation,ssl=tls,
                    origin='https://'+host,subprotocols=protocols,
                    additional_headers={'X-Forwarded-Proto':'http'}) as socket:
                assert json.loads(await socket.recv()) == {'scheme':'wss','host':host,'operation':operation}
    for origin in ['https://evil.test','https://proxy','http://proxy:8443']:
        try:
            async with websockets.connect('wss://proxy:8443'+path+'stream',ssl=tls,
                    origin=origin,subprotocols=protocols):
                raise AssertionError('wrong origin accepted')
        except InvalidStatus as exc: assert exc.response.status_code == 403
    # A direct caller is not the trusted proxy and cannot claim TLS via headers.
    try:
        async with websockets.connect('ws://backend:8000'+path+'stream',
                origin='https://backend:8000',subprotocols=protocols,
                additional_headers={'X-Forwarded-Proto':'https','X-Forwarded-For':'127.0.0.1'}):
            raise AssertionError('untrusted forwarded headers accepted')
    except InvalidStatus as exc: assert exc.response.status_code == 403
asyncio.run(check())
'''


def test_tls_proxy_domain_port_reconnect_and_untrusted_forwarding(tmp_path):
    suffix = uuid4().hex[:10]
    network = 'codex-voice-tls-' + suffix
    backend, proxy = 'codex-voice-tls-app-' + suffix, 'codex-voice-tls-proxy-' + suffix
    names = []
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-subj', '/CN=proxy', '-addext', 'subjectAltName=DNS:proxy,DNS:next-site.test',
                    '-keyout', str(tmp_path/'key.pem'), '-out', str(tmp_path/'cert.pem')],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (tmp_path/'probe.py').write_text(PROBE)
    config = Path('nginx/voice-wss.conf.example').read_text()
    config = config.replace('listen 443 ssl;', 'listen 8443 ssl;')
    config = config.replace('/etc/nginx/certs/voice-fullchain.pem', '/probe/cert.pem')
    config = config.replace('/etc/nginx/certs/voice-key.pem', '/probe/key.pem')
    (tmp_path/'nginx.conf').write_text(config)
    docker('network', 'create', '--internal', network)
    try:
        docker('run', '-d', '--pull=never', '--name', backend, '--network', network,
               '--network-alias', 'backend', '-v', str(tmp_path)+':/probe:ro',
               '-e', 'PYTHONPATH=/app:/probe', '--entrypoint', 'python',
               'lxm_for-backend:latest', '-c', 'import time; time.sleep(3600)')
        names.append(backend)
        docker('run', '-d', '--pull=never', '--name', proxy, '--network', network,
               '--network-alias', 'proxy', '--network-alias', 'next-site.test',
               '-v', str(tmp_path)+':/probe:ro',
               '-v', str(tmp_path/'nginx.conf')+':/etc/nginx/nginx.conf:ro', 'nginx:alpine')
        names.append(proxy)
        proxy_ip = docker('inspect', '-f', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', proxy)
        docker('exec', '-d', backend, 'python', '-m', 'uvicorn', 'probe:app',
               '--host', '0.0.0.0', '--port', '8000', '--forwarded-allow-ips', proxy_ip,
               '--log-level', 'critical', '--no-access-log')
        docker('exec', backend, 'python', '-c', CLIENT)
        docker('exec', proxy, 'nginx', '-t')
    finally:
        for name in reversed(names):
            docker('rm', '-f', name)
        docker('network', 'rm', network)
