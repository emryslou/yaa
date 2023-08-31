import asyncio
import http

from yast.debug import get_debug_response
from yast.requests import Request
from yast.responses import Response, PlainTextResponse

class HttpException(Exception):
    def __init__(self, status_code: int, detail: str = None):
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase
        
        self.status_code = status_code
        self.detail = detail

class ExceptionMiddleware(object):
    def __init__(self, app, debug=False):
        self.app = app
        self.debug = debug
        self._exception_handlers = {
            Exception: self.server_error,
            HttpException: self.http_exception
        }
    
    def add_exception_handler(self, exc_class, handler):
        assert issubclass(exc_class, Exception)
        self._exception_handlers[exc_class] = handler
    
    def _lookup_exception_handler(self, exc):
        for cls in type(exc).__mro__:
            handler = self._exception_handlers.get(cls)
            if handler:
                return handler, cls
    
    def __call__(self, scope):
        if scope['type'] != 'http':
            self.app(scope)
        
        async def app(recevie, send):
            responsed_started = False

            async def sender(message):
                nonlocal responsed_started
                if message['type'] == 'http.response.start':
                    responsed_started = True
                await send(message)
            
            try:
                try:
                    await self.app(scope)(recevie, sender)
                except BaseException as exc:
                    handler, cls = self._lookup_exception_handler(exc)
                    if cls is Exception:
                        raise exc from None
                    if responsed_started:
                        raise RuntimeError('Caught handled exception, but response already started')
                    
                    req = Request(scope, recevie)
                    if asyncio.iscoroutinefunction(handler):
                        res = await handler(req, exc)
                    else:
                        res = handler(req, exc)
                    
                    await res(recevie, sender)
                    
            except Exception as exc:
                if self.debug:
                    handler = get_debug_response
                else:
                    handler = self._exception_handlers[Exception]
                req = Request(scope, recevie)
                if asyncio.iscoroutinefunction(handler):
                    res = await handler(req, exc)
                else:
                    res = handler(req, exc)
                
                if not responsed_started:
                    await res(recevie, send)
                
                raise
        
        return app

    def http_exception(self, req: Request, exc: type) -> Response:
        assert isinstance(exc, HttpException)
        if exc.status_code in {204, 304}:
            return Response(b'', status_code=exc.status_code)
        
        return PlainTextResponse(exc.detail, status_code=exc.status_code)
    
    def server_error(self, req: Request, exc: type) -> Response:
        return PlainTextResponse('Internal Server Error', status_code=500)