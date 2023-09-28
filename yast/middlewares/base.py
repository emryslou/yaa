import asyncio
import typing

from yast.middlewares.core import Middleware
from yast.requests import Request
from yast.responses import Response, StreamingResponse
from yast.types import ASGIApp, ASGIInstance, Receive, Scope, Send

RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[ASGIInstance]]
DispatchFunction = typing.Callable[
    [Request, RequestResponseEndpoint], typing.Awaitable[ASGIInstance]
]


class BaseHttpMiddleware(Middleware):
    def __init__(
        self, app: ASGIApp, debug: bool = False, dispatch: DispatchFunction = None
    ) -> None:
        super().__init__(app)
        self.debug = debug
        self.dispatch_func = dispatch if dispatch is not None else self.dispatch

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
        else:
            req = Request(scope, receive=receive)
            res = await self.dispatch_func(req, self.call_next)
            await res(scope, receive, send)

    async def call_next(self, req: Request) -> ASGIInstance:
        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()
        scope = req.scope
        receive = req.receive
        send = queue.put

        async def coro() -> None:
            try:
                await self.app(scope, receive, send)
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

    async def dispatch(
        self, req: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        raise NotImplementedError()  # pragma: nocover
