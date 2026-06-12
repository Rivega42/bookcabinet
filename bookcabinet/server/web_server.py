"""
aiohttp Web Server.

Статика: предпочитается свежий vite-билд dist/public (npm run build);
если его нет — фоллбек на закоммиченный bookcabinet/server/static.
"""
import os
from aiohttp import web

from ..config import HOST, PORT
from .api_routes import setup_routes

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _static_dir() -> str:
    dist = os.path.join(_REPO_ROOT, 'dist', 'public')
    if os.path.exists(os.path.join(dist, 'index.html')):
        return dist
    return os.path.join(os.path.dirname(__file__), 'static')


async def index_handler(request):
    return web.FileResponse(os.path.join(_static_dir(), 'index.html'))


def create_app() -> web.Application:
    app = web.Application()

    setup_routes(app)

    static_path = _static_dir()
    if os.path.exists(static_path):
        app.router.add_static('/static', static_path)
        assets = os.path.join(static_path, 'assets')
        if os.path.exists(assets):
            app.router.add_static('/assets', assets)

    # SPA-маршруты (wouter на клиенте)
    app.router.add_get('/', index_handler)
    app.router.add_get('/admin', index_handler)
    app.router.add_get('/kiosk', index_handler)
    app.router.add_get('/rfid', index_handler)

    return app


def run_server():
    app = create_app()
    web.run_app(app, host=HOST, port=PORT)
