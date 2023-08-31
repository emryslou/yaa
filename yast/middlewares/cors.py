import functools
import typing

from yast.datastructures import Headers, MutableHeaders
from yast.responses import Response, PlainTextResponse
from yast.types import ASGIApp, ASGIInstance, Scope, Receive, Send, Message

ALL_METHODS = (
    'DELETE', 'GET', 'PATCH',
    'OPTIONS', 'POST', 'PUT',
)

class CORSMiddleware(object):
    def __init__(
            self,
            app: ASGIApp,
            allow_origins: typing.Sequence[str] = (),
            allow_methods: typing.Sequence[str] = ('GET'),
            allow_headers: typing.Sequence[str] = (),
            allow_credentials: bool = False,
            expose_headers: typing.Sequence[str] = (),
            max_age: int = 600,
        ) -> None:
        if '*' in allow_methods:
            allow_methods = ALL_METHODS
        
        simple_headers = {}
        if '*' in allow_origins:
            simple_headers['Access-Control-Allow-Origin'] = '*'
        if allow_credentials:
            simple_headers['Access-Control-Allow-Credentials'] = 'true'
        if expose_headers:
            simple_headers['Access-Control-Expose-Headers'] = ','.join(expose_headers)

        preflight_headers = {}
        if '*' in allow_origins:
            preflight_headers['Access-Control-Allow-Origin'] = '*'
        else:
            preflight_headers['Vary'] = 'Origin'
        
        preflight_headers.update({
            'Access-Control-Allow-Methods': ','.join(allow_methods),
            'Access-Control-Max-Age': str(max_age), 
        })

        if allow_headers and '*' not in allow_headers:
            preflight_headers['Access-Control-Allow-Headers'] = ','.join(allow_headers)
        if allow_credentials:
            preflight_headers['Access-Control-Allow-Credentials'] = 'true'
        
        self.app = app
        
        self.allow_origins = allow_origins
        self.allow_methods = allow_methods
        self.allow_headers = allow_headers
        self.allow_all_origins = '*' in allow_origins
        self.allow_all_headers = '*' in allow_headers

        self.simple_headers = simple_headers
        self.preflight_headers = preflight_headers
    
    def __call__(self, scope: Scope) -> Response:
        if scope['type'] == 'http':
            method = scope['method']
            headers = Headers(scope['headers'])
            origin = headers.get('origin')

            if origin is not None:
                if (
                    method == 'OPTIONS' and 
                    'access-control-request-method' in headers
                ):
                    return self.preflight_response(headers)
                else:
                    return functools.partial(
                            self.simple_response,
                            scope=scope,
                            origin=origin
                        )
        return self.app(scope)
    
    def preflight_response(self, request_headers) -> Response:
        req_origin = request_headers['origin']
        req_method = request_headers['access-control-request-method']
        req_headers = request_headers.get('access-control-request-headers')

        headers = dict(self.preflight_headers)
        failures = []
        if not self.allow_all_origins:
            if req_origin in self.allow_origins:
                headers['Access-Control-Allow-Origin'] = req_origin
            else:
                failures.append('origin')
        
        if req_method not in self.allow_methods:
            failures.append('method')
        
        if self.allow_all_headers and request_headers is not None:
            headers['Access-Control-Allow-Headers'] = req_headers
        elif req_headers is not None:
            for header in req_headers.split(','):
                if header.strip() not in self.allow_headers:
                    failures.append('headers')
        
        if failures:
            failure_text = 'Disabllowed CORS ' + ','.join(failures)
            return PlainTextResponse(
                    failure_text, status_code=400, headers=headers
                )
        
        return PlainTextResponse('OK', status_code=200, headers=headers)
    
    async def simple_response(
            self, receive: Receive, send: Send,
            scope = None, origin = None
        ):
        inner = self.app(scope)
        send = functools.partial(self.send, send=send, origin=origin)
        await inner(receive, send)

    async def send(self, message: Message, send: Send, origin=None) -> None:
        if message['type'] != 'http.response.start':
            await send(message)
        message.setdefault('headers', [])
        headers = MutableHeaders(message['headers'])

        if not self.allow_all_origins and origin in self.allow_origins:
            headers['Access-Control-Allow-Origin'] = origin
        headers.update(self.simple_headers)
        await send(message)
