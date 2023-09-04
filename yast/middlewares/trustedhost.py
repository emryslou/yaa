from yast.datastructures import Headers
from yast.responses import Response, PlainTextResponse
from yast.types import ASGIApp, Scope

class TrustedHostMiddleware(object):
    def __init__(self, app: ASGIApp, allowed_hosts=['*']) -> None:
        self.app = app
        self.allowed_hosts = allowed_hosts
        self.allow_any = '*' in self.allowed_hosts
    
    def __call__(self, scope: Scope) -> Response:
        if scope['type'] in ('http', 'websocket') and not self.allow_any:
            headers = Headers(scope=scope)
            host = headers.get('host')
            if host not in self.allowed_hosts:
                return PlainTextResponse('Invalid host header', status_code=400)

        return self.app(scope) 
