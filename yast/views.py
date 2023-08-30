from yast.request import Request
from yast.response import Response, PlainTextResponse
from yast.types import Scope, Recevie, Send


class View(object):
    def __init__(self, scope: Scope):
        self.scope = scope
    
    async def __call__(self, recevie: Recevie, send: Send):
        req = Request(self.scope, recevie) 
        res = await self.dispatch(req, **self.scope.get('kwargs', {}))

        await res(recevie, send)
    
    async def dispatch(self, req: Request, **kwargs) -> Response:
        handler_name = 'get' if req.method == 'HEAD' else req.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        return await handler(req, **kwargs)
    
    async def method_not_allowed(self, req: Request, **kwargs):
        return PlainTextResponse('Method not allowed', 405)