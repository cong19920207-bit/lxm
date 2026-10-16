import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from backend.routers.admin import voice_transport as module
from backend.services.proxy_discovery import ProxyDiscovery, DiscoveredProxyHeadersMiddleware
from backend.utils.admin_auth import get_current_admin


class Cache:
    def __init__(self):
        self.values = {}
    async def set(self, key, value, **kwargs):
        if kwargs.get('nx') and key in self.values:
            return None
        self.values[key] = value
        return True
    async def get(self, key): return self.values.get(key)
    async def getdel(self, key): return self.values.pop(key, None)
    async def hgetall(self, key): return {}
    async def eval(self, script, count, key, probe_id, value):
        if json.loads(self.values[key])['probe_id'] == probe_id:
            self.values[key] = value


@pytest.fixture
def harness(monkeypatch):
    cache, app = Cache(), FastAPI()
    async def resolve_ip(): return {'127.0.0.1'}
    app.state.proxy_discovery = ProxyDiscovery(resolve_ip)
    app.add_middleware(DiscoveredProxyHeadersMiddleware, discovery=app.state.proxy_discovery)
    app.include_router(module.router, prefix='/api/admin/voice')
    app.include_router(module.socket_router, prefix='/api/voice')
    async def admin(request: Request):
        from fastapi import HTTPException
        if 'x-role' not in request.headers: raise HTTPException(401)
        return SimpleNamespace(id=1, role=request.headers['x-role'])
    async def get_cache(): return cache
    app.dependency_overrides[get_current_admin] = admin
    app.dependency_overrides[module.cache_dependency] = get_cache
    monkeypatch.setattr(module, 'get_redis', get_cache)
    monkeypatch.delenv('VOICE_ALLOW_INSECURE_LOCAL', raising=False)
    monkeypatch.delenv('VOICE_ALLOWED_ORIGINS', raising=False)
    with TestClient(app, base_url='https://testserver') as client:
        yield client, cache


BASE = '/api/admin/voice/master-switch/diagnostics'


@pytest.mark.parametrize('operation', ['status', 'start', 'result'])
def test_success_uses_standard_admin_envelope_and_no_store(harness, operation):
    client, cache = harness
    headers = {'x-role': 'tech_ops'}
    if operation == 'status':
        result = client.get(BASE, headers=headers)
    elif operation == 'start':
        result = client.post(BASE + '/probes', headers=headers)
    else:
        started = client.post(BASE + '/probes', headers=headers).json()['data']
        result = client.get(BASE + '/probes/' + started['probe_id'], headers=headers)
    assert result.status_code == 200
    body = result.json()
    assert set(body) == {'code', 'data', 'message'}
    assert body['code'] == 0 and body['message'] == 'success'
    assert isinstance(body['data'], dict)
    assert result.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('role', ['super_admin','tech_ops','ai_trainer','ops_admin','observer'])
def test_diagnostic_permissions_and_missing_samples(harness, role):
    client, cache = harness
    assert client.get(BASE).status_code == 401
    result = client.get(BASE, headers={'x-role': role})
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'no-store'
    assert result.json()['data']['recent_rejections']['status'] == 'missing'
    response = client.post(BASE + '/probes', headers={'x-role': role})
    assert response.status_code == (200 if role in ('super_admin','tech_ops') else 403)


def issue(client):
    return client.post(BASE + '/probes', headers={'x-role': 'tech_ops'}).json()['data']


def test_probe_roundtrip_single_use_and_no_call_ticket_reuse(harness):
    client, cache = harness
    info = issue(client)
    protocols = ['voice.v1', 'ticket.' + info['ticket'], 'device.diagnostic']
    with client.websocket_connect('wss://testserver' + info['path'], headers={'origin':'https://testserver'}, subprotocols=protocols) as ws:
        assert ws.receive_json() == {'type':'diagnostic.ready'}
        ws.send_json({'type':'diagnostic.ack'})
        result = ws.receive_json()['result']
        assert result['status'] == 'passed' and result['scheme'] == 'wss'
        assert result['local_insecure'] is False
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('wss://testserver' + info['path'], headers={'origin':'https://testserver'}, subprotocols=protocols): pass
    assert client.post(BASE + '/probes', headers={'x-role':'tech_ops'}).status_code == 429
    assert client.get(BASE + '/probes/' + info['probe_id'], headers={'x-role':'observer'}).json()['data']['status'] == 'passed'
    assert all('voice_call' not in key and 'voice.ws.rejection' not in key for key in cache.values)


@pytest.mark.parametrize('url,origin,reason', [
    ('wss://testserver', 'https://evil.test', 'socket_origin_or_url_rejected'),
    ('ws://testserver', 'http://testserver', 'wss_required'),
    ('wss://testserver?x=1', 'https://testserver', 'socket_origin_or_url_rejected'),
])
def test_rejected_transport_is_reported_without_accepting_socket(harness, url, origin, reason):
    client, cache = harness
    info = issue(client)
    address = url.replace('?x=1','') + info['path'] + ('?x=1' if '?' in url else '')
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(address, headers={'origin':origin},
                subprotocols=['voice.v1','ticket.' + info['ticket'],'device.diagnostic']): pass
    result = client.get(BASE, headers={'x-role':'observer'}).json()['data']['last_probe']
    assert result['status'] == 'failed' and result['reason'] == reason


def test_store_failure_is_unavailable_not_healthy(harness):
    client, cache = harness
    cache.get = AsyncMock(side_effect=RuntimeError('secret details'))
    result = client.get(BASE, headers={'x-role':'observer'}).json()['data']
    assert result['last_probe'] is None and result['probe_storage'] == 'unavailable'
    cache.set = AsyncMock(side_effect=RuntimeError('secret details'))
    response = client.post(BASE + '/probes', headers={'x-role':'tech_ops'})
    assert response.status_code == 503 and 'secret details' not in response.text


def test_untrusted_forwarding_and_wrong_ticket_cannot_pass(harness):
    client, cache = harness
    info = issue(client)
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('ws://testserver' + info['path'],
                headers={'origin':'https://testserver','x-forwarded-proto':'https'},
                subprotocols=['voice.v1','ticket.' + info['ticket'],'device.diagnostic']): pass
    result = client.get(BASE, headers={'x-role':'observer'}).json()['data']['last_probe']
    assert result['status'] == 'failed' and result['scheme'] == 'ws'
    before = cache.values.copy()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('wss://testserver' + info['path'],
                headers={'origin':'https://testserver'},
                subprotocols=['voice.v1','ticket.' + 'x'*43,'device.diagnostic']): pass
    assert cache.values == before


def test_force_refresh_reports_actual_dns_failure_and_recovery(harness):
    client, cache = harness
    async def failed(): raise OSError('DNS detail must not be leaked')
    client.app.state.proxy_discovery.resolver = failed
    result = client.post(BASE + '/probes', headers={'x-role':'tech_ops'}).json()['data']
    assert result['proxy']['status'] == 'error'
    assert result['proxy']['trusted_addresses'] == []
    assert 'DNS detail' not in json.dumps(result)
    async def recovered(): return {'172.18.0.9'}
    client.app.state.proxy_discovery.resolver = recovered
    cache.values.pop(module.PREFIX + 'rate:1')
    result = client.post(BASE + '/probes', headers={'x-role':'tech_ops'}).json()['data']
    assert result['proxy']['status'] == 'ready'
    assert result['proxy']['trusted_addresses'] == ['172.18.0.9']
