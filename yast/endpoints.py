import asyncio

from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import Response, PlainTextResponse
from yast.types import Scope, Recevie, Send


class HttpEndPoint(object):
    def __init__(self, scope: Scope):
        self.scope = scope
    
    async def __call__(self, recevie: Recevie, send: Send):
        req = Request(self.scope, recevie) 
        res = await self.dispatch(req, **self.scope.get('kwargs', {}))

        await res(recevie, send)
    
    async def dispatch(self, req: Request, **kwargs) -> Response:
        handler_name = 'get' if req.method == 'HEAD' else req.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        if asyncio.iscoroutinefunction(handler):
            res = await handler(req, **kwargs)
        else:
            res = handler(req, **kwargs)
        return res
    
    async def method_not_allowed(self, req: Request, **kwargs):
        if 'app' in self.scope:
            raise HttpException(status_code=405)
        return PlainTextResponse('Method Not Allowed', 405)