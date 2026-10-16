"""Trust only the current Docker DNS addresses of our nginx service.

Uvicorn's own proxy processing MUST be disabled (Dockerfile). No request header
or environment-supplied IP can enlarge this trust boundary.
"""
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import ipaddress
import logging
import socket
import time
from uuid import uuid4

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


async def resolve_nginx():
    rows = await asyncio.get_running_loop().getaddrinfo(
        'nginx', 80, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    return {str(ipaddress.ip_address(row[4][0])) for row in rows}


class ProxyDiscovery:
    refresh_seconds = 5
    timeout_seconds = 1

    def __init__(self, resolver=resolve_nginx, clock=time.monotonic):
        self.resolver, self.clock = resolver, clock
        self.addresses = frozenset()
        self.last_attempt = None
        self.checked_at = None
        self.changed_at = None
        self.error = None
        self.generation = 0
        self.instance = uuid4().hex[:12]
        self.lock = asyncio.Lock()

    async def refresh(self, *, force=False, peer=None):
        # Unknown peers get an early retry, bounded to once/second per process.
        interval = 1 if force or (peer is not None and peer not in self.addresses) else self.refresh_seconds
        observed_attempt = self.last_attempt
        async with self.lock:
            if self.last_attempt != observed_attempt or (not force and self.last_attempt is not None and self.clock() - self.last_attempt < interval):
                return self.snapshot()
            try:
                found = await asyncio.wait_for(self.resolver(), self.timeout_seconds)
                addresses = frozenset(str(ipaddress.ip_address(ip)) for ip in found)
                if not addresses:
                    raise ValueError('empty_dns_answer')
                error = None
            except Exception:
                # Never retain stale trust or fall back to '*' after DNS failure.
                addresses, error = frozenset(), 'proxy_dns_unavailable'
            self.last_attempt, self.checked_at = self.clock(), utc_now()
            if addresses != self.addresses or error != self.error:
                self.generation += 1
                self.changed_at = self.checked_at
                logger.info('proxy.discovery state=%s generation=%s address_count=%s',
                            error or 'ready', self.generation, len(addresses))
            self.addresses, self.error = addresses, error
            return self.snapshot()

    def snapshot(self):
        age = None if self.last_attempt is None else max(0, self.clock() - self.last_attempt)
        stale = age is None or age > self.refresh_seconds * 2
        return dict(mode='docker_dns', service='nginx', instance=self.instance,
                    generation=self.generation, status='unknown' if age is None else
                    'stale' if stale else 'error' if self.error else 'ready',
                    discovered_addresses=sorted(self.addresses),
                    trusted_addresses=[] if stale else sorted(self.addresses),
                    checked_at=self.checked_at, changed_at=self.changed_at,
                    error=self.error, refresh_seconds=self.refresh_seconds)

    async def run(self):
        while True:
            await self.refresh()
            await asyncio.sleep(self.refresh_seconds)


class DiscoveredProxyHeadersMiddleware:
    def __init__(self, app, discovery):
        self.app, self.discovery = app, discovery

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            task = asyncio.create_task(self.discovery.run())
            try:
                await self.app(scope, receive, send)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            return
        if scope['type'] not in ('http', 'websocket'):
            return await self.app(scope, receive, send)
        peer = (scope.get('client') or ('', 0))[0]
        snapshot = await self.discovery.refresh(peer=peer)
        scope = dict(scope)
        scope['voice_proxy'] = dict(instance=snapshot['instance'], generation=snapshot['generation'],
                                    peer=peer, trusted=peer in snapshot['trusted_addresses'])
        # Construct from a snapshot; never mutate Uvicorn internals while a
        # previously accepted websocket is still running.
        handler = ProxyHeadersMiddleware(self.app, trusted_hosts=snapshot['trusted_addresses'])
        await handler(scope, receive, send)
