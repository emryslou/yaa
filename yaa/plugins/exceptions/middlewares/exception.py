import asyncio
import typing
import warnings

from yaa.concurrency import run_in_threadpool
from yaa.exceptions import HttpException
from yaa.middlewares.core import Middleware
from yaa.requests import Request
from yaa.responses import PlainTextResponse, Response
from yaa.types import ASGIApp, Message, Receive, Scope, Send


class ExceptionMiddleware(Middleware):
    def __init__(
        self,
        app: ASGIApp,
        debug: bool = False,
        handlers: typing.Optional[
            typing.Dict[typing.Union[int, typing.Type[Exception]], typing.Callable]
        ] = None,
    ) -> None:
        self.app = app
        self.debug = debug
        self._status_handlers: typing.Dict[int, typing.Callable] = {}
        self._exception_handlers = {
            HttpException: self.http_exception,
        }
        for _type, _handler in (handlers or {}).items():
            self.add_exception_handler(_type, _handler)

    def add_exception_handler(
        self,
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
    ) -> None:
        if isinstance(exc_class_or_status_code, (type, Exception)):
            self._exception_handlers[exc_class_or_status_code] = handler  # type: ignore
        elif isinstance(exc_class_or_status_code, int):
            self._status_handlers[exc_class_or_status_code] = handler
        else:
            warnings.warn("unknown type exc_class or status_code")  # pragma: no cover
            print(
                "unknown type exc_class or status_code", type(exc_class_or_status_code)
            )  # pragma: no cover

    def _lookup_exception_handler(
        self, exc: Exception
    ) -> typing.Optional[typing.Callable]:
        for cls in type(exc).__mro__:
            handler = self._exception_handlers.get(cls)  # type: ignore
            if handler:
                return handler
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore
        if scope["type"] != "http":
            await self.app(scope, receive=receive, send=send)  # type: ignore
            return

        responsed_started = False

        async def sender(message: Message) -> None:
            nonlocal responsed_started
            if message["type"] == "http.response.start":
                responsed_started = True
            await send(message)

        try:
            await self.app(scope, receive, sender)  # type: ignore
        except Exception as exc:
            handler = None
            if isinstance(exc, HttpException):
                handler = self._status_handlers.get(exc.status_code)
            if handler is None:
                handler = self._lookup_exception_handler(exc)
            if handler is None:
                raise exc

            if responsed_started:
                raise RuntimeError(
                    "Caught handled exception, but response already started"
                )  # pragma: no cover

            req = Request(scope, receive)
            if asyncio.iscoroutinefunction(handler):
                res = await handler(req, exc)
            else:
                res = await run_in_threadpool(handler, req, exc)

            await res(scope, receive, sender)
        # end except

    def http_exception(self, req: Request, exc: type) -> Response:
        assert isinstance(exc, HttpException)
        if exc.status_code in {204, 304}:
            return Response(status_code=exc.status_code, headers=exc.headers)

        return PlainTextResponse(
            exc.detail, status_code=exc.status_code, headers=exc.headers
        )
