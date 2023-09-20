from yast.datastructures import URL
from yast.middlewares.core import Middleware
from yast.responses import RedirectResponse, Response
from yast.types import ASGIApp


class HttpsRedirectMiddleware(Middleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    def __call__(self, scope) -> Response:
        if scope["type"] in ("http", "websocket") and scope["scheme"] in ("http", "ws"):
            url = URL(scope=scope)
            redirect_scheme = {"http": "https", "ws": "wss"}[scope["scheme"]]
            netloc = url.hostname if url.port in (80, 443) else url.netloc
            url = url.replace(scheme=redirect_scheme, netloc=netloc)

            return RedirectResponse(url, status_code=301)
        # end if
        return self.app(scope)
