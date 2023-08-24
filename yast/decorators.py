from .request import Request
from .response import Response
from asyncio.coroutines import iscoroutine

def AsgiApp(func):
    def app(scope):
        async def awaitable(recv, send):
            req = Request(scope, recv)
            
            res = func(req)    

            assert isinstance(res, Response)

            await res(recv, send)

        return awaitable

    return app
