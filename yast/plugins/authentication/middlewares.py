import typing

from yast.middlewares.core import Middleware
from yast.requests import HttpConnection
from yast.responses import PlainTextResponse, Response
from yast.types import ASGIApp, Receive, Scope, Send

from .base import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    UnauthenticatedUser,
)


class AuthenticationMiddleware(Middleware):
    def __init__(
        self,
        app: ASGIApp,
        backend: AuthenticationBackend,
        on_error: typing.Callable[
            [HttpConnection, AuthenticationError], Response
        ] = None,
    ) -> None:
        super().__init__(app)
        self.backend = backend
        self.on_error = on_error if on_error is not None else self.default_on_error

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            await self.asgi(scope=scope, receive=receive, send=send)
        else:
            await self.app(scope, receive=receive, send=send)

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        conn = HttpConnection(scope=scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except AuthenticationError as exc:
            if scope["type"] == "websocket":
                from yast.websockets import WebSocketClose

                ws_close = WebSocketClose()
                await ws_close(receive, send)
            else:
                res = self.on_error(conn, exc)
                await res(scope, receive, send)

            return
        if auth_result is None:
            auth_result = AuthCredentials(), UnauthenticatedUser()

        scope["auth"], scope["user"] = auth_result

        await self.app(scope, receive, send)

    @staticmethod
    def default_on_error(conn: HttpConnection, exc: Exception) -> Response:
        return PlainTextResponse(str(exc), status_code=400)
