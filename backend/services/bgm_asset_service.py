"""Immutable BGM objects in the existing OSS bucket, with anonymous HTTPS verification."""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from backend import config
from backend.services.bgm_media import MediaError


def object_location(track_id, version, kind='audio'):
    # These identifiers are server-generated; refuse unrelated namespaces even
    # if a caller accidentally passes an untrusted value.
    UUID(track_id); UUID(version)
    if kind not in {'audio', 'cover'}:
        raise MediaError('invalid_asset')
    directory, extension = ('tracks', 'm4a') if kind == 'audio' else ('covers', 'webp')
    key = f'bgm/{directory}/{track_id}/{version}.{extension}'
    bucket = config.get_oss_bucket()
    endpoint = config.get_oss_endpoint().strip()
    domain = config.get_oss_cdn_domain().strip()
    if not bucket or not endpoint:
        raise MediaError('storage_unavailable')
    if not domain:
        host = urlsplit(endpoint if '://' in endpoint else 'https://' + endpoint).hostname
        domain = f'{bucket}.{host}' if host else ''
    parsed = urlsplit(domain if '://' in domain else 'https://' + domain)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {'', '/'}):
        raise MediaError('storage_configuration')
    return dict(bucket=bucket, object_key=key, public_url='https://' + parsed.netloc + '/' + key)


def _bucket():
    import oss2
    if not config.get_oss_access_key_id() or not config.get_oss_access_key_secret():
        raise MediaError('storage_unavailable')
    return oss2.Bucket(oss2.Auth(config.get_oss_access_key_id(), config.get_oss_access_key_secret()),
                       config.get_oss_endpoint(), config.get_oss_bucket(), connect_timeout=10)


def media_origins():
    """Explicit deployed H5 origins; never infer them from an admin request."""
    origins = list(dict.fromkeys(value.strip() for value in os.getenv('BGM_MEDIA_ORIGINS', '').split(',')))
    if not origins or len(origins) > 16:
        raise MediaError('storage_configuration')
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            valid = (parsed.hostname and '*' not in parsed.hostname and parsed.port != 0
                     and origin.isascii() and parsed.geturl() == origin
                     and not parsed.username and not parsed.password
                     and not parsed.path and not parsed.query and not parsed.fragment
                     and not any(c.isspace() or ord(c) < 32 for c in origin)
                     and (parsed.scheme == 'https' or
                          (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'})))
        except ValueError:
            valid = False
        if not valid:
            raise MediaError('storage_configuration')
    return origins


def _check_cors(response, origin):
    # Anonymous media accepts "*" or exactly its serialized origin, never a
    # comma-separated list, missing header, or an unrelated allowed origin.
    if response.headers.get('access-control-allow-origin') not in {'*', origin}:
        raise MediaError('remote_cors')


def put_and_verify(path: Path, location, metadata):
    """One immutable key: an uncertain PUT is checked at that same key, never renamed."""
    import httpx
    if location['bucket'] != config.get_oss_bucket():
        raise MediaError('storage_configuration')
    origins = media_origins() if metadata['mime_type'] == 'audio/mp4' else []
    bucket = _bucket()
    key = location['object_key']
    headers = {'Content-Type': metadata['mime_type'], 'Cache-Control': 'public, max-age=2592000, immutable',
               'x-oss-meta-bgm-sha256': metadata['sha256'], 'x-oss-forbid-overwrite': 'true'}
    try:
        bucket.put_object_from_file(key, str(path), headers=headers)
    except Exception:
        # A timeout may follow a successful PUT. HEAD + full public GET below
        # establish the original result; errors retain the pre-registered asset.
        pass
    try:
        head = bucket.head_object(key)
        if (head.content_length != metadata['size_bytes']
                or head.headers.get('x-oss-meta-bgm-sha256') != metadata['sha256']):
            raise MediaError('remote_mismatch')
        digest = hashlib.sha256(); size = 0; prefix = bytearray()
        public_headers = {'Accept-Encoding': 'identity'}
        if origins:
            public_headers['Origin'] = origins[0]
        with httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False) as client:
            with client.stream('GET', location['public_url'], headers=public_headers) as response:
                if response.status_code != 200:
                    raise MediaError('remote_unreadable')
                if response.headers.get('content-type', '').split(';')[0] != metadata['mime_type']:
                    raise MediaError('remote_mime')
                if origins:
                    _check_cors(response, origins[0])
                for chunk in response.iter_bytes(65536):
                    size += len(chunk)
                    if size > metadata['size_bytes']:
                        raise MediaError('remote_mismatch')
                    digest.update(chunk)
                    if len(prefix) < 1024:
                        prefix.extend(chunk[:1024-len(prefix)])
            if size != metadata['size_bytes'] or digest.hexdigest() != metadata['sha256']:
                raise MediaError('remote_mismatch')
            for origin in origins:
                # Bounded actual 206 + exact bytes, not just Accept-Ranges.
                # The enclosing worker's original deadline also bounds all origins.
                end = len(prefix) - 1
                with client.stream('GET', location['public_url'], headers={
                        'Accept-Encoding': 'identity', 'Origin': origin,
                        'Range': f'bytes=0-{end}'}) as response:
                    if (response.status_code != 206 or
                            response.headers.get('content-range') != f'bytes 0-{end}/{size}'):
                        raise MediaError('remote_range')
                    _check_cors(response, origin)
                    if response.headers.get('content-type', '').split(';')[0] != metadata['mime_type']:
                        raise MediaError('remote_mime')
                    received = bytearray()
                    for chunk in response.iter_bytes(1024):
                        received.extend(chunk)
                        if len(received) > len(prefix):
                            raise MediaError('remote_range')
                    if received != prefix:
                        raise MediaError('remote_range')
    except MediaError:
        raise
    except Exception:
        raise MediaError('storage_unknown') from None


def delete_owned_asset(asset):
    """Delete only the exact immutable object registered to this BGM asset.

    Never enumerate a prefix, follow a public URL, or infer ownership from a URL.
    An ambiguous DELETE is reconciled at the same key with an authenticated HEAD.
    """
    try:
        expected = object_location(asset['track_id'], asset['version'], asset['kind'])
    except (ValueError, KeyError, TypeError):
        raise MediaError('asset_ownership') from None
    if asset['object_key'] != expected['object_key'] or asset['bucket'] != expected['bucket']:
        raise MediaError('asset_ownership')
    bucket = _bucket()
    try:
        bucket.delete_object(expected['object_key'])
    except Exception:
        pass
    try:
        if bucket.object_exists(expected['object_key']):
            raise MediaError('cleanup_not_confirmed')
    except MediaError:
        raise
    except Exception:
        raise MediaError('storage_unknown') from None
    return {'deleted': True}
