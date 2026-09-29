"""Portable voice origin policy at the actual WebSocket boundary."""
import pytest
from starlette.websockets import WebSocket

from backend.services.realtime_voice_gateway_service import socket_credentials
from backend.services.realtime_voice_ticket_service import TicketError


def socket(*, origin='https://voice.test', host='voice.test', scheme='wss',
           peer='203.0.113.10', extra=(), query=b''):
    headers = [(b'host', host.encode()),
               (b'sec-websocket-protocol', b'voice.v1, ticket.signed, device.bound')]
    if origin is not None:
        headers.append((b'origin', origin.encode()))
    headers.extend(extra)
    return WebSocket({'type': 'websocket', 'scheme': scheme, 'path': '/api/voice/calls/id/stream',
                      'query_string': query, 'headers': headers, 'client': (peer, 50000),
                      'server': ('backend', 8000)}, receive=None, send=None)


@pytest.mark.parametrize('origin,host', [
    ('https://voice.test', 'voice.test'),
    ('https://new-server.example:9443', 'new-server.example:9443'),
    ('https://VOICE.test:443', 'voice.test'),
    ('https://[::1]:9443', '[::1]:9443'),
])
def test_unconfigured_whitelist_accepts_exact_site(origin, host):
    assert socket_credentials(socket(origin=origin, host=host), set()) == ('signed', 'bound')


@pytest.mark.parametrize('origin', [
    None, 'null', 'https://evil.test', 'http://voice.test', 'https://voice.test:444',
    'https://voice.test/path', 'https://user@voice.test', 'https://voice.test?',
    'https://voice.test#', 'https://voice.test,https://evil.test',
])
def test_unconfigured_whitelist_rejects_cross_origin_or_invalid_origin(origin):
    with pytest.raises(TicketError):
        socket_credentials(socket(origin=origin), set())


def test_explicit_whitelist_remains_exclusive_and_supports_cross_origin():
    with pytest.raises(TicketError):
        socket_credentials(socket(), {'https://other.test'})
    assert socket_credentials(socket(origin='https://other.test'), {'https://other.test'}) == ('signed', 'bound')


@pytest.mark.parametrize('peer', ['127.0.0.1', '::1', '192.168.65.1', '172.22.0.1'])
@pytest.mark.parametrize('host', ['localhost', 'localhost:8000', '127.0.0.1:9080', '[::1]:9080'])
def test_explicit_local_mode_supports_loopback_and_docker_forwarding(peer, host):
    ws = socket(origin='http://' + host, host=host, scheme='ws', peer=peer)
    assert socket_credentials(ws, set(), allow_local_http=True) == ('signed', 'bound')


@pytest.mark.parametrize('origin,host,peer,enabled', [
    ('http://localhost:8000', 'localhost:8000', '192.168.65.1', False),
    ('http://localhost:8000', 'localhost:8000', '8.8.8.8', True),
    ('http://localhost:8000', 'localhost:8000', '0.0.0.0', True),
    ('http://localhost.evil.test', 'localhost.evil.test', '192.168.65.1', True),
    ('http://server.test', 'server.test', '172.22.0.1', True),
    ('http://localhost:8000', 'evil.test:8000', '172.22.0.1', True),
])
def test_local_exception_is_never_a_general_http_bypass(origin, host, peer, enabled):
    with pytest.raises(TicketError):
        socket_credentials(socket(origin=origin, host=host, scheme='ws', peer=peer),
                           {origin}, allow_local_http=enabled)


@pytest.mark.parametrize('headers', [
    [(b'x-forwarded-proto', b'https')],
    [(b'forwarded', b'proto=https;host=voice.test')],
    [(b'x-forwarded-proto', b'https'), (b'x-forwarded-for', b'127.0.0.1')],
])
def test_untrusted_forwarded_headers_cannot_upgrade_plain_ws(headers):
    with pytest.raises(TicketError):
        socket_credentials(socket(scheme='ws', extra=headers), {'https://voice.test'})


@pytest.mark.parametrize('extra,query', [
    ([(b'origin', b'https://evil.test')], b''),
    ([(b'host', b'evil.test')], b''),
    ([], b'ticket=secret'),
])
def test_ambiguous_headers_and_url_credentials_rejected(extra, query):
    with pytest.raises(TicketError):
        socket_credentials(socket(extra=extra, query=query), set())
