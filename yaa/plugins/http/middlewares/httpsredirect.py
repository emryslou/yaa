from yaa.datastructures import URL
from yaa.middlewares.core import Middleware
from yaa.responses import RedirectResponse
from yaa.types import ASGIApp, Receive, Scope, Send


class HttpsRedirectMiddleware(Middleware):
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        super().__init__(app)
        self.debug = debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and scope["scheme"] in ("http", "ws"):
            url = URL(scope=scope)
            redirect_scheme = {"http": "https", "ws": "wss"}[scope["scheme"]]
            netloc = url.hostname if url.port in (80, 443) else url.netloc
            url = url.replace(scheme=redirect_scheme, netloc=netloc)

            await RedirectResponse(url, status_code=308)(scope, receive, send)
        else:
            await self.app(scope, receive, send)
