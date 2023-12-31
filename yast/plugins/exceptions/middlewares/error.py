import asyncio
import typing

from yast.concurrency import run_in_threadpool
from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import PlainTextResponse, Response
from yast.types import ASGIApp, Receive, Scope, Send


class ExceptionMiddleware(object):
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        self.app = app
        self.debug = debug
        self._status_handlers: typing.Dict[int, typing.Callable] = {}
        self._exception_handlers = {
            HttpException: self.http_exception,
        }

    def add_exception_handler(
        self,
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
    ) -> None:
        if isinstance(exc_class_or_status_code, Exception):
            self._exception_handlers[exc_class_or_status_code] = handler
        elif isinstance(exc_class_or_status_code, int):
            self._status_handlers[exc_class_or_status_code] = handler

    def _lookup_exception_handler(
        self, exc: Exception
    ) -> typing.Optional[typing.Callable]:
        for cls in type(exc).__mro__:
            handler = self._exception_handlers.get(cls)
            if handler:
                return handler
        return None

    def __call__(self, scope: Scope):
        if scope["type"] != "http":
            return self.app(scope)

        async def app(receive: Receive, send: Send):
            responsed_started = False

            async def sender(message):
                nonlocal responsed_started
                if message["type"] == "http.response.start":
                    responsed_started = True
                await send(message)

            try:
                await self.app(scope)(receive, sender)
            except Exception as exc:
                handler = None
                if isinstance(exc, HttpException):
                    handler = self._status_handlers.get(exc.status_code)
                if handler is None:
                    handler = self._lookup_exception_handler(exc)

                if handler is None:
                    raise exc from None

                if responsed_started:
                    raise RuntimeError(
                        "Caught handled exception, but response already started"
                    )

                req = Request(scope, receive)
                if asyncio.iscoroutinefunction(handler):
                    res = await handler(req, exc)
                else:
                    res = await run_in_threadpool(handler, req, exc)

                await res(receive, sender)

        # endapp

        return app

    def http_exception(self, req: Request, exc: type) -> Response:
        assert isinstance(exc, HttpException)
        if exc.status_code in {204, 304}:
            return Response(b"", status_code=exc.status_code)

        return PlainTextResponse(exc.detail, status_code=exc.status_code)
