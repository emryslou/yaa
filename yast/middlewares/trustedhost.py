from yast.datastructures import Headers
from yast.responses import Response, PlainTextResponse
from yast.types import ASGIApp, Scope

ENFORCE_DOMAIN_WILDCARD = (
    "Domain wildcard patterns must be like '*.example.com'."
)

class TrustedHostMiddleware(object):
    def __init__(self, app: ASGIApp, allowed_hosts=['*']) -> None:
        for pattern in allowed_hosts:
            assert '*' not in pattern[1:], ENFORCE_DOMAIN_WILDCARD
            if pattern.startswith('*') and pattern != '*':
                assert pattern.startswith('*'), ENFORCE_DOMAIN_WILDCARD
        self.app = app
        self.allowed_hosts = allowed_hosts
        self.allow_any = '*' in self.allowed_hosts
    
    def __call__(self, scope: Scope) -> Response:
        if scope['type'] in ('http', 'websocket') and not self.allow_any:
            headers = Headers(scope=scope)
            host = headers.get('host', '').split(':')[0]
            for pattern in self.allowed_hosts:
                if (
                        host == pattern or 
                        pattern.startswith('*') and 
                        host.endswith(pattern[1:])
                    ):
                    break
            else:
                return PlainTextResponse('Invalid host header', status_code=400)

        return self.app(scope) 
