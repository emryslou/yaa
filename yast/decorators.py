from .request import Request
from .response import Response
from .types import ASGIInstance, Recevie, Send, Scope
from asyncio.coroutines import iscoroutine

def AsgiApp(func):
    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(recv: Recevie, send: Send) -> None:
            req = Request(scope, recv)
            res = func(req)
            
            await res(recv, send)

        return awaitable

    return app
