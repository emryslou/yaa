import typing

import anyio

from yaa.middlewares.core import Middleware
from yaa.requests import Request
from yaa.responses import Response, StreamingResponse
from yaa.types import ASGI3App, Message, Receive, Scope, Send, T

RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
DispatchFunction = typing.Callable[
    [Request, RequestResponseEndpoint], typing.Awaitable[Response]
]


class BaseHttpMiddleware(Middleware):
    def __init__(
        self,
        app: ASGI3App,
        debug: bool = False,
        dispatch: typing.Optional[DispatchFunction] = None,
    ) -> None:
        super().__init__(app)
        self.debug = debug
        self.dispatch_func = dispatch if dispatch is not None else self.dispatch

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_sent = anyio.Event()

        async def call_next(req: Request) -> Response:
            app_exc: typing.Optional[Exception] = None
            stream_send, stream_receive = anyio.create_memory_object_stream()

            async def receive_or_disconnect() -> Message:
                if response_sent.is_set():
                    return {"type": "http.disconnect"}
                async with anyio.create_task_group() as _tg:

                    async def wrap(func: typing.Callable[[], typing.Awaitable[T]]) -> T:
                        result = await func()
                        _tg.cancel_scope.cancel()
                        return result

                    _tg.start_soon(wrap, response_sent.wait)
                    message = await wrap(req.receive)

                if response_sent.is_set():
                    return {"type": "http.disconnect"}

                return message

            async def close_recv_stream_on_response_sent() -> None:
                await response_sent.wait()
                stream_receive.close()

            async def send_no_error(message: Message) -> None:
                try:
                    await stream_send.send(message)
                except anyio.BrokenResourceError:
                    return

            async def coro() -> None:
                nonlocal app_exc
                async with stream_send:
                    try:
                        await self.app(scope, receive_or_disconnect, send_no_error)
                    except Exception as exc:
                        app_exc = exc

            # end coro
            tg.start_soon(close_recv_stream_on_response_sent)
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
                        body = message.get("body", b"")
                        if body:
                            yield body
                        if not message.get("more_body", False):
                            break
                    # end async for
                # end async with
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
            response_sent.set()
        # end async with

    async def dispatch(
        self, req: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        raise NotImplementedError()
