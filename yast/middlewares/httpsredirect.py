from yast.datastructures import URL
from yast.responses import Response, RedirectResponse
from yast.types import ASGIApp, Scope

class HttpsRedirectMiddleware(object):
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
    
    def __call__(self, scope) -> Response:
        if (
                scope['type'] in ('http', 'websocket') and 
                scope['scheme'] in ('http', 'ws')
            ):
            redirect_scheme = {'http': 'https', 'ws': 'wss'}[scope['scheme']]
            url = URL(scope=scope)
            url = url.replace(scheme=redirect_scheme, netloc=url.hostname)

            return RedirectResponse(url, status_code=301)
        return self.app(scope)
    
