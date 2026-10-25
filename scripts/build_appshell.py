#!/usr/bin/env python3
"""Build a content-addressed H5 resource closure. Never activate or prune a build."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tempfile

SCHEMA = 1
TEXT = {'.js', '.css', '.html', '.json', '.svg'}
MIMES = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html',
         '.json': 'application/json', '.svg': 'image/svg+xml'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def references(key: str, text: str, known: set[str]) -> list[str]:
    """Validate literal dependency edges; the full static inventory also includes lazy assets."""
    refs = set(re.findall(r'''["'`](/static/[^"'`\s<>]+)["'`]''', text))
    if key.endswith('.js'):
        refs.update(re.findall(r'''(?:\b(?:import|export)\s+[^;\n]*?\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)["']([^"']+)["']''', text))
        refs.update(re.findall(r'''new\s+URL\(\s*["']([^"']+)["']\s*,\s*import\.meta\.url''', text))
    if key.endswith(('.css', '.html')):
        refs.update(re.findall(r'''url\(\s*["']?([^\s"')]+)''', text))
        refs.update(re.findall(r'''(?:src|href)=["']([^"']+)["']''', text))
        refs.update(re.findall(r'''@import\s+["']([^"']+)["']''', text))
    dependencies = set()
    for ref in refs:
        if ref.startswith('/static/app-builds/'):
            continue  # runtime descriptor validation, not an unversioned source dependency
        if ref.startswith(('https:', 'http:', 'data:', '#', '/api/', '/pages/')):
            continue
        if '${' in ref or ref.endswith('/'):
            # Dynamic asset directories are copied in full, never fetched from a newer build.
            prefix = ref.removeprefix('/static/').split('${')[0]
            if ref.startswith('/static/') and not any(p.startswith(prefix) for p in known):
                raise ValueError(f'{key}: missing dynamic directory {ref}')
            continue
        target = ref.split('?', 1)[0].split('#', 1)[0]
        if target.startswith('/static/'):
            target = target[len('/static/'):]
        elif target.startswith('/'):
            continue  # a business route, not a static dependency
        else:
            target = posixpath.normpath(posixpath.join(posixpath.dirname(key), target))
        if target not in known:
            raise ValueError(f'{key}: missing static dependency {ref} -> {target}')
        dependencies.add(target)
    return sorted(dependencies)


def build(source: Path, output: Path) -> dict:
    files = {}
    for directory, prefix in [(source / 'static', ''), (source / 'templates', 'templates/')]:
        if not directory.exists():
            continue
        for parent, dirs, names in os.walk(directory):
            dirs[:] = sorted(d for d in dirs if d != 'app-builds' and not d.startswith('.'))
            for name in sorted(names):
                p = Path(parent) / name
                if name.startswith('.'):
                    continue
                if p.is_symlink():
                    raise ValueError(f'symlink not allowed in build: {p}')
                files[prefix + p.relative_to(directory).as_posix()] = p.read_bytes()
    shell = (source / 'app.html').read_bytes()
    required = ['js/app/entry.js', 'js/app/resources.js', 'js/app/bootstrap.js',
                'js/voice-microphone-worklet.js', 'js/voice-audio-transport.js']
    for key in required:
        if key not in files:
            raise ValueError(f'missing required resource: {key}')
    # Builder changes are versioned as well, so transformation changes cannot mutate an old URL.
    fingerprint = json.dumps({k: digest(v) for k, v in sorted(files.items())}, sort_keys=True).encode()
    build_id = 'aps1-' + digest(fingerprint + shell + Path(__file__).read_bytes())[:24]
    base = f'/static/app-builds/{build_id}/'
    resources, transformed = {}, {}
    for key, data in sorted(files.items()):
        deps = []
        if PurePosixPath(key).suffix in TEXT:
            text = data.decode('utf-8')
            deps = references(key, text, set(files))
            # Preserve existing signed API/media URLs; only version our own static assets.
            data = re.sub(r'/static/(?!app-builds/)', base, text).encode('utf-8')
        transformed[key] = data
        resources[key] = dict(url=base + key, sha256=digest(data), bytes=len(data),
                              mime=MIMES.get(PurePosixPath(key).suffix,
                                             mimetypes.guess_type(key)[0] or 'application/octet-stream'),
                              dependencies=deps)
    manifest = dict(schema=SCHEMA, buildId=build_id, baseURL=base, resources=resources)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    config = dict(schema=SCHEMA, buildId=build_id, baseURL=base, manifestURL=base + 'manifest.json',
                  manifestSHA256=digest(manifest_bytes))
    sri = 'sha256-' + base64.b64encode(bytes.fromhex(resources['js/app/entry.js']['sha256'])).decode()
    page = shell.decode().replace('__APP_CONFIG__', json.dumps(config).replace('<', '\\u003c'))
    page = page.replace('__APP_ENTRY__', resources['js/app/entry.js']['url']).replace('__APP_ENTRY_SRI__', sri)
    transformed.update({'manifest.json': manifest_bytes, 'app.html': page.encode()})
    descriptor = {**config, 'shellSHA256': digest(transformed['app.html']), 'resourceCount': len(resources)}
    transformed['build.json'] = (json.dumps(descriptor, indent=2) + '\n').encode()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / build_id
    if destination.exists():
        actual = {p.relative_to(destination).as_posix(): p.read_bytes()
                  for p in destination.rglob('*') if p.is_file()}
        if actual != transformed:
            raise ValueError(f'immutable build already exists with different content: {build_id}')
        return descriptor
    staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=output))
    try:
        for key, data in transformed.items():
            p = staging / key; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return descriptor


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path('frontend'))
    parser.add_argument('--output-dir', type=Path, default=Path('frontend/static/app-builds'))
    args = parser.parse_args()
    print(json.dumps(build(args.source_root, args.output_dir), ensure_ascii=False, indent=2))
