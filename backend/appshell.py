"""H5 entry selection only; API routing and application lifespan are unchanged.

The deployment tool atomically installs a complete, verified app-entry.html.
No entry means the existing independent HTML pages remain active.
"""
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

H5_PAGES = frozenset(('index', 'chat', 'feed', 'diary', 'memory', 'relationship', 'settings', 'login'))


class H5StaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.startswith('app-builds/') and response.status_code in (200, 304):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


def h5_response(page_name=None, *, frontend=Path('frontend')):
    entry = frontend / 'app-entry.html'
    try:
        # Read once before returning: FileResponse would reopen a mutable entry after
        # headers/stat, racing an atomic activation or removal for legacy rollback.
        html = entry.read_text(encoding='utf-8')
    except FileNotFoundError:
        html = None
    if html is not None:
        if page_name not in H5_PAGES:
            # / and unknown /pages/*.html intentionally start at Login on FastAPI.
            html = html.replace('<head>', '<head><meta name="lxm-initial-page" content="login">', 1)
        return HTMLResponse(html, headers={'Cache-Control': 'no-cache'})
    page = frontend / 'pages' / ((page_name if page_name in H5_PAGES else 'login') + '.html')
    return FileResponse(page, headers={'Cache-Control': 'no-cache'})
