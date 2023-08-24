from .request import Request
from .response import Response
from .types import ASGIInstance, Recevie, Send, Scope
from asyncio.coroutines import iscoroutinefunction

def AsgiApp(func):
    is_coroutine = iscoroutinefunction(func)

    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(recv: Recevie, send: Send) -> None:
            req = Request(scope, recv)
            if is_coroutine:
                res = await func(req)
            else:    
                res = func(req)
            
            await res(recv, send)

        return awaitable

    return app
