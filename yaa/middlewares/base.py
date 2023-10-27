import logging
import sys
import typing
from contextlib import contextmanager

import anyio
from anyio.abc import ObjectReceiveStream, ObjectSendStream

from yaa._utils import get_logger, collapse_excgroups
from yaa.background import BackgroundTask
from yaa.middlewares.core import Middleware
from yaa.requests import ClientDisconnect, Request
from yaa.responses import Response, StreamingResponse
from yaa.types import ASGI3App, ContentStream, Message, Receive, Scope, Send, T


RequestResponseEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
DispatchFunction = typing.Callable[
    [Request, RequestResponseEndpoint], typing.Awaitable[Response]
]
logger = get_logger(__name__)


class _CachedRequest(Request):
    def __init__(self, scope: Scope, receive: Receive) -> None:
        super().__init__(scope, receive)
        self._wrapped_rcv_disconnected = False
        self._wrapped_rcv_consumed = False
        self._wrapped_rcv_stream = self.stream()

    async def wrapped_receive(self) -> Message:
        logger.debug("wrapped_receive calling")
        if self._wrapped_rcv_disconnected:
            return {"type": "http.disconnect"}

        if self._wrapped_rcv_consumed:
            if self._is_disconnected:
                self._wrapped_rcv_disconnected = True
                return {"type": "http.disconnect"}

            msg = await self.receive()
            if msg["type"] != "http.disconnect":
                raise RuntimeError(
                    f'Unexpected message receive {msg["type"]}'
                )  # pragma: no cover
            logger.debug(
                f"{__name__}::{self.__class__.__name__}::wrapped_receive::{self.receive}"
            )
            return msg

        if getattr(self, "_body", None) is not None:
            self._wrapped_rcv_consumed = True
            return {
                "type": "http.request",
                "body": self._body,
                "more_body": False,
            }
        elif self._stream_consumed:
            self._wrapped_rcv_consumed = True
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }
        else:
            try:
                stream = self.stream()
                chunk = await stream.__anext__()
                self._wrapped_rcv_consumed = self._stream_consumed
                logger.debug("stream chunk")
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": not self._stream_consumed,
                }
            except ClientDisconnect:
                self._wrapped_rcv_disconnected = True
                return {"type": "http.disconnect"}


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

        request = _CachedRequest(scope, receive=receive)
        wrapped_receive = request.wrapped_receive
        response_sent = anyio.Event()

        async def call_next(req: Request) -> Response:
            app_exc: typing.Optional[Exception] = None
            stream_send: ObjectSendStream[typing.MutableMapping[str, typing.Any]]
            stream_receive: ObjectReceiveStream[typing.MutableMapping[str, typing.Any]]
            stream_send, stream_receive = anyio.create_memory_object_stream[
                typing.MutableMapping[str, typing.Any]
            ]()

            async def receive_or_disconnect() -> Message:
                if response_sent.is_set():
                    return {"type": "http.disconnect"}
                async with anyio.create_task_group() as _tg:

                    async def wrap(func: typing.Callable[[], typing.Awaitable[T]]) -> T:
                        result = await func()
                        _tg.cancel_scope.cancel()
                        return result

                    _tg.start_soon(wrap, response_sent.wait)
                    message = await wrap(wrapped_receive)

                if response_sent.is_set():
                    return {"type": "http.disconnect"}

                return message

            async def close_recv_stream_on_response_sent() -> None:
                await response_sent.wait()
                stream_receive.close()

            async def send_no_error(message: Message) -> None:
                try:
                    await stream_send.send(message)  # type: ignore[arg-type]
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
                info = message.get("info", None)
                if message["type"] == "http.response.debug" and info is not None:
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

            res = _StreamingResponse(
                status_code=message["status"], content=body_stream(), info=info
            )
            res.raw_headers = message["headers"]
            return res

        # end call_next
        with collapse_excgroups():
            async with anyio.create_task_group() as tg:
                res = await self.dispatch_func(request, call_next)
                await res(scope, wrapped_receive, send)
                response_sent.set()
        # end async with

    async def dispatch(
        self, req: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        raise NotImplementedError()


class _StreamingResponse(StreamingResponse):
    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
        info: typing.Optional[typing.Mapping[str, typing.Any]] = None,
    ) -> None:
        self._info = info
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,  # type: ignore[arg-type]
            media_type=media_type,
            background=background,
        )

    async def response(self, send: Send, scope: Scope) -> None:
        await super().response(send, scope)
        if self._info:
            await send({"type": "http.response.debug", "info": self._info})
