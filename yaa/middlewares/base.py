import typing

import anyio

from yaa.middlewares.core import Middleware
from yaa.requests import Request
from yaa.responses import Response, StreamingResponse
from yaa.types import ASGIApp, Receive, Scope, Send

RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
DispatchFunction = typing.Callable[
    [Request, RequestResponseEndpoint], typing.Awaitable[Response]
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
            return

        async def call_next(req: Request):
            app_exc: typing.Optional[Exception] = None
            stream_send, stream_receive = anyio.create_memory_object_stream()

            async def coro() -> None:
                nonlocal app_exc
                async with stream_send:
                    try:
                        await self.app(scope, req.receive, stream_send.send)
                    except Exception as exc:
                        app_exc = exc

            # end coro

            tg.start_soon(coro)
            try:
                message = await stream_receive.receive()
            except anyio.EndOfStream:
                if app_exc is not None:
                    raise app_exc
                raise RuntimeError("No response returned.")

            assert message["type"] == "http.response.start"

            async def body_stream() -> typing.AsyncGenerator[bytes, None]:
                async with stream_receive:
                    async for message in stream_receive:
                        assert message["type"] == "http.response.body"
                        yield message.get("body", b"")
                if app_exc is not None:
                    raise app_exc

            res = StreamingResponse(
                status_code=message["status"], content=body_stream()
            )
            res.raw_headers = message["headers"]
            return res

        # end call_next

        async with anyio.create_task_group() as tg:
            req = Request(scope, receive=receive)
            res = await self.dispatch_func(req, call_next)
            await res(scope, receive, send)
            tg.cancel_scope.cancel()
        # end async with

    async def dispatch(
        self, req: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        raise NotImplementedError()  # pragma: nocover
