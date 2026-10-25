#!/usr/bin/env python3
"""Validate and atomically select a preloaded AppShell build. Never prunes resources.

The frontend root must be the directory shared by both prepared service entries.
This changes entry bytes only; it does not upgrade/restart services or publish assets.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'not a regular file: {path}')
    return path.read_bytes()


def validate(root, build_id):
    if not re.fullmatch(r'aps1-[0-9a-f]{24}', build_id):
        raise ValueError('invalid build id')
    directory = root / 'static' / 'app-builds' / build_id
    if directory.resolve() != directory.absolute():
        raise ValueError('symlink in build path')
    descriptor = json.loads(read_regular(directory / 'build.json'))
    manifest_bytes = read_regular(directory / 'manifest.json')
    manifest = json.loads(manifest_bytes)
    page = read_regular(directory / 'app.html')
    base = f'/static/app-builds/{build_id}/'
    config = dict(schema=1, buildId=build_id, baseURL=base,
                  manifestURL=base + 'manifest.json', manifestSHA256=sha(manifest_bytes))
    if any(descriptor.get(k) != v for k, v in config.items()):
        raise ValueError('descriptor identity or manifest digest mismatch')
    if descriptor.get('shellSHA256') != sha(page):
        raise ValueError('shell digest mismatch')
    if any(manifest.get(k) != config[k] for k in ('schema', 'buildId', 'baseURL')):
        raise ValueError('manifest identity mismatch')
    resources = manifest.get('resources', {})
    if not resources or descriptor.get('resourceCount') != len(resources):
        raise ValueError('resource count mismatch')
    for key, item in resources.items():
        parts = PurePosixPath(key).parts
        if not parts or key != '/'.join(parts) or any(p in ('..', '.') for p in parts) or key.startswith('/'):
            raise ValueError(f'unsafe resource path: {key}')
        path = directory / key
        if path.resolve() != path.absolute():
            raise ValueError(f'symlink in resource path: {key}')
        data = read_regular(path)
        if item.get('url') != base + key or item.get('bytes') != len(data) or item.get('sha256') != sha(data):
            raise ValueError(f'resource identity/digest mismatch: {key}')
        if not item.get('mime') or any(dep not in resources for dep in item.get('dependencies', [])):
            raise ValueError(f'incomplete resource metadata: {key}')
    html = page.decode('utf-8')
    embedded = re.findall(r'<script type="application/json" id="app-build">(.*?)</script>', html, re.S)
    if len(embedded) != 1 or json.loads(embedded[0]) != config:
        raise ValueError('shell config mismatch')
    entry = resources['js/app/entry.js']
    sri = 'sha256-' + base64.b64encode(bytes.fromhex(entry['sha256'])).decode()
    if f'src="{entry["url"]}" integrity="{sri}"' not in html:
        raise ValueError('shell entry/SRI mismatch')
    for required in ('js/voice-microphone-worklet.js', 'js/voice-audio-transport.js'):
        if required not in resources:
            raise ValueError(f'missing required resource: {required}')
    return descriptor, page


def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.entry-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def release(root, action, build_id=None, expected=None):
    root = root.resolve(strict=True)
    entry = root / 'app-entry.html'
    descriptor, page = validate(root, build_id) if build_id else (None, None)
    if action == 'inspect':
        return dict(candidate=descriptor, current=sha(read_regular(entry)) if entry.exists() else 'absent')
    if action == 'activate' and page is None:
        raise ValueError('activate requires --build-id')
    if not expected or (expected != 'absent' and not re.fullmatch(r'[0-9a-f]{64}', expected)):
        raise ValueError('mutation requires --expected-entry-sha256 (digest or absent)')
    # Cooperating release invocations serialize and compare the reviewed entry.
    with (root / '.appshell-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = read_regular(entry) if entry.exists() or entry.is_symlink() else None
        current = sha(previous) if previous is not None else 'absent'
        if current != expected:
            raise ValueError(f'entry changed: expected {expected}, found {current}')
        backup = None
        if previous is not None:
            backup_dir = root / '.appshell-entries'
            backup_dir.mkdir(exist_ok=True)
            if backup_dir.is_symlink():
                raise ValueError('symlink backup directory')
            backup = backup_dir / (current + '.html')
            if backup.exists():
                if read_regular(backup) != previous:
                    raise ValueError('backup digest mismatch')
            else:
                atomic_write(backup, previous)
        if action == 'activate':
            atomic_write(entry, page)
        elif action == 'deactivate':
            if previous is not None:
                entry.unlink()
        else:
            raise ValueError('unknown action')
    return dict(action=action, previous=current, current=sha(page) if action == 'activate' else 'absent',
                buildId=descriptor['buildId'] if descriptor else None,
                backup=str(backup) if backup else None, resourcesRetained=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'activate', 'deactivate'])
    parser.add_argument('--frontend-root', required=True, type=Path)
    parser.add_argument('--build-id')
    parser.add_argument('--expected-entry-sha256')
    args = parser.parse_args()
    try:
        print(json.dumps(release(args.frontend_root, args.action, args.build_id, args.expected_entry_sha256), indent=2))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f'AppShell release rejected: {error}\n')
