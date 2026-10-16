import asyncio
import pytest
from backend.services.proxy_discovery import ProxyDiscovery, DiscoveredProxyHeadersMiddleware


@pytest.mark.asyncio
async def test_nginx_address_changes_revoke_old_peer_and_dns_failure_fails_closed():
    now, addresses = [0], {'172.18.0.4'}
    async def resolver():
        if not addresses:
            raise OSError('unavailable')
        return addresses.copy()
    discovery = ProxyDiscovery(resolver, lambda: now[0])
    seen = []
    async def app(scope, receive, send):
        seen.append(scope)
    handler = DiscoveredProxyHeadersMiddleware(app, discovery)
    async def call(peer):
        await handler(dict(type='websocket', scheme='ws', client=(peer, 1234),
                           headers=[(b'x-forwarded-proto', b'https'), (b'x-forwarded-for', b'203.0.113.9')]), None, None)
        return seen[-1]
    assert (await call('172.18.0.4'))['scheme'] == 'wss'
    assert (await call('172.18.0.9'))['scheme'] == 'ws'
    addresses.clear(); addresses.add('172.18.0.6'); now[0] += 1.1
    new = await call('172.18.0.6')
    assert new['scheme'] == 'wss' and new['voice_proxy']['peer'] == '172.18.0.6'
    assert new['client'][0] == '203.0.113.9'
    assert (await call('172.18.0.4'))['scheme'] == 'ws'
    addresses.clear(); now[0] += 6
    assert (await call('172.18.0.6'))['scheme'] == 'ws'
    assert discovery.snapshot()['trusted_addresses'] == []
    assert discovery.snapshot()['status'] == 'error'
    addresses.add('172.18.0.8'); now[0] += 6
    assert (await call('172.18.0.8'))['scheme'] == 'wss'


@pytest.mark.asyncio
async def test_force_refresh_coalescing_staleness_and_no_environment_trust(monkeypatch):
    monkeypatch.setenv('FORWARDED_ALLOW_IPS', '*')
    calls, now = [], [0]
    async def resolver():
        calls.append(1)
        await asyncio.sleep(.01)
        return {'172.18.0.4'}
    discovery = ProxyDiscovery(resolver, lambda: now[0])
    await asyncio.gather(*(discovery.refresh() for _ in range(20)))
    assert len(calls) == 1
    await discovery.refresh(force=True)
    assert len(calls) == 2
    assert discovery.snapshot()['trusted_addresses'] == ['172.18.0.4']
    now[0] = 11
    assert discovery.snapshot()['status'] == 'stale'
    assert discovery.snapshot()['trusted_addresses'] == []


@pytest.mark.asyncio
async def test_background_refresh_does_not_block_startup_and_stops_on_shutdown():
    started, cancelled = asyncio.Event(), asyncio.Event()
    async def resolver():
        started.set()
        try:
            await asyncio.sleep(100)
        finally:
            cancelled.set()
    discovery = ProxyDiscovery(resolver)
    async def app(scope, receive, send):
        await started.wait()
    await DiscoveredProxyHeadersMiddleware(app, discovery)({'type': 'lifespan'}, None, None)
    assert cancelled.is_set()
