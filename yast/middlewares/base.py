import asyncio
import functools
import typing

from yast.requests import Request
from yast.responses import StreamingResponse
from yast.types import ASGIApp, ASGIInstance, Receive, Scope, Send

RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[ASGIInstance]]
DispatchFunction = typing.Callable[
    [Request, RequestResponseEndpoint], typing.Awaitable[ASGIInstance]
]


class BaseHttpMiddleware(object):
    def __init__(self, app: ASGIApp, dispatch: DispatchFunction = None) -> None:
        self.app = app
        self.dispatch_func = dispatch if dispatch is not None else self.dispath

    def __call__(self, scope: Scope) -> ASGIInstance:
        if scope["type"] != "http":
            return self.app(scope)

        return functools.partial(self.asgi, scope=scope)

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        req = Request(scope, receive=receive)
        res = await self.dispatch_func(req, self.call_next)
        await res(receive, send)

    async def call_next(self, req: Request) -> ASGIInstance:
        inner = self.app(dict(req))

        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()

        async def coro() -> None:
            try:
                await inner(req._receive, queue.put)
            finally:
                await queue.put(None)

        task = loop.create_task(coro())
        message = await queue.get()
        if message is None:
            task.result()
            raise RuntimeError("No response resulted.")
        assert message["type"] == "http.response.start"

        async def body_stream() -> typing.AsyncGenerator[bytes, None]:
            while True:
                message = await queue.get()
                if message is None:
                    break

                assert message["type"] == "http.response.body"
                yield message["body"]
            task.result()

        res = StreamingResponse(status_code=message["status"], content=body_stream())
        res.raw_headers = message["headers"]
        return res

    async def dispath(
        self, req: Request, call_next: RequestResponseEndpoint
    ) -> ASGIInstance:
        raise NotImplementedError()
