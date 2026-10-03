#!/usr/bin/env python3
"""Serve only the STEP-001 preview and the fourteen approved image files."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=54322)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[5]
    exports = root / 'frontend/static/images/home-scene/v4'
    manifest_path = exports / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    allowed = {'/': evidence / 'preview.html', '/manifest.json': manifest_path}
    for asset in manifest['assets']:
        source = Path(asset['source'])
        allowed['/source/' + source.name] = source
        allowed['/export/' + asset['file']] = exports / asset['file']

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = allowed.get(urlparse(self.path).path)
            if path is None:
                self.send_error(404)
                return
            data = path.read_bytes()
            self.send_response(200)
            mime = {'.html': 'text/html; charset=utf-8', '.json': 'application/json',
                    '.png': 'image/png', '.webp': 'image/webp'}[path.suffix]
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'STEP-001 preview: http://{args.host}:{args.port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
