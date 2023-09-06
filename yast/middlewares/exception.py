import asyncio
import typing

from yast.debug import get_debug_response
from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import Response, PlainTextResponse
from yast.types import ASGIApp, Scope, Receive, Send


class ExceptionMiddleware(object):
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        self.app = app
        self.debug = debug
        self._exception_handlers = {
            Exception: self.server_error,
            HttpException: self.http_exception,
        }

    def add_exception_handler(self, exc_class: type, handler: typing.Callable) -> None:
        assert issubclass(exc_class, Exception)
        self._exception_handlers[exc_class] = handler

    def _lookup_exception_handler(
        self, exc: type
    ) -> typing.Tuple[typing.Callable, Exception]:
        for cls in type(exc).__mro__:
            handler = self._exception_handlers.get(cls)
            if handler:
                return handler, cls

    def __call__(self, scope: Scope):
        if scope["type"] != "http":
            self.app(scope)

        async def app(receive: Receive, send: Send):
            responsed_started = False

            async def sender(message):
                nonlocal responsed_started
                if message["type"] == "http.response.start":
                    responsed_started = True
                await send(message)

            try:
                try:
                    await self.app(scope)(receive, sender)
                except BaseException as exc:
                    handler, cls = self._lookup_exception_handler(exc)
                    if cls is Exception:
                        raise exc from None
                    if responsed_started:
                        raise RuntimeError(
                            "Caught handled exception, but response already started"
                        )

                    req = Request(scope, receive)
                    if asyncio.iscoroutinefunction(handler):
                        res = await handler(req, exc)
                    else:
                        res = handler(req, exc)

                    await res(receive, sender)

            except Exception as exc:
                if self.debug:
                    handler = get_debug_response
                else:
                    handler = self._exception_handlers[Exception]
                req = Request(scope, receive)
                if asyncio.iscoroutinefunction(handler):
                    res = await handler(req, exc)
                else:
                    res = handler(req, exc)

                if not responsed_started:
                    await res(receive, send)

                raise

        return app

    def http_exception(self, req: Request, exc: type) -> Response:
        assert isinstance(exc, HttpException)
        if exc.status_code in {204, 304}:
            return Response(b"", status_code=exc.status_code)

        return PlainTextResponse(exc.detail, status_code=exc.status_code)

    def server_error(self, req: Request, exc: type) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500)
